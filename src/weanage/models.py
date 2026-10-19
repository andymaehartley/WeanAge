"""Weaning curves and how they are fitted to the data.

While an animal suckles, its δ15N is raised by about one step in the food chain.
After weaning it falls to the adult level. Every curve here has

* post - the adult (after weaning) δ15N level
* drop - how much higher the suckling level is (so suckling level = post + drop)

and differs only in the *shape* of the fall. "elbow" copies the method of the WEAN
tool (Ganiatsou et al. 2023) so its answers can be compared side by side.
"""

import math
import warnings

import numpy as np
from scipy import stats
from scipy.optimize import curve_fit

from .schema import AnalysisOptions

MILESTONES = ["onset", "midpoint", "completion"]


# ───────────── curve shapes (t = age in months) ─────────────
def falling_step(t, middle, width):
    """Goes smoothly from 1 down to 0 around `middle`."""
    z = np.clip((np.asarray(t, dtype=float) - middle) / width, -60, 60)
    return 1 / (1 + np.exp(z))


def logistic(t, post, drop, t_mid, scale):
    return post + drop * falling_step(t, t_mid, scale)


def piecewise(t, post, drop, t_start, duration):
    progress = np.clip((np.asarray(t, dtype=float) - t_start) / duration, 0, 1)
    return post + drop * (1 - progress)


def exponential(t, post, drop, t_start, tau):
    elapsed = np.clip(np.asarray(t, dtype=float) - t_start, 0, None)
    return post + drop * np.exp(-elapsed / tau)


def two_phase(t, post, drop, first_fraction, t1, gap, scale):
    """Two falls: part of the drop at t1, the rest `gap` months later."""
    first = first_fraction * falling_step(t, t1, scale)
    second = (1 - first_fraction) * falling_step(t, t1 + gap, scale)
    return post + drop * (first + second)


# ───────────── weaning ages from the fitted parameters ─────────────
# `p` is one set of parameters, or a table with one row per random draw, so
# p[..., 2] means "the third parameter" in both cases. q is the threshold (5 %).
def logistic_ages(p, q):
    t_mid, scale = p[..., 2], p[..., 3]
    half = scale * math.log((1 - q) / q)
    return {"onset": t_mid - half, "midpoint": t_mid, "completion": t_mid + half}


def piecewise_ages(p, q):
    start, duration = p[..., 2], p[..., 3]
    return {"onset": start, "midpoint": start + duration / 2, "completion": start + duration}


def exponential_ages(p, q):
    start, tau = p[..., 2], p[..., 3]
    return {"onset": start, "midpoint": start + tau * math.log(2), "completion": start + tau * math.log(1 / q)}


def two_phase_ages(p, q):
    post, drop, f, t1, gap, scale = (p[..., i] for i in range(6))
    half = scale * math.log((1 - q) / q)
    # Midpoint = where half the drop has happened. Found by halving the search range 40 times.
    low, high = t1 - 10 * scale, t1 + gap + 10 * scale
    for _ in range(40):
        middle = (low + high) / 2
        still_high = two_phase(middle, post, drop, f, t1, gap, scale) > post + drop / 2
        low, high = np.where(still_high, middle, low), np.where(still_high, high, middle)
    return {"onset": t1 - half, "midpoint": (low + high) / 2, "completion": t1 + gap + half}


# Each parameter has a "kind" that decides its starting guess and allowed range.
MODELS: dict[str, dict] = {
    "logistic": {
        "label": "Logistic (sigmoid)", "curve": logistic, "ages": logistic_ages,
        "params": {"post": "level", "drop": "drop", "t_mid": "time", "scale": "width"},
        "about": "Smooth S-shaped decline from the nursing to the adult plateau. Onset and completion "
                 "are where the curve has covered the chosen threshold of the drop.",
    },
    "piecewise": {
        "label": "Piecewise linear (broken stick)", "curve": piecewise, "ages": piecewise_ages,
        "params": {"post": "level", "drop": "drop", "t_start": "time", "duration": "width"},
        "about": "Flat nursing plateau, straight-line decline, flat adult plateau. Onset and completion "
                 "are the two breakpoints.",
    },
    "exponential": {
        "label": "Exponential decay", "curve": exponential, "ages": exponential_ages,
        "params": {"post": "level", "drop": "drop", "t_start": "time", "tau": "width"},
        "about": "Nursing plateau followed by an abrupt start to weaning and an exponential approach to "
                 "the adult value (fast early change, slowing later).",
    },
    "two_phase": {
        "label": "Two-phase (staged weaning)", "curve": two_phase, "ages": two_phase_ages,
        "params": {"post": "level", "drop": "drop", "first_fraction": "fraction", "t1": "time",
                   "gap": "gap", "scale": "width"},
        "about": "Two logistic steps with an intermediate plateau: early supplementary feeding while "
                 "suckling continues, then final weaning. Expected where milk was shared with people "
                 "(dairying). Compare its AICc with the logistic model.",
    },
}
ELBOW_ABOUT = ("Re-implementation of WEAN (Ganiatsou et al. 2023): a 4th-degree polynomial is fitted and "
               "weaning completion is the 'elbow', the point farthest below the line from the δ15N peak "
               "to the last sample. Reports completion only.")
MODEL_CATALOG = [{"name": n, "label": m["label"], "description": m["about"], "params": list(m["params"])}
                 for n, m in MODELS.items()]
MODEL_CATALOG.append({"name": "elbow", "label": "Elbow on polynomial (WEAN-style)",
                      "description": ELBOW_ABOUT, "params": ["c4", "c3", "c2", "c1", "c0"]})


def limits(kinds, t, y, post_range=None):
    """Lowest and highest allowed value of each parameter."""
    span = max(float(np.ptp(t)), 1.0)
    level_low, level_high = post_range or (y.min() - 5, y.max() + 5)
    table = {
        "level": (level_low, level_high),
        "drop": (0.0, max(float(np.ptp(y)) * 3, 1.0)),
        "time": (t.min() - span, t.max() + span),
        "width": (span * 1e-3, span * 4),
        "fraction": (0.05, 0.95),
        "gap": (span * 0.02, span * 2),
    }
    low = [float(table[k][0]) for k in kinds]
    high = [float(table[k][1]) for k in kinds]
    return low, high


def starting_guesses(kinds, t, y):
    """Several sensible starting points; the fit keeps whichever ends up best."""
    span = max(float(np.ptp(t)), 1.0)
    post = float(np.percentile(y, 15))
    drop = max(float(np.percentile(y, 85)) - post, 0.5)
    guesses = []
    for centre in np.linspace(0.15, 0.75, 5):
        for width in (0.03, 0.08):
            for gap in ((0.15, 0.3) if "gap" in kinds else (0.2,)):
                values = {"level": post, "drop": drop, "time": t.min() + centre * span,
                          "width": width * span, "fraction": 0.5, "gap": gap * span}
                guesses.append([values[k] for k in kinds])
    return guesses


def aicc(sse, n, n_params):
    """Small-sample AIC: lower = better balance of fit and simplicity."""
    k = n_params + 1  # the noise level counts as one more parameter
    if n - k - 1 <= 0 or sse <= 0:
        return None
    return n * math.log(sse / n) + 2 * k + 2 * k * (k + 1) / (n - k - 1)


def interval(values):
    """The middle 95 % of a set of random draws."""
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size < 20:
        return None, None
    low, high = np.percentile(values, [2.5, 97.5])
    return float(low), float(high)


def new_result(name, label):
    return {"model": name, "label": label, "converged": False, "message": "", "params": {}, "param_se": {},
            "nursing_d15N": None, "adult_d15N": None, "drop_permil": None, "enrichment_permil": None,
            "extra": {}, "onset": None, "midpoint": None, "completion": None, "rmse": None, "r2": None,
            "aicc": None, "delta_aicc": None, "akaike_weight": None, "warnings": [],
            "curve_age": [], "curve_d15N": [], "_draws": {}}


def add_milestones(result, best_guess, draws, age_sd, rng):
    """Store each weaning age with its 95 % interval.

    The age model's own error moves every sample of a tooth together, so it is
    added as one random shift per draw.
    """
    for key, estimate in best_guess.items():
        low = high = None
        if draws is not None and len(draws.get(key, [])):
            values = np.asarray(draws[key], dtype=float) + rng.normal(0, age_sd, len(draws[key]))
            low, high = interval(values)
            result["_draws"][key] = values
        result[key] = {"estimate": float(estimate), "ci_low": low, "ci_high": high}


def drop_warnings(drop, options):
    """Is the nursing-to-adult δ15N drop believable?

    Suckling young feed one step up the food chain from their mother, which raises
    δ15N by about 3-4‰ (DeNiro & Epstein 1981; Minagawa & Wada 1984). Observed nursing
    enrichment is usually 2-3‰ (e.g. cattle dentine: Balasse et al. 2001; infants:
    Fuller et al. 2006). Much smaller drops are noise; much larger ones need another cause.
    """
    if drop < options.min_weaning_drop_permil:
        return [f"δ15N drop of {drop:.2f}‰ is below the {options.min_weaning_drop_permil:.2f}‰ minimum: "
                "no clear weaning signal"]
    if drop > options.max_plausible_drop_permil:
        return [f"δ15N drop of {drop:.2f}‰ is larger than one food-chain step ({options.max_plausible_drop_permil:.1f}‰; "
                "nursing usually adds 2-3‰): check for a diet change, mixed-up samples or teeth"]
    return []


def fit_model(name, ages, d15n, options=None, age_sd=0.0, windows=None, weights=None,
              post_range=None, baseline=None):
    """Fit one model to one specimen and work out its weaning ages.

    windows/weights switch on time averaging: row i of `windows` holds the ages
    mixed into sample i, and the sample is predicted as their weighted average.
    """
    options = options or AnalysisOptions()
    order = np.argsort(ages, kind="stable")
    t = np.asarray(ages, dtype=float)[order]
    y = np.asarray(d15n, dtype=float)[order]
    if windows is not None:
        windows = np.asarray(windows, dtype=float)[order]
    if name == "elbow":
        result = fit_elbow(t, y, options, age_sd)
    else:
        result = fit_curve(name, t, y, options, age_sd, windows, weights, post_range)
    if baseline is not None and result["nursing_d15N"] is not None:
        result["enrichment_permil"] = result["nursing_d15N"] - baseline
        if result["enrichment_permil"] > options.max_plausible_drop_permil:
            result["warnings"].append(f"Nursing δ15N is {result['enrichment_permil']:.1f}‰ above the adult females, "
                                      "more than one food-chain step: check the baseline and the samples")
    return result


def fit_curve(name, t, y, options, age_sd, windows, weights, post_range):
    spec = MODELS[name]
    kinds = list(spec["params"].values())
    names = list(spec["params"])
    seasonal = options.seasonal_term
    if seasonal:  # an extra yearly wave: a·sin + b·cos
        kinds, names = kinds + ["wave", "wave"], names + ["season_sin", "season_cos"]
    result = new_result(name, spec["label"] + (" + seasonal" if seasonal else ""))
    n = len(t)
    if n < len(kinds) + 2:
        result["message"] = f"Need at least {len(kinds) + 2} samples, got {n}"
        return result

    def curve(ages, *p):
        out = spec["curve"](ages, *p[:len(spec["params"])])
        if seasonal:
            angle = 2 * math.pi * np.asarray(ages) / options.season_period_months
            out = out + p[-2] * np.sin(angle) + p[-1] * np.cos(angle)
        return out

    def predict(ages, *p):
        if windows is None:
            return curve(ages, *p)
        w = np.ones(windows.shape[1]) if weights is None else np.asarray(weights, dtype=float)
        return curve(windows, *p) @ (w / w.sum())

    base_kinds = [k for k in kinds if k != "wave"]
    low, high = limits(base_kinds, t, y, post_range)
    guesses = starting_guesses(base_kinds, t, y)
    if seasonal:
        wave = max(float(np.ptp(y)), 0.5)
        low, high = low + [-wave, -wave], high + [wave, wave]
        guesses = [g + [0.0, 0.0] for g in guesses]
    sigma = np.full(n, options.analytical_sd_permil) if options.analytical_sd_permil else None

    best = None
    for guess in guesses:
        try:
            p, cov, sse = least_squares(predict, t, y, sigma, guess, (low, high))
        except (RuntimeError, ValueError):
            continue
        if best is None or sse < best[2]:
            best = (p, cov, sse)
    if best is None:
        result["message"] = "Optimiser did not converge from any starting point"
        return result

    p, cov, sse = best
    se = np.sqrt(np.diag(cov)) if np.all(np.isfinite(cov)) else [None] * len(p)
    fitted = predict(t, *p)
    result.update(
        converged=True,
        params={k: float(v) for k, v in zip(names, p)},
        param_se={k: (float(v) if v is not None and np.isfinite(v) else None) for k, v in zip(names, se)},
        adult_d15N=float(p[0]), nursing_d15N=float(p[0] + p[1]), drop_permil=float(p[1]),
        rmse=float(np.sqrt(np.mean((y - fitted) ** 2))),
        r2=float(1 - sse / np.sum((y - y.mean()) ** 2)) if np.ptp(y) > 0 else None,
        aicc=aicc(sse, n, len(p)),
    )
    if name == "two_phase":
        result["extra"] = {"intermediate_d15N": float(p[0] + p[1] * (1 - p[2])),
                           "first_phase_fraction": float(p[2]), "supplementation_months": float(p[4])}
    if seasonal:
        result["extra"]["seasonal_amplitude_permil"] = float(math.hypot(p[-2], p[-1]))

    # Uncertainty: re-compute the weaning ages for many plausible versions of the fit.
    rng = np.random.default_rng(options.random_seed)
    draws = None
    if options.uncertainty == "bootstrap" and options.bootstrap_draws > 0:
        refits = []
        for _ in range(options.bootstrap_draws):  # refit to the curve plus reshuffled leftovers
            y_new = fitted + rng.choice(y - fitted, size=n)
            try:
                refits.append(least_squares(predict, t, y_new, sigma, p, (low, high))[0])
            except (RuntimeError, ValueError):
                pass
        if len(refits) >= 20:
            draws = spec["ages"](np.array(refits), options.transition_threshold)
    elif options.monte_carlo_draws > 0 and np.all(np.isfinite(cov)):
        samples = rng.multivariate_normal(p, cov, size=options.monte_carlo_draws, check_valid="ignore")
        draws = spec["ages"](np.clip(samples, low, high), options.transition_threshold)
    best_guess = spec["ages"](np.asarray(p), options.transition_threshold)
    add_milestones(result, best_guess, draws, age_sd, rng)
    if draws is None:
        result["warnings"].append("Parameter uncertainty unavailable: no confidence intervals")

    result["warnings"] += drop_warnings(p[1], options)
    if best_guess["onset"] < t.min():
        result["warnings"].append("Weaning onset falls before the first sample (nursing plateau not captured)")
    if best_guess["completion"] > t.max():
        result["warnings"].append("Weaning completion falls after the last sample (extrapolated)")
    grid = np.linspace(t.min(), t.max(), 200)
    result["curve_age"] = [round(float(v), 4) for v in grid]
    result["curve_d15N"] = [round(float(v), 4) for v in curve(grid, *p)]
    return result


def least_squares(predict, t, y, sigma, guess, bounds):
    """SciPy's curve_fit, starting from `guess` (nudged inside the bounds)."""
    guess = np.clip(guess, np.array(bounds[0]) + 1e-9, np.array(bounds[1]) - 1e-9)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        p, cov = curve_fit(predict, t, y, p0=guess, sigma=sigma, absolute_sigma=sigma is not None,
                           bounds=bounds, method="trf", maxfev=20000)
    return p, cov, float(np.sum((y - predict(t, *p)) ** 2))


# ───────────── the WEAN-style elbow method ─────────────
def find_elbow(grid, curve, normalise):
    """Index of the curve's peak, and of the point farthest below the line from the peak to the end."""
    peak = int(np.argmax(curve))
    if len(grid) - peak < 3:
        return None
    x, y = grid[peak:], curve[peak:]
    if normalise:  # rescale both axes to 0–1 so months and ‰ count equally
        x = (x - x[0]) / ((x[-1] - x[0]) or 1)
        y = (y - y.min()) / ((y.max() - y.min()) or 1)
    dx, dy = x[-1] - x[0], y[-1] - y[0]
    distance_below_line = dy * (x - x[0]) - dx * (y - y[0])
    return peak, peak + int(np.argmax(distance_below_line))


def fit_elbow(t, y, options, age_sd, degree=4):
    result = new_result("elbow", "Elbow on polynomial (WEAN-style)")
    n = len(t)
    if n < degree + 3:
        result["message"] = f"Need at least {degree + 3} samples, got {n}"
        return result
    weights = np.full(n, 1 / options.analytical_sd_permil) if options.analytical_sd_permil else None
    centre = t.mean()  # centring the ages keeps the polynomial maths accurate
    coef, cov = np.polyfit(t - centre, y, degree, w=weights, cov="unscaled" if weights is not None else True)
    grid = np.linspace(t.min(), t.max(), 200)
    powers = np.vander(grid - centre, degree + 1)  # polynomial value = powers @ coefficients
    curve = powers @ coef
    found = find_elbow(grid, curve, options.elbow_normalise)
    if found is None:
        result["message"] = "δ15N peaks at the end of the series: no declining segment to analyse"
        return result
    peak, elbow = found
    fitted = np.polyval(coef, t - centre)
    sse = float(np.sum((y - fitted) ** 2))
    after = y[t >= grid[elbow]]
    names = [f"c{degree - i}" for i in range(degree + 1)]
    result.update(
        converged=True,
        params={k: float(c) for k, c in zip(names, coef)},
        param_se={k: float(s) for k, s in zip(names, np.sqrt(np.clip(np.diag(cov), 0, None)))},
        rmse=float(np.sqrt(sse / n)),
        r2=float(1 - sse / np.sum((y - y.mean()) ** 2)) if np.ptp(y) > 0 else None,
        aicc=aicc(sse, n, degree + 1),
        nursing_d15N=float(curve[peak]),
        adult_d15N=float(after.mean() if len(after) else curve[-1]),
    )
    result["drop_permil"] = result["nursing_d15N"] - result["adult_d15N"]

    rng = np.random.default_rng(options.random_seed)
    many = None  # many plausible sets of polynomial coefficients
    if options.uncertainty == "bootstrap" and options.bootstrap_draws > 0:
        many = np.array([np.polyfit(t - centre, fitted + rng.choice(y - fitted, n), degree, w=weights)
                         for _ in range(options.bootstrap_draws)])
    elif options.monte_carlo_draws > 0:
        many = rng.multivariate_normal(coef, cov, size=options.monte_carlo_draws, check_valid="ignore")
    draws = None
    if many is not None:
        elbows = [find_elbow(grid, c, options.elbow_normalise) for c in many @ powers.T]
        draws = {"completion": [grid[e[1]] for e in elbows if e is not None]}
    add_milestones(result, {"completion": grid[elbow]}, draws, age_sd, rng)
    result["onset"] = {"estimate": float(grid[peak]), "ci_low": None, "ci_high": None}

    slope = float(np.polyval(np.polyder(coef), grid[elbow] - centre))
    if slope > 0:
        result["warnings"].append(f"Curve is rising at the elbow (slope {slope:+.2f}‰/month): possible false estimate")
    result["warnings"] += drop_warnings(result["drop_permil"], options)
    if elbow >= len(grid) - 2:
        result["warnings"].append("Elbow falls at the last sample: weaning may not be complete within the series")
    if curve.max() > y.max() + 0.5 or curve.min() < y.min() - 0.5:
        result["warnings"].append("Polynomial overshoots the observed δ15N range (>0.5‰); check the curve visually")
    result["curve_age"] = [round(float(v), 4) for v in grid]
    result["curve_d15N"] = [round(float(v), 4) for v in curve]
    return result


# ───────────── comparing and averaging models ─────────────
def compare_fits(fits):
    """Add ΔAICc and Akaike weights (shares of support that add up to 1); return the best model."""
    scored = [f for f in fits if f["converged"] and f["aicc"] is not None]
    if not scored:
        return None
    lowest = min(f["aicc"] for f in scored)
    support = [math.exp(-0.5 * (f["aicc"] - lowest)) for f in scored]
    for f, s in zip(scored, support):
        f["delta_aicc"] = f["aicc"] - lowest
        f["akaike_weight"] = s / sum(support)
    return min(scored, key=lambda f: f["aicc"])["model"]


def model_average(fits, seed=42, n_draws=4000):
    """Each weaning age averaged over the models, weighted by their support.

    The interval comes from mixing the models' own random draws in the same proportions.
    """
    rng = np.random.default_rng(seed)
    average = {}
    for key in MILESTONES:
        members = [f for f in fits if f["akaike_weight"] is not None and f.get(key)]
        if not members:
            continue
        weights = np.array([f["akaike_weight"] for f in members])
        weights = weights / weights.sum()
        estimate = float(sum(w * f[key]["estimate"] for w, f in zip(weights, members)))
        low = high = None
        if all(len(f["_draws"].get(key, [])) for f in members):
            counts = rng.multinomial(n_draws, weights)
            mixed = np.concatenate([rng.choice(f["_draws"][key], c) for f, c in zip(members, counts) if c])
            low, high = interval(mixed)
        average[key] = {"estimate": estimate, "ci_low": low, "ci_high": high}
    return average


def seasonal_test(t, values, period=12.0, detrend=1, shape=None):
    """Is there a yearly up-and-down cycle in `values`? Returns (size of the cycle, p-value).

    Compares a straight-line trend with the same trend plus a sine wave (an F-test).
    `shape` (optional) is another pattern to allow for first, e.g. the weaning curve,
    so that a one-off step at weaning is not mistaken for a yearly cycle.
    Returns None if the series is too short or covers less than 3/4 of a year.
    """
    t, v = np.asarray(t, dtype=float), np.asarray(values, dtype=float)
    keep = np.isfinite(t) & np.isfinite(v)
    t, v = t[keep], v[keep]
    trend = np.vander(t - t.mean(), detrend + 1)
    if shape is not None and np.ptp(np.asarray(shape)[keep]) > 0:
        trend = np.column_stack([trend, np.asarray(shape, dtype=float)[keep]])
    if len(t) < trend.shape[1] + 5 or np.ptp(t) < 0.75 * period:
        return None
    angle = 2 * math.pi * t / period
    with_wave = np.column_stack([trend, np.sin(angle), np.cos(angle)])
    leftover_trend = np.sum((v - trend @ np.linalg.lstsq(trend, v, rcond=None)[0]) ** 2)
    coef = np.linalg.lstsq(with_wave, v, rcond=None)[0]
    leftover_wave = np.sum((v - with_wave @ coef) ** 2)
    spare = len(t) - with_wave.shape[1]
    if leftover_wave <= 0 or spare <= 0:
        return None
    f_stat = ((leftover_trend - leftover_wave) / 2) / (leftover_wave / spare)
    return float(math.hypot(coef[-2], coef[-1])), float(stats.f.sf(f_stat, 2, spare))
