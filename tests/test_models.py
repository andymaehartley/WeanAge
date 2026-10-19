import math

import numpy as np
import pytest

from weanage.models import MODELS, aicc, compare_fits, fit_model
from weanage.validation import error_metrics

from .conftest import logistic_series


@pytest.mark.parametrize("t_mid,scale", [(5.0, 0.6), (7.0, 0.8), (9.0, 1.2)])
def test_logistic_recovers_known_parameters(t_mid, scale):
    t, y = logistic_series(t_mid=t_mid, scale=scale, noise=0.05)
    fit = fit_model("logistic", t, y, draws=300)
    assert fit.converged
    assert fit.midpoint.estimate == pytest.approx(t_mid, abs=0.3)
    expected_completion = t_mid + scale * math.log(19)
    assert fit.completion.estimate == pytest.approx(expected_completion, abs=0.6)
    assert fit.completion.ci_low < fit.completion.estimate < fit.completion.ci_high
    assert fit.drop_permil == pytest.approx(3.0, abs=0.2)


def test_piecewise_recovers_breakpoints():
    t = np.linspace(0, 15, 60)
    y = MODELS["piecewise"].func(t, 5.0, 3.0, 4.0, 5.0) + np.random.default_rng(1).normal(0, 0.05, t.size)
    fit = fit_model("piecewise", t, y, draws=0)
    assert fit.onset.estimate == pytest.approx(4.0, abs=0.4)
    assert fit.completion.estimate == pytest.approx(9.0, abs=0.4)


def test_exponential_recovers_onset():
    t = np.linspace(0, 20, 60)
    y = MODELS["exponential"].func(t, 5.0, 3.0, 6.0, 2.0) + np.random.default_rng(2).normal(0, 0.05, t.size)
    fit = fit_model("exponential", t, y, draws=0)
    assert fit.onset.estimate == pytest.approx(6.0, abs=0.5)
    assert fit.completion.estimate == pytest.approx(6.0 + 2.0 * math.log(20), abs=1.5)


def test_flat_profile_warns_no_weaning_signal():
    t = np.linspace(0, 15, 40)
    y = 6 + np.random.default_rng(3).normal(0, 0.1, t.size)
    fit = fit_model("logistic", t, y, min_drop=1.0, draws=0)
    assert any("no clear weaning signal" in w for w in fit.warnings)


def test_too_few_points():
    fit = fit_model("logistic", [1, 2, 3], [8, 7, 6])
    assert not fit.converged and "at least" in fit.message


def test_correct_model_preferred_by_aicc():
    t, y = logistic_series(noise=0.05, seed=4)
    fits = [fit_model(m, t, y, draws=0) for m in MODELS]
    best = compare_fits(fits)
    assert best in {"logistic", "piecewise"}
    assert sum(f.akaike_weight for f in fits) == pytest.approx(1.0)


def test_aicc_needs_enough_points():
    assert aicc(1.0, 5, 4) is None
    assert aicc(1.0, 30, 4) is not None


def test_simulation_accuracy_metrics():
    """Mini validation study on synthetic animals with known completion ages."""
    rng = np.random.default_rng(10)
    est, known = [], []
    for i in range(12):
        t_mid, scale = rng.uniform(4, 9), rng.uniform(0.5, 1.0)
        t, y = logistic_series(t_mid=t_mid, scale=scale, noise=0.15, seed=i)
        est.append(fit_model("logistic", t, y, draws=0).completion.estimate)
        known.append(t_mid + scale * math.log(19))
    m = error_metrics(est, known)
    assert m["n"] == 12
    assert m["mae"] < 1.0 and abs(m["bias"]) < 0.6 and m["pearson_r"] > 0.9
