"""Accuracy metrics for validating estimates against known-age reference animals.

TBD-LAB: the reference dataset (modern animals with known weaning ages, plus
published archaeological series) is still to be compiled. Point
``lab_parameters.json -> reference_dataset`` at it once available and run
``validate()`` / the pytest suite against it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .schema import EstimateRow


def error_metrics(estimated, known) -> dict[str, float]:
    est = np.asarray(estimated, dtype=float)
    ref = np.asarray(known, dtype=float)
    mask = np.isfinite(est) & np.isfinite(ref)
    est, ref = est[mask], ref[mask]
    n = int(est.size)
    if n == 0:
        return {"n": 0, "bias": np.nan, "mae": np.nan, "rmse": np.nan, "pearson_r": np.nan}
    err = est - ref
    r = float(np.corrcoef(est, ref)[0, 1]) if n > 2 and np.std(est) > 0 and np.std(ref) > 0 else np.nan
    return {
        "n": n,
        "bias": float(err.mean()),
        "mae": float(np.abs(err).mean()),
        "rmse": float(np.sqrt((err**2).mean())),
        "pearson_r": r,
    }


def interval_coverage(ci_low, ci_high, known) -> float:
    lo, hi, ref = (np.asarray(a, dtype=float) for a in (ci_low, ci_high, known))
    mask = np.isfinite(lo) & np.isfinite(hi) & np.isfinite(ref)
    if not mask.any():
        return float("nan")
    return float(np.mean((ref[mask] >= lo[mask]) & (ref[mask] <= hi[mask])))


REFERENCES = {
    "known_weaning_age_months": "known age",
    "published_weaning_age_months": "published estimate",
}


def validate(rows: list[EstimateRow], milestone: str = "completion") -> pd.DataFrame:
    """Per-model accuracy against known ages and/or published estimates.

    Known-age reference animals test accuracy; published estimates (e.g. WEAN or
    visual readings of the same profiles) test agreement with existing methods.
    """
    cols = ["reference", "model", "n", "bias", "mae", "rmse", "pearson_r", "ci_coverage"]
    df = pd.DataFrame([r.model_dump() for r in rows])
    out = []
    for ref_col, ref_label in REFERENCES.items():
        if df.empty or ref_col not in df or df[ref_col].isna().all():
            continue
        for model, sub in df.groupby("model"):
            metrics = error_metrics(sub[milestone], sub[ref_col])
            if metrics["n"] == 0:
                continue
            metrics["ci_coverage"] = (
                interval_coverage(sub["completion_ci_low"], sub["completion_ci_high"], sub[ref_col])
                if milestone == "completion"
                else np.nan
            )
            out.append({"reference": ref_label, "model": model, **metrics})
    return pd.DataFrame(out, columns=cols)
