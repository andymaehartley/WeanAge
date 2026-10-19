"""Weaning curve models and the SciPy fitting engine.

Each model describes δ15N as a function of age (months). All three share the same
two "level" parameters so their results are directly comparable:

* ``post``  - post-weaning (adult diet) δ15N plateau
* ``drop``  - nursing enrichment above that plateau (‰, constrained >= 0)

so the nursing plateau is ``post + drop``. They differ in the shape of the
transition, which is exactly the methodological choice whose effect on weaning-age
estimates the project sets out to measure.

A fourth, non-parametric method re-implements the elbow approach of WEAN
(Ganiatsou et al. 2023) so its estimates can be compared side by side.

Optionally each sample can be treated as the average of the curve over the age
window its increment spans (time averaging, after Tsutaya 2020 / MDSS); the
milestones then refer to the underlying, un-averaged dietary curve.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from typing import Callable

import numpy as np
from scipy.optimize import OptimizeWarning, curve_fit

from .schema import FitResult, ModelName, ValueWithCI

Milestones = dict[str, float]


def _logistic(t, post, drop, t_mid, scale):
    z = np.clip((np.asarray(t, dtype=float) - t_mid) / scale, -60, 60)
    return post + drop / (1.0 + np.exp(z))


def _piecewise(t, post, drop, t_start, duration):
    t = np.asarray(t, dtype=float)
    frac = np.clip((t - t_start) / duration, 0.0, 1.0)
    return post + drop * (1.0 - frac)


def _exponential(t, post, drop, t_start, tau):
    t = np.asarray(t, dtype=float)
    elapsed = np.clip(t - t_start, 0.0, None)
    return post + drop * np.exp(-elapsed / tau)


def _logistic_milestones(p: np.ndarray, q: float) -> Milestones:
    _, _, t_mid, scale = p
    half_width = scale * math.log((1 - q) / q)
    return {"onset": t_mid - half_width, "midpoint": t_mid, "completion": t_mid + half_width}


def _piecewise_milestones(p: np.ndarray, q: float) -> Milestones:
    _, _, t_start, duration = p
    return {"onset": t_start, "midpoint": t_start + duration / 2, "completion": t_start + duration}


def _exponential_milestones(p: np.ndarray, q: float) -> Milestones:
    _, _, t_start, tau = p
    return {
        "onset": t_start,
        "midpoint": t_start + tau * math.log(2),
        "completion": t_start + tau * math.log(1 / q),
    }


@dataclass(frozen=True)
class CurveModel:
    name: ModelName
    label: str
    description: str
    param_names: tuple[str, str, str, str]
    func: Callable[..., np.ndarray]
    milestones: Callable[[np.ndarray, float], Milestones]

    def starts(self, t: np.ndarray, y: np.ndarray) -> list[list[float]]:
        """Multi-start initial guesses spread across the sampled age range."""
        span = max(float(np.ptp(t)), 1.0)
        post = float(np.percentile(y, 15))
        drop = max(float(np.percentile(y, 85)) - post, 0.5)
        guesses = []
        for frac in (0.15, 0.3, 0.45, 0.6, 0.75):
            centre = float(t.min()) + frac * span
            for width in (0.1, 0.25):
                w = width * span
                if self.name == "logistic":
                    guesses.append([post, drop, centre, w / 3])
                else:
                    guesses.append([post, drop, centre - w, w])
        return guesses

    def bounds(
        self, t: np.ndarray, y: np.ndarray, post_range: tuple[float, float] | None = None
    ) -> tuple[list[float], list[float]]:
        span = max(float(np.ptp(t)), 1.0)
        lo_t, hi_t = float(t.min()) - span, float(t.max()) + span
        y_lo, y_hi = post_range or (float(y.min()) - 5, float(y.max()) + 5)
        lower = [y_lo, 0.0, lo_t, span * 1e-3]
        upper = [y_hi, max(float(np.ptp(y)) * 3, 1.0), hi_t, span * 4]
        return lower, upper


MODELS: dict[str, CurveModel] = {
    "logistic": CurveModel(
        "logistic",
        "Logistic (sigmoid)",
        "Smooth S-shaped decline from the nursing to the adult plateau. Onset and "
        "completion are where the curve has covered the chosen threshold of the drop.",
        ("post", "drop", "t_mid", "scale"),
        _logistic,
        _logistic_milestones,
    ),
    "piecewise": CurveModel(
        "piecewise",
        "Piecewise linear (broken stick)",
        "Flat nursing plateau, straight-line decline, flat adult plateau. Onset and "
        "completion are the two breakpoints.",
        ("post", "drop", "t_start", "duration"),
        _piecewise,
        _piecewise_milestones,
    ),
    "exponential": CurveModel(
        "exponential",
        "Exponential decay",
        "Nursing plateau followed by an abrupt start to weaning and an exponential "
        "approach to the adult value (fast early change, slowing later).",
        ("post", "drop", "t_start", "tau"),
        _exponential,
        _exponential_milestones,
    ),
}


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
            func,
            t,
            y,
            p0=np.clip(p0, np.array(bounds[0]) + 1e-9, np.array(bounds[1]) - 1e-9),
            sigma=sigma,
            absolute_sigma=sigma is not None,
            bounds=bounds,
            method="trf",
            maxfev=20000,
        )
    sse = float(np.sum((y - func(t, *popt)) ** 2))
    return popt, pcov, sse


def _ci(values: np.ndarray) -> tuple[float | None, float | None]:
    values = values[np.isfinite(values)]
    if values.size < 20:
        return None, None
    lo, hi = np.percentile(values, [2.5, 97.5])
    return float(lo), float(hi)


def fit_model(
    name: ModelName,
    age: np.ndarray,
    d15n: np.ndarray,
    *,
    threshold: float = 0.05,
    analytical_sd: float | None = None,
    min_drop: float = 1.0,
    draws: int = 1000,
    seed: int | None = 42,
    curve_points: int = 200,
    age_uncertainty: float = 0.0,
    age_windows: np.ndarray | None = None,
    post_range: tuple[float, float] | None = None,
    adult_baseline: float | None = None,
    elbow_normalise: bool = True,
) -> FitResult:
    """Fit one model and derive weaning milestones with Monte Carlo 95 % intervals.

    ``age_uncertainty`` (months, 1 SD) from the tooth growth table is added in
    quadrature to the milestone intervals. ``age_windows`` (n × k ages, one row per
    sample) switches on time averaging: each sample is predicted as the mean of the
    curve over its row. ``post_range`` bounds the adult plateau, and
    ``adult_baseline`` (adult-female mean δ15N) is used to report nursing enrichment.
    """
    t = np.asarray(age, dtype=float)
    y = np.asarray(d15n, dtype=float)
    order = np.argsort(t)
    t, y = t[order], y[order]
    if name == "elbow":
        result = fit_elbow(
            t, y, analytical_sd=analytical_sd, min_drop=min_drop, draws=draws, seed=seed,
            curve_points=curve_points, age_uncertainty=age_uncertainty, normalise=elbow_normalise,
        )
        _set_enrichment(result, adult_baseline)
        return result

    model = MODELS[name]
    n = t.size
    result = FitResult(model=name, label=model.label, converged=False)

    if n < len(model.param_names) + 1:
        result.message = f"Need at least {len(model.param_names) + 1} samples, got {n}"
        return result

    sigma = np.full(n, analytical_sd) if analytical_sd else None
    bounds = model.bounds(t, y, post_range)
    func = model.func
    if age_windows is not None:
        windows = np.asarray(age_windows, dtype=float)[order]

        def func(_t, *p):
            return model.func(windows, *p).mean(axis=1)

    best = None
    for p0 in model.starts(t, y):
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
    result.converged = True
    result.params = {k: float(v) for k, v in zip(model.param_names, popt)}
    diag = np.diag(pcov) if np.all(np.isfinite(pcov)) else np.full(len(popt), np.nan)
    result.param_se = {
        k: (float(math.sqrt(v)) if np.isfinite(v) and v >= 0 else None)
        for k, v in zip(model.param_names, diag)
    }
    post, drop = float(popt[0]), float(popt[1])
    result.adult_d15N, result.nursing_d15N, result.drop_permil = post, post + drop, drop

    resid = y - func(t, *popt)
    result.rmse = float(math.sqrt(np.mean(resid**2)))
    sst = float(np.sum((y - y.mean()) ** 2))
    result.r2 = float(1 - sse / sst) if sst > 0 else None
    result.aicc = aicc(sse, n, len(popt))

    point = model.milestones(popt, threshold)
    samples = _monte_carlo(model, popt, pcov, bounds, threshold, draws, seed)
    for key in ("onset", "midpoint", "completion"):
        lo, hi = _ci(samples[key]) if samples is not None else (None, None)
        if lo is not None and age_uncertainty > 0:
            half_lo = math.hypot(point[key] - lo, 1.96 * age_uncertainty)
            half_hi = math.hypot(hi - point[key], 1.96 * age_uncertainty)
            lo, hi = point[key] - half_lo, point[key] + half_hi
        setattr(result, key, ValueWithCI(estimate=float(point[key]), ci_low=lo, ci_high=hi))
    if samples is None:
        result.warnings.append("Parameter covariance unavailable: no confidence intervals")

    if drop < min_drop:
        result.warnings.append(
            f"δ15N drop of {drop:.2f}‰ is below the {min_drop:.2f}‰ minimum: no clear weaning signal"
        )
    if point["onset"] < t.min():
        result.warnings.append("Weaning onset falls before the first sample (nursing plateau not captured)")
    if point["completion"] > t.max():
        result.warnings.append("Weaning completion falls after the last sample (extrapolated)")

    grid = np.linspace(t.min(), t.max(), curve_points)
    result.curve_age = [round(float(v), 4) for v in grid]
    result.curve_d15N = [round(float(v), 4) for v in model.func(grid, *popt)]
    _set_enrichment(result, adult_baseline)
    return result


def _set_enrichment(result: FitResult, adult_baseline: float | None) -> None:
    if adult_baseline is not None and result.nursing_d15N is not None:
        result.enrichment_permil = result.nursing_d15N - adult_baseline


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


def fit_elbow(
    t: np.ndarray,
    y: np.ndarray,
    *,
    analytical_sd: float | None = None,
    min_drop: float = 1.0,
    draws: int = 1000,
    seed: int | None = 42,
    curve_points: int = 200,
    age_uncertainty: float = 0.0,
    normalise: bool = True,
    degree: int = 4,
) -> FitResult:
    """WEAN-style estimate: 4th-degree polynomial fit, weaning age at its elbow."""
    label = "Elbow on polynomial (WEAN-style)"
    result = FitResult(model="elbow", label=label, converged=False)
    n = t.size
    if n < degree + 3:
        result.message = f"Need at least {degree + 3} samples, got {n}"
        return result

    weights = np.full(n, 1 / analytical_sd) if analytical_sd else None
    # Centre ages for a well-conditioned polynomial fit.
    t0 = float(t.mean())
    coef, cov = np.polyfit(t - t0, y, degree, w=weights, cov="unscaled" if weights is not None else True)
    grid = np.linspace(t.min(), t.max(), curve_points)
    curve = np.polyval(coef, grid - t0)
    idx = _elbow_index(grid, curve, normalise)
    if idx is None:
        result.message = "δ15N peaks at the end of the series: no declining segment to analyse"
        return result

    peak, elbow = idx
    fitted = np.polyval(coef, t - t0)
    sse = float(np.sum((y - fitted) ** 2))
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

    lo = hi = None
    if draws > 0 and np.all(np.isfinite(cov)):
        rng = np.random.default_rng(seed)
        sims = rng.multivariate_normal(coef, cov, size=draws, check_valid="ignore")
        curves = sims @ np.vander(grid - t0, degree + 1).T
        ages = [grid[i[1]] for c in curves if (i := _elbow_index(grid, c, normalise)) is not None]
        lo, hi = _ci(np.asarray(ages))
        if lo is not None and age_uncertainty > 0:
            lo = t_elbow - math.hypot(t_elbow - lo, 1.96 * age_uncertainty)
            hi = t_elbow + math.hypot(hi - t_elbow, 1.96 * age_uncertainty)
    result.onset = ValueWithCI(estimate=float(grid[peak]))
    result.completion = ValueWithCI(estimate=t_elbow, ci_low=lo, ci_high=hi)

    slope = float(np.polyval(np.polyder(coef), t_elbow - t0))
    if slope > 0:
        result.warnings.append(
            f"Curve is rising at the elbow (slope {slope:+.2f}‰/month): possible false estimate"
        )
    if result.drop_permil < min_drop:
        result.warnings.append(
            f"δ15N drop of {result.drop_permil:.2f}‰ is below the {min_drop:.2f}‰ minimum: no clear weaning signal"
        )
    if elbow >= curve_points - 2:
        result.warnings.append("Elbow falls at the last sample: weaning may not be complete within the series")
    if curve.max() > y.max() + 0.5 or curve.min() < y.min() - 0.5:
        result.warnings.append(
            "Polynomial overshoots the observed δ15N range (>0.5‰); check the curve visually"
        )
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


def _monte_carlo(model, popt, pcov, bounds, threshold, draws, seed):
    if draws <= 0 or not np.all(np.isfinite(pcov)):
        return None
    rng = np.random.default_rng(seed)
    try:
        sims = rng.multivariate_normal(popt, pcov, size=draws, check_valid="ignore")
    except (np.linalg.LinAlgError, ValueError):
        return None
    sims = np.clip(sims, bounds[0], bounds[1])
    # Shape parameters must stay positive for the milestones to be defined.
    sims = sims[sims[:, 3] > 0]
    out: dict[str, list[float]] = {"onset": [], "midpoint": [], "completion": []}
    for p in sims:
        for key, value in model.milestones(p, threshold).items():
            out[key].append(value)
    return {k: np.asarray(v) for k, v in out.items()}


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
