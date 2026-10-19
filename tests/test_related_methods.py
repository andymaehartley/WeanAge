"""Features derived from WEAN, MDSS and WARN."""

import math

import numpy as np
import pytest

from weanage.analysis import analyze, estimate_rows, rising_profile_warning
from weanage.ingest import canonical_column
from weanage.models import MODELS, fit_model
from weanage.schema import AnalysisOptions, IsotopeSample
from weanage.validation import validate


def _samples(values, positions, **extra):
    return [
        IsotopeSample(specimen_id="X", site="S", species="cattle", tooth="M2",
                      position_mm=float(p), d15N=float(v), cn_ratio=3.2, **extra)
        for p, v in zip(positions, values)
    ]


# ── WEAN: elbow method ─────────────────────────────────────────────
def test_elbow_finds_end_of_decline():
    t = np.linspace(0, 20, 60)
    y = MODELS["piecewise"].func(t, 5.0, 3.0, 4.0, 6.0) + np.random.default_rng(5).normal(0, 0.05, t.size)
    fit = fit_model("elbow", t, y, draws=200)
    assert fit.converged
    assert fit.completion.estimate == pytest.approx(10.0, abs=1.5)
    assert fit.completion.ci_low < fit.completion.estimate < fit.completion.ci_high
    assert fit.midpoint is None


def test_elbow_needs_a_decline():
    t = np.linspace(0, 10, 20)
    fit = fit_model("elbow", t, 5 + 0.3 * t, draws=0)
    assert not fit.converged and "peaks at the end" in fit.message


def test_rising_profile_flagged():
    t = np.linspace(0, 12, 30)
    assert rising_profile_warning(t, 5 + 0.2 * t) is not None
    assert rising_profile_warning(t, 8 - 0.2 * t) is None


# ── MDSS: time averaging ───────────────────────────────────────────
def test_time_averaging_removes_lag_bias():
    """Sections that average later dentine shift the apparent curve; modelling it fixes that."""
    rate, offset, t_mid, scale = 3.0, 4.0, 7.0, 0.4  # placeholder cattle M2: age = 1 + pos/3
    pos = np.arange(0.5, 40, 1.0)
    sub = np.linspace(0, 1, 15)
    truth = lambda a: 5 + 3 / (1 + np.exp((a - t_mid) / scale))
    obs = [truth(1 + ((p - 0.5) + sub * (1 + offset)) / rate).mean() for p in pos]
    samples = _samples(obs, pos)
    plain = analyze(samples, AnalysisOptions(models=["logistic"], monte_carlo_draws=0))[0]
    avg = analyze(samples, AnalysisOptions(models=["logistic"], monte_carlo_draws=0,
                                           time_averaging=True, growth_layer_offset_mm=offset))[0]
    err_plain = abs(plain.fits[0].midpoint.estimate - t_mid)
    err_avg = abs(avg.fits[0].midpoint.estimate - t_mid)
    assert err_avg < 0.15 < err_plain
    assert avg.points[0].age_min < avg.points[0].age_months < avg.points[0].age_max


# ── WARN: adult-female baseline ────────────────────────────────────
def test_adult_baseline_enrichment_and_constraint(make_samples):
    samples = make_samples(post=5.5, drop=3.0)
    opts = AnalysisOptions(models=["logistic"], monte_carlo_draws=0,
                           adult_baselines={"cattle": {"mean": 5.0, "sd": 0.1}},
                           constrain_adult_plateau=True)
    [res] = analyze(samples, opts)
    fit = res.fits[0]
    assert fit.adult_d15N <= 5.2 + 1e-6  # held within mean ± 2 SD
    assert fit.enrichment_permil == pytest.approx(fit.nursing_d15N - 5.0)
    assert res.adult_baseline.mean == 5.0


def test_site_specific_baseline_wins():
    opts = AnalysisOptions(adult_baselines={"cattle": {"mean": 5}, "Site A:cattle": {"mean": 6}})
    assert opts.baseline_for("site a", "cattle").mean == 6
    assert opts.baseline_for("Site B", "cattle").mean == 5


# ── validation against published estimates (WEAN's re-estimation test) ──
def test_validation_against_published_estimates(make_samples):
    samples = [s.model_copy(update={"published_weaning_age_months": 9.0}) for s in make_samples()]
    table = validate(estimate_rows(analyze(samples, AnalysisOptions(monte_carlo_draws=0))))
    assert set(table["reference"]) == {"published estimate"}
    assert set(table["model"]) == {"logistic", "piecewise", "exponential", "elbow"}


def test_new_column_aliases():
    assert canonical_column("Published weaning age (months)") == "published_weaning_age_months"
    assert canonical_column("Increment width (mm)") == "increment_width_mm"
