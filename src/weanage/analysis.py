"""Analyses one specimen at a time: quality check -> ages -> curve fits -> weaning ages.

A "specimen" is one tooth, or every tooth from one animal when they share an
individual_id (each tooth uses its own growth table, so they join into one timeline).
"""

import atexit
import os

import numpy as np
from scipy import stats

from .config import find_growth_table
from .growth import position_to_age
from .models import compare_fits, fit_model, model_average, seasonal_test
from .qc import passes_qc, qc_flags

SLICE_STEPS = 8  # points across a slice's height, and again across its depth (8 x 8 = 64 points)


def group_by_specimen(samples):
    groups = {}
    for s in samples:
        groups.setdefault(s.individual_id or s.specimen_id, []).append(s)
    return groups


def slice_ages(row, table, override, options):
    """The ages of the dentine mixed into one slice (for time averaging).

    A slice is a horizontal disc of dentine: it has a height (the slice width) and a
    depth (from the enamel inwards to the pulp). Growth layers run at an angle, so the
    dentine at depth d was laid down when the growth front had reached
    `growth_layer_offset_mm × d` further along the tooth (d = 0 at the enamel, 1 at the pulp).
    This follows the geometry of Tsutaya (2020) and MDSS, with straight growth layers.
    We take an 8 x 8 grid over height and depth and return the age of each point.
    """
    width = row.increment_width_mm or options.increment_width_mm
    positions = slice_positions(row.position_mm, width, options.growth_layer_offset_mm)
    ages, _ = position_to_age(positions, table, override)
    return ages


def depth_steps(offset):
    """Points across the dentine depth. With no offset every depth has the same age, so one is enough."""
    return SLICE_STEPS if offset > 0 else 1


def slice_positions(position, width, offset):
    """The grid of growth-front positions (mm) mixed into one slice; see slice_ages."""
    heights = np.linspace(max(position - width / 2, 0.0), position + width / 2, SLICE_STEPS)
    depths = np.linspace(0, 1, depth_steps(offset))
    return (heights[:, None] + depths[None, :] * offset).ravel()


def slice_weights(offset, inner_dentine_weight):
    """How much dentine each grid point stands for. Inner dentine sits on a smaller circle
    around the pulp, so there is less of it: the weight falls from 1 at the enamel to
    `inner_dentine_weight` at the pulp (the ratio of inner to outer radius)."""
    depths = np.linspace(0, 1, depth_steps(offset))
    per_depth = 1 - depths * (1 - inner_dentine_weight)
    return np.tile(per_depth, SLICE_STEPS)  # the same for every height


def rising_profile_warning(t, y):
    """Weaning makes δ15N fall; a clear rise needs a different explanation.

    WEAN (Ganiatsou et al. 2023) saw rising profiles in malnourished people, and
    Beaumont & Montgomery (2016) showed that stress and starvation raise δ15N.
    """
    if len(t) < 5 or np.ptp(y) == 0:
        return None
    rho, p = stats.spearmanr(t, y)
    if rho > 0.3 and p < 0.05:
        return (f"δ15N rises with age (Spearman ρ = {rho:.2f}), unlike a typical weaning decline: "
                "consider physiological stress (Beaumont & Montgomery 2016), a diet change or sampling order before interpreting")
    return None


def seasonality_checks(t, d15n, residuals, d13c, period, weaning_curve=None):
    """Look for a yearly cycle (seasonal pasture/fodder) that could be mistaken for weaning.

    δ13C can also step up or down at weaning (Balasse et al. 2001), so the fitted
    weaning curve is allowed for before looking for a yearly cycle in δ13C.
    """
    warnings, found = [], {}
    if residuals is not None:
        test = seasonal_test(t, residuals, period, detrend=0)
        if test:
            found["residual_seasonal_amplitude"], found["residual_seasonal_p"] = test
            if test[1] < 0.05 and test[0] >= 0.2:
                warnings.append(f"Residuals show an annual cycle ({test[0]:.2f}‰, p = {test[1]:.3f}): consider "
                                "enabling the seasonal term, as seasonal diet change may be distorting the weaning estimate "
                                "(prehistoric cattle calved and foraged seasonally: Balasse et al. 2021)")
    has_c = np.isfinite(d13c)
    if has_c.sum() >= 6:
        shape = weaning_curve[has_c] if weaning_curve is not None else None
        test = seasonal_test(t[has_c], d13c[has_c], period, detrend=1, shape=shape)
        if test:
            found["d13C_seasonal_amplitude"], found["d13C_seasonal_p"] = test
            if test[1] < 0.05 and test[0] >= 0.3:
                warnings.append(f"δ13C oscillates annually ({test[0]:.2f}‰, p = {test[1]:.3f}), suggesting seasonal "
                                "diet change; check whether the δ15N decline coincides with a season rather than weaning")
        if np.ptp(d13c[has_c]) > 0 and np.ptp(d15n[has_c]) > 0:
            found["d13C_d15N_spearman"] = float(stats.spearmanr(d13c[has_c], d15n[has_c])[0])
    return warnings, found


def carbon_weaning_check(t, d13c, fit, species):
    """Compare δ13C before weaning starts with δ13C after it ends.

    In known-age calves, δ13C rose at the same time as δ15N fell (Balasse et al. 2001),
    so a clear δ13C fall in cattle suggests the δ15N decline may not be weaning.
    Returns (warning or None, shift in ‰ or None).
    """
    onset, end = (fit.get("onset") or {}).get("estimate"), (fit.get("completion") or {}).get("estimate")
    has_c = np.isfinite(d13c)
    if onset is None or end is None:
        return None, None
    before, after = d13c[has_c & (t < onset)], d13c[has_c & (t > end)]
    if len(before) < 2 or len(after) < 2:
        return None, None
    shift = float(after.mean() - before.mean())
    if species == "cattle" and shift <= -0.5:
        return (f"δ13C falls by {-shift:.1f}‰ across weaning, whereas in known-age calves it rose as δ15N fell "
                "(Balasse et al. 2001): check whether this δ15N decline reflects weaning or another diet change"), shift
    return None, shift


def analyze_specimen(samples, options):
    first = samples[0]
    rows = sorted(samples, key=lambda s: (s.tooth, s.position_mm))
    teeth = list(dict.fromkeys(r.tooth for r in rows))  # unique, in order
    result = {
        "specimen_id": first.individual_id or first.specimen_id, "site": first.site, "species": first.species,
        "tooth": "+".join(teeth), "period": first.period, "growth_table": "none", "growth_placeholder": False,
        "points": [], "fits": [], "best_model": None, "model_average": {}, "diagnostics": {}, "warnings": [],
        "known_weaning_age_months": first.known_weaning_age_months,
        "published_weaning_age_months": first.published_weaning_age_months, "adult_baseline": None,
        "age_sd_months": 0.0,
    }
    warnings = result["warnings"]

    # 1. Find the age model of every tooth.
    age_models, labels, age_sd = {}, [], 0.0
    for tooth in teeth:
        override = options.override_for(first.species, tooth)
        table = None if override else find_growth_table(first.species, tooth, options.growth_tables)
        if override:
            labels.append(f"{tooth}: custom linear {override.initiation_age_months:g} mo + position / "
                          f"{override.extension_rate_mm_per_month:g} mm·mo⁻¹")
        elif table:
            labels.append(table.label)
            result["growth_placeholder"] |= table.placeholder
            age_sd = max(age_sd, table.age_uncertainty_months)
        else:
            warnings.append(f"No growth table for {first.species} {tooth}; supply a custom age model")
            return result
        age_models[tooth] = (table, override)
    result["growth_table"] = "; ".join(labels)
    result["age_sd_months"] = age_sd
    if result["growth_placeholder"]:
        warnings.append("Ages use a PLACEHOLDER growth table (TBD-LAB); estimates are illustrative only")
    if len(teeth) > 1:
        warnings.append(f"{len(teeth)} teeth ({', '.join(teeth)}) combined into one timeline")

    # 2. Turn each slice's position into an age, and check its collagen quality.
    points, windows = [], []
    for row in rows:
        table, override = age_models[row.tooth]
        age, beyond_table = position_to_age([row.position_mm], table, override)
        window = slice_ages(row, table, override, options) if options.time_averaging else None
        flags = qc_flags(row, options.qc)
        points.append({
            "position_mm": row.position_mm, "age_months": round(float(age[0]), 4),
            "age_min": round(float(window[0]), 4) if window is not None else None,
            "age_max": round(float(window[-1]), 4) if window is not None else None,
            "d15N": row.d15N, "d13C": row.d13C, "tooth": row.tooth, "extrapolated": bool(beyond_table[0]),
            "qc_flags": flags, "used_in_fit": passes_qc(flags) or not options.qc.exclude_failed,
        })
        windows.append(window)
    order = np.argsort([p["age_months"] for p in points], kind="stable")
    points = [points[i] for i in order]
    windows = [windows[i] for i in order]
    result["points"] = points

    extrapolated = sum(p["extrapolated"] for p in points)
    if extrapolated:
        warnings.append(f"{extrapolated} sample(s) lie beyond the growth table; their ages are extrapolated")
    excluded = sum(not p["used_in_fit"] for p in points)
    if excluded:
        warnings.append(f"{excluded} sample(s) failed collagen QC and were excluded from fitting")
    used = [p for p in points if p["used_in_fit"]]
    t = np.array([p["age_months"] for p in used])
    y = np.array([p["d15N"] for p in used])
    rising = rising_profile_warning(t, y)
    if rising:
        warnings.append(rising)
    if options.time_averaging:
        warnings.append("Time averaging on: curves show the underlying diet signal, which is sharper than the sampled "
                        "values (Tsutaya 2020)")

    # 3. Fit every model and compare them.
    baseline = options.baseline_for(first.site, first.species)
    post_range = None
    if baseline and options.constrain_adult_plateau:
        post_range = (baseline.mean - 2 * baseline.sd, baseline.mean + 2 * baseline.sd)
    used_windows = None
    if options.time_averaging:
        used_windows = np.array([w for w, p in zip(windows, points) if p["used_in_fit"]])
    weights = slice_weights(options.growth_layer_offset_mm, options.inner_dentine_weight)
    fits = [fit_model(name, t, y, options, age_sd, used_windows, weights, post_range,
                      baseline.mean if baseline else None) for name in options.models]
    result["best_model"] = compare_fits(fits)
    if sum(f["akaike_weight"] is not None for f in fits) > 1:
        result["model_average"] = model_average(fits, options.random_seed)

    # 4. Check for seasonal cycles, using what the best curve leaves unexplained.
    best = next((f for f in fits if f["model"] == result["best_model"]), None)
    if best and best["curve_age"]:
        fitted = np.interp(t, best["curve_age"], best["curve_d15N"])
        leftover = None if options.seasonal_term else y - fitted
        d13c = np.array([np.nan if p["d13C"] is None else p["d13C"] for p in used])
        extra_warnings, result["diagnostics"] = seasonality_checks(t, y, leftover, d13c, options.season_period_months, fitted)
        warnings += extra_warnings
        carbon_warning, result["diagnostics"]["d13C_weaning_shift"] = carbon_weaning_check(t, d13c, best, first.species)
        if carbon_warning:
            warnings.append(carbon_warning)

    for f in fits:
        del f["_draws"]  # only needed for the model average
    result["fits"] = fits
    result["adult_baseline"] = baseline.model_dump() if baseline else None
    return result


# A pool of worker processes is kept alive so repeated analyses start quickly.
# "spawn" is safe to use from the web server's threads.
POOL: dict = {}


def worker_pool(workers):
    # Imported here, not at the top: the browser version has no extra processes to start.
    import multiprocessing
    from concurrent.futures import ProcessPoolExecutor

    if workers not in POOL:
        POOL.clear()
        POOL[workers] = ProcessPoolExecutor(workers, mp_context=multiprocessing.get_context("spawn"))
    return POOL[workers]


atexit.register(lambda: [pool.shutdown(wait=False, cancel_futures=True) for pool in POOL.values()])


def analyze(samples, options, progress=None, workers=None):
    """Analyse every specimen; datasets of 6+ specimens are split across processor cores."""
    groups = list(group_by_specimen(samples).values())
    results = [None] * len(groups)
    workers = workers if workers is not None else min(os.cpu_count() or 1, 8)
    if workers > 1 and len(groups) >= 6:
        try:
            from concurrent.futures import as_completed

            jobs = {worker_pool(workers).submit(analyze_specimen, g, options): i for i, g in enumerate(groups)}
            for done, job in enumerate(as_completed(jobs), start=1):
                results[jobs[job]] = job.result()
                if progress:
                    progress(done, len(groups))
            return results
        except Exception:  # e.g. no permission to start processes: fall back to one at a time
            POOL.clear()
    for i, rows in enumerate(groups):
        results[i] = analyze_specimen(rows, options)
        if progress:
            progress(i + 1, len(groups))
    return results


def estimate_rows(results):
    """One flat row per specimen and model (plus the model average), used for comparisons."""
    rows = []
    for res in results:
        common = {k: res[k] for k in ["specimen_id", "site", "species", "period",
                                      "known_weaning_age_months", "published_weaning_age_months"]}
        sources = [(f["model"], f) for f in res["fits"] if f["converged"]]
        if res["model_average"]:
            sources.append(("average", res["model_average"]))
        for model, fit in sources:
            completion = fit.get("completion") or {}
            rows.append({**common, "model": model, "is_best": model == res["best_model"],
                         "onset": (fit.get("onset") or {}).get("estimate"),
                         "midpoint": (fit.get("midpoint") or {}).get("estimate"),
                         "completion": completion.get("estimate"),
                         "completion_ci_low": completion.get("ci_low"),
                         "completion_ci_high": completion.get("ci_high"),
                         "akaike_weight": fit.get("akaike_weight")})
    return rows
