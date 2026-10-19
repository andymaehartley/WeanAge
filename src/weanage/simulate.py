"""Sampling planner: test a sampling plan on made-up teeth whose weaning age we know.

We invent teeth with known weaning curves, "cut" them the way the lab would
(slice height and spacing, angled growth layers, measurement noise, lost samples),
run the normal analysis and score each model against the truth. Repeating this
while changing one setting (e.g. 0.5 vs 1 vs 2 mm slices) shows which plan works.
"""

import math
from typing import Literal

import numpy as np
from pydantic import BaseModel, Field

from .aggregate import error_metrics, interval_coverage, plain, to_frame
from .analysis import analyze, estimate_rows, slice_positions
from .config import find_growth_table
from .growth import position_to_age
from .models import MODELS
from .schema import AnalysisOptions, IsotopeSample, LinearGrowthOverride

Shape = Literal["logistic", "piecewise", "exponential", "two_phase", "mixed"]
SweepParam = Literal["sampling_interval_mm", "increment_width_mm", "noise_sd", "missing_fraction",
                     "growth_layer_offset_mm", "n_specimens"]


class SimulationScenario(BaseModel):
    species: str = "cattle"
    tooth: str = "M2"
    growth_override: LinearGrowthOverride | None = None
    n_specimens: int = Field(default=30, ge=2, le=500)
    sampling_interval_mm: float = Field(default=1.0, gt=0, le=10)
    increment_width_mm: float = Field(default=1.0, gt=0, le=10)
    sampled_length_mm: float | None = Field(default=None, gt=0)  # default: the whole growth table
    noise_sd: float = Field(default=0.15, ge=0, le=3)
    missing_fraction: float = Field(default=0.0, ge=0, lt=0.9)
    growth_layer_offset_mm: float = Field(default=0.0, ge=0, le=50)
    age_model_error_sd: float = Field(default=0.0, ge=0, le=12)  # how wrong the age model is per animal
    midpoint_range_months: tuple[float, float] = (4.0, 9.0)  # true curves are drawn from these ranges
    scale_range_months: tuple[float, float] = (0.4, 1.0)
    adult_d15N: float = 5.5
    drop_permil_range: tuple[float, float] = (2.0, 3.5)
    # The shape of the true curves. Testing with logistic truths alone would favour the
    # logistic model, so other shapes (or a random mix) can be used instead.
    true_shape: Shape = "logistic"
    seed: int = 1


def true_curve(shape, post, drop, middle, scale, rng, q):
    """Parameters for a true curve of the given shape, centred on `middle` (months).

    Every shape takes about as long to go from 5 % to 95 % of the drop as a logistic
    curve of width `scale`, so the shapes are directly comparable.
    """
    span = 2 * scale * math.log((1 - q) / q)  # time from onset to completion of the logistic
    if shape == "piecewise":
        return [post, drop, middle - span / 2, span]
    if shape == "exponential":
        tau = span / math.log(1 / q)
        return [post, drop, middle - tau * math.log(2), tau]
    if shape == "two_phase":  # some of the drop first, the rest 1.5-4 months later
        gap = rng.uniform(1.5, 4.0)
        return [post, drop, rng.uniform(0.3, 0.7), middle - gap / 2, gap, scale]
    return [post, drop, middle, scale]


def simulate_samples(sc, threshold=0.05):
    """Made-up samples, and each animal's true weaning (completion) age."""
    table = None if sc.growth_override else find_growth_table(sc.species, sc.tooth)
    if table is None and sc.growth_override is None:
        raise ValueError(f"no growth table for {sc.species} {sc.tooth}; give a growth_override")
    length = sc.sampled_length_mm or (table.knots[-1].position_mm if table else 40.0)
    rng = np.random.default_rng(sc.seed)
    samples, truth = [], {}
    for i in range(sc.n_specimens):
        sid = f"SIM-{i + 1:03d}"
        t_mid = rng.uniform(*sc.midpoint_range_months)
        scale = rng.uniform(*sc.scale_range_months)
        drop = rng.uniform(*sc.drop_permil_range)
        shape = rng.choice(["logistic", "piecewise", "exponential", "two_phase"]) if sc.true_shape == "mixed" \
            else sc.true_shape
        params = true_curve(shape, sc.adult_d15N, drop, t_mid, scale, rng, threshold)
        curve = MODELS[shape]["curve"]
        shift = rng.normal(0, sc.age_model_error_sd) if sc.age_model_error_sd else 0.0  # this animal vs the table
        truth[sid] = float(MODELS[shape]["ages"](np.array(params), threshold)["completion"])
        centres = np.arange(sc.increment_width_mm / 2, length, sc.sampling_interval_mm)
        for p in centres[rng.random(len(centres)) >= sc.missing_fraction]:
            # A slice holds dentine from its own height plus angled later layers; average the true curve over it.
            positions = slice_positions(p, sc.increment_width_mm, sc.growth_layer_offset_mm)
            ages, _ = position_to_age(positions, table, sc.growth_override)
            value = np.mean(curve(ages + shift, *params))
            samples.append(IsotopeSample(
                specimen_id=sid, site="Simulated", species=sc.species, tooth=sc.tooth, position_mm=float(p),
                d15N=float(np.clip(value + rng.normal(0, sc.noise_sd), -10, 30)), cn_ratio=3.2,
                increment_width_mm=sc.increment_width_mm, known_weaning_age_months=truth[sid]))
    return samples, truth


def run_simulation(sc, options=None, progress=None):
    options = (options or AnalysisOptions(monte_carlo_draws=300)).model_copy(deep=True)
    if sc.growth_override:
        options.growth_overrides = {f"{sc.species}:{sc.tooth}": sc.growth_override}
    elif find_growth_table(sc.species, sc.tooth):
        # Tell the analysis how uncertain the age model really is in this scenario.
        table = find_growth_table(sc.species, sc.tooth)
        options.growth_tables = [table.model_copy(update={"age_uncertainty_months": sc.age_model_error_sd})]
    if options.time_averaging:
        options.increment_width_mm = sc.increment_width_mm
        options.growth_layer_offset_mm = sc.growth_layer_offset_mm
    samples, _ = simulate_samples(sc, options.transition_threshold)
    df = to_frame(estimate_rows(analyze(samples, options, progress=progress)))
    scores = []
    for model in options.models + ["average"]:
        sub = df[df["model"] == model] if not df.empty else df
        if model == "average" and sub.empty:
            continue
        m = error_metrics(sub["completion"], sub["known_weaning_age_months"]) if len(sub) else {"n": 0}
        coverage = interval_coverage(sub["completion_ci_low"], sub["completion_ci_high"],
                                     sub["known_weaning_age_months"]) if len(sub) else np.nan
        scores.append({"model": model, "n_fitted": int(m["n"]), "success_rate": m["n"] / sc.n_specimens,
                       "bias": plain(m.get("bias")), "mae": plain(m.get("mae")), "rmse": plain(m.get("rmse")),
                       "ci_coverage": plain(coverage)})
    return {"scenario": sc.model_dump(), "true_milestone": "completion", "scores": scores}


def sweep(sc, param, values, options=None, progress=None):
    """Run the same scenario (same random seed) once for each value of one setting."""
    runs = []
    for k, value in enumerate(values):
        change = {param: int(value) if param == "n_specimens" else value}
        if param == "sampling_interval_mm":
            change["increment_width_mm"] = value  # slices touch each other: height = spacing

        def report(done, total, done_before=k * sc.n_specimens):
            if progress:  # count progress over all the runs together
                progress(done_before + done, len(values) * sc.n_specimens)

        runs.append(run_simulation(sc.model_copy(update=change), options, report))
    return runs
