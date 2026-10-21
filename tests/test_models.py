"""Curve fitting, weaning ages, uncertainty, model comparison and seasonality."""

import math

import numpy as np
import pytest

from weanage.aggregate import error_metrics
from weanage.models import MODELS, aicc, compare_fits, fit_model, model_average, seasonal_test

from .conftest import logistic_series, opts


def completion(fit):
    return fit["completion"]["estimate"]


def width(fit):
    return fit["completion"]["ci_high"] - fit["completion"]["ci_low"]


@pytest.mark.parametrize("t_mid,scale", [(5.0, 0.6), (7.0, 0.8), (9.0, 1.2)])
def test_logistic_recovers_known_curve(t_mid, scale):
    t, y = logistic_series(t_mid=t_mid, scale=scale, noise=0.05)
    fit = fit_model("logistic", t, y, opts())
    assert fit["midpoint"]["estimate"] == pytest.approx(t_mid, abs=0.3)
    assert completion(fit) == pytest.approx(t_mid + scale * math.log(19), abs=0.6)
    assert fit["completion"]["ci_low"] < completion(fit) < fit["completion"]["ci_high"]
    assert fit["drop_permil"] == pytest.approx(3.0, abs=0.2)


def test_piecewise_and_exponential_recover_breakpoints():
    t = np.linspace(0, 20, 60)
    noise = np.random.default_rng(1).normal(0, 0.05, len(t))
    fit = fit_model("piecewise", t, MODELS["piecewise"]["curve"](t, 5, 3, 4, 5) + noise, opts(monte_carlo_draws=0))
    assert fit["onset"]["estimate"] == pytest.approx(4, abs=0.4) and completion(fit) == pytest.approx(9, abs=0.4)
    fit = fit_model("exponential", t, MODELS["exponential"]["curve"](t, 5, 3, 6, 2) + noise, opts(monte_carlo_draws=0))
    assert fit["onset"]["estimate"] == pytest.approx(6, abs=0.5)


def test_two_phase_finds_staged_weaning_only_when_present():
    t = np.linspace(0, 16, 50)
    y = MODELS["two_phase"]["curve"](t, 5.4, 3.0, 0.45, 3.5, 6.5, 0.5) + np.random.default_rng(0).normal(0, 0.1, len(t))
    fits = [fit_model(m, t, y, opts()) for m in ("logistic", "two_phase")]
    assert compare_fits(fits) == "two_phase"
    extra = fits[1]["extra"]
    assert extra["supplementation_months"] == pytest.approx(6.5, abs=1) and extra["intermediate_d15N"] == pytest.approx(7.05, abs=0.3)
    t, y = logistic_series(noise=0.1, seed=3)
    assert compare_fits([fit_model(m, t, y, opts(monte_carlo_draws=0)) for m in ("logistic", "two_phase")]) == "logistic"


def test_elbow():
    t = np.linspace(0, 20, 60)
    y = MODELS["piecewise"]["curve"](t, 5, 3, 4, 6) + np.random.default_rng(5).normal(0, 0.05, len(t))
    fit = fit_model("elbow", t, y, opts())
    assert completion(fit) == pytest.approx(10, abs=1.5) and fit["midpoint"] is None
    rising = fit_model("elbow", t[:20], 5 + 0.3 * t[:20], opts())
    assert not rising["converged"] and "peaks at the end" in rising["message"]


def test_elbow_gives_no_age_without_a_real_drop():
    """A flat, noisy series still has an 'elbow' somewhere; it must not be reported as a weaning age."""
    t = np.linspace(0, 12, 12)
    flat = 6.5 + np.random.default_rng(1).normal(0, 0.2, len(t))
    fit = fit_model("elbow", t, flat, opts())
    assert fit["completion"] is None and fit["onset"] is None
    assert fit["message"].startswith("No weaning age reported") and fit["curve_d15N"]
    before_birth = fit_model("elbow", t - 8, MODELS["piecewise"]["curve"](t, 5, 3, 1, 3), opts())
    assert before_birth["completion"] is None and "before birth" in before_birth["message"]


def test_model_average_ignores_a_withheld_elbow():
    t = np.linspace(0, 12, 12)
    flat = 6.5 + np.random.default_rng(1).normal(0, 0.2, len(t))
    fits = [fit_model(name, t, flat, opts()) for name in ("logistic", "elbow")]
    compare_fits(fits)
    average = model_average(fits).get("completion")
    logistic = fits[0]["completion"]
    assert average is None or average["estimate"] == pytest.approx(logistic["estimate"])


def test_warnings_and_too_few_points():
    t = np.linspace(0, 15, 40)
    flat = fit_model("logistic", t, 6 + np.random.default_rng(3).normal(0, 0.1, len(t)), opts(monte_carlo_draws=0))
    assert any("no clear weaning signal" in w for w in flat["warnings"])
    short = fit_model("logistic", [1, 2, 3], [8, 7, 6], opts())
    assert not short["converged"] and "at least" in short["message"]
    assert aicc(1.0, 5, 4) is None and aicc(1.0, 30, 4) is not None


def test_seasonal_term():
    t = np.linspace(0, 24, 72)
    y = MODELS["logistic"]["curve"](t, 5, 3, 8, 0.8) + 0.6 * np.sin(2 * np.pi * t / 12) + np.random.default_rng(4).normal(0, 0.1, len(t))
    plain = fit_model("logistic", t, y, opts(monte_carlo_draws=0))
    seasonal = fit_model("logistic", t, y, opts(monte_carlo_draws=0, seasonal_term=True))
    assert seasonal["aicc"] < plain["aicc"]
    assert seasonal["extra"]["seasonal_amplitude_permil"] == pytest.approx(0.6, abs=0.15)


def test_seasonal_test_is_calibrated():
    rng = np.random.default_rng(1)
    t = np.linspace(0, 14, 40)
    false_alarms = np.mean([seasonal_test(t, rng.normal(0, 0.3, len(t)))[1] < 0.05 for _ in range(300)])
    assert false_alarms <= 0.1
    amplitude, p = seasonal_test(t, np.sin(2 * np.pi * t / 12) + rng.normal(0, 0.1, len(t)))
    assert p < 1e-6 and amplitude == pytest.approx(1, abs=0.15)
    assert seasonal_test(t[:10], np.zeros(10)) is None


def test_uncertainty_options():
    t, y = logistic_series(noise=0.1, seed=6)
    boot = fit_model("logistic", t, y, opts(uncertainty="bootstrap", bootstrap_draws=100))
    assert boot["completion"]["ci_low"] < completion(boot) < boot["completion"]["ci_high"]
    # A shared age-model error of 1 SD widens the interval by about ±1.96 months.
    t, y = logistic_series(noise=0.02, seed=7)
    narrow = fit_model("logistic", t, y, opts(monte_carlo_draws=2000))
    wide = fit_model("logistic", t, y, opts(monte_carlo_draws=2000), age_sd=1.0)
    assert width(wide) == pytest.approx(np.hypot(width(narrow), 2 * 1.96), rel=0.15)


def test_model_average():
    t, y = logistic_series(noise=0.1, seed=8)
    fits = [fit_model(m, t, y, opts(monte_carlo_draws=500)) for m in ("logistic", "piecewise", "exponential")]
    compare_fits(fits)
    assert sum(f["akaike_weight"] for f in fits) == pytest.approx(1)
    average = model_average(fits)["completion"]
    assert min(map(completion, fits)) <= average["estimate"] <= max(map(completion, fits))
    assert average["ci_low"] < average["estimate"] < average["ci_high"]


def test_accuracy_on_simulated_animals():
    rng = np.random.default_rng(10)
    estimates, truth = [], []
    for i in range(12):
        t_mid, scale = rng.uniform(4, 9), rng.uniform(0.5, 1.0)
        t, y = logistic_series(t_mid=t_mid, scale=scale, noise=0.15, seed=i)
        estimates.append(completion(fit_model("logistic", t, y, opts(monte_carlo_draws=0))))
        truth.append(t_mid + scale * math.log(19))
    m = error_metrics(estimates, truth)
    assert m["mae"] < 1 and abs(m["bias"]) < 0.6 and m["pearson_r"] > 0.9
