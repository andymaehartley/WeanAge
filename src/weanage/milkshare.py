"""How much of a child's diet was breast milk at each dentine increment.

Each increment's collagen is a mix of what it would be on breast milk alone and on the adult diet
alone. On the adult diet it would match the adult females (the mothers' stand-in: WARN's baseline,
Tsutaya & Yoneda 2013); on milk alone it would sit one nursing enrichment E higher (δ15N) and
slightly higher in δ13C (about 1‰, Fuller et al. 2006). So, for a milk share p,

    expected δ15N = baseline + p·E,   variance = sd_baseline² + p²·sd_E² + sd_measurement²

and likewise for δ13C when a δ13C baseline is given. An optional third food (for example animal milk
or a millet pap), given as the collagen value it would produce on its own, needs δ13C as well, since
δ15N alone cannot tell three foods apart. The shares get a flat prior and the posterior is computed
on a grid over all mixes.

Dentine increments average weeks to months of growth and collagen lags the diet, so the curve is a
smoothed and slightly delayed picture of feeding (Beaumont et al. 2015; Tsutaya 2020).
"""

import numpy as np

from .config import species_priors

STEP = 0.01  # grid spacing of the shares


def share_grid(three):
    """Rows (milk, adult diet, other food) covering every mix in steps of STEP."""
    values = np.round(np.arange(0, 1 + STEP / 2, STEP), 10)
    if not three:
        return np.column_stack([values, 1 - values, np.zeros_like(values)])
    milk, other = np.meshgrid(values, values)
    keep = milk + other <= 1 + 1e-9
    milk, other = milk[keep], other[keep]
    return np.column_stack([milk, 1 - milk - other, other])


def weighted_quantiles(values, weights, qs=(0.025, 0.975)):
    order = np.argsort(values)
    cumulative = np.cumsum(weights[order])
    return [float(values[order][min(np.searchsorted(cumulative, q * cumulative[-1]), len(values) - 1)]) for q in qs]


def milk_share(points, baseline, species, options):
    """Posterior milk share at every used increment. points: [{age_months, d15N, d13C}]; baseline: AdultBaseline."""
    priors = species_priors(species)
    e15, e15_sd = (options.nursing_enrichment_d15N if options.nursing_enrichment_d15N is not None else priors["enrichment_mean"],
                   options.nursing_enrichment_d15N_sd if options.nursing_enrichment_d15N_sd is not None else priors["enrichment_sd"])
    e13, e13_sd = options.nursing_enrichment_d13C, options.nursing_enrichment_d13C_sd
    food = options.weaning_food
    has_c = baseline.d13C_mean is not None
    out = {"points": [], "enrichment_d15N": e15, "enrichment_d15N_sd": e15_sd, "warnings": [],
           "other_food": food.name if food else None}
    if food and not (has_c and food.d13C is not None):
        out["warnings"].append("The other weaning food is left out: it needs δ13C for both the food and the "
                               "adult females, because δ15N alone cannot tell three foods apart")
        food = None
    grid = share_grid(bool(food))
    milk, adult, other = grid.T
    measurement = (options.analytical_sd_permil or 0.2) ** 2  # 0.2‰ when the lab precision is not given
    for p in points:
        log_like = np.zeros(len(grid))
        isotopes = [("d15N", baseline.mean, baseline.sd, e15, e15_sd, food and food.d15N, food and food.d15N_sd)]
        if has_c and p["d13C"] is not None:
            isotopes.append(("d13C", baseline.d13C_mean, baseline.d13C_sd, e13, e13_sd, food and food.d13C, food and food.d13C_sd))
        for key, base, base_sd, enrich, enrich_sd, food_mean, food_sd in isotopes:
            expected = (milk + adult) * base + milk * enrich + other * (food_mean or 0.0)
            variance = (milk + adult) ** 2 * base_sd ** 2 + milk ** 2 * enrich_sd ** 2 + other ** 2 * (food_sd or 0.0) ** 2 + measurement
            log_like += -0.5 * (p[key] - expected) ** 2 / variance - 0.5 * np.log(variance)
        w = np.exp(log_like - log_like.max())
        w /= w.sum()
        low, high = weighted_quantiles(milk, w)
        row = {"age_months": p["age_months"], "milk": {"estimate": float(w @ milk), "ci_low": low, "ci_high": high},
               "isotopes": [i[0] for i in isotopes]}
        if food:
            olow, ohigh = weighted_quantiles(other, w)
            row["other"] = {"estimate": float(w @ other), "ci_low": olow, "ci_high": ohigh}
        out["points"].append(row)
    out["points"].sort(key=lambda r: r["age_months"])
    # Shares near 0 or 1 keep posterior means away from the bounds, so only the half-way point is dated.
    out["below_half_age"] = crossing([r["age_months"] for r in out["points"]], [r["milk"]["estimate"] for r in out["points"]], 0.5)
    if out["points"] and out["points"][0]["milk"]["estimate"] < 0.5:
        out["warnings"].append("The earliest increment already has under half milk: check the adult-female baseline "
                               "and the nursing enrichment, or the tooth began forming after weaning had started")
    return out


def crossing(ages, shares, level):
    """The first age at which the share falls below `level` and stays below it; None if it never does."""
    for i in range(len(shares)):
        if all(s < level for s in shares[i:]):
            if i == 0:
                return None
            a0, a1, s0, s1 = ages[i - 1], ages[i], shares[i - 1], shares[i]
            return float(a0 + (s0 - level) / (s0 - s1) * (a1 - a0)) if s0 != s1 else float(a1)
    return None
