"""Summaries of the estimate rows: group averages, model disagreement and accuracy."""

import numpy as np
import pandas as pd
from scipy import stats


def to_frame(rows):
    return pd.DataFrame(list(rows))


def describe(values):
    """n, mean, SD, median, range and the 95 % confidence interval of the mean."""
    v = values.dropna().to_numpy(dtype=float)
    n = len(v)
    out = {"n": n, "mean": np.nan, "sd": np.nan, "median": np.nan, "min": np.nan, "max": np.nan,
           "ci95_low": np.nan, "ci95_high": np.nan}
    if n:
        out.update(mean=v.mean(), median=np.median(v), min=v.min(), max=v.max())
    if n > 1:
        sd = v.std(ddof=1)
        half = stats.t.ppf(0.975, n - 1) * sd / np.sqrt(n)
        out.update(sd=sd, ci95_low=v.mean() - half, ci95_high=v.mean() + half)
    return out


def pick(df, model):
    """model=None: each specimen's best model; otherwise the named model (or "average")."""
    return df[df["is_best"]] if model is None else df[df["model"] == model]


def aggregate(rows, group_by=("site", "species"), milestone="completion", model=None):
    df = to_frame(rows)
    group_by = list(group_by)
    if df.empty or pick(df, model).empty:
        return pd.DataFrame(columns=[*group_by, "model", "n", "mean", "sd"])
    df = pick(df, model).copy()
    df[group_by] = df[group_by].fillna("—")
    table = []
    for keys, sub in df.groupby(group_by):
        keys = keys if isinstance(keys, tuple) else (keys,)
        table.append({**dict(zip(group_by, keys)), "model": model or "best (AICc)", **describe(sub[milestone])})
    return pd.DataFrame(table)


def model_disagreement(rows, milestone="completion"):
    """How far apart the models' estimates are for each specimen (thesis question 1)."""
    df = to_frame(rows)
    if df.empty or (df["model"] != "average").sum() == 0:
        return pd.DataFrame(columns=["specimen_id", "site", "species", "n_models", "range"])
    df = df[df["model"] != "average"]
    wide = df.pivot_table(index=["specimen_id", "site", "species"], columns="model", values=milestone)
    models = list(wide.columns)
    wide["n_models"] = wide[models].notna().sum(axis=1)
    wide["min"], wide["max"] = wide[models].min(axis=1), wide[models].max(axis=1)
    wide["range"] = wide["max"] - wide["min"]
    wide.columns.name = None
    return wide.reset_index()


def error_metrics(estimated, known):
    """Bias (average signed error), MAE, RMSE and correlation between estimates and true values."""
    est, ref = np.asarray(estimated, dtype=float), np.asarray(known, dtype=float)
    ok = np.isfinite(est) & np.isfinite(ref)
    est, ref = est[ok], ref[ok]
    if len(est) == 0:
        return {"n": 0, "bias": np.nan, "mae": np.nan, "rmse": np.nan, "pearson_r": np.nan}
    err = est - ref
    r = np.corrcoef(est, ref)[0, 1] if len(est) > 2 and est.std() > 0 and ref.std() > 0 else np.nan
    return {"n": len(est), "bias": err.mean(), "mae": np.abs(err).mean(), "rmse": np.sqrt((err ** 2).mean()),
            "pearson_r": r}


def interval_coverage(low, high, known):
    """Share of the 95 % intervals that contain the true value."""
    low, high, ref = (np.asarray(a, dtype=float) for a in (low, high, known))
    ok = np.isfinite(low) & np.isfinite(high) & np.isfinite(ref)
    if not ok.any():
        return np.nan
    return float(np.mean((ref[ok] >= low[ok]) & (ref[ok] <= high[ok])))


REFERENCES = {"known_weaning_age_months": "known age", "published_weaning_age_months": "published estimate"}


def validate(rows, milestone="completion"):
    """Accuracy of each model against known ages and/or published estimates."""
    df = to_frame(rows)
    table = []
    for column, label in REFERENCES.items():
        if df.empty or column not in df or df[column].isna().all():
            continue
        for model, sub in df.groupby("model"):
            metrics = error_metrics(sub[milestone], sub[column])
            if metrics["n"]:
                coverage = np.nan
                if milestone == "completion":
                    coverage = interval_coverage(sub["completion_ci_low"], sub["completion_ci_high"], sub[column])
                table.append({"reference": label, "model": model, **metrics, "ci_coverage": coverage})
    return pd.DataFrame(table, columns=["reference", "model", "n", "bias", "mae", "rmse", "pearson_r", "ci_coverage"])


def plain(value):
    """numpy numbers -> normal Python numbers, and NaN -> None, so the value can go into JSON."""
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and np.isnan(value):
        return None
    return value


def records(df):
    return [{key: plain(value) for key, value in row.items()} for row in df.to_dict(orient="records")]
