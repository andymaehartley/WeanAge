"""Kill-off profiles from aged mandibles."""

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from weanage import config
from weanage.killoff import allocate, analyze_killoff, ingest_killoff_dataframe
from weanage.schema import PAYNE_BOUNDS, KilloffSample

EXAMPLE = config.DATA_DIR / "examples" / "synthetic_killoff_example.csv"


def test_stages_and_ranges():
    assert (KilloffSample(specimen_id="M", site="S", species="sheep", payne_stage="d-e").age_min_months,
            KilloffSample(specimen_id="M", site="S", species="sheep", payne_stage="D/E").age_max_months) == (12, 36)
    with pytest.raises(ValidationError):
        KilloffSample(specimen_id="M", site="S", species="sheep")  # no age at all
    with pytest.raises(ValidationError):
        KilloffSample(specimen_id="M", site="S", species="sheep", payne_stage="B/D/F")


def test_ambiguous_mandibles_follow_the_unambiguous_ones():
    # Three mandibles in C only, one in D only, one C/D: shared 3:1 (Payne 1973).
    ranges = [(6, 12)] * 3 + [(12, 24), (6, 24)]
    shares = allocate(ranges, PAYNE_BOUNDS)
    assert np.allclose(shares[-1][2:4], [0.75, 0.25]) and np.allclose(shares.sum(axis=1), 1)
    # With nothing to follow, by how much of each class the range covers.
    alone = allocate([(10, 14)], PAYNE_BOUNDS)[0]
    assert np.allclose(alone[2:4], [0.5, 0.5])


def test_example_profiles_differ():
    report = ingest_killoff_dataframe(pd.read_csv(EXAMPLE))
    assert not report["issues"] and len(report["samples"]) == 120
    out = analyze_killoff(report["samples"])
    a, b = out["results"]
    assert a["peak_class"] in "AB" and b["peak_class"] in "CD"
    assert a["indicators"]["killed_before_6"]["estimate"] > 0.4 > b["indicators"]["killed_before_6"]["estimate"]
    assert b["indicators"]["killed_6_to_36"]["ci_low"] > a["indicators"]["killed_6_to_36"]["ci_high"]
    assert all(abs(sum(c["deaths"]["estimate"] for c in g["classes"]) - 1) < 1e-9 for g in out["results"])
    assert out["comparisons"][0]["p_value"] < 0.01


def test_same_herd_is_not_called_different():
    rng = np.random.default_rng(1)
    stages = rng.choice(list("ABCDEFGHI"), size=80)
    samples = [KilloffSample(specimen_id=str(i), site="X" if i % 2 else "Y", species="sheep", payne_stage=s)
               for i, s in enumerate(stages)]
    (comparison,) = analyze_killoff(samples)["comparisons"]
    assert comparison["p_value"] > 0.05


def test_payne_stages_for_cattle_warn():
    df = pd.DataFrame({"specimen_id": ["1"], "site": ["S"], "species": ["cattle"], "stage": ["C"]})
    assert "sheep and goats" in ingest_killoff_dataframe(df)["issues"][0]["message"]
