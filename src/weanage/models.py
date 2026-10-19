"""Weaning curve models and the SciPy fitting engine.

Each model describes δ15N as a function of age (months). All three share the same
two "level" parameters so their results are directly comparable:

* ``post``  - post-weaning (adult diet) δ15N plateau
* ``drop``  - nursing enrichment above that plateau (‰, constrained >= 0)

so the nursing plateau is ``post + drop``. They differ in the shape of the
transition, which is exactly the methodological choice whose effect on weaning-age
estimates the project sets out to measure.
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

    def bounds(self, t: np.ndarray, y: np.ndarray) -> tuple[list[float], list[float]]:
        span = max(float(np.ptp(t)), 1.0)
        lo_t, hi_t = float(t.min()) - span, float(t.max()) + span
        y_lo, y_hi = float(y.min()) - 5, float(y.max()) + 5
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


def _fit_once(model: CurveModel, t, y, sigma, p0, bounds):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", OptimizeWarning)
        warnings.simplefilter("ignore", RuntimeWarning)
        popt, pcov = curve_fit(
            model.func,
            t,
            y,
            p0=np.clip(p0, np.array(bounds[0]) + 1e-9, np.array(bounds[1]) - 1e-9),
            sigma=sigma,
            absolute_sigma=sigma is not None,
            bounds=bounds,
            method="trf",
            maxfev=20000,
        )
    sse = float(np.sum((y - model.func(t, *popt)) ** 2))
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
) -> FitResult:
    """Fit one model and derive weaning milestones with Monte Carlo 95 % intervals.

    ``age_uncertainty`` (months, 1 SD) from the tooth growth table is added in
    quadrature to the milestone intervals.
    """
    model = MODELS[name]
    t = np.asarray(age, dtype=float)
    y = np.asarray(d15n, dtype=float)
    order = np.argsort(t)
    t, y = t[order], y[order]
    n = t.size
    result = FitResult(model=name, label=model.label, converged=False)

    if n < len(model.param_names) + 1:
        result.message = f"Need at least {len(model.param_names) + 1} samples, got {n}"
        return result

    sigma = np.full(n, analytical_sd) if analytical_sd else None
    bounds = model.bounds(t, y)
    best = None
    for p0 in model.starts(t, y):
        try:
            popt, pcov, sse = _fit_once(model, t, y, sigma, p0, bounds)
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

    resid = y - model.func(t, *popt)
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
    return result


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
