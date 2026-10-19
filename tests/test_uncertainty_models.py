"""Two-phase model, seasonal term, bootstrap, correlated age error and model averaging."""

import numpy as np
import pytest

from weanage.analysis import analyze, estimate_rows, seasonality_checks
from weanage.models import MODELS, FitSettings, fit_model, model_average, compare_fits, seasonal_test
from weanage.schema import AnalysisOptions

from .conftest import logistic_series


def test_two_phase_detects_staged_weaning():
    t = np.linspace(0, 16, 50)
    y = MODELS["two_phase"].func(t, 5.4, 3.0, 0.45, 3.5, 6.5, 0.5) + np.random.default_rng(0).normal(0, 0.1, t.size)
    fits = [fit_model(m, t, y, draws=200) for m in ("logistic", "two_phase")]
    best = compare_fits(fits)
    two = fits[1]
    assert best == "two_phase"
    assert two.extra["supplementation_months"] == pytest.approx(6.5, abs=1.0)
    assert two.extra["intermediate_d15N"] == pytest.approx(5.4 + 3.0 * 0.55, abs=0.3)
    assert two.onset.estimate < two.midpoint.estimate < two.completion.estimate


def test_two_phase_not_preferred_for_simple_weaning():
    t, y = logistic_series(noise=0.1, seed=3)
    fits = [fit_model(m, t, y, draws=0) for m in ("logistic", "two_phase")]
    assert compare_fits(fits) == "logistic"


def test_seasonal_term_recovers_weaning_under_annual_cycle():
    t = np.linspace(0, 24, 72)
    rng = np.random.default_rng(4)
    y = MODELS["logistic"].func(t, 5.0, 3.0, 8.0, 0.8) + 0.6 * np.sin(2 * np.pi * t / 12) + rng.normal(0, 0.1, t.size)
    plain = fit_model("logistic", t, y, draws=0)
    seasonal = fit_model("logistic", t, y, draws=0, seasonal=True)
    assert seasonal.aicc < plain.aicc
    assert seasonal.extra["seasonal_amplitude_permil"] == pytest.approx(0.6, abs=0.15)
    assert abs(seasonal.midpoint.estimate - 8.0) < abs(plain.midpoint.estimate - 8.0) + 0.05


def test_seasonal_test_calibrated():
    rng = np.random.default_rng(1)
    t = np.linspace(0, 14, 40)
    p_noise = [seasonal_test(t, rng.normal(0, 0.3, t.size))[1] for _ in range(300)]
    assert 0.0 <= np.mean(np.array(p_noise) < 0.05) <= 0.1
    amp, p = seasonal_test(t, np.sin(2 * np.pi * t / 12) + rng.normal(0, 0.1, t.size))
    assert p < 1e-6 and amp == pytest.approx(1.0, abs=0.15)
    assert seasonal_test(t[:10], np.zeros(10)) is None  # spans < 0.75 cycle


def test_seasonality_check_flags_d13c_cycle():
    t = np.linspace(0, 14, 40)
    d13c = -22 + 0.8 * np.sin(2 * np.pi * t / 12)
    warnings, diag = seasonality_checks(t, np.zeros_like(t), None, d13c, 12)
    assert any("δ13C oscillates" in w for w in warnings) and diag["d13C_seasonal_p"] < 0.05


def test_bootstrap_intervals():
    t, y = logistic_series(noise=0.1, seed=6)
    fit = fit_model("logistic", t, y, uncertainty="bootstrap", bootstrap_draws=100)
    assert fit.completion.ci_low < fit.completion.estimate < fit.completion.ci_high


def test_age_error_is_shared_across_samples():
    """A shared shift widens the interval by about ±1.96·SD, not by per-point noise."""
    t, y = logistic_series(noise=0.02, seed=7)
    narrow = fit_model("logistic", t, y, draws=2000)
    wide = fit_model("logistic", t, y, draws=2000, age_uncertainty=1.0)
    width = lambda f: f.completion.ci_high - f.completion.ci_low
    assert width(wide) == pytest.approx(np.hypot(width(narrow), 2 * 1.96), rel=0.15)


def test_model_average_between_models():
    t, y = logistic_series(noise=0.1, seed=8)
    fits = [fit_model(m, t, y, draws=500) for m in ("logistic", "piecewise", "exponential")]
    compare_fits(fits)
    avg = model_average(fits)
    ests = [f.completion.estimate for f in fits]
    assert min(ests) <= avg["completion"].estimate <= max(ests)
    assert avg["completion"].ci_low < avg["completion"].estimate < avg["completion"].ci_high


def test_average_rows_and_window_weights(make_samples):
    opts = AnalysisOptions(models=["logistic", "piecewise"], monte_carlo_draws=200,
                           time_averaging=True, inner_dentine_weight=0.3)
    [res] = analyze(make_samples(), opts)
    rows = estimate_rows([res])
    assert {r.model for r in rows} == {"logistic", "piecewise", "average"}
    assert res.model_average["completion"].estimate is not None


def test_parallel_matches_sequential(make_samples):
    samples = sum((make_samples(f"S{i}", seed=i) for i in range(6)), [])
    opts = AnalysisOptions(models=["logistic"], monte_carlo_draws=50)
    seq = analyze(samples, opts, workers=1)
    par = analyze(samples, opts, workers=2)
    assert [r.fits[0].completion.estimate for r in seq] == pytest.approx(
        [r.fits[0].completion.estimate for r in par])
