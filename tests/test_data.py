"""Reading and checking data, quality control, growth tables and calibration."""

import io
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from weanage import config
from weanage.calibrate import CalibrationPoint, calibrate_growth_table
from weanage.growth import position_to_age
from weanage.ingest import canonical_column, ingest_file, ingest_records
from weanage.qc import passes_qc, qc_flags
from weanage.schema import GrowthTable, IsotopeSample, LinearGrowthOverride, QCThresholds

BASE = dict(specimen_id="T", site="S", species="Cattle", tooth="M2", d15N=7.0)


def test_sample_tidying():
    s = IsotopeSample(**BASE, position_mm=1, pct_C=42.0, pct_N=15.0, notes="  ")
    assert s.species == "cattle" and s.notes is None
    assert s.cn_ratio == pytest.approx(42 / 15 * 14.007 / 12.011, abs=1e-3)
    with pytest.raises(ValidationError):
        IsotopeSample(**BASE, position_mm=-1)


def test_cervix_positions_converted_once():
    s = IsotopeSample(**BASE, position_mm=10, position_reference="Cervix", crown_height_mm=45)
    assert (s.position_mm, s.position_measured_mm, s.position_reference) == (35, 10, "apex")
    assert IsotopeSample(**s.model_dump()).position_mm == 35  # sending it back must not convert again
    with pytest.raises(ValidationError):
        IsotopeSample(**BASE, position_mm=10, position_reference="cervix")


@pytest.mark.parametrize("header,expected", [
    ("δ15N (‰)", "d15N"), ("d15N_AIR", "d15N"), ("C:N", "cn_ratio"), ("%C", "pct_C"), ("Specimen ID", "specimen_id"),
    ("Position (mm)", "position_mm"), ("Animal", "individual_id"), ("Increment width (mm)", "increment_width_mm"),
    ("Published weaning age (months)", "published_weaning_age_months"), ("mystery", None),
])
def test_column_names(header, expected):
    assert canonical_column(header) == expected


def test_csv_with_errors_and_unknown_columns():
    report = ingest_file(b"Specimen ID,Site,Taxon,Tooth,Position (mm),d15N,C:N,extra\n"
                        b"A1,S,cattle,M2,0.5,8.1,3.2,x\nA1,S,cattle,M2,1.5,oops,3.2,x\n")
    assert len(report["samples"]) == 1
    assert any(i["row"] == 2 and i["field"] == "d15N" for i in report["issues"])
    assert any("kept for grouping in Compare: extra" in i["message"] for i in report["issues"])
    assert report["samples"][0].labels == {"extra": "x"}
    assert "Missing required column" in ingest_file(b"specimen_id,site\nA,B\n")["issues"][0]["message"]


def test_excel_upload():
    buf = io.BytesIO()
    pd.DataFrame({"Specimen ID": ["A"] * 3, "Site": "S", "Species": "cattle", "Tooth": "M2",
                  "Position (mm)": [0.5, 1.5, 2.5], "δ15N (‰)": [8.0, 7.5, 7.0]}).to_excel(buf, index=False)
    assert len(ingest_file(buf.getvalue(), "data.xlsx")["samples"]) == 3


def test_dataset_checks():
    rows = [dict(BASE, specimen_id="A", species="sheep", position_mm=i) for i in range(3)]
    rows += [dict(BASE, specimen_id="x", individual_id="X", position_mm=i) for i in range(6)]
    rows += [dict(BASE, specimen_id="y", individual_id="X", species="pig", tooth="M1", position_mm=i) for i in range(6)]
    messages = " ".join(i["message"] for i in ingest_records(rows)["issues"])
    assert "only 3 samples" in messages and "No growth table" in messages and "different species" in messages


def test_bundled_example_is_valid():
    report = ingest_file(Path(__file__).parent / "data" / "synthetic_example.csv")
    assert not [i for i in report["issues"] if i["severity"] == "error"] and len(report["specimens"]) >= 10


def test_quality_control():
    base = dict(BASE, position_mm=0)
    assert passes_qc(qc_flags(IsotopeSample(**base, cn_ratio=3.2, pct_C=40, pct_N=14), QCThresholds()))
    assert not passes_qc(qc_flags(IsotopeSample(**base, cn_ratio=4.0), QCThresholds()))
    assert qc_flags(IsotopeSample(**base), QCThresholds()) == ["qc_not_assessed"]


def test_position_to_age():
    table = GrowthTable(species="x", tooth="M1", label="x",
                        knots=[{"position_mm": 0, "age_months": 0}, {"position_mm": 10, "age_months": 5}])
    ages, outside = position_to_age([0, 5, 10, 12], table)
    np.testing.assert_allclose(ages, [0, 2.5, 5, 6])
    assert outside.tolist() == [False, False, False, True]
    ages, _ = position_to_age([0, 6], table, LinearGrowthOverride(initiation_age_months=2, extension_rate_mm_per_month=3))
    np.testing.assert_allclose(ages, [2, 4])
    with pytest.raises(ValidationError):
        GrowthTable(species="x", tooth="M1", label="x",
                    knots=[{"position_mm": 5, "age_months": 1}, {"position_mm": 2, "age_months": 3}])


def test_calibration():
    rng = np.random.default_rng(0)
    points = [CalibrationPoint(position_mm=p, age_months=1 + p / 3 + rng.normal(0, 0.3)) for p in np.linspace(0, 40, 20)]
    result = calibrate_growth_table("cattle", "M2", points, "linear")
    knots = result["table"]["knots"]
    assert knots[0]["age_months"] == pytest.approx(1, abs=0.4) and knots[-1]["age_months"] == pytest.approx(14.3, abs=0.5)
    assert result["residual_sd"] == pytest.approx(0.3, abs=0.15) and not result["table"]["placeholder"]
    ages = [k["age_months"] for k in calibrate_growth_table("cattle", "M2", points, "isotonic")["table"]["knots"]]
    assert ages == sorted(ages)


def test_saved_tables_and_placeholders(tmp_path, monkeypatch):
    monkeypatch.setenv("WEANAGE_HOME", str(tmp_path))
    ids = {i["id"] for i in config.tbd_items()}
    assert "growth:cattle:M2" in ids and "qc:thresholds" in ids
    edited = config.find_growth_table("cattle", "M2").model_copy(update={"placeholder": False, "label": "lab"})
    config.save_growth_table(edited)
    assert config.find_growth_table("cattle", "M2").label == "lab"
    assert "growth:cattle:M2" not in {i["id"] for i in config.tbd_items()}
    assert config.delete_saved_growth_table("cattle:M2") and config.find_growth_table("cattle", "M2").placeholder
    upper = edited.model_copy(update={"species": "Cattle"})
    assert type(upper).model_validate(upper.model_dump()).key == "cattle:M2"  # one key, whatever the case
