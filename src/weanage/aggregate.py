"""Site- and species-level summaries of weaning-age estimates."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .schema import EstimateRow

DEFAULT_GROUP = ("site", "species")


def estimates_frame(rows: list[EstimateRow]) -> pd.DataFrame:
    return pd.DataFrame([r.model_dump() for r in rows])


def _t_ci(values: pd.Series) -> pd.Series:
    v = values.dropna().to_numpy(dtype=float)
    n = v.size
    mean = float(v.mean()) if n else np.nan
    sd = float(v.std(ddof=1)) if n > 1 else np.nan
    if n > 1:
        half = stats.t.ppf(0.975, n - 1) * sd / np.sqrt(n)
        lo, hi = mean - half, mean + half
    else:
        lo = hi = np.nan
    return pd.Series(
        {
            "n": n,
            "mean": mean,
            "sd": sd,
            "median": float(np.median(v)) if n else np.nan,
            "min": float(v.min()) if n else np.nan,
            "max": float(v.max()) if n else np.nan,
            "ci95_low": lo,
            "ci95_high": hi,
        }
    )


def aggregate(
    rows: list[EstimateRow],
    *,
    group_by: tuple[str, ...] | list[str] = DEFAULT_GROUP,
    milestone: str = "completion",
    model: str | None = None,
) -> pd.DataFrame:
    """Average one milestone per group.

    ``model=None`` uses each specimen's best-supported (lowest AICc) model; pass a
    model name to summarise that model for every specimen instead.
    """
    df = estimates_frame(rows)
    if df.empty:
        return pd.DataFrame(columns=[*group_by, "model", "n", "mean", "sd"])
    df = df[df["is_best"]] if model is None else df[df["model"] == model]
    group_by = [g for g in group_by if g in df.columns]
    if df.empty:
        return pd.DataFrame(columns=[*group_by, "model", "n", "mean", "sd"])
    df = df.assign(period=df["period"].fillna("—")) if "period" in group_by else df
    out = (
        df.groupby(group_by, dropna=False)[milestone]
        .apply(_t_ci)
        .unstack()
        .reset_index()
    )
    out.insert(len(group_by), "model", model or "best (AICc)")
    out["n"] = out["n"].astype(int)
    return out


def model_disagreement(rows: list[EstimateRow], milestone: str = "completion") -> pd.DataFrame:
    """Per-specimen spread of a milestone across models (thesis question 1)."""
    df = estimates_frame(rows)
    if df.empty:
        return pd.DataFrame(columns=["specimen_id", "site", "species", "n_models", "range"])
    wide = df.pivot_table(
        index=["specimen_id", "site", "species"], columns="model", values=milestone
    )
    models = list(wide.columns)
    wide["n_models"] = wide[models].notna().sum(axis=1)
    wide["min"] = wide[models].min(axis=1)
    wide["max"] = wide[models].max(axis=1)
    wide["range"] = wide["max"] - wide["min"]
    wide.columns.name = None
    return wide.reset_index()


def frame_to_records(df: pd.DataFrame) -> list[dict]:
    """JSON-safe records (NaN -> None, numpy scalars -> Python)."""
    clean = df.astype(object).where(pd.notna(df), None)
    return [
        {k: (v.item() if isinstance(v, np.generic) else v) for k, v in rec.items()}
        for rec in clean.to_dict(orient="records")
    ]
