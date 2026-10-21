"""The bone (cross-sectional, WARN-style) weaning model."""

import numpy as np
import pandas as pd
import pytest

from weanage import config, service
from weanage.bone import STEP, analyze_bones, bone_curve, ingest_bone_dataframe, milk_share, renewal
from weanage.schema import BoneOptions, BoneSample

QUICK = BoneOptions(warmup=1000, keep=1000)  # shorter runs keep the tests fast


def test_milk_share():
    t = np.array([0, 2, 5, 8, 20])
    assert milk_share(t, 2, 8, "linear").tolist() == [1, 1, 0.5, 0, 0]


def test_bone_follows_the_diet_with_a_delay():
    grid = np.arange(0, 120 + STEP, STEP)
    renewed = renewal(config.find_turnover_table("cattle"), grid)
    bone, diet = bone_curve(grid, renewed, 3, 9, 2.5, 5.0, 6.0)
    assert bone[0] == pytest.approx(6.0)  # born with the mother's value
    assert diet[0] == pytest.approx(8.5) and diet[-1] == pytest.approx(5.0)
    at = lambda age: bone[int(age / STEP)]  # noqa: E731
    assert at(3) > 6.5 and 5.0 < at(120) < at(24) < at(12)  # rises while suckling, then slowly approaches weaning food
    peak = grid[np.argmax(bone)]
    assert 3 < peak < 12  # bone keeps rising after weaning starts: it lags the diet


def test_several_curves_at_once_match_one_at_a_time():
    grid = np.arange(0, 40, STEP)
    renewed = renewal(config.find_turnover_table("sheep"), grid)
    params = np.array([[2, 6, 2.0, 5.5, 6.0], [1, 3, 3.0, 6.5, 7.0]])
    together = bone_curve(grid, renewed, *(params[:, i:i + 1] for i in range(5)))[0]
    for row, p in zip(together, params):
        assert np.allclose(row, bone_curve(grid, renewed, *p)[0])


def test_bone_sample_reading():
    s = BoneSample(specimen_id="x", site="A", species="Cattle", age_min_months=2, age_max_months=6, d15N=7,
                   sex="F?", age_class="juvenile")
    assert s.age_months == 4 and s.sex == "f" and s.age_class == "non-adult" and s.species == "cattle"
    assert BoneSample(specimen_id="y", site="A", species="cattle", age_class="Adult", d15N=6).is_adult
    with pytest.raises(ValueError, match="needs age_months"):
        BoneSample(specimen_id="z", site="A", species="cattle", d15N=6)
    with pytest.raises(ValueError, match="larger than"):
        BoneSample(specimen_id="z", site="A", species="cattle", d15N=6, age_min_months=5, age_max_months=2)


def test_ingest_aliases_and_checks():
    df = pd.DataFrame({"Animal": ["a", "b"], "Site": ["S", "S"], "Taxon": ["cattle", "cattle"],
                       "Age at death (months)": [3, None], "Age class": ["", "adult"], "δ15N (‰)": [8, 6]})
    report = ingest_bone_dataframe(df)
    assert len(report["samples"]) == 2 and report["groups"][0]["n_young"] == 1
    messages = " ".join(i["message"] for i in report["issues"])
    assert "1 non-adults" in messages and "no adult females" in messages
    missing = ingest_bone_dataframe(pd.DataFrame({"specimen_id": ["a"], "site": ["S"]}))
    assert "Missing required" in missing["issues"][0]["message"]


def test_recovers_the_synthetic_weaning_ages():
    """The example was simulated with Site A weaning 3–9 months and Site B 1–4 months."""
    data = service.bone_example()
    samples = [BoneSample(**s) for s in data["samples"]]
    results = {r["site"]: r for r in analyze_bones(samples, QUICK)}
    truth = {"Site A": (3, 9), "Site B": (1, 4)}
    for site, (t1, t2) in truth.items():
        e = results[site]["estimates"]
        assert e["onset"]["ci_low"] < t1 < e["onset"]["ci_high"]
        assert e["completion"]["ci_low"] < t2 < e["completion"]["ci_high"]
        assert e["completion"]["estimate"] == pytest.approx(t2, abs=1.5)
        assert e["enrichment_permil"]["ci_low"] < 2.2 < e["enrichment_permil"]["ci_high"]
        assert results[site]["rhat"] < 1.2 and len(results[site]["curve"]["age"]) > 50
        assert any("PLACEHOLDER" in w for w in results[site]["warnings"])
    assert results["Site A"]["estimates"]["completion"]["estimate"] > results["Site B"]["estimates"]["completion"]["estimate"]


def test_no_mothers_and_unknown_species():
    young = [BoneSample(specimen_id=str(i), site="S", species="cattle", age_months=i, d15N=7) for i in range(5)]
    assert "mothers" in analyze_bones(young, QUICK)[0]["message"]
    with_baseline = analyze_bones(young, BoneOptions(warmup=500, keep=500, female_mean=6.0))[0]
    assert with_baseline["estimates"] and any("Settings" in w for w in with_baseline["warnings"])
    deer = [BoneSample(specimen_id="d", site="S", species="deer", age_months=1, d15N=7)]
    assert "turnover" in analyze_bones(deer, QUICK)[0]["message"]


def test_weaning_forms_follow_warn():
    """WARN Eq. 8: the non-milk share rises as ((t - t1) / (t2 - t1))², or linearly, or fast at first."""
    t = np.array([2.0, 5.0, 8.0])
    assert (1 - milk_share(t, 2, 8, "parabolic")).tolist() == [0, 0.25, 1]
    assert (1 - milk_share(t, 2, 8, "reverse")).tolist() == [0, 0.75, 1]


def test_human_turnover_matches_warn_table_1():
    human = config.find_turnover_table("human")
    assert not human.placeholder
    first_year = 1 - (1 - human.renewed_per_month[1]) ** 12  # share renewed over the first year
    assert first_year == pytest.approx(1 - np.exp(-1.413), abs=1e-3)
