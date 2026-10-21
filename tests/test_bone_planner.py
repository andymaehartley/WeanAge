"""Planning a bone study by simulation."""

import numpy as np

from weanage.bone_planner import BoneScenario, run_bone_plan, simulate_site
from weanage.config import find_turnover_table
from weanage.schema import BoneOptions

QUICK = BoneOptions(chains=8, warmup=500, keep=500)


def test_simulated_site_matches_the_design():
    scenario = BoneScenario(n_young=25, n_adult_females=7, age_error_months=2, oldest_young_months=30)
    samples, truth = simulate_site(scenario, np.random.default_rng(0), find_turnover_table("cattle"))
    young = [s for s in samples if not s.is_adult]
    assert len(young) == 25 and len(samples) == 32
    assert all(abs((s.age_max_months - s.age_min_months) - 4) < 1e-6 for s in young)  # ± 2 months
    assert 6 <= truth["completion"] <= 12 and truth["onset"] < truth["completion"]


def test_more_young_animals_give_narrower_intervals():
    out = run_bone_plan(BoneScenario(replicates=3), QUICK, "n_young", [12, 60])
    few, many = (run["metrics"] for run in out["runs"])
    assert many["ci_width"] < few["ci_width"]
    assert many["signal_found"] == 1 and many["mae"] < 3
    assert out["turnover_placeholder"] and out["sweep_param"] == "n_young"


def test_sweep_values_are_checked():
    import pydantic
    import pytest

    with pytest.raises(pydantic.ValidationError):
        run_bone_plan(BoneScenario(replicates=2), QUICK, "age_error_months", [-1])
