"""The whole pipeline, comparisons between groups, validation and the sampling planner."""

import numpy as np
import pytest

from weanage.aggregate import aggregate, interval_coverage, model_disagreement, validate
from weanage.analysis import analyze, carbon_weaning_check, estimate_rows, seasonality_checks
from weanage.inference import compare_groups, holm, random_effects
from weanage.schema import IsotopeSample
from weanage.simulate import SimulationScenario, run_simulation, sweep

from .conftest import opts


def test_end_to_end(make_samples):
    samples = make_samples()
    samples[5] = samples[5].model_copy(update={"cn_ratio": 4.2, "d15N": 15.0})  # one bad sample
    [res] = analyze(samples, opts())
    assert res["growth_placeholder"] and any("PLACEHOLDER" in w for w in res["warnings"])
    assert {f["model"] for f in res["fits"]} == {"logistic", "piecewise", "exponential", "two_phase", "elbow"}
    assert sum(not p["used_in_fit"] for p in res["points"]) == 1
    logistic = next(f for f in res["fits"] if f["model"] == "logistic")
    assert logistic["completion"]["estimate"] == pytest.approx(7 + 0.8 * 2.944, abs=0.7)
    assert {r["model"] for r in estimate_rows([res])} >= {"logistic", "average"}


def test_missing_growth_table_and_linear_model(make_samples):
    samples = make_samples(species="sheep")
    assert "No growth table" in analyze(samples, opts())[0]["warnings"][0]
    custom = opts(growth_overrides={"sheep:M2": {"initiation_age_months": 1, "extension_rate_mm_per_month": 3}})
    assert analyze(samples, custom)[0]["fits"]


def test_teeth_of_one_animal_join(make_samples):
    m1 = [s.model_copy(update={"specimen_id": "A-M1", "tooth": "M1"}) for s in make_samples(n=30)]
    samples = [s.model_copy(update={"individual_id": "A"}) for s in m1 + make_samples("A-M2")]
    [res] = analyze(samples, opts(models=["logistic"], monte_carlo_draws=0))
    assert res["specimen_id"] == "A" and res["tooth"] == "M1+M2"
    ages = [p["age_months"] for p in res["points"]]
    assert ages == sorted(ages)


def test_time_averaging_removes_lag():
    """Slices that mix in later dentine shift the curve; modelling the mixing fixes that."""
    positions = np.arange(0.5, 40, 1.0)
    steps = np.linspace(0, 1, 15)
    blurred = [np.mean(5 + 3 / (1 + np.exp((1 + ((p - 0.5) + steps * 5) * 11.5 / 45 - 7) / 0.4))) for p in positions]
    samples = [IsotopeSample(specimen_id="X", site="S", species="cattle", tooth="M2", position_mm=p, d15N=v, cn_ratio=3.2)
               for p, v in zip(positions, blurred)]
    plain = analyze(samples, opts(models=["logistic"], monte_carlo_draws=0))[0]
    fixed = analyze(samples, opts(models=["logistic"], monte_carlo_draws=0, time_averaging=True,
                                  growth_layer_offset_mm=4, inner_dentine_weight=1))[0]
    assert abs(fixed["fits"][0]["midpoint"]["estimate"] - 7) < 0.15 < abs(plain["fits"][0]["midpoint"]["estimate"] - 7)
    assert fixed["points"][0]["age_min"] < fixed["points"][0]["age_months"] < fixed["points"][0]["age_max"]


def test_adult_baseline(make_samples):
    settings = opts(models=["logistic"], monte_carlo_draws=0, adult_baselines={"cattle": {"mean": 5.0, "sd": 0.1}},
                    constrain_adult_plateau=True)
    fit = analyze(make_samples(), settings)[0]["fits"][0]
    assert fit["adult_d15N"] <= 5.2 + 1e-6 and fit["enrichment_permil"] == pytest.approx(fit["nursing_d15N"] - 5)
    both = opts(adult_baselines={"cattle": {"mean": 5}, "Site A:cattle": {"mean": 6}})
    assert both.baseline_for("site a", "cattle").mean == 6 and both.baseline_for("Site B", "cattle").mean == 5


def test_rising_and_seasonal_warnings():
    t = np.linspace(0, 14, 40)
    warnings, found = seasonality_checks(t, np.zeros_like(t), None, -22 + 0.8 * np.sin(2 * np.pi * t / 12), 12)
    assert any("δ13C oscillates" in w for w in warnings) and found["d13C_seasonal_p"] < 0.05
    # A single δ13C step at weaning is not a yearly cycle once the weaning curve is allowed for.
    curve = 5 + 3 / (1 + np.exp(t - 7))
    step = -22 + (8 - curve) / 3 + np.random.default_rng(1).normal(0, 0.1, t.size)
    assert not seasonality_checks(t, curve, None, step, 12, weaning_curve=curve)[0]
    samples = [IsotopeSample(specimen_id="R", site="S", species="cattle", tooth="M2", position_mm=p, d15N=5 + p / 10,
                             cn_ratio=3.2) for p in np.arange(0.5, 40, 1.0)]
    assert any("rises with age" in w for w in analyze(samples, opts(models=["logistic"]))[0]["warnings"])


def test_parallel_matches_one_at_a_time(make_samples):
    samples = sum((make_samples(f"S{i}", seed=i) for i in range(6)), [])
    settings = opts(models=["logistic"], monte_carlo_draws=50)
    first = [r["fits"][0]["completion"]["estimate"] for r in analyze(samples, settings, workers=1)]
    second = [r["fits"][0]["completion"]["estimate"] for r in analyze(samples, settings, workers=2)]
    assert first == pytest.approx(second)


def site_estimates(make_samples):
    samples = []
    for i in range(4):
        samples += make_samples(f"A{i}", site="A", t_mid=8.5 + 0.2 * i, seed=i)
        samples += make_samples(f"B{i}", site="B", t_mid=4.5 + 0.2 * i, seed=10 + i)
    return estimate_rows(analyze(samples, opts(models=["logistic", "piecewise"])))


def test_summaries_and_group_tests(make_samples):
    rows = site_estimates(make_samples)
    summary = aggregate(rows, ["site"]).set_index("site")
    assert summary.loc["A", "n"] == 4 and summary.loc["A", "mean"] > summary.loc["B", "mean"] + 2
    assert set(aggregate(rows, ["site"], model="average")["model"]) == {"average"}
    assert len(model_disagreement(rows)) == 8
    result = compare_groups(rows, ["site"])
    assert result["q_p"] < 0.001 and result["pairwise"][0]["p_holm"] < 0.001 and result["permutation_p"] < 0.05
    pair = result["bayes"]["pairs"][0]
    assert pair["prob_a_earlier"] < 0.01 and result["bayes"]["rhat_max"] < 1.1  # A weaned later than B


def test_statistics_helpers():
    mean, se, tau = random_effects(np.array([5.0, 5.0, 5.0]), np.array([1.0, 1.0, 1.0]))
    assert mean == 5 and tau == 0 and se == pytest.approx(1 / np.sqrt(3))
    assert random_effects(np.array([2.0, 8.0, 5.0, 11.0]), np.array([0.2] * 4))[2] > 2
    assert holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert interval_coverage([1], [3], [2]) == 1


def test_validation(make_samples):
    known = [s.model_copy(update={"known_weaning_age_months": 9.36, "published_weaning_age_months": 9.0})
             for s in make_samples(noise=0.05)]
    table = validate(estimate_rows(analyze(known, opts())))
    assert set(table["reference"]) == {"known age", "published estimate"}
    assert table.set_index(["reference", "model"]).loc[("known age", "logistic"), "mae"] < 1


def test_sampling_planner():
    logistic_only = opts(models=["logistic"], monte_carlo_draws=0)
    score = run_simulation(SimulationScenario(n_specimens=8, seed=3), logistic_only)["scores"][0]
    assert score["success_rate"] == 1 and score["mae"] < 0.6
    runs = sweep(SimulationScenario(n_specimens=10, seed=4), "noise_sd", [0.05, 0.6], logistic_only)
    assert runs[0]["scores"][0]["mae"] < runs[1]["scores"][0]["mae"]
    clean = run_simulation(SimulationScenario(n_specimens=20, seed=5), logistic_only)["scores"][0]["mae"]
    noisy = run_simulation(SimulationScenario(n_specimens=20, seed=5, age_model_error_sd=1.5), logistic_only)["scores"][0]["mae"]
    assert noisy > clean + 0.4


def test_carbon_shift_at_weaning():
    t = np.arange(0, 12, 0.5)
    fit = {"onset": {"estimate": 4}, "completion": {"estimate": 8}}
    rising = np.where(t < 6, -22.0, -21.0)  # δ13C up by 1‰, as in Balasse et al. (2001)
    assert carbon_weaning_check(t, rising, fit, "cattle") == (None, 1.0)
    warning, shift = carbon_weaning_check(t, -rising - 43, fit, "cattle")  # δ13C down by 1‰
    assert shift == -1.0 and "Balasse" in warning
    assert carbon_weaning_check(t, -rising - 43, fit, "pig")[0] is None  # only reported for other species
    assert carbon_weaning_check(t, np.full(t.size, np.nan), fit, "cattle") == (None, None)


def test_validate_command(make_samples, tmp_path, capsys):
    import pandas as pd

    from weanage.cli import main

    rows = [s.model_dump() | {"known_weaning_age_months": 9.4} for s in make_samples()]
    pd.DataFrame(rows).to_csv(tmp_path / "reference.csv", index=False)
    main(["validate", str(tmp_path / "reference.csv")])
    assert "known" in capsys.readouterr().out.lower()
