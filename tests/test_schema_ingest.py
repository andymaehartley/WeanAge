import pytest
from pydantic import ValidationError

from weanage.config import DATA_DIR
from weanage.ingest import canonical_column, ingest_csv, ingest_records
from weanage.schema import GrowthTable, IsotopeSample


def test_cn_ratio_derived_from_percentages():
    s = IsotopeSample(specimen_id="a", site="s", species="Cattle", tooth="M2",
                      position_mm=1, d15N=7, pct_C=42.0, pct_N=15.0)
    assert s.species == "cattle"
    assert s.cn_ratio == pytest.approx(42 / 15 * 14.007 / 12.011, abs=1e-3)


def test_out_of_range_values_rejected():
    with pytest.raises(ValidationError):
        IsotopeSample(specimen_id="a", site="s", species="cattle", tooth="M2", position_mm=-1, d15N=7)


def test_growth_table_must_be_monotonic():
    with pytest.raises(ValidationError):
        GrowthTable(species="x", tooth="M1", label="x",
                    knots=[{"position_mm": 5, "age_months": 1}, {"position_mm": 2, "age_months": 3}])


@pytest.mark.parametrize("header,expected", [
    ("δ15N (‰)", "d15N"), ("d15N_AIR", "d15N"), ("C:N", "cn_ratio"), ("%C", "pct_C"),
    ("Specimen ID", "specimen_id"), ("Position (mm)", "position_mm"), ("mystery", None),
])
def test_column_aliases(header, expected):
    assert canonical_column(header) == expected


def test_csv_ingest_with_aliases_and_errors():
    csv = (
        "Specimen ID,Site,Taxon,Tooth,Position (mm),δ15N (‰),C:N,extra\n"
        "A1,S,cattle,M2,0.5,8.1,3.2,x\n"
        "A1,S,cattle,M2,1.5,not-a-number,3.2,x\n"
    ).encode()
    report = ingest_csv(csv)
    assert len(report.samples) == 1
    assert any(i.row == 2 and i.field == "d15N" for i in report.issues)
    assert "extra" in report.unrecognised_columns
    assert not report.ok


def test_missing_required_column():
    report = ingest_csv(b"specimen_id,site\nA,B\n")
    assert not report.samples
    assert "Missing required column" in report.issues[0].message


def test_dataset_level_warnings():
    rows = [dict(specimen_id="A", site="S", species="sheep", tooth="M2", position_mm=i, d15N=7) for i in range(3)]
    msgs = [i.message for i in ingest_records(rows).issues]
    assert any("only 3 samples" in m for m in msgs)
    assert any("No growth table" in m for m in msgs)


def test_bundled_example_is_valid():
    report = ingest_csv(DATA_DIR / "examples" / "synthetic_example.csv")
    assert report.ok and len(report.specimens) >= 5
