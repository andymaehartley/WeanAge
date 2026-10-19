import pytest

from weanage.aggregate import aggregate, model_disagreement
from weanage.analysis import analyze, estimate_rows
from weanage.schema import AnalysisOptions
from weanage.validation import interval_coverage, validate


@pytest.fixture
def opts():
    return AnalysisOptions(monte_carlo_draws=200)


def test_end_to_end_specimen(make_samples, opts):
    [res] = analyze(make_samples(), opts)
    assert res.growth_placeholder
    assert any("PLACEHOLDER" in w for w in res.warnings)
    assert {f.model for f in res.fits} == {"logistic", "piecewise", "exponential"}
    assert res.best_model is not None
    logistic = next(f for f in res.fits if f.model == "logistic")
    assert logistic.completion.estimate == pytest.approx(7.0 + 0.8 * 2.944, abs=0.7)


def test_failed_qc_sample_excluded(make_samples, opts):
    samples = make_samples()
    samples[5] = samples[5].model_copy(update={"cn_ratio": 4.2, "d15N": 15.0})
    [res] = analyze(samples, opts)
    assert sum(not p.used_in_fit for p in res.points) == 1


def test_missing_growth_table_and_override(make_samples, opts):
    samples = make_samples(species="sheep")
    [res] = analyze(samples, opts)
    assert not res.fits and "No growth table" in res.warnings[0]
    opts = AnalysisOptions(
        monte_carlo_draws=200,
        growth_overrides={"sheep:M2": {"initiation_age_months": 1, "extension_rate_mm_per_month": 3}},
    )
    [res] = analyze(samples, opts)
    assert res.fits and not res.growth_placeholder


def test_aggregation_by_site(make_samples, opts):
    samples = (
        make_samples("A1", site="A", t_mid=8, seed=1) + make_samples("A2", site="A", t_mid=8.5, seed=2)
        + make_samples("B1", site="B", t_mid=4.5, seed=3) + make_samples("B2", site="B", t_mid=5, seed=4)
    )
    rows = estimate_rows(analyze(samples, opts))
    summary = aggregate(rows).set_index("site")
    assert summary.loc["A", "n"] == 2
    assert summary.loc["A", "mean"] > summary.loc["B", "mean"] + 2
    per_model = aggregate(rows, model="logistic", group_by=["site"])
    assert set(per_model["model"]) == {"logistic"}
    dis = model_disagreement(rows)
    assert len(dis) == 4 and (dis["range"] >= 0).all()


def test_validation_with_known_ages(make_samples, opts):
    samples = [
        s.model_copy(update={"known_weaning_age_months": 9.36}) for s in make_samples(noise=0.05)
    ]
    table = validate(estimate_rows(analyze(samples, opts)))
    logistic = table.set_index("model").loc["logistic"]
    assert logistic["n"] == 1 and logistic["mae"] < 1.0
    assert interval_coverage([1], [3], [2]) == 1.0
