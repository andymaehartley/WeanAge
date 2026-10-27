"""Season of birth, rumen development and C3/C4 diet from sequential enamel δ18O and δ13C, for cattle.

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
* C3 or C4 diet (δ13C). Enamel δ13C is about 14‰ above the diet's (Cerling & Harris 1999), and C4
  grasses (millet, maize, many tropical grasses) are about 15‰ higher than C3 plants. The share of C4
  plants is found by mixing a C3 and a C4 end member, from the enamel formed after the rumen works.
* Mobility (87Sr/86Sr). Enamel strontium follows the geology where the animal fed; a shift in level
  along the crown suggests a move (Bentley 2006), and its position against the δ18O cycle gives its
  season. Enamel averages strontium over months, so shifts are blurred (Montgomery et al. 2010).
* Calendar. The δ18O maximum is set to a month (summer by default), so any position can be placed
  in the year: the enamel x mm below the maximum formed x/X of a year later. Birth months need a
  reference tooth with a known birth month; with an age at weaning from the same animal's dentine,
  they give the month of weaning.

Enamel takes months to mineralise at any one position (Zazzo et al. 2005), so all signals are
smoothed: amplitudes are lower and transitions more gradual than in life. When the length of crown
over which enamel matures is given, the cosine amplitude and the width of the rumen step are
corrected for a moving average of that length (after Passey & Cerling 2002); this is approximate.
Positions are not converted into ages, because enamel formation tables for cattle are not yet available.
"""

import math
import warnings

import numpy as np
from scipy.optimize import curve_fit

from .changes import find_shifts
from .ingest import check_rows, column_lookup, issue, match_columns
from .models import aicc, interval
from .schema import EnamelOptions, EnamelSample

ALIASES = {
    "specimen_id": ["specimen", "specimenid", "sampleid", "toothid"],
    "tooth": ["element"],
    "erj_distance_mm": ["erj", "erjdistance", "distancefromerj", "distancefromerjmm", "heightaboveerj", "herj"],
    "d18O": ["δ18o", "delta18o", "d18ovpdb", "d18ocarbonate"],
    "sr87_86": ["87sr86sr", "sr8786", "srratio", "sr"],
    "weaning_age_months": ["weaningage", "weaningagemonths"],
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
                    "n_sr": sum(r.sr87_86 is not None for r in rows),
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


def share_after_maximum(position, x0, period):
    """Share of a year (0–1) from the δ18O maximum to when the enamel at this position formed."""
    return ((np.asarray(x0) - np.asarray(position)) / np.asarray(period)) % 1


def to_month(share, options):
    """A share of the year after the δ18O maximum as a month number (1 = start of January, up to 13)."""
    return (options.d18O_max_month - 1 + 12 * np.asarray(share)) % 12 + 1


def month_estimate(share, share_draws, options):
    """Month of a share of the year with its circular 95% interval."""
    low, high = circular_interval(share_draws, share) if share_draws is not None and len(share_draws) else (None, None)
    as_month = lambda v: None if v is None else float(to_month(v, options))  # noqa: E731
    return {"estimate": as_month(share), "ci_low": as_month(low), "ci_high": as_month(high)}


def fit_season(x, y, options, rng):
    """Cosine fit of δ18O along the crown. Returns the result, with no birth index when there is no clear cycle."""
    out = {"n": len(x), "birth_index": None, "message": "", "warnings": [], "curve_x": [], "curve_y": [], "draws": None}
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
    if options.mineralisation_length_mm:
        # A moving average over L mm lowers a cosine of period X by sinc(L/X).
        kept = float(np.sinc(options.mineralisation_length_mm / period))
        if kept < 0.3:
            out["warnings"].append(f"Averaging over {options.mineralisation_length_mm:g} mm leaves too little of a "
                                   f"{period:.0f} mm cycle to restore its amplitude")
        else:
            out["amplitude_restored_permil"] = amplitude / kept
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
        draws[:, 2] = np.clip(draws[:, 2], lo_p, hi_p)
        low, high = circular_interval((draws[:, 3] % draws[:, 2]) / draws[:, 2], index)
        out["birth_index"].update(ci_low=low, ci_high=high)
        out["draws"] = draws  # used by analyze_tooth, then dropped
    return out


def fit_rumen(x, y, period, tooth, options, rng):
    """Is there a rise in δ13C towards the ERJ beyond the seasonal wave? Compared by AICc."""
    out = {"n": len(x), "detected": False, "message": "", "warnings": [], "curve_x": [], "curve_y": [], "draws": None}
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
        out["draws"] = np.clip(draws[:, -2], x.min(), x.max())
        low, high = interval(out["draws"])
        out["transition_mm"].update(ci_low=low, ci_high=high)
    # 10% to 90% of the rise; a moving average over L mm adds L²/12 to the step's variance (π²w²/3).
    out["width_mm"] = 2 * math.log(9) * width
    if options.mineralisation_length_mm:
        restored = math.sqrt(max(width ** 2 - options.mineralisation_length_mm ** 2 / (4 * math.pi ** 2), 0))
        out["width_restored_mm"] = 2 * math.log(9) * restored
    if period:  # crown growth between the first (highest) sample and the transition
        out["months_after_first_sample"] = (float(x.max()) - middle) / period * 12
        out["duration_months"] = out["width_mm"] / period * 12
        if "width_restored_mm" in out:
            out["duration_restored_months"] = out["width_restored_mm"] / period * 12
    if middle > x.max() - 0.1 * span:
        out["warnings"].append("The rise sits at the top of the sampled crown: it may have begun before the "
                               "first sample formed")
    if rise > options.max_rumen_rise_permil:
        out["warnings"].append(f"A δ13C rise of {rise:.1f}‰ is more than rumen development alone is expected to "
                               "give (about 1–2‰): a change of diet (e.g. to C4 plants) may be involved")
    return out


def diet_c4(x, y, rumen, tooth, options, rng):
    """Share of C4 plants in the diet: diet δ13C = enamel δ13C − spacing, mixed from a C3 and a C4 end member.

    The uncertainty of the spacing, of both end members and of the tooth's mean is carried through by
    random draws. When a rumen transition was found, only enamel formed after it is used, because milk
    and an undeveloped rumen lower enamel δ13C.
    """
    after = bool(rumen and rumen.get("detected"))
    used = x < rumen["transition_mm"]["estimate"] if after else np.ones(len(x), dtype=bool)
    out = {"n": int(used.sum()), "after_rumen": after, "share_c4": None, "message": "", "warnings": []}
    if used.sum() < 3:
        out["message"] = f"Only {int(used.sum())} δ13C values formed after the rumen transition; at least 3 are needed"
        return out
    o = options
    values = y[used]
    mean, se = float(values.mean()), float(values.std(ddof=1) / math.sqrt(len(values)))
    to_share = lambda enamel, spacing, c3, c4: (enamel - spacing - c3) / (c4 - c3)  # noqa: E731
    raw = to_share(mean, o.enamel_diet_spacing_permil, o.c3_plants_d13C, o.c4_plants_d13C)
    estimate = float(np.clip(raw, 0, 1))
    n = max(o.draws, 1000)
    draws = np.clip(to_share(rng.normal(mean, se, n), rng.normal(o.enamel_diet_spacing_permil, o.enamel_diet_spacing_sd, n),
                             rng.normal(o.c3_plants_d13C, o.c3_plants_sd, n), rng.normal(o.c4_plants_d13C, o.c4_plants_sd, n)), 0, 1)
    low, high = interval(draws)
    each = np.clip(to_share(values, o.enamel_diet_spacing_permil, o.c3_plants_d13C, o.c4_plants_d13C), 0, 1)
    category = "C3 diet" if estimate < 0.2 else "C4 diet" if estimate > 0.8 else "mixed C3 and C4 diet"
    out.update(enamel_mean_d13C=mean, diet_d13C=mean - o.enamel_diet_spacing_permil, category=category,
               share_c4={"estimate": estimate, "ci_low": low, "ci_high": high},
               sample_range=[float(each.min()), float(each.max())])
    if not after and tooth.lower() == "m1":
        out["warnings"].append("Part of this M1 formed while the calf suckled, when milk and an undeveloped rumen lower "
                               "δ13C: the C4 share may be underestimated (an M2, M3 or the part after a rumen transition "
                               "is better)")
    if raw < -0.25:
        out["warnings"].append("δ13C is lower than a pure C3 diet should give: closed forest (the canopy effect) or a "
                               "different enamel-diet spacing may explain it")
    if raw > 1.25:
        out["warnings"].append("δ13C is higher than a pure C4 diet should give: check the end members and the spacing")
    return out


def mobility(x, y, season, options):
    """Shifts in 87Sr/86Sr along the crown, placed in the year when the δ18O cycle is known."""
    out = {"n": len(x), "mean": float(np.mean(y)), "range": [float(np.min(y)), float(np.max(y))], "shifts": [],
           "warnings": [], "outside_local": None}
    if len(x) < 4:
        out["message"] = f"Only {len(x)} 87Sr/86Sr values; at least 4 are needed to look for shifts"
        return out
    for s in find_shifts(-x, y, options.sr_min_shift):  # -x: in the order the enamel formed
        s["position"], s["between"] = -s["position"], [-v for v in s["between"]]
        if season:  # the shift happened between the two samples, so take their midpoint
            s["month"] = month_estimate(float(share_after_maximum(s["position"], season["x0_mm"], season["period_mm"])), None, options)
        out["shifts"].append(s)
    if options.local_sr_min is not None and options.local_sr_max is not None:
        outside = (y < options.local_sr_min) | (y > options.local_sr_max)
        out["outside_local"] = int(outside.sum())
        if outside.any():
            out["warnings"].append(f"{int(outside.sum())} of {len(y)} 87Sr/86Sr values lie outside the local range "
                                   f"{options.local_sr_min:.4f}–{options.local_sr_max:.4f}: time spent elsewhere")
    if out["shifts"]:
        out["warnings"].append("Enamel averages strontium over months, so the true move was sharper, and may have been "
                               "earlier, than the shift seen (Montgomery et al. 2010)")
    return out


def calendar(season, rumen, rows, options, rng):
    """Months of rumen development, birth and weaning. Each needs different inputs; missing ones give None."""
    out = {"rumen_month": None, "birth_month": None, "weaning_month": None, "message": ""}
    if not season or not season["birth_index"]:
        out["message"] = "Needs a δ18O cycle"
        return out
    draws = season["draws"]
    if rumen and rumen["detected"]:
        share = float(share_after_maximum(rumen["transition_mm"]["estimate"], season["x0_mm"], season["period_mm"]))
        share_draws = None
        if draws is not None and rumen["draws"] is not None:
            n = min(len(draws), len(rumen["draws"]))
            share_draws = share_after_maximum(rumen["draws"][:n], draws[:n, 3] % draws[:n, 2], draws[:n, 2])
        out["rumen_month"] = month_estimate(share, share_draws, options)
    if options.reference_birth_index is None or options.reference_birth_month is None:
        out["message"] = "Birth and weaning months need a reference tooth with a known birth month"
        return out
    # A later birth puts the summer maximum lower on the crown, so the birth index falls by 1/12 a month.
    index = season["birth_index"]["estimate"]
    index_draws = None if draws is None else (draws[:, 3] % draws[:, 2]) / draws[:, 2]
    birth = lambda i: (options.reference_birth_month - 1 + 12 * (options.reference_birth_index - np.asarray(i))) % 12  # noqa: E731
    as_share = lambda m: np.asarray(m) / 12  # noqa: E731
    shares = None if index_draws is None else as_share(birth(index_draws))
    calendar_options = options.model_copy(update={"d18O_max_month": 1.0})  # birth() already gives calendar months
    out["birth_month"] = month_estimate(float(as_share(birth(index))), shares, calendar_options)
    age = next((r.weaning_age_months for r in rows if r.weaning_age_months is not None), None)
    if age is None:
        out["message"] = "The weaning month needs the animal's weaning age (weaning_age_months)"
        return out
    sd = next((r.weaning_age_sd_months for r in rows if r.weaning_age_sd_months is not None), 0.0)
    n = max(options.draws, 1000)
    birth_draws = birth(index_draws) if index_draws is not None else np.full(n, float(birth(index)))
    ages = rng.normal(age, sd, len(birth_draws))
    out["weaning_month"] = month_estimate(float(as_share(birth(index) + age) % 1), as_share(birth_draws + ages) % 1, calendar_options)
    out["weaning_age_months"] = age
    return out


def analyze_tooth(rows, options, rng):
    rows = sorted(rows, key=lambda r: -r.erj_distance_mm)  # first formed first
    first = rows[0]
    points = [{"x": r.erj_distance_mm, "d18O": r.d18O, "d13C": r.d13C, "sr87_86": r.sr87_86, "sample_index": r.sample_index}
              for r in rows]
    o = [(r.erj_distance_mm, r.d18O) for r in rows if r.d18O is not None]
    c = [(r.erj_distance_mm, r.d13C) for r in rows if r.d13C is not None]
    sr = [(r.erj_distance_mm, r.sr87_86) for r in rows if r.sr87_86 is not None]
    season = fit_season(*map(np.array, zip(*o)), options, rng) if o else None
    dated = season if season and season["birth_index"] else None
    period = dated["period_mm"] if dated else None
    rumen = fit_rumen(*map(np.array, zip(*c)), period, first.tooth, options, rng) if c else None
    diet = diet_c4(*map(np.array, zip(*c)), rumen, first.tooth, options, rng) if c else None
    strontium = mobility(*map(np.array, zip(*sr)), dated, options) if sr else None
    months = calendar(dated, rumen, rows, options, rng)
    for fit in (season, rumen):
        if fit:
            fit.pop("draws")
    return {"specimen_id": first.specimen_id, "site": first.site, "species": first.species, "tooth": first.tooth,
            "period": first.period, "points": points, "season": season, "rumen": rumen, "diet": diet,
            "strontium": strontium, "calendar": months}


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


def group_summary(results):
    """Each site × species × tooth (× period): birth indices and C4 shares of its teeth.

    x0/X is only comparable between teeth of the same type. The spread of the indices (the shortest
    stretch of the year holding them all), times 12, approximates how many months births were spread
    over (Balasse et al. 2012).
    """
    groups: dict[tuple, list] = {}
    for r in results:
        groups.setdefault((r["site"], r["species"], r["tooth"], r["period"]), []).append(r)
    out = []
    for (site, species, tooth, period), members in groups.items():
        index_of = {r["specimen_id"]: r["season"]["birth_index"]["estimate"] for r in members
                    if r["season"] and r["season"]["birth_index"]}
        shares = [r["diet"]["share_c4"]["estimate"] for r in members if r["diet"] and r["diet"]["share_c4"]]
        rumen_months = [r["calendar"]["rumen_month"]["estimate"] for r in members if r["calendar"]["rumen_month"]]
        indices = list(index_of.values())
        arc = smallest_arc(indices) if indices else None
        out.append({"group": " · ".join(str(k) for k in (site, species, tooth, period) if k), "site": site,
                    "species": species, "tooth": tooth, "period": period, "n": len(members), "n_index": len(indices),
                    "mean_index": circular_mean(indices) if indices else None, "spread_index": arc,
                    "spread_months": arc * 12 if arc is not None else None,
                    "mean_share_c4": float(np.mean(shares)) if shares else None, "n_diet": len(shares),
                    "mean_rumen_month": circular_mean((np.array(rumen_months) - 1) / 12) * 12 + 1 if rumen_months else None,
                    "n_movers": sum(bool(r["strontium"] and r["strontium"]["shifts"]) for r in members),
                    "teeth": [{"specimen_id": sid, "birth_index": v} for sid, v in index_of.items()]})
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
    return {"results": results, "groups": group_summary(results)}
