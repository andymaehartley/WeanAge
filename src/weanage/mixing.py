"""What share of the diet came from each food group: a Bayesian mixing model for collagen.

Collagen δ13C, δ15N (and optionally δ34S) are a mix of the foods eaten, shifted by a collagen-diet
offset. With food groups s, diet shares p (summing to 1) and offsets Δ, each isotope's expected
value is Σ p_s·μ_s + Δ, with variance Σ p_s²·σ_s² + σ_Δ² + σ_measurement² (as in FRUITS,
Fernandes et al. 2014; and MixSIAR-style models, Stock et al. 2018). The shares get a Dirichlet
prior, flat by default; a food's `prior` weight above 1 favours it. The posterior is found by
drawing many diets from the prior and weighting each by how well it explains the sample
(importance sampling).

Concentration dependence (Phillips & Koch 2002). Foods differ in how much carbon, nitrogen or sulphur
they hold: meat supplies far more nitrogen than the same amount of cereal. When the element
concentrations of every food are given, each isotope is mixed by the share of the element each food
supplies, w_s = p_s·c_s / Σ p·c, instead of by the food shares p_s themselves.

Limits, as for every mixing model (Phillips et al. 2014): with more food groups than isotopes + 1,
the shares are not fixed by the data and the intervals stay wide; and the answer can be no better
than the food values and offsets, which are placeholders until measured locally.
"""

import math

import numpy as np

from . import config
from .ingest import check_rows, column_lookup, match_columns
from .schema import DietSource, MixingOptions, MixingSample

ALIASES = {
    "specimen_id": ["specimen", "specimenid", "sampleid", "individual", "labid"],
    "d13C": ["δ13c", "delta13c", "d13cvpdb"],
    "d15N": ["δ15n", "delta15n", "d15nair"],
    "d34S": ["δ34s", "delta34s", "d34svcdt"],
}
LOOKUP = column_lookup(MixingSample, ALIASES)
ISOTOPES = ["d13C", "d15N", "d34S"]
ELEMENT = {"d13C": "conc_C", "d15N": "conc_N", "d34S": "conc_S"}
MIN_ESS = 200  # fewer effective draws than this and the intervals are rough


def ingest_mixing_dataframe(df):
    df, issues = match_columns(df, LOOKUP, MixingSample)
    if df is None:
        return {"samples": [], "issues": issues}
    samples, row_issues = check_rows(MixingSample, df.to_dict(orient="records"))
    return {"samples": samples, "issues": row_issues + issues}


def with_defaults(options):
    """Fill in the sources and offsets left empty from data/diet_sources.json."""
    stored = config.diet_sources()
    filled = {key: stored[key] for key in MixingOptions.model_fields if key in stored and getattr(options, key) is None}
    if options.sources is None:
        filled["sources"] = [DietSource(**s) for s in stored["sources"]]
    return options.model_copy(update=filled)


def weighted_interval(values, weights):
    order = np.argsort(values)
    cumulative = np.cumsum(weights[order])
    return [float(values[order][np.searchsorted(cumulative, q * cumulative[-1])]) for q in (0.025, 0.975)]


def element_shares(shares, concentrations):
    """The share of an element each food supplies, from the food shares (rows) and its concentrations."""
    if concentrations is None:
        return shares
    supplied = shares * concentrations
    return supplied / supplied.sum(axis=1, keepdims=True)


def analyze_sample(sample, isotopes, shares, means, variances, offsets, names, concentrations):
    """Posterior diet shares of one sample, from the prior draws `shares` (draws × sources)."""
    log_like = np.zeros(len(shares))
    worst_z = np.zeros(len(shares))
    for iso in isotopes:
        observed = getattr(sample, iso)
        w = element_shares(shares, concentrations[iso])
        expected = w @ means[iso] + offsets[iso][0]
        variance = (w ** 2) @ variances[iso] + offsets[iso][1] ** 2
        z = (observed - expected) / np.sqrt(variance)
        log_like += -0.5 * z ** 2 - 0.5 * np.log(variance)
        worst_z = np.maximum(worst_z, np.abs(z))
    weights = np.exp(log_like - log_like.max())
    weights /= weights.sum()
    ess = float(1 / np.sum(weights ** 2))
    estimates = {}
    for k, name in enumerate(names):
        low, high = weighted_interval(shares[:, k], weights)
        estimates[name] = {"estimate": float(weights @ shares[:, k]), "ci_low": low, "ci_high": high}
    warnings = []
    if worst_z.min() > 2.5:
        warnings.append("No mix of the food groups explains this sample (it lies outside the mixing space): a food "
                        "group is missing, or the food values or offsets are wrong")
    if ess < MIN_ESS:
        warnings.append(f"Only {ess:.0f} effective draws: raise the number of draws for steadier intervals")
    return {"specimen_id": sample.specimen_id, "site": sample.site, "species": sample.species, "period": sample.period,
            "d13C": sample.d13C, "d15N": sample.d15N, "d34S": sample.d34S, "isotopes": isotopes,
            "shares": estimates, "effective_draws": ess, "warnings": warnings}


def analyze_mixing(samples, options=None, progress=None):
    options = with_defaults(options or MixingOptions())
    sources = options.sources
    names = [s.name for s in sources]
    rng = np.random.default_rng(options.random_seed)
    shares = rng.dirichlet([s.prior for s in sources], options.draws)
    measurement = options.measurement_sd_permil ** 2
    usable = [iso for iso in ISOTOPES if all(getattr(s, iso) is not None for s in sources)
              and getattr(options, f"offset_{iso}") is not None]
    means = {iso: np.array([getattr(s, iso) for s in sources]) for iso in usable}
    variances = {iso: np.array([getattr(s, f"{iso}_sd") or 0.0 for s in sources]) ** 2 for iso in usable}
    concentrations = {iso: np.array([getattr(s, ELEMENT[iso]) for s in sources])
                      if all(getattr(s, ELEMENT[iso]) is not None for s in sources) else None for iso in usable}
    offsets = {iso: (getattr(options, f"offset_{iso}"), math.sqrt((getattr(options, f"offset_{iso}_sd") or 0) ** 2 + measurement))
               for iso in usable}
    results = []
    for i, sample in enumerate(samples):
        isotopes = [iso for iso in usable if getattr(sample, iso) is not None]
        result = analyze_sample(sample, isotopes, shares, means, variances, offsets, names, concentrations)
        if len(sources) > len(isotopes) + 1:
            result["warnings"].append(f"{len(sources)} food groups but {len(isotopes)} isotopes: the shares are not "
                                      "fixed by the data alone, so read the intervals, not the means (Phillips et al. 2014)")
        results.append(result)
        if progress:
            progress(i + 1, len(samples))
    stored = config.diet_sources()
    placeholder = stored.get("placeholder", False) and sources == [DietSource(**s) for s in stored["sources"]]
    return {"results": results, "groups": group_means(results, names), "sources": [s.model_dump() for s in sources],
            "offsets": {iso: {"mean": getattr(options, f"offset_{iso}"), "sd": getattr(options, f"offset_{iso}_sd")}
                        for iso in ISOTOPES},
            "isotopes_used": usable, "placeholder": placeholder,
            "concentration_dependent": [iso for iso in usable if concentrations[iso] is not None],
            "prior": {s.name: s.prior for s in sources}}


def group_means(results, names):
    """Mean diet shares of each site × species × period, from its samples' posterior means."""
    groups: dict[tuple, list] = {}
    for r in results:
        groups.setdefault((r["site"], r["species"], r["period"]), []).append(r)
    return [{"group": " · ".join(str(k) for k in key if k), "n": len(members),
             "shares": {name: float(np.mean([m["shares"][name]["estimate"] for m in members])) for name in names},
             "d13C": float(np.mean([m["d13C"] for m in members])), "d15N": float(np.mean([m["d15N"] for m in members]))}
            for key, members in groups.items()]
