"""Simulation study for sampling design.

Generates synthetic teeth with known weaning ages, samples them the way a lab would
(increment interval and height, oblique growth layers, measurement noise, missing
or failed samples), runs the normal analysis and scores every model against the
truth. Sweeping one setting (e.g. 0.5 vs 1 vs 2 mm increments) shows how accuracy
depends on the sampling protocol before any tooth is cut.
"""

from __future__ import annotations

import math
from typing import Callable, Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from .analysis import analyze, estimate_rows
from .config import find_growth_table
from .growth import position_to_age
from .schema import AnalysisOptions, IsotopeSample, LinearGrowthOverride
from .validation import error_metrics, interval_coverage

SweepParam = Literal[
    "sampling_interval_mm", "increment_width_mm", "noise_sd", "missing_fraction",
    "growth_layer_offset_mm", "n_specimens",
]


class SimulationScenario(BaseModel):
    species: str = "cattle"
    tooth: str = "M2"
    growth_override: LinearGrowthOverride | None = None
    n_specimens: int = Field(default=30, ge=2, le=500)
    sampling_interval_mm: float = Field(default=1.0, gt=0, le=10)
    increment_width_mm: float = Field(default=1.0, gt=0, le=10)
    sampled_length_mm: float | None = Field(default=None, gt=0, description="Defaults to the growth table's length")
    noise_sd: float = Field(default=0.15, ge=0, le=3)
    missing_fraction: float = Field(default=0.0, ge=0, lt=0.9)
    growth_layer_offset_mm: float = Field(default=0.0, ge=0, le=50)
    # Error of the age model itself: each animal's true ages are offset from the
    # growth table by N(0, sd) months, and the analysis is told this SD.
    age_model_error_sd: float = Field(default=0.0, ge=0, le=12)
    # True weaning curves (logistic) are drawn uniformly from these ranges.
    midpoint_range_months: tuple[float, float] = (4.0, 9.0)
    scale_range_months: tuple[float, float] = (0.4, 1.0)
    adult_d15N: float = 5.5
    drop_permil_range: tuple[float, float] = (2.0, 3.5)
    seed: int = 1


class ModelScore(BaseModel):
    model: str
    n_fitted: int
    success_rate: float
    bias: float | None
    mae: float | None
    rmse: float | None
    ci_coverage: float | None


class SimulationResult(BaseModel):
    scenario: SimulationScenario
    true_milestone: str
    scores: list[ModelScore]


def _clean(v):
    return None if v is None or (isinstance(v, float) and not math.isfinite(v)) else float(v)


def simulate_samples(sc: SimulationScenario, threshold: float = 0.05) -> tuple[list[IsotopeSample], dict[str, float]]:
    """Synthetic samples plus the true completion age of each specimen."""
    table = None if sc.growth_override else find_growth_table(sc.species, sc.tooth)
    if table is None and sc.growth_override is None:
        raise ValueError(f"no growth table for {sc.species} {sc.tooth}; give a growth_override")
    length = sc.sampled_length_mm or (table.knots[-1].position_mm if table else 40.0)
    rng = np.random.default_rng(sc.seed)
    sub = np.linspace(0, 1, 15)
    samples: list[IsotopeSample] = []
    truth: dict[str, float] = {}
    for i in range(sc.n_specimens):
        sid = f"SIM-{i + 1:03d}"
        t_mid = rng.uniform(*sc.midpoint_range_months)
        scale = rng.uniform(*sc.scale_range_months)
        drop = rng.uniform(*sc.drop_permil_range)
        shift = rng.normal(0, sc.age_model_error_sd) if sc.age_model_error_sd else 0.0
        # The animal's real weaning age; its teeth record it on the (offset) table scale.
        truth[sid] = t_mid + scale * math.log((1 - threshold) / threshold)
        centres = np.arange(sc.increment_width_mm / 2, length, sc.sampling_interval_mm)
        keep = rng.random(centres.size) >= sc.missing_fraction
        for p in centres[keep]:
            # Each section averages the true curve over the dentine it contains.
            lo = max(p - sc.increment_width_mm / 2, 0)
            hi = p + sc.increment_width_mm / 2 + sc.growth_layer_offset_mm
            ages, _ = position_to_age(lo + sub * (hi - lo), table, sc.growth_override)
            value = np.mean(sc.adult_d15N + drop / (1 + np.exp((ages + shift - t_mid) / scale)))
            samples.append(IsotopeSample(
                specimen_id=sid, site="Simulated", species=sc.species, tooth=sc.tooth,
                position_mm=float(p), d15N=float(np.clip(value + rng.normal(0, sc.noise_sd), -10, 30)),
                cn_ratio=3.2, increment_width_mm=sc.increment_width_mm,
                known_weaning_age_months=truth[sid],
            ))
    return samples, truth


def run_simulation(
    sc: SimulationScenario,
    options: AnalysisOptions | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> SimulationResult:
    options = (options or AnalysisOptions(monte_carlo_draws=300)).model_copy(deep=True)
    if sc.growth_override:
        options.growth_overrides = {f"{sc.species}:{sc.tooth}": sc.growth_override}
    else:
        table = find_growth_table(sc.species, sc.tooth)
        if table is not None:
            options.growth_tables = [table.model_copy(update={"age_uncertainty_months": sc.age_model_error_sd})]
    if options.time_averaging:
        options.increment_width_mm = sc.increment_width_mm
        options.growth_layer_offset_mm = sc.growth_layer_offset_mm
    samples, truth = simulate_samples(sc, options.transition_threshold)
    rows = estimate_rows(analyze(samples, options, progress=progress))
    df = pd.DataFrame([r.model_dump() for r in rows])
    scores = []
    for model in [*options.models, "average"]:
        sub = df[df["model"] == model] if not df.empty else df
        if model == "average" and sub.empty:
            continue
        m = error_metrics(sub["completion"], sub["known_weaning_age_months"]) if len(sub) else {"n": 0}
        cov = interval_coverage(sub["completion_ci_low"], sub["completion_ci_high"],
                                sub["known_weaning_age_months"]) if len(sub) else float("nan")
        scores.append(ModelScore(
            model=model, n_fitted=int(m["n"]), success_rate=m["n"] / sc.n_specimens,
            bias=_clean(m.get("bias")), mae=_clean(m.get("mae")), rmse=_clean(m.get("rmse")),
            ci_coverage=_clean(cov),
        ))
    return SimulationResult(scenario=sc, true_milestone="completion", scores=scores)


def sweep(
    sc: SimulationScenario,
    param: SweepParam,
    values: list[float],
    options: AnalysisOptions | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> list[SimulationResult]:
    """Run the same scenario (same seed) for each value of one setting."""
    out = []
    total = len(values) * sc.n_specimens
    for k, value in enumerate(values):
        update = {param: int(value) if param == "n_specimens" else value}
        if param == "sampling_interval_mm":
            # Contiguous sampling: sections as tall as the interval between them.
            update["increment_width_mm"] = value
        scen = sc.model_copy(update=update)
        done = k * sc.n_specimens

        def step(i, n, done=done):
            if progress:
                progress(done + i, total)

        out.append(run_simulation(scen, options, progress=step))
    return out
