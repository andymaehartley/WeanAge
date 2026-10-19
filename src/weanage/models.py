"""Weaning curve models and the SciPy fitting engine.

The parametric models describe δ15N as a function of age (months). All share the
two "level" parameters

* ``post``  - post-weaning (adult diet) δ15N plateau
* ``drop``  - nursing enrichment above that plateau (‰, constrained >= 0)

so the nursing plateau is ``post + drop``; they differ in the shape of the
transition, which is exactly the methodological choice whose effect on weaning-age
estimates the project sets out to measure. ``two_phase`` adds an intermediate
plateau (supplementary feeding while suckling continues, as expected where milk is
shared with people). A non-parametric ``elbow`` method re-implements WEAN
(Ganiatsou et al. 2023).

Options applied by :func:`fit_model`:

* time averaging (after Tsutaya 2020 / MDSS) - each sample is the weighted mean of
  the curve over the age window its increment spans;
* a seasonal term ``a·sin(2πt/P) + b·cos(2πt/P)`` added to any parametric curve;
* uncertainty from the parameter covariance or a residual bootstrap, with the
  growth-table age uncertainty applied as one shared offset per draw (an error in
  the age model moves every sample of a tooth together).
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field
from typing import Callable, Literal

import numpy as np
from scipy import stats
from scipy.optimize import OptimizeWarning, curve_fit

from .schema import FitResult, ModelName, ValueWithCI

Milestones = dict[str, float]
MILESTONES = ("onset", "midpoint", "completion")


# ───────────────────────── curve functions ─────────────────────────
def _desc(t, t_mid, scale):
    """Descending logistic step from 1 to 0 centred on ``t_mid``."""
    z = np.clip((np.asarray(t, dtype=float) - t_mid) / scale, -60, 60)
    return 1.0 / (1.0 + np.exp(z))


def _logistic(t, post, drop, t_mid, scale):
    return post + drop * _desc(t, t_mid, scale)


def _piecewise(t, post, drop, t_start, duration):
    t = np.asarray(t, dtype=float)
    frac = np.clip((t - t_start) / duration, 0.0, 1.0)
    return post + drop * (1.0 - frac)


def _exponential(t, post, drop, t_start, tau):
    t = np.asarray(t, dtype=float)
    elapsed = np.clip(t - t_start, 0.0, None)
    return post + drop * np.exp(-elapsed / tau)


def _two_phase(t, post, drop, first_fraction, t1, gap, scale):
    return post + drop * (
        first_fraction * _desc(t, t1, scale) + (1 - first_fraction) * _desc(t, t1 + gap, scale)
    )


# ───────────────────────── milestones ─────────────────────────
# Each accepts one parameter vector (k,) or a batch of draws (n, k) and returns
# floats or arrays accordingly.
def _logistic_milestones(p, q: float) -> Milestones:
    p = np.asarray(p, dtype=float)
    t_mid, scale = p[..., 2], p[..., 3]
    half_width = scale * math.log((1 - q) / q)
    return {"onset": t_mid - half_width, "midpoint": t_mid, "completion": t_mid + half_width}


def _piecewise_milestones(p, q: float) -> Milestones:
    p = np.asarray(p, dtype=float)
    t_start, duration = p[..., 2], p[..., 3]
    return {"onset": t_start, "midpoint": t_start + duration / 2, "completion": t_start + duration}


def _exponential_milestones(p, q: float) -> Milestones:
    p = np.asarray(p, dtype=float)
    t_start, tau = p[..., 2], p[..., 3]
    return {
        "onset": t_start,
        "midpoint": t_start + tau * math.log(2),
        "completion": t_start + tau * math.log(1 / q),
    }


def _two_phase_milestones(p, q: float) -> Milestones:
    p = np.asarray(p, dtype=float)
    post, drop, f, t1, gap, scale = (p[..., i] for i in range(6))
    half_width = scale * math.log((1 - q) / q)
    # Midpoint: where half the total drop has happened (vectorised bisection on the
    # monotone curve).
    lo, hi = t1 - 10 * scale, t1 + gap + 10 * scale
    target = post + drop / 2
    for _ in range(40):
        mid = (lo + hi) / 2
        above = _two_phase(mid, post, drop, f, t1, gap, scale) > target
        lo, hi = np.where(above, mid, lo), np.where(above, hi, mid)
    return {"onset": t1 - half_width, "midpoint": (lo + hi) / 2, "completion": t1 + gap + half_width}


# ───────────────────────── starts & bounds ─────────────────────────
def _levels(y):
    post = float(np.percentile(y, 15))
    drop = max(float(np.percentile(y, 85)) - post, 0.5)
    return post, drop


def _span(t):
    return max(float(np.ptp(t)), 1.0)


def _base_bounds(t, y, post_range):
    span = _span(t)
    y_lo, y_hi = post_range or (float(y.min()) - 5, float(y.max()) + 5)
    max_drop = max(float(np.ptp(y)) * 3, 1.0)
    return span, (y_lo, y_hi), max_drop, float(t.min()) - span, float(t.max()) + span


def _four_param_bounds(t, y, post_range):
    span, (y_lo, y_hi), max_drop, lo_t, hi_t = _base_bounds(t, y, post_range)
    return [y_lo, 0.0, lo_t, span * 1e-3], [y_hi, max_drop, hi_t, span * 4]


def _four_param_starts(kind):
    def starts(t, y):
        span, (post, drop) = _span(t), _levels(y)
        out = []
        for frac in (0.15, 0.3, 0.45, 0.6, 0.75):
            centre = float(t.min()) + frac * span
            for width in (0.1, 0.25):
                w = width * span
                out.append([post, drop, centre, w / 3] if kind == "logistic" else [post, drop, centre - w, w])
        return out

    return starts


def _two_phase_bounds(t, y, post_range):
    span, (y_lo, y_hi), max_drop, lo_t, hi_t = _base_bounds(t, y, post_range)
    return [y_lo, 0.0, 0.05, lo_t, span * 0.02, span * 1e-3], [y_hi, max_drop, 0.95, hi_t, span * 2, span]


def _two_phase_starts(t, y):
    span, (post, drop) = _span(t), _levels(y)
    out = []
    for t1_frac in (0.15, 0.3, 0.45):
        for gap_frac in (0.15, 0.3):
            for f in (0.3, 0.6):
                out.append([post, drop, f, float(t.min()) + t1_frac * span, gap_frac * span, span * 0.03])
    return out


@dataclass(frozen=True)
class CurveModel:
    name: ModelName
    label: str
    description: str
    param_names: tuple[str, ...]
    func: Callable[..., np.ndarray]
    milestones: Callable[..., Milestones]
    starts: Callable[[np.ndarray, np.ndarray], list[list[float]]]
    bounds: Callable[..., tuple[list[float], list[float]]]

    @property
    def n_params(self) -> int:
        return len(self.param_names)


MODELS: dict[str, CurveModel] = {
    "logistic": CurveModel(
        "logistic",
        "Logistic (sigmoid)",
        "Smooth S-shaped decline from the nursing to the adult plateau. Onset and "
        "completion are where the curve has covered the chosen threshold of the drop.",
        ("post", "drop", "t_mid", "scale"),
        _logistic, _logistic_milestones, _four_param_starts("logistic"), _four_param_bounds,
    ),
    "piecewise": CurveModel(
        "piecewise",
        "Piecewise linear (broken stick)",
        "Flat nursing plateau, straight-line decline, flat adult plateau. Onset and "
        "completion are the two breakpoints.",
        ("post", "drop", "t_start", "duration"),
        _piecewise, _piecewise_milestones, _four_param_starts("piecewise"), _four_param_bounds,
    ),
    "exponential": CurveModel(
        "exponential",
        "Exponential decay",
        "Nursing plateau followed by an abrupt start to weaning and an exponential "
        "approach to the adult value (fast early change, slowing later).",
        ("post", "drop", "t_start", "tau"),
        _exponential, _exponential_milestones, _four_param_starts("exponential"), _four_param_bounds,
    ),
    "two_phase": CurveModel(
        "two_phase",
        "Two-phase (staged weaning)",
        "Two logistic steps with an intermediate plateau: early supplementary feeding "
        "while suckling continues, then final weaning. Expected where milk was shared "
        "with people (dairying). Compare its AICc with the logistic model.",
        ("post", "drop", "first_fraction", "t1", "gap", "scale"),
        _two_phase, _two_phase_milestones, _two_phase_starts, _two_phase_bounds,
    ),
}


# ───────────────────────── settings ─────────────────────────
@dataclass
class FitSettings:
    threshold: float = 0.05
    analytical_sd: float | None = None
    min_drop: float = 1.0
    draws: int = 1000
    seed: int | None = 42
    curve_points: int = 200
    age_uncertainty: float = 0.0
    age_windows: np.ndarray | None = None
    window_weights: np.ndarray | None = None
    post_range: tuple[float, float] | None = None
    adult_baseline: float | None = None
    elbow_normalise: bool = True
    seasonal: bool = False
    season_period: float = 12.0
    uncertainty: Literal["covariance", "bootstrap"] = "covariance"
    bootstrap_draws: int = 200
    extra: dict = field(default_factory=dict)


def aicc(sse: float, n: int, n_params: int) -> float | None:
    """Small-sample corrected AIC for least squares (variance counted as a parameter)."""
    k = n_params + 1
    if n - k - 1 <= 0 or sse <= 0:
        return None
    return n * math.log(sse / n) + 2 * k + (2 * k * (k + 1)) / (n - k - 1)


def _fit_once(func, t, y, sigma, p0, bounds):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", OptimizeWarning)
        warnings.simplefilter("ignore", RuntimeWarning)
        popt, pcov = curve_fit(
            func, t, y,
            p0=np.clip(p0, np.array(bounds[0]) + 1e-9, np.array(bounds[1]) - 1e-9),
            sigma=sigma, absolute_sigma=sigma is not None,
            bounds=bounds, method="trf", maxfev=20000,
        )
    sse = float(np.sum((y - func(t, *popt)) ** 2))
    return popt, pcov, sse


def _ci(values: np.ndarray) -> tuple[float | None, float | None]:
    values = values[np.isfinite(values)]
    if values.size < 20:
        return None, None
    lo, hi = np.percentile(values, [2.5, 97.5])
    return float(lo), float(hi)


def _summarise(result: FitResult, point: Milestones, draws: dict[str, np.ndarray] | None,
               age_sd: float, rng: np.random.Generator) -> None:
    """Attach milestone estimates and intervals; age-model error is one shared shift per draw."""
    stored: dict[str, np.ndarray] = {}
    for key, estimate in point.items():
        lo = hi = None
        if draws is not None and draws.get(key) is not None and draws[key].size:
            values = draws[key].copy()
            if age_sd > 0:
                values = values + rng.normal(0, age_sd, values.size)
            lo, hi = _ci(values)
            stored[key] = values
        setattr(result, key, ValueWithCI(estimate=float(estimate), ci_low=lo, ci_high=hi))
    result._draws = stored


def _seasonal_terms(t, period):
    w = 2 * math.pi / period
    t = np.asarray(t, dtype=float)
    return np.sin(w * t), np.cos(w * t)


def fit_model(name: ModelName, age, d15n, settings: FitSettings | None = None, **kwargs) -> FitResult:
    """Fit one model and derive weaning milestones with 95 % intervals."""
    s = settings or FitSettings(**kwargs)
    t = np.asarray(age, dtype=float)
    y = np.asarray(d15n, dtype=float)
    order = np.argsort(t, kind="stable")
    t, y = t[order], y[order]
    windows = np.asarray(s.age_windows, dtype=float)[order] if s.age_windows is not None else None
    if name == "elbow":
        result = fit_elbow(t, y, s)
    else:
        result = _fit_parametric(MODELS[name], t, y, windows, s)
    if s.adult_baseline is not None and result.nursing_d15N is not None:
        result.enrichment_permil = result.nursing_d15N - s.adult_baseline
    return result


def _fit_parametric(model: CurveModel, t, y, windows, s: FitSettings) -> FitResult:
    n, k = t.size, model.n_params
    label = model.label + (" + seasonal" if s.seasonal else "")
    result = FitResult(model=model.name, label=label, converged=False)
    n_total = k + (2 if s.seasonal else 0)
    if n < n_total + 2:
        result.message = f"Need at least {n_total + 2} samples, got {n}"
        return result

    def curve(tt, *p):
        out = model.func(tt, *p[:k])
        if s.seasonal:
            sin, cos = _seasonal_terms(tt, s.season_period)
            out = out + p[k] * sin + p[k + 1] * cos
        return out

    if windows is not None:
        wts = s.window_weights if s.window_weights is not None else np.ones(windows.shape[1])
        wts = np.asarray(wts, dtype=float) / np.sum(wts)

        def func(_t, *p):
            return curve(windows, *p) @ wts
    else:
        func = curve

    lower, upper = model.bounds(t, y, s.post_range)
    starts = model.starts(t, y)
    if s.seasonal:
        amp = max(float(np.ptp(y)), 0.5)
        lower, upper = lower + [-amp, -amp], upper + [amp, amp]
        starts = [p + [0.0, 0.0] for p in starts]
    bounds = (lower, upper)

    sigma = np.full(n, s.analytical_sd) if s.analytical_sd else None
    best = None
    for p0 in starts:
        try:
            popt, pcov, sse = _fit_once(func, t, y, sigma, p0, bounds)
        except (RuntimeError, ValueError):
            continue
        if best is None or sse < best[2]:
            best = (popt, pcov, sse)
    if best is None:
        result.message = "Optimiser did not converge from any starting point"
        return result

    popt, pcov, sse = best
    names = list(model.param_names) + (["season_sin", "season_cos"] if s.seasonal else [])
    result.converged = True
    result.params = {nm: float(v) for nm, v in zip(names, popt)}
    diag = np.diag(pcov) if np.all(np.isfinite(pcov)) else np.full(len(popt), np.nan)
    result.param_se = {
        nm: (float(math.sqrt(v)) if np.isfinite(v) and v >= 0 else None) for nm, v in zip(names, diag)
    }
    post, drop = float(popt[0]), float(popt[1])
    result.adult_d15N, result.nursing_d15N, result.drop_permil = post, post + drop, drop
    if model.name == "two_phase":
        f, gap = float(popt[2]), float(popt[4])
        result.extra["intermediate_d15N"] = post + drop * (1 - f)
        result.extra["first_phase_fraction"] = f
        result.extra["supplementation_months"] = gap
    if s.seasonal:
        result.extra["seasonal_amplitude_permil"] = float(math.hypot(popt[k], popt[k + 1]))

    fitted = func(t, *popt)
    resid = y - fitted
    result.rmse = float(math.sqrt(np.mean(resid**2)))
    sst = float(np.sum((y - y.mean()) ** 2))
    result.r2 = float(1 - sse / sst) if sst > 0 else None
    result.aicc = aicc(sse, n, len(popt))

    rng = np.random.default_rng(s.seed)
    point = model.milestones(popt, s.threshold)
    if s.uncertainty == "bootstrap":
        draws = _bootstrap(func, model, t, fitted, resid, sigma, popt, bounds, s, rng)
    else:
        draws = _covariance_draws(model, popt, pcov, bounds, s, rng)
    _summarise(result, point, draws, s.age_uncertainty, rng)
    if draws is None:
        result.warnings.append("Parameter uncertainty unavailable: no confidence intervals")

    if drop < s.min_drop:
        result.warnings.append(
            f"δ15N drop of {drop:.2f}‰ is below the {s.min_drop:.2f}‰ minimum: no clear weaning signal"
        )
    if point["onset"] < t.min():
        result.warnings.append("Weaning onset falls before the first sample (nursing plateau not captured)")
    if point["completion"] > t.max():
        result.warnings.append("Weaning completion falls after the last sample (extrapolated)")

    grid = np.linspace(t.min(), t.max(), s.curve_points)
    result.curve_age = [round(float(v), 4) for v in grid]
    result.curve_d15N = [round(float(v), 4) for v in curve(grid, *popt)]
    return result


def _milestone_draws(model, sims, threshold):
    return {k: np.asarray(v, dtype=float) for k, v in model.milestones(np.asarray(sims), threshold).items()}


def _covariance_draws(model, popt, pcov, bounds, s: FitSettings, rng):
    if s.draws <= 0 or not np.all(np.isfinite(pcov)):
        return None
    try:
        sims = rng.multivariate_normal(popt, pcov, size=s.draws, check_valid="ignore")
    except (np.linalg.LinAlgError, ValueError):
        return None
    sims = np.clip(sims, bounds[0], bounds[1])
    return _milestone_draws(model, sims, s.threshold)


def _bootstrap(func, model, t, fitted, resid, sigma, popt, bounds, s: FitSettings, rng):
    """Residual bootstrap: refit to fitted + resampled residuals, starting from the best fit."""
    if s.bootstrap_draws <= 0:
        return None
    sims = []
    for _ in range(s.bootstrap_draws):
        y_b = fitted + rng.choice(resid, size=resid.size, replace=True)
        try:
            p_b, _, _ = _fit_once(func, t, y_b, sigma, popt, bounds)
        except (RuntimeError, ValueError):
            continue
        sims.append(p_b)
    if len(sims) < 20:
        return None
    return _milestone_draws(model, np.asarray(sims), s.threshold)


# ───────────────────────── elbow (WEAN) ─────────────────────────
def _elbow_index(grid: np.ndarray, curve: np.ndarray, normalise: bool) -> tuple[int, int] | None:
    """Indices of (peak, elbow) on a fitted curve.

    Following WEAN, the elbow is the point of greatest perpendicular distance below
    the straight line joining the curve's maximum to its last point. With
    ``normalise`` both axes are rescaled to [0, 1] first, so the result does not
    depend on the units (months vs ‰); WEAN itself uses raw units.
    """
    start = int(np.argmax(curve))
    if grid.size - start < 3:
        return None
    x, y = grid[start:], curve[start:]
    if normalise:
        x = (x - x[0]) / ((x[-1] - x[0]) or 1.0)
        y = (y - y.min()) / ((y.max() - y.min()) or 1.0)
    dx, dy = x[-1] - x[0], y[-1] - y[0]
    # Signed distance: positive when the curve sags below the chord (a convex decline).
    dist = (dy * (x - x[0]) - dx * (y - y[0])) / (np.hypot(dx, dy) or 1.0)
    return start, start + int(np.argmax(dist))


def fit_elbow(t: np.ndarray, y: np.ndarray, s: FitSettings | None = None, degree: int = 4) -> FitResult:
    """WEAN-style estimate: 4th-degree polynomial fit, weaning age at its elbow."""
    s = s or FitSettings()
    result = FitResult(model="elbow", label="Elbow on polynomial (WEAN-style)", converged=False)
    n = t.size
    if n < degree + 3:
        result.message = f"Need at least {degree + 3} samples, got {n}"
        return result

    weights = np.full(n, 1 / s.analytical_sd) if s.analytical_sd else None
    t0 = float(t.mean())  # centred ages keep the polynomial well conditioned
    coef, cov = np.polyfit(t - t0, y, degree, w=weights, cov="unscaled" if weights is not None else True)
    grid = np.linspace(t.min(), t.max(), s.curve_points)
    vander = np.vander(grid - t0, degree + 1)
    curve = vander @ coef
    idx = _elbow_index(grid, curve, s.elbow_normalise)
    if idx is None:
        result.message = "δ15N peaks at the end of the series: no declining segment to analyse"
        return result

    peak, elbow = idx
    fitted = np.polyval(coef, t - t0)
    resid = y - fitted
    sse = float(np.sum(resid**2))
    sst = float(np.sum((y - y.mean()) ** 2))
    result.converged = True
    result.params = {f"c{degree - i}": float(c) for i, c in enumerate(coef)}
    se = np.sqrt(np.clip(np.diag(cov), 0, None)) if np.all(np.isfinite(cov)) else [None] * len(coef)
    result.param_se = {f"c{degree - i}": (float(v) if v is not None else None) for i, v in enumerate(se)}
    result.rmse = float(np.sqrt(sse / n))
    result.r2 = float(1 - sse / sst) if sst > 0 else None
    result.aicc = aicc(sse, n, degree + 1)

    t_elbow = float(grid[elbow])
    post_mask = t >= t_elbow
    result.nursing_d15N = float(curve[peak])
    result.adult_d15N = float(y[post_mask].mean()) if post_mask.any() else float(curve[-1])
    result.drop_permil = result.nursing_d15N - result.adult_d15N

    rng = np.random.default_rng(s.seed)
    sims = None
    if s.uncertainty == "bootstrap" and s.bootstrap_draws > 0:
        sims = np.array([
            np.polyfit(t - t0, fitted + rng.choice(resid, n), degree, w=weights)
            for _ in range(s.bootstrap_draws)
        ])
    elif s.draws > 0 and np.all(np.isfinite(cov)):
        sims = rng.multivariate_normal(coef, cov, size=s.draws, check_valid="ignore")
    draws = None
    if sims is not None:
        ages = [grid[i[1]] for c in sims @ vander.T if (i := _elbow_index(grid, c, s.elbow_normalise))]
        draws = {"completion": np.asarray(ages)}
    _summarise(result, {"completion": t_elbow}, draws, s.age_uncertainty, rng)
    result.onset = ValueWithCI(estimate=float(grid[peak]))

    slope = float(np.polyval(np.polyder(coef), t_elbow - t0))
    if slope > 0:
        result.warnings.append(
            f"Curve is rising at the elbow (slope {slope:+.2f}‰/month): possible false estimate"
        )
    if result.drop_permil < s.min_drop:
        result.warnings.append(
            f"δ15N drop of {result.drop_permil:.2f}‰ is below the {s.min_drop:.2f}‰ minimum: no clear weaning signal"
        )
    if elbow >= s.curve_points - 2:
        result.warnings.append("Elbow falls at the last sample: weaning may not be complete within the series")
    if curve.max() > y.max() + 0.5 or curve.min() < y.min() - 0.5:
        result.warnings.append("Polynomial overshoots the observed δ15N range (>0.5‰); check the curve visually")
    result.curve_age = [round(float(v), 4) for v in grid]
    result.curve_d15N = [round(float(v), 4) for v in curve]
    return result


MODEL_CATALOG = [
    {"name": m.name, "label": m.label, "description": m.description, "params": list(m.param_names)}
    for m in MODELS.values()
] + [
    {
        "name": "elbow",
        "label": "Elbow on polynomial (WEAN-style)",
        "description": "Re-implementation of WEAN (Ganiatsou et al. 2023): a 4th-degree polynomial "
        "is fitted and weaning completion is the 'elbow', the point farthest below the line from "
        "the δ15N peak to the last sample. Reports completion only.",
        "params": ["c4", "c3", "c2", "c1", "c0"],
    }
]
MODEL_NAMES = {m["name"] for m in MODEL_CATALOG}


# ───────────────────────── comparison & averaging ─────────────────────────
def compare_fits(fits: list[FitResult]) -> ModelName | None:
    """Fill in ΔAICc and Akaike weights; return the best-supported model."""
    scored = [f for f in fits if f.converged and f.aicc is not None]
    if not scored:
        return None
    best = min(f.aicc for f in scored)
    rel = {f.model: math.exp(-0.5 * (f.aicc - best)) for f in scored}
    total = sum(rel.values())
    for f in scored:
        f.delta_aicc = f.aicc - best
        f.akaike_weight = rel[f.model] / total
    return min(scored, key=lambda f: f.aicc).model


def model_average(fits: list[FitResult], seed: int | None = 42, n_draws: int = 4000) -> dict[str, ValueWithCI]:
    """Akaike-weighted average of each milestone across models.

    The point estimate is the weighted mean over the models that report the
    milestone (weights renormalised); the interval comes from a weighted mixture of
    the models' own Monte Carlo / bootstrap draws.
    """
    rng = np.random.default_rng(seed)
    out: dict[str, ValueWithCI] = {}
    for key in MILESTONES:
        members = [
            (f, getattr(f, key)) for f in fits
            if f.akaike_weight is not None and getattr(f, key) is not None
            and getattr(f, key).estimate is not None
        ]
        if not members:
            continue
        w = np.array([f.akaike_weight for f, _ in members])
        w = w / w.sum()
        estimate = float(np.sum(w * [v.estimate for _, v in members]))
        pools = [(wi, f._draws.get(key)) for wi, (f, _) in zip(w, members)]
        lo = hi = None
        if all(p is not None and p.size for _, p in pools):
            counts = rng.multinomial(n_draws, w)
            mix = np.concatenate([rng.choice(p, c) for (_, p), c in zip(pools, counts) if c])
            lo, hi = _ci(mix)
        out[key] = ValueWithCI(estimate=estimate, ci_low=lo, ci_high=hi)
    return out


# ───────────────────────── seasonality diagnostics ─────────────────────────
def seasonal_test(t, values, period: float = 12.0, detrend: int = 1) -> tuple[float, float] | None:
    """F-test for an annual sinusoid in a series after removing a polynomial trend.

    Returns ``(amplitude, p_value)`` or ``None`` when the series spans too little
    of a cycle (< 0.75 period) or is too short to test.
    """
    t = np.asarray(t, dtype=float)
    v = np.asarray(values, dtype=float)
    mask = np.isfinite(t) & np.isfinite(v)
    t, v = t[mask], v[mask]
    if t.size < detrend + 6 or np.ptp(t) < 0.75 * period:
        return None
    base = np.vander(t - t.mean(), detrend + 1)
    sin, cos = _seasonal_terms(t, period)
    full = np.column_stack([base, sin, cos])
    rss0 = float(np.sum((v - base @ np.linalg.lstsq(base, v, rcond=None)[0]) ** 2))
    coef, *_ = np.linalg.lstsq(full, v, rcond=None)
    rss1 = float(np.sum((v - full @ coef) ** 2))
    df1, df2 = 2, t.size - full.shape[1]
    if rss1 <= 0 or df2 <= 0:
        return None
    f_stat = ((rss0 - rss1) / df1) / (rss1 / df2)
    return float(math.hypot(coef[-2], coef[-1])), float(stats.f.sf(f_stat, df1, df2))
