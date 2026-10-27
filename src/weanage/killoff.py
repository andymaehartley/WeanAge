"""Kill-off (mortality) profiles from aged mandibles, after Payne (1973).

Each mandible's age is a range: a wear stage (Payne 1973, for sheep and goats) or an age range in
months. The animals of a group (site × species × period) are counted into age classes:

* A mandible whose range lies in one class counts 1 there.
* One spanning several classes is shared among them in proportion to the mandibles that fall in
  only one of those classes, as Payne (1973) shared mandibles between stages. When none do, it is
  shared in proportion to how much of each class its range covers.

From the counts come the share killed in each class and the survivorship: the share still alive at
the end of each class. Bootstrapping the mandibles gives 95% intervals. Three summaries match the
herding aims Payne (1973) modelled (see also Vigne & Helmer 2007): many deaths before 6 months
(milk, or culling of surplus young), deaths between 6 months and 3 years (meat at its best weight),
and many survivors past 4 years (wool, hair, breeding or traction). A profile seldom fits one aim,
and taphonomy removes young mandibles first, so these are prompts, not verdicts.

Groups are compared with a permutation test: how often does shuffling the mandibles between the
two groups give class shares at least as different as those observed?
"""

import numpy as np

from .ingest import check_rows, column_lookup, issue, match_columns
from .models import interval
from .schema import PAYNE_BOUNDS, KilloffOptions, KilloffSample

ALIASES = {
    "specimen_id": ["specimen", "specimenid", "mandible", "mandibleid", "sampleid"],
    "payne_stage": ["stage", "payne", "wearstage", "mws"],
    "age_min_months": ["agemin", "minage", "agefrom"],
    "age_max_months": ["agemax", "maxage", "ageto"],
}
LOOKUP = column_lookup(KilloffSample, ALIASES)
PAYNE_SPECIES = {"sheep", "goat", "sheep/goat", "ovis", "capra", "caprine", "ovicaprine", "ovis/capra"}


def ingest_killoff_dataframe(df):
    df, issues = match_columns(df, LOOKUP, KilloffSample)
    if df is None:
        return {"samples": [], "issues": issues, "groups": []}
    samples, row_issues = check_rows(KilloffSample, df.to_dict(orient="records"))
    other = sorted({s.species for s in samples if s.payne_stage and s.species not in PAYNE_SPECIES})
    if other:
        issues.append(issue(f"Payne stages are for sheep and goats; {', '.join(other)} mandibles need their own age "
                            "ranges (age_min_months, age_max_months)", severity="warning"))
    groups: dict[str, int] = {}
    for s in samples:
        groups[group_name(s)] = groups.get(group_name(s), 0) + 1
    return {"samples": samples, "issues": row_issues + issues,
            "groups": [{"group": g, "n": n} for g, n in groups.items()]}


def group_name(s):
    return " · ".join(str(k) for k in (s.site, s.species, s.period) if k)


def class_labels(bounds):
    if list(bounds) == PAYNE_BOUNDS:
        return list("ABCDEFGHI")
    return [f"{a:g}–{b:g} mo" for a, b in zip(bounds, bounds[1:])]


def overlaps(lo, hi, bounds):
    """How much of each class the age range lo–hi covers, as shares of the range."""
    edges = np.asarray(bounds, dtype=float)
    cover = np.clip(np.minimum(hi, edges[1:]) - np.maximum(lo, edges[:-1]), 0, None)
    return cover / cover.sum() if cover.sum() else cover


def allocate(ranges, bounds):
    """One row per mandible: its share in each class (each row sums to 1, or 0 if beyond the classes)."""
    cover = np.array([overlaps(lo, hi, bounds) for lo, hi in ranges])
    single = (cover > 0).sum(axis=1) == 1
    counts = (cover[single] > 0).sum(axis=0).astype(float)
    shares = cover.copy()
    for i in np.where(~single)[0]:
        weights = counts * (cover[i] > 0)
        shares[i] = weights / weights.sum() if weights.sum() else cover[i]
    return shares


def profile(shares):
    """Deaths per class (shares of the group) and survivorship at the end of each class."""
    total = shares.sum()
    deaths = shares.sum(axis=0) / total if total else np.zeros(shares.shape[1])
    return deaths, 1 - np.cumsum(deaths)


def indicators(deaths, survival, bounds):
    """Share killed before 6 months, between 6 and 36 months, and surviving past 48 months.

    Deaths are taken as spread evenly within each class.
    """
    edges = np.asarray(bounds, dtype=float)

    def killed(lo, hi):
        return float(deaths @ (np.clip(np.minimum(hi, edges[1:]) - np.maximum(lo, edges[:-1]), 0, None) / np.diff(edges)))

    alive = float(np.interp(48, edges, [1.0, *survival])) if edges[-1] >= 48 else None
    return {"killed_before_6": killed(0, 6), "killed_6_to_36": killed(6, 36), "surviving_past_48": alive}


def summarise(shares, bounds):
    deaths, survival = profile(shares)
    return deaths, survival, indicators(deaths, survival, bounds)


def with_interval(estimate, draws):
    low, high = interval(draws)
    return {"estimate": float(estimate), "ci_low": low, "ci_high": high}


def analyze_group(name, members, options, rng):
    bounds = options.class_bounds_months
    shares = allocate([(s.age_min_months, s.age_max_months) for s in members], bounds)
    beyond = int((shares.sum(axis=1) == 0).sum())
    kept = shares[shares.sum(axis=1) > 0]
    deaths, survival, marks = summarise(kept, bounds)
    boot = [summarise(kept[rng.integers(0, len(kept), len(kept))], bounds) for _ in range(options.bootstrap_draws)] if len(kept) else []
    labels = class_labels(bounds)
    classes = [{"label": labels[k], "from_months": bounds[k], "to_months": bounds[k + 1], "count": float(kept[:, k].sum()),
                "deaths": with_interval(deaths[k], [b[0][k] for b in boot]),
                "survival": with_interval(survival[k], [b[1][k] for b in boot])} for k in range(len(labels))]
    peak = int(np.argmax(kept.sum(axis=0))) if len(kept) else None
    warnings = []
    if len(kept) < 30:
        warnings.append(f"{len(kept)} mandibles: kill-off profiles are unstable below about 30")
    if beyond:
        warnings.append(f"{beyond} mandibles fall outside the age classes and are left out")
    first = members[0]
    return {"group": name, "site": first.site, "species": first.species, "period": first.period, "n": len(kept),
            "classes": classes, "peak_class": labels[peak] if peak is not None else None, "shares": kept,
            "indicators": {k: with_interval(v, [b[2][k] for b in boot if b[2][k] is not None]) if v is not None else None
                           for k, v in marks.items()},
            "warnings": warnings}


def compare(a, b, options, rng):
    """Permutation test of the difference between two groups' class shares (half the summed absolute difference)."""
    distance = lambda x, y: 0.5 * float(np.abs(profile(x)[0] - profile(y)[0]).sum())  # noqa: E731
    observed = distance(a, b)
    pooled = np.vstack([a, b])
    hits = 0
    for _ in range(options.permutations):
        order = rng.permutation(len(pooled))
        hits += distance(pooled[order[:len(a)]], pooled[order[len(a):]]) >= observed - 1e-12
    p = (hits + 1) / (options.permutations + 1) if options.permutations else None
    return {"difference": observed, "p_value": p}


def analyze_killoff(samples, options=None, progress=None):
    options = options or KilloffOptions()
    rng = np.random.default_rng(options.random_seed)
    groups: dict[str, list] = {}
    for s in samples:
        groups.setdefault(group_name(s), []).append(s)
    results = []
    for i, (name, members) in enumerate(groups.items()):
        results.append(analyze_group(name, members, options, rng))
        if progress:
            progress(i + 1, len(groups) + 1)
    comparisons = []
    for i, a in enumerate(results):
        for b in results[i + 1:]:
            if a["n"] and b["n"]:
                comparisons.append({"groups": [a["group"], b["group"]], **compare(a["shares"], b["shares"], options, rng)})
    for r in results:
        r.pop("shares")
    if progress:
        progress(len(groups) + 1, len(groups) + 1)
    return {"results": results, "comparisons": comparisons, "class_labels": class_labels(options.class_bounds_months)}
