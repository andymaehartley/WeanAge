"""Human calculations: dental age, enamel hypoplasia, milk share, life tables, mobility, grouping."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from weanage import config, service
from weanage.dental_age import stage_ages, tooth_age
from weanage.hypoplasia import analyze_leh
from weanage.lifetable import analyze_lifetable, survival
from weanage.mobility import drinking_water
from weanage.schema import (
    AdultBaseline,
    AnalysisOptions,
    DentineContext,
    LehOptions,
    LehSample,
    LifeSample,
    LifeTableOptions,
    LinearGrowthOverride,
    MobilitySample,
    WeaningFood,
    stage_name,
    tooth_name,
)

EXAMPLES = config.DATA_DIR / "examples"
TEST_DATA = Path(__file__).parent / "data"


def from_file(name, path):
    """Run a calculation on a table, as the app does after a file is dropped."""
    report = service.CALCULATIONS[name].ingest(pd.read_csv(path))
    assert not [i for i in report["issues"] if i["severity"] == "error"]
    return service.run_calculation(name, {"samples": [s.model_dump() for s in report["samples"]], "options": {"bootstrap_draws": 200}})


def truth(notes, unit):
    return float(notes.split("true age ")[1].split(f" {unit}")[0])


def test_names_are_read_leniently():
    assert [tooth_name(t) for t in ("lower left P4", "dm2", "M1", "upper I1")] == ["PM2", "dm2", "M1", "I1"]
    assert [stage_name(s) for s in ("Cr ½", "crc", 7, "Cli")] == ["Cr1/2", "Crc", "Ri", "Ri"]
    with pytest.raises(ValueError):
        stage_name("R5")


def test_stage_ages_rise_and_match_the_table():
    table = config.dental_stages()
    assert set(table["stages"]) == set(stage_ages("M1", table)) and set(table["teeth"]) >= {"M1", "dm2", "I1"}
    for tooth in table["teeth"]:
        ages = list(stage_ages(tooth, table).values())
        assert ages == sorted(ages), tooth
    assert "minimum" in tooth_age("M1", "Ac", table)


def test_dental_example_is_recovered():
    df = pd.read_csv(EXAMPLES / "synthetic_dental_example.csv")
    ex = service.calculation_example("dental")
    out = service.run_calculation("dental", {"samples": ex["samples"], "options": {}})
    true = df.groupby("specimen_id").notes.first().map(lambda n: truth(n, "months"))
    errors = [r["estimate_months"] - true[r["specimen_id"]] for r in out["results"]]
    inside = [r["age_min_months"] <= true[r["specimen_id"]] <= r["age_max_months"] for r in out["results"]]
    assert np.mean(np.abs(errors)) < 6 and np.mean(inside) > 0.85 and out["placeholder"]


def test_hypoplasia_dates_and_links_to_weaning():
    defect = LehSample(specimen_id="H1", site="S", species="human", tooth="I1", defect_mm=5.5, crown_height_mm=11)
    t = config.dental_stages()["teeth"]["I1"]
    out = analyze_leh([defect], LehOptions(dentine={"H1": DentineContext(onset=20, completion=40, stress=[(25, 30)])}))
    (r,) = out["results"]
    assert abs(r["age"]["estimate"] - (t["initiation"] + (t["crown"] - t["initiation"]) / 2)) < 1e-9
    assert r["dentine"]["weaning"] == "during" and r["dentine"]["stress_episodes"] == [[25, 30]]
    with pytest.raises(ValidationError):
        LehSample(specimen_id="H1", site="S", species="human", tooth="I1", defect_mm=12, crown_height_mm=11)


def child_tooth(age_months, baseline=9.0, enrichment=2.0, seed=1):
    from weanage.models import logistic
    from weanage.schema import IsotopeSample

    rng = np.random.default_rng(seed)
    pos = np.arange(0.5, 30, 1.0)
    age = pos / 0.25
    d15n = logistic(age, baseline, enrichment, age_months, 3) + rng.normal(0, 0.1, age.size)
    d13c = -20 + 1.0 / (1 + np.exp((age - age_months) / 3)) + rng.normal(0, 0.1, age.size)
    return [IsotopeSample(specimen_id="H1", site="X", species="human", tooth="M1", position_mm=p, d15N=n, d13C=c, cn_ratio=3.2)
            for p, n, c in zip(pos, d15n, d13c)]


def test_milk_share_falls_at_weaning():
    from weanage.analysis import analyze_specimen

    options = AnalysisOptions(monte_carlo_draws=50, nursing_enrichment_d15N=2.0, nursing_enrichment_d15N_sd=0.3,
                              growth_overrides={"human:M1": LinearGrowthOverride(initiation_age_months=0, extension_rate_mm_per_month=0.25)},
                              adult_baselines={"human": AdultBaseline(mean=9.0, sd=0.3, d13C_mean=-20, d13C_sd=0.3)})
    share = analyze_specimen(child_tooth(24), options)["milk_share"]
    assert abs(share["below_half_age"] - 24) < 4
    first, last = share["points"][0]["milk"], share["points"][-1]["milk"]
    assert first["estimate"] > 0.7 and last["estimate"] < 0.3 and last["ci_low"] <= 0.05
    with_food = analyze_specimen(child_tooth(24), options.model_copy(update={"weaning_food": WeaningFood(name="millet", d15N=8, d13C=-12)}))
    assert "other" in with_food["milk_share"]["points"][0]
    no_carbon = options.model_copy(update={"adult_baselines": {"human": AdultBaseline(mean=9.0, sd=0.3)},
                                           "weaning_food": WeaningFood(name="millet", d15N=8)})
    assert "left out" in analyze_specimen(child_tooth(24), no_carbon)["milk_share"]["warnings"][0]


def test_life_table_arithmetic_and_siler():
    # Ten skeletons, all exactly in one class each: the table can be checked by hand.
    ages = [(0, 1)] * 2 + [(1, 2)] + [(20, 30)] * 3 + [(50, 60)] * 4
    samples = [LifeSample(specimen_id=str(i), site="S", species="human", age_min_years=a, age_max_years=b)
               for i, (a, b) in enumerate(ages)]
    out = analyze_lifetable(samples, LifeTableOptions(class_bounds_years=[0, 1, 2, 20, 30, 50, 60], bootstrap_draws=0, siler=False))
    rows = out["results"][0]["rows"]
    assert [round(r["d"], 2) for r in rows] == [0.2, 0.1, 0, 0.3, 0, 0.4]
    assert [round(r["l"], 2) for r in rows] == [1, 0.8, 0.7, 0.7, 0.4, 0.4]
    # e0 = years lived per person: 0.9 + 0.75 + 18·0.7 + 10·0.55 + 20·0.4 + 10·0.2 = 29.75
    assert abs(out["results"][0]["summary"]["e0"]["estimate"] - 29.75) < 1e-9
    assert out["results"][0]["summary"]["infant_share"]["estimate"] == pytest.approx(0.2)


def test_cemetery_example():
    out = from_file("lifetable", TEST_DATA / "synthetic_cemetery_example.csv")
    a, b = out["results"]
    true_e0 = float(np.sum(survival(np.linspace(0, 100, 20001), 0.25, 1.0, 0.01, 0.0004, 0.09)) * 100 / 20000)
    assert abs(a["siler"]["e0"] - true_e0) < 6 and abs(a["summary"]["e0"]["estimate"] - true_e0) < 6
    assert a["summary"]["infant_share"]["estimate"] > b["summary"]["infant_share"]["estimate"]
    assert any("infant burials" in w for w in b["warnings"])


def test_drinking_water_equations():
    assert drinking_water(MobilitySample(specimen_id="a", site="s", species="human", d18O=-4.0)) == pytest.approx(-6.04, abs=0.01)
    phosphate = MobilitySample(specimen_id="a", site="s", species="human", d18O=17.5, d18O_material="phosphate")
    assert drinking_water(phosphate) == pytest.approx(1.54 * 17.5 - 33.72)
    # Chenery's combined equation = their carbonate-to-phosphate step followed by Daux's.
    c = 25.0
    assert 1.590 * c - 48.634 == pytest.approx(1.54 * (1.0322 * c - 9.6849) - 33.72, abs=0.02)


def test_mobility_example_finds_the_incomers():
    df = pd.read_csv(TEST_DATA / "synthetic_mobility_example.csv")
    out = from_file("mobility", TEST_DATA / "synthetic_mobility_example.csv")
    found = {r["specimen_id"] for r in out["results"] if r["non_local"]}
    assert found == set(df[df.notes.str.contains("elsewhere")].specimen_id)
    assert out["sites"][0]["sr_range_from"] == "12 baseline samples"


def test_group_by_kept_columns():
    from weanage.ingest import ingest_dataframe

    df = pd.read_csv(TEST_DATA / "synthetic_example.csv")
    df["burial"] = np.where(df.specimen_id.str[-1].isin(list("13579")), "crouched", "extended")
    report = ingest_dataframe(df)
    assert all("burial" in s.labels for s in report["samples"])
    out = service.run_analysis(service.AnalyzeIn(samples=report["samples"][:60], options=AnalysisOptions(monte_carlo_draws=50)), workers=1)
    body = service.AggregateIn(estimates=out["estimates"], group_by=["burial"], bayes=False)
    assert {row["burial"] for row in service.compare(body)["summary"]} <= {"crouched", "extended"}
    with pytest.raises(ValueError):
        service.compare(service.AggregateIn(estimates=out["estimates"], group_by=["nothing"], bayes=False))


def test_detect_offers_only_the_calculations_a_table_can_feed():
    from fastapi.testclient import TestClient

    from weanage.api import app

    content = (TEST_DATA / "synthetic_mobility_example.csv").read_bytes()
    found = service.detect("m.csv", content)["calculations"]
    assert [name for name, d in found.items() if d["rows"]] == ["mobility"]
    assert "d15N" in found["tooth"]["problem"]
    tooth = TestClient(app).post("/api/detect", files={"file": ("t.csv", (TEST_DATA / "synthetic_example.csv").read_bytes())}).json()
    assert {name for name, d in tooth["calculations"].items() if d["rows"]} == {"tooth", "mixing"}


@pytest.mark.parametrize("name", ["lifetable", "killoff", "mixing", "mobility"])
def test_published_examples_run(name):
    example = service.calculation_example(name)
    assert example["samples"] and not [i for i in example["issues"] if i["severity"] == "error"]
    out = service.run_calculation(name, {"samples": example["samples"], "options": {}})
    assert out["results"]
