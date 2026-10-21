"""Planning a bone study: how many young animals, of what ages, are needed to date weaning?

Before bones are sampled, this invents assemblages whose weaning ages are known, "samples" them
as the planned study would (so many young animals, ages at death known only to within a range,
measurement scatter), runs the bone calculation on each, and scores how close the estimates come
to the truth. Reynard & Tuross (2015) found that many bone studies have too few individuals to
date weaning at all; this shows, for a given design, whether one would.

The simulated bone δ15N values come from the bone model itself (bone.py) with the species'
turnover table, so the planner tests the design, not the model's assumptions.
"""

from typing import Literal

import numpy as np
from pydantic import BaseModel, Field

from . import config
from .bone import STEP, analyze_bones, bone_curve, priors_for, renewal
from .schema import BoneOptions, BoneSample

BoneSweepParam = Literal["n_young", "age_error_months", "n_adult_females", "scatter_permil", "oldest_young_months"]
MOTHERS_MEAN = 6.0  # the δ15N level does not matter, only the differences


class BoneScenario(BaseModel):
    """One planned bone study. Ages are in months."""

    species: str = "cattle"
    n_young: int = Field(default=40, ge=5, le=400)  # young animals per site
    oldest_young_months: float = Field(default=36, gt=1, le=240)  # the oldest young animal sampled
    age_spread: Literal["even", "mostly_young"] = "even"  # "mostly_young" is like most death assemblages
    age_error_months: float = Field(default=3, ge=0, le=60)  # ages at death known to within ± this
    n_adult_females: int = Field(default=10, ge=0, le=200)
    completion_range_months: tuple[float, float] = (6, 12)  # true end of suckling, drawn in this range
    enrichment_permil: float = Field(default=2.5, ge=0, le=6)  # true nursing enrichment
    newborn_offset_permil: float = Field(default=0.8, ge=-3, le=3)
    scatter_permil: float = Field(default=0.4, gt=0, le=3)  # between-animal and measurement scatter
    weaning_form: Literal["parabolic", "linear", "reverse"] = "parabolic"
    replicates: int = Field(default=8, ge=2, le=100)  # simulated sites per setting
    seed: int = 1


def simulate_site(scenario, rng, table, name="Simulated"):
    """One invented site: its bone samples and the true weaning ages."""
    low, high = scenario.completion_range_months
    t2 = rng.uniform(low, high)
    t1 = t2 * rng.uniform(0.2, 0.6)
    weaning_food = MOTHERS_MEAN - rng.uniform(0, 0.8)
    grid = np.arange(0, scenario.oldest_young_months + scenario.age_error_months + 2, STEP)
    bone, _ = bone_curve(grid, renewal(table, grid), t1, t2, scenario.enrichment_permil, weaning_food,
                         MOTHERS_MEAN, scenario.weaning_form, scenario.newborn_offset_permil)
    if scenario.age_spread == "even":
        ages = rng.uniform(0, scenario.oldest_young_months, scenario.n_young)
    else:  # many deaths in early life, fewer later
        ages = np.minimum(rng.exponential(scenario.oldest_young_months / 3, scenario.n_young), scenario.oldest_young_months)
    samples = []
    for i, age in enumerate(ages):
        # The ageing method gives a range of the stated width that contains the true age.
        width = 2 * scenario.age_error_months
        start = max(0.0, age - rng.uniform(0, width))
        samples.append(BoneSample(specimen_id=f"Y{i + 1}", site=name, species=scenario.species,
                                  age_min_months=round(start, 2), age_max_months=round(start + width, 2),
                                  d15N=float(np.interp(age, grid, bone) + rng.normal(0, scenario.scatter_permil))))
    for i in range(scenario.n_adult_females):
        samples.append(BoneSample(specimen_id=f"F{i + 1}", site=name, species=scenario.species, age_class="adult",
                                  sex="F", d15N=MOTHERS_MEAN + rng.normal(0, scenario.scatter_permil)))
    return samples, {"onset": t1, "completion": t2}


def score(cases):
    """Accuracy of the end-of-suckling estimates over the simulated sites."""
    fitted = [c for c in cases if c["estimate"] is not None]
    errors = np.array([c["estimate"] - c["truth"] for c in fitted])
    if not len(fitted):
        return {"mae": None, "bias": None, "rmse": None, "ci_coverage": None, "ci_width": None,
                "signal_found": None, "success_rate": 0.0}
    return {
        "mae": float(np.mean(np.abs(errors))),
        "bias": float(np.mean(errors)),
        "rmse": float(np.sqrt(np.mean(errors ** 2))),
        "ci_coverage": float(np.mean([c["ci_low"] <= c["truth"] <= c["ci_high"] for c in fitted])),
        "ci_width": float(np.median([c["ci_high"] - c["ci_low"] for c in fitted])),
        "signal_found": float(np.mean([c["signal"] for c in cases])),
        "success_rate": len(fitted) / len(cases),
    }


def run_scenario(scenario: BoneScenario, options: BoneOptions, progress=None, done=0, total=None):
    table = config.find_turnover_table(scenario.species, options.turnover_tables)
    if table is None:
        raise ValueError(f"No bone turnover table for {scenario.species}")
    rng = np.random.default_rng(scenario.seed)
    cases = []
    for r in range(scenario.replicates):
        samples, truth = simulate_site(scenario, rng, table)
        result = analyze_bones(samples, options)[0]
        end = (result["estimates"] or {}).get("completion")
        check = result["nursing_check"]
        cases.append({"truth": truth["completion"], "estimate": end["estimate"] if end else None,
                      "ci_low": end["ci_low"] if end else None, "ci_high": end["ci_high"] if end else None,
                      "signal": bool(check["p_value"] is not None and check["p_value"] < 0.05)})
        if progress:
            progress(done + r + 1, total or scenario.replicates)
    return {"metrics": score(cases), "cases": cases}


def plan_options(scenario, options=None):
    """Sampler settings for the planner: shorter runs than a real analysis, as many sites are fitted."""
    base = options or BoneOptions(chains=8, warmup=800, keep=800)
    return base.model_copy(update={"weaning_form": scenario.weaning_form, "random_seed": scenario.seed})


def run_bone_plan(scenario: BoneScenario, options: BoneOptions | None = None, sweep_param: BoneSweepParam | None = None,
                  values=(), progress=None):
    """Score one design, or the same design with one setting changed to each of `values`."""
    options = plan_options(scenario, options)
    settings = [(None, scenario)] if not sweep_param or not values else [
        (v, scenario.model_copy(update={sweep_param: int(v) if sweep_param.startswith("n_") else float(v)})) for v in values]
    total = len(settings) * scenario.replicates
    runs = []
    for i, (value, s) in enumerate(settings):
        run = run_scenario(s, options, progress, i * scenario.replicates, total)
        runs.append({"x": value, **run})
    filled, _ = priors_for(scenario.species, options)
    return {"sweep_param": sweep_param, "runs": runs, "species": scenario.species,
            "max_weaning_age_months": filled.max_weaning_age_months,
            "turnover_placeholder": bool(config.find_turnover_table(scenario.species).placeholder)}
