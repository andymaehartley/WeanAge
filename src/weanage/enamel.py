"""Season of birth and rumen development from sequential enamel δ18O and δ13C, for cattle.

A molar's enamel forms from the cusp tip down to the enamel-root junction (ERJ) over several
months, so samples taken up the crown are a time series: the further from the ERJ, the earlier
in life the enamel formed. Each sample's position is its distance from the ERJ.

* Season (δ18O). Enamel δ18O follows the δ18O of drinking water, which is higher in summer.
  The series is fitted with a cosine, δ18O(x) = M + A·cos(2π(x − x0)/X) (Balasse et al. 2012):
  X is the crown length formed in a year and x0 the position of the δ18O maximum. Between
  animals with the same tooth, differences in x0/X reflect differences in season of birth
  (Balasse et al. 2012; for cattle, Towers et al. 2014; Balasse et al. 2021).
* Rumen development (δ13C). In a suckling calf the rumen is not yet working. As it develops,
  fermentation enriches the carbon that reaches the enamel in 13C (Passey et al. 2005), so first
  molar enamel δ13C rises (Towers et al. 2014). The δ13C series is fitted with a seasonal wave of
  the same period X plus a rising step, and the step is kept only if it improves the fit (AICc).

Enamel takes months to mineralise at any one position (Zazzo et al. 2005), so both signals are
smoothed: amplitudes are lower and transitions more gradual than in life. Positions are not
converted into ages, because enamel formation tables for cattle are not yet available.
"""

import math
import warnings

import numpy as np
from scipy.optimize import curve_fit

from .ingest import check_rows, column_lookup, issue, match_columns
from .models import aicc, interval
from .schema import EnamelOptions, EnamelSample

ALIASES = {
    "specimen_id": ["specimen", "specimenid", "sampleid", "toothid"],
    "tooth": ["element"],
    "erj_distance_mm": ["erj", "erjdistance", "distancefromerj", "distancefromerjmm", "heightaboveerj", "herj"],
    "d18O": ["δ18o", "delta18o", "d18ovpdb", "d18ocarbonate"],
    "sample_index": ["sampleno", "sample"],
}
LOOKUP = column_lookup(EnamelSample, ALIASES)
MIN_SAMPLES = 6
MIN_CYCLE_SHARE = 0.75  # the samples should cover at least 3/4 of a year's crown growth
TOOTH_NOTES = {
    "m3": "M3 forms after weaning, so no rumen development is expected in it",
}


def ingest_enamel_dataframe(df):
    """Check a table of enamel samples; returns samples, problems and a summary per tooth."""
    df, issues = match_columns(df, LOOKUP, EnamelSample)
    if df is None:
        return {"samples": [], "issues": issues, "teeth": []}
    samples, row_issues = check_rows(EnamelSample, df.to_dict(orient="records"))
    teeth = summarise(samples)
    for t in teeth:
        if t["n_samples"] < MIN_SAMPLES:
            issues.append(issue(f"Tooth {t['specimen_id']} has only {t['n_samples']} samples; at least "
                                f"{MIN_SAMPLES} are needed", severity="warning"))
        if t["species"] != "cattle":
            issues.append(issue(f"Tooth {t['specimen_id']} is {t['species']}: the method is set up for cattle",
                                severity="warning"))
    return {"samples": samples, "issues": row_issues + issues, "teeth": teeth}


def by_tooth(samples):
    teeth: dict[str, list] = {}
    for s in samples:
        teeth.setdefault(s.specimen_id, []).append(s)
    return teeth


def summarise(samples):
    out = []
    for sid, rows in by_tooth(samples).items():
        x = [r.erj_distance_mm for r in rows]
        out.append({"specimen_id": sid, "site": rows[0].site, "species": rows[0].species, "tooth": rows[0].tooth,
                    "period": rows[0].period, "n_samples": len(rows),
                    "n_d18O": sum(r.d18O is not None for r in rows), "n_d13C": sum(r.d13C is not None for r in rows),
                    "span_mm": round(max(x) - min(x), 2)})
    return out


# Shapes fitted along the crown (x = distance from the ERJ, mm)
def cosine(x, mean, amplitude, period, x0):
    return mean + amplitude * np.cos(2 * np.pi * (np.asarray(x, dtype=float) - x0) / period)


def rumen_step(x, middle, width):
    """0 high on the crown (before the rumen works), 1 towards the ERJ (after)."""
    z = np.clip((np.asarray(x, dtype=float) - middle) / width, -60, 60)
    return 1 / (1 + np.exp(z))


def best_fit(f, x, y, guesses, bounds):
    """Least-squares fit from several starting points; returns (params, covariance, sse) or None."""
    best = None
    low, high = np.array(bounds[0]), np.array(bounds[1])
    for guess in guesses:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                p, cov = curve_fit(f, x, y, p0=np.clip(guess, low + 1e-9, high - 1e-9), bounds=bounds, maxfev=20000)
        except (RuntimeError, ValueError):
            continue
        sse = float(np.sum((y - f(x, *p)) ** 2))
        if best is None or sse < best[2]:
            best = (p, cov, sse)
    return best


def circular_interval(draws, estimate):
    """95% interval of a share of the year (0–1), measured around the estimate so it can cross 0/1."""
    offset = (np.asarray(draws) - estimate + 0.5) % 1 - 0.5
    low, high = interval(offset)
    return (None, None) if low is None else ((estimate + low) % 1, (estimate + high) % 1)


def fit_season(x, y, options, rng):
    """Cosine fit of δ18O along the crown. Returns the result, with no birth index when there is no clear cycle."""
    out = {"n": len(x), "birth_index": None, "message": "", "warnings": [], "curve_x": [], "curve_y": []}
    if len(x) < MIN_SAMPLES:
        out["message"] = f"Only {len(x)} δ18O values; at least {MIN_SAMPLES} are needed"
        return out
    span = float(np.ptp(x))
    lo_p, hi_p = options.period_min_mm, options.period_max_mm
    amp0 = max(float(np.ptp(y)) / 2, 0.1)
    guesses = [[float(y.mean()), amp0, period, x0] for period in np.linspace(lo_p, hi_p, 4)
               for x0 in np.linspace(x.min(), x.min() + period, 6, endpoint=False)]
    bounds = ([y.min() - 5, 0, lo_p, x.min() - hi_p], [y.max() + 5, 3 * float(np.ptp(y)) + 1, hi_p, x.max() + hi_p])
    fit = best_fit(cosine, x, y, guesses, bounds)
    if fit is None:
        out["message"] = "The cosine could not be fitted"
        return out
    p, cov, sse = fit
    mean, amplitude, period, x0 = (float(v) for v in p)
    flat = aicc(float(np.sum((y - y.mean()) ** 2)), len(x), 1)
    own = aicc(sse, len(x), 4)
    gain = None if flat is None or own is None else flat - own
    index = (x0 % period) / period
    grid = np.linspace(x.min(), x.max(), 200)
    out.update(mean_permil=mean, amplitude_permil=amplitude, period_mm=period, x0_mm=x0 % period,
               rmse=float(np.sqrt(sse / len(x))), delta_aicc_vs_flat=gain, span_mm=span,
               curve_x=[round(float(v), 3) for v in grid], curve_y=[round(float(v), 3) for v in cosine(grid, *p)])
    if span < MIN_CYCLE_SHARE * period:
        out["warnings"].append(f"The samples cover {span:.0f} mm, under 3/4 of the {period:.0f} mm formed in a year: "
                               "the period and the position of the maximum are poorly fixed")
    if amplitude < options.min_amplitude_permil or gain is None or gain < 2:
        out["message"] = (f"No clear seasonal cycle (δ18O amplitude {amplitude:.2f}‰, minimum "
                          f"{options.min_amplitude_permil:.2f}‰)" if amplitude < options.min_amplitude_permil
                          else "A cosine does not fit clearly better than a flat line")
        return out
    out["birth_index"] = {"estimate": index, "ci_low": None, "ci_high": None}
    if options.draws and np.all(np.isfinite(cov)):
        draws = rng.multivariate_normal(p, cov, size=options.draws, check_valid="ignore")
        periods = np.clip(draws[:, 2], lo_p, hi_p)
        low, high = circular_interval((draws[:, 3] % periods) / periods, index)
        out["birth_index"].update(ci_low=low, ci_high=high)
    return out


def fit_rumen(x, y, period, tooth, options, rng):
    """Is there a rise in δ13C towards the ERJ beyond the seasonal wave? Compared by AICc."""
    out = {"n": len(x), "detected": False, "message": "", "warnings": [], "curve_x": [], "curve_y": []}
    if len(x) < MIN_SAMPLES + 1:
        out["message"] = f"Only {len(x)} δ13C values; at least {MIN_SAMPLES + 1} are needed"
        return out
    span = max(float(np.ptp(x)), 1.0)
    angle = (lambda xx: 2 * np.pi * np.asarray(xx, dtype=float) / period) if period else None

    def seasonal(xx, base, b, c):
        return base + b * np.sin(angle(xx)) + c * np.cos(angle(xx))

    def with_step(xx, base, b, c, rise, middle, width):
        return seasonal(xx, base, b, c) + rise * rumen_step(xx, middle, width)

    if period:  # the seasonal wave has the δ18O period; its phase is free (δ13C need not peak in summer)
        background = best_fit(seasonal, x, y, [[float(y.mean()), 0, 0]], ([-40, -5, -5], [20, 5, 5]))
        model, k_background, wave, wave_low, wave_high = with_step, 3, [0.0, 0.0], [-5, -5], [5, 5]
    else:
        background = (None, None, float(np.sum((y - y.mean()) ** 2)))
        model = lambda xx, base, rise, middle, width: base + rise * rumen_step(xx, middle, width)  # noqa: E731
        k_background, wave, wave_low, wave_high = 1, [], [], []
    guesses = [[float(y.min())] + wave + [max(float(np.ptp(y)), 0.1), middle, span * share]
               for middle in np.linspace(x.min(), x.max(), 5) for share in (0.05, 0.15)]
    bounds = ([-40] + wave_low + [0, x.min(), span * 0.01], [20] + wave_high + [10, x.max(), span])
    fit = best_fit(model, x, y, guesses, bounds)
    if fit is None or background is None:
        out["message"] = "The δ13C models could not be fitted"
        return out
    p, cov, sse = fit
    rise, middle, width = (float(v) for v in p[-3:])
    without, with_rise = aicc(background[2], len(x), k_background), aicc(sse, len(x), k_background + 3)
    gain = None if without is None or with_rise is None else without - with_rise
    grid = np.linspace(x.min(), x.max(), 200)
    out.update(rise_permil=rise, rmse=float(np.sqrt(sse / len(x))), delta_aicc_vs_seasonal=gain,
               curve_x=[round(float(v), 3) for v in grid], curve_y=[round(float(v), 3) for v in model(grid, *p)])
    note = TOOTH_NOTES.get(tooth.lower())
    if note:
        out["warnings"].append(note)
    if gain is None or gain < 2 or rise < options.min_rumen_rise_permil:
        out["message"] = (f"No clear rise in δ13C (rise {rise:.2f}‰, minimum {options.min_rumen_rise_permil:.2f}‰)"
                          if rise < options.min_rumen_rise_permil else
                          "A rise in δ13C does not fit clearly better than the seasonal wave alone")
        return out
    out["detected"] = True
    out["transition_mm"] = {"estimate": middle, "ci_low": None, "ci_high": None}
    if options.draws and np.all(np.isfinite(cov)):
        draws = rng.multivariate_normal(p, cov, size=options.draws, check_valid="ignore")
        low, high = interval(np.clip(draws[:, -2], x.min(), x.max()))
        out["transition_mm"].update(ci_low=low, ci_high=high)
    if period:  # crown growth between the first (highest) sample and the transition
        out["months_after_first_sample"] = (float(x.max()) - middle) / period * 12
    if middle > x.max() - 0.1 * span:
        out["warnings"].append("The rise sits at the top of the sampled crown: it may have begun before the "
                               "first sample formed")
    if rise > options.max_rumen_rise_permil:
        out["warnings"].append(f"A δ13C rise of {rise:.1f}‰ is more than rumen development alone is expected to "
                               "give (about 1–2‰): a change of diet (e.g. to C4 plants) may be involved")
    return out


def analyze_tooth(rows, options, rng):
    rows = sorted(rows, key=lambda r: -r.erj_distance_mm)  # first formed first
    first = rows[0]
    points = [{"x": r.erj_distance_mm, "d18O": r.d18O, "d13C": r.d13C, "sample_index": r.sample_index} for r in rows]
    o = [(r.erj_distance_mm, r.d18O) for r in rows if r.d18O is not None]
    c = [(r.erj_distance_mm, r.d13C) for r in rows if r.d13C is not None]
    season = fit_season(*map(np.array, zip(*o)), options, rng) if o else None
    period = season.get("period_mm") if season and season["birth_index"] else None
    rumen = fit_rumen(*map(np.array, zip(*c)), period, first.tooth, options, rng) if c else None
    return {"specimen_id": first.specimen_id, "site": first.site, "species": first.species, "tooth": first.tooth,
            "period": first.period, "points": points, "season": season, "rumen": rumen}


def circular_mean(values):
    angles = 2 * np.pi * np.asarray(values)
    return float((math.atan2(np.sin(angles).mean(), np.cos(angles).mean()) / (2 * np.pi)) % 1)


def smallest_arc(values):
    """The shortest stretch of the year (0–1) that holds every value."""
    v = np.sort(np.asarray(values) % 1)
    if len(v) < 2:
        return 0.0
    gaps = np.diff(np.concatenate([v, [v[0] + 1]]))
    return float(1 - gaps.max())


def birth_seasons(results):
    """Birth indices of each site × species × tooth (× period): their circular mean and spread.

    x0/X is only comparable between teeth of the same type. The spread of the indices, times 12,
    approximates how many months births were spread over (Balasse et al. 2012).
    """
    groups: dict[tuple, list] = {}
    for r in results:
        if r["season"] and r["season"]["birth_index"]:
            key = (r["site"], r["species"], r["tooth"], r["period"])
            groups.setdefault(key, []).append((r["specimen_id"], r["season"]["birth_index"]["estimate"]))
    out = []
    for (site, species, tooth, period), items in groups.items():
        values = [v for _, v in items]
        arc = smallest_arc(values)
        out.append({"group": " · ".join(str(k) for k in (site, species, tooth, period) if k), "site": site,
                    "species": species, "tooth": tooth, "period": period, "n": len(values),
                    "mean_index": circular_mean(values), "spread_index": arc, "spread_months": arc * 12,
                    "teeth": [{"specimen_id": s, "birth_index": v} for s, v in items]})
    return out


def analyze_enamel(samples, options=None, progress=None):
    options = options or EnamelOptions()
    rng = np.random.default_rng(options.random_seed)
    teeth = list(by_tooth(samples).values())
    results = []
    for i, rows in enumerate(teeth):
        results.append(analyze_tooth(rows, options, rng))
        if progress:
            progress(i + 1, len(teeth))
    return {"results": results, "groups": birth_seasons(results)}
