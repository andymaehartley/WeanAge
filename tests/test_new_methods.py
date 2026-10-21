"""The one-stage Bayesian model, the nursing-enrichment check, slice geometry and planner shapes."""

import numpy as np
import pytest

from weanage.analysis import analyze, slice_positions, slice_weights
from weanage.joint import joint_bayes, specimens_from_results, starting_values
from weanage.models import MODELS, drop_warnings
from weanage.schema import AnalysisOptions
from weanage.simulate import SimulationScenario, simulate_samples, true_curve

from .conftest import opts


def test_one_stage_model_recovers_group_ages(make_samples):
    """Two groups whose true completion ages are about 9.4 and 6.9 months."""
    samples = []
    for i in range(3):
        samples += make_samples(f"A{i}", site="A", t_mid=7.0 + 0.2 * i, seed=i)
        samples += make_samples(f"B{i}", site="B", t_mid=4.5 + 0.2 * i, seed=10 + i)
    results = analyze(samples, opts(models=["logistic"], monte_carlo_draws=0), workers=1)
    specimens, skipped = specimens_from_results(results, ["site"], "completion")
    assert len(specimens) == 6 and not skipped
    names, group_of, m, mu, tau = joint_bayes(specimens, "completion", warmup=800, keep=800)
    a, b = mu[..., 0].ravel(), mu[..., 1].ravel()
    assert list(names) == ["A", "B"]
    assert abs(a.mean() - (7.2 + 0.8 * 2.944)) < 0.6 and abs(b.mean() - (4.7 + 0.8 * 2.944)) < 0.6
    assert np.mean(b < a) > 0.9  # B weaned earlier (only 3 animals per group, so not certain)


def test_one_stage_starts_inside_the_prior():
    spec = {"logistic": {"post": 5.0, "drop": 30.0, "t_mid": 6.0, "scale": 1.0}}
    assert starting_values(spec)["drop"] < 20


def test_drop_plausibility():
    options = AnalysisOptions()
    assert "no clear weaning signal" in drop_warnings(0.5, options)[0]
    assert drop_warnings(2.5, options) == []
    assert "food-chain step" in drop_warnings(7.0, options)[0]


def test_slice_geometry():
    grid = slice_positions(10.0, 1.0, 4.0)
    assert len(grid) == 64 and grid.min() == 9.5 and grid.max() == 14.5  # height + full depth offset
    weights = slice_weights(4.0, 0.5)
    assert weights[0] == 1.0 and weights[7] == 0.5  # enamel side to pulp side
    assert len(slice_positions(10.0, 1.0, 0.0)) == len(slice_weights(0.0, 0.5)) == 8  # no offset: one depth is enough


@pytest.mark.parametrize("shape", ["logistic", "piecewise", "exponential", "two_phase"])
def test_planner_shapes_are_centred_alike(shape):
    params = true_curve(shape, 5.5, 3.0, 7.0, 0.8, np.random.default_rng(0), 0.05)
    ages = MODELS[shape]["ages"](np.array(params), 0.05)
    assert ages["onset"] < ages["midpoint"] < ages["completion"] and abs(ages["midpoint"] - 7.0) < 1.5
    samples, truth = simulate_samples(SimulationScenario(n_specimens=3, true_shape=shape))
    assert len(truth) == 3 and samples
