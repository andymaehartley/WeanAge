"""Life tables and mortality profiles from skeletal ages at death.

Each skeleton's age range is spread over the age classes in proportion to how much of each it covers
(an open-ended adult range runs to the last class boundary). For each site × period:

    Dx deaths, dx = Dx / N, lx survivors at the start of the class, qx = dx / lx,
    Lx = n·(lx + lx+n) / 2 years lived in the class, Tx = Σ Lx from x on, ex = Tx / lx

(Chamberlain 2006). The juvenility index D5–14 / D20+ (Bocquet-Appel & Masset 1977) compares child
with adult deaths and is less sensitive to the poor ageing of older adults. Intervals come from
resampling the skeletons.

A Siler (1979) hazard, h(t) = a1·e^(−b1·t) + a2 + a3·e^(b3·t), can also be fitted to the age ranges
by maximum likelihood, treating each range as interval-censored, which avoids splitting skeletons
over classes.

Missing infants. Infant burials are often lost or never excavated. With an expected share of deaths
in the first year (from a comparable population or a model life table), each group is also given a
corrected table in which infant deaths are added until they reach that share; nothing else changes.
The correction is only as good as the expected share.

A life table describes a population only if it was stationary (no growth, no migration) and the
dead are a fair sample of who died; selective mortality and hidden frailty (the osteological
paradox, Wood et al. 1992) and the frequent loss of infant burials (Bocquet-Appel & Masset 1982)
mean these figures describe the cemetery, not necessarily the living population.
"""

import math
import warnings

import numpy as np
from scipy.optimize import minimize

from .ingest import check_rows, column_lookup, records_with_labels
from .killoff import compare
from .models import interval
from .schema import LifeSample, LifeTableOptions

ALIASES = {
    "specimen_id": ["individual", "individualid", "skeleton", "burial", "sampleid"],
    "age_min_years": ["agemin", "minage", "agefrom", "agelower", "lowerage"],
    "age_max_years": ["agemax", "maxage", "ageto", "ageupper", "upperage"],
}
LOOKUP = column_lookup(LifeSample, ALIASES)


def ingest_life_dataframe(df):
    records, issues = records_with_labels(df, LOOKUP, LifeSample, "the life tables")
    if records is None:
        return {"samples": [], "issues": issues, "groups": []}
    samples, row_issues = check_rows(LifeSample, records)
    groups: dict[str, int] = {}
    for s in samples:
        groups[group_name(s)] = groups.get(group_name(s), 0) + 1
    columns = sorted({k for s in samples for k in s.labels})
    return {"samples": samples, "issues": row_issues + issues, "columns": columns,
            "groups": [{"group": g, "n": n} for g, n in groups.items()]}


def group_name(s, group_by=("site", "period")):
    """The group a skeleton belongs to: its values of the group_by columns (site, period, sex or a kept column)."""
    return " · ".join(str(v) for v in (getattr(s, k, None) or s.labels.get(k) for k in group_by) if v) or "all"


def spread(ranges, bounds):
    """One row per skeleton: its share in each class, by overlap."""
    edges = np.asarray(bounds, dtype=float)
    rows = []
    for lo, hi in ranges:
        hi = edges[-1] if hi is None else min(hi, edges[-1])
        lo = min(lo, edges[-1] - 1e-9)
        hi = max(hi, lo + 1e-9)
        cover = np.clip(np.minimum(hi, edges[1:]) - np.maximum(lo, edges[:-1]), 0, None)
        rows.append(cover / cover.sum())
    return np.array(rows)


def table(shares, bounds):
    edges = np.asarray(bounds, dtype=float)
    width = np.diff(edges)
    deaths = shares.sum(axis=0)
    d = deaths / deaths.sum()
    l_start = 1 - np.concatenate([[0], np.cumsum(d)[:-1]])
    l_end = l_start - d
    q = np.divide(d, l_start, out=np.ones_like(d), where=l_start > 1e-12)
    years = width * (l_start + l_end) / 2
    t = np.cumsum(years[::-1])[::-1]
    e = np.divide(t, l_start, out=np.zeros_like(t), where=l_start > 1e-12)

    def died(lo, hi):  # deaths between two ages, spread evenly within a class
        return float(d @ (np.clip(np.minimum(hi, edges[1:]) - np.maximum(lo, edges[:-1]), 0, None) / width))

    adults = died(20, edges[-1])
    summary = {"e0": float(e[0]), "juvenility_index": died(5, 15) / adults if adults > 0 else None,
               "infant_share": died(0, 1), "under5_share": died(0, 5)}
    return {"D": deaths, "d": d, "l": l_start, "q": q, "L": years, "T": t, "e": e}, summary


def survival(t, a1, b1, a2, a3, b3):
    t = np.asarray(t, dtype=float)
    return np.exp(-(a1 / b1) * (1 - np.exp(-b1 * t)) - a2 * t - (a3 / b3) * np.expm1(np.minimum(b3 * t, 50)))


# Plausible ranges of the Siler parameters (per year), so that sparse adult ages cannot push the fit to
# meaningless corners: infant hazard falling with a half-life of weeks to years, senescent hazard
# doubling every 3.5-70 years.
SILER_BOUNDS = [(1e-4, 5), (0.05, 10), (1e-5, 0.2), (1e-7, 0.5), (0.01, 0.2)]


def fit_siler(ranges, top):
    """Maximum-likelihood Siler hazard for interval-censored ages (years). Returns params or None."""
    lo = np.array([r[0] for r in ranges])
    hi = np.array([top * 1.2 if r[1] is None else r[1] for r in ranges])

    def nll(x):
        a1, b1, a2, a3, b3 = np.exp(x)
        p = survival(lo, a1, b1, a2, a3, b3) - survival(hi, a1, b1, a2, a3, b3)
        return -float(np.sum(np.log(np.clip(p, 1e-300, None))))

    best = None
    log_bounds = [(math.log(a), math.log(b)) for a, b in SILER_BOUNDS]
    for start in ([0.3, 1.0, 0.005, 0.0005, 0.08], [0.1, 0.5, 0.01, 0.001, 0.06], [0.6, 2.0, 0.002, 0.0002, 0.1]):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = minimize(nll, np.log(start), method="L-BFGS-B", bounds=log_bounds)
        if np.isfinite(res.fun) and (best is None or res.fun < best.fun):
            best = res
    return None if best is None else np.exp(best.x)


def siler_summary(params, top):
    grid = np.linspace(0, top, 401)
    s = survival(grid, *params)
    e0 = float(np.sum((s[1:] + s[:-1]) / 2 * np.diff(grid)))  # area under the survival curve
    hazard = params[0] * np.exp(-params[1] * grid) + params[2] + params[3] * np.exp(np.minimum(params[4] * grid, 50))
    return {"params": dict(zip(["a1", "b1", "a2", "a3", "b3"], (float(v) for v in params))), "e0": e0,
            "curve_age": [round(float(v), 3) for v in grid], "curve_survival": [round(float(v), 5) for v in s],
            "curve_hazard": [round(float(v), 6) for v in hazard]}


def infant_correction(shares, bounds, target):
    """Add infant deaths (spread over the first year) until they are `target` of all deaths."""
    infant = np.asarray(spread([(0, 1)], bounds))[0]
    have = float(shares.sum(axis=0) @ infant)  # deaths under 1 already in the table
    others = shares.sum() - have
    needed = max(target * others / (1 - target) - have, 0.0)
    columns, summary = table(np.vstack([shares, infant * needed]), bounds)
    rows = [{"from_years": bounds[k], "to_years": bounds[k + 1], **{col: float(v[k]) for col, v in columns.items()}}
            for k in range(len(bounds) - 1)]
    return {"added_infants": needed, "target_share": target, "summary": summary, "rows": rows}


def analyze_group(name, members, options, rng):
    bounds = options.class_bounds_years
    ranges = [(s.age_min_years, s.age_max_years) for s in members]
    shares = spread(ranges, bounds)
    columns, summary = table(shares, bounds)
    boot = [table(shares[rng.integers(0, len(shares), len(shares))], bounds) for _ in range(options.bootstrap_draws)]
    with_ci = {key: {"estimate": value, "ci_low": None, "ci_high": None} for key, value in summary.items()}
    for key in summary:
        if summary[key] is None:
            with_ci[key] = None
            continue
        low, high = interval([b[1][key] for b in boot if b[1][key] is not None])
        with_ci[key].update(ci_low=low, ci_high=high)
    rows = [{"from_years": bounds[k], "to_years": bounds[k + 1], **{col: float(v[k]) for col, v in columns.items()}}
            for k in range(len(bounds) - 1)]
    out = {"group": name, "site": members[0].site, "period": members[0].period, "n": len(members), "rows": rows,
           "summary": with_ci, "siler": None, "warnings": [], "shares": shares}
    if len(members) < 30:
        out["warnings"].append(f"{len(members)} skeletons: life tables are unstable below about 30")
    if summary["infant_share"] < 0.1:
        out["warnings"].append(f"Infants are {summary['infant_share']:.0%} of the dead; pre-modern populations usually "
                               "lost far more in the first year, so infant burials are probably missing (Bocquet-Appel & Masset 1982)")
    if options.expected_infant_share:
        out["corrected"] = infant_correction(shares, bounds, options.expected_infant_share)
    if options.siler and len(members) >= 20:
        params = fit_siler(ranges, bounds[-1])
        if params is not None:
            out["siler"] = siler_summary(params, bounds[-1])
    return out


def analyze_lifetable(samples, options=None, progress=None):
    options = options or LifeTableOptions()
    rng = np.random.default_rng(options.random_seed)
    groups: dict[str, list] = {}
    for s in samples:
        groups.setdefault(group_name(s, options.group_by), []).append(s)
    results = []
    for i, (name, members) in enumerate(groups.items()):
        results.append(analyze_group(name, members, options, rng))
        if progress:
            progress(i + 1, len(groups) + 1)
    comparisons = [{"groups": [a["group"], b["group"]], **compare(a["shares"], b["shares"], options, rng)}
                   for i, a in enumerate(results) for b in results[i + 1:]]
    for r in results:
        r.pop("shares")
    return {"results": results, "comparisons": comparisons, "bounds": options.class_bounds_years,
            "warnings": ["A life table describes a living population only if it was stationary and the dead are a fair "
                         "sample of those who died (the osteological paradox, Wood et al. 1992)"]}
