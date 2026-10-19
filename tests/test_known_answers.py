"""Known answers: the bundled synthetic example must keep giving the same results.

If a change to the code moves any of these numbers, this test fails, so the change
is noticed and can be justified (and these values updated on purpose).
Values: best model, logistic completion age (months), logistic δ15N drop (‰).
"""

import pytest

from weanage.analysis import analyze
from weanage.config import DATA_DIR, default_options
from weanage.ingest import ingest_csv

EXPECTED = {
    "SYN-C01": ("logistic", 9.31, 2.84),
    "SYN-C02": ("logistic", 11.15, 2.95),
    "SYN-C03": ("two_phase", 8.73, 3.22),
    "SYN-C04": ("logistic", 6.37, 2.50),
    "SYN-C05": ("piecewise", 5.19, 2.53),
    "SYN-C06": ("logistic", 6.86, 2.76),
    "SYN-C07": ("two_phase", 38.09, 9.86),  # two-phase truth: the logistic curve fits it badly (and is flagged)
    "SYN-IND1": ("logistic", 7.95, 2.71),
    "SYN-P01": ("logistic", 3.55, 2.39),
    "SYN-P02": ("logistic", 2.81, 2.19),
    "SYN-H01": ("piecewise", 9.08, 2.69),
}


@pytest.fixture(scope="module")
def results():
    options = default_options().model_copy(update={"monte_carlo_draws": 200})
    samples = ingest_csv(DATA_DIR / "examples" / "synthetic_example.csv")["samples"]
    return {r["specimen_id"]: r for r in analyze(samples, options, workers=1)}


@pytest.mark.parametrize("specimen", EXPECTED)
def test_example_results_are_unchanged(results, specimen):
    best, completion, drop = EXPECTED[specimen]
    result = results[specimen]
    logistic = next(f for f in result["fits"] if f["model"] == "logistic")
    assert result["best_model"] == best
    assert logistic["completion"]["estimate"] == pytest.approx(completion, abs=0.02)
    assert logistic["drop_permil"] == pytest.approx(drop, abs=0.02)


def test_implausible_drop_is_flagged(results):
    logistic = next(f for f in results["SYN-C07"]["fits"] if f["model"] == "logistic")
    assert any("food-chain step" in w for w in logistic["warnings"])
