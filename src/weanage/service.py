"""Everything the app can ask for, as plain Python functions.

Two front doors use these same functions:
* api.py      the local web server (FastAPI), used by `weanage`
* browser.py  the browser version, where Python runs inside the web page (Pyodide)

Bad requests raise ValueError; each front door turns that into an error message.
"""

from collections.abc import Callable
from typing import Any, Literal, NamedTuple

import pandas as pd
from pydantic import BaseModel, Field

from . import __version__, config
from .aggregate import aggregate, model_disagreement, records, validate
from .analysis import analyze, estimate_rows
from .bone import analyze_bones, ingest_bone_dataframe
from .bone_planner import BoneScenario, BoneSweepParam, run_bone_plan
from .calibrate import CalibrationPoint, Method, calibrate_growth_table
from .dental_age import analyze_dental, ingest_dental_dataframe
from .enamel import analyze_enamel, ingest_enamel_dataframe
from .hypoplasia import analyze_leh, ingest_leh_dataframe
from .inference import compare_groups
from .ingest import ingest_file, ingest_records, read_table
from .killoff import analyze_killoff, ingest_killoff_dataframe
from .lifetable import analyze_lifetable, ingest_life_dataframe
from .mixing import analyze_mixing, ingest_mixing_dataframe
from .mixing import with_defaults as with_diet_defaults
from .mobility import analyze_mobility, ingest_mobility_dataframe
from .models import MODEL_CATALOG
from .qc import FLAG_DESCRIPTIONS
from .schema import (
    AnalysisOptions,
    BoneOptions,
    BoneSample,
    DentalOptions,
    DentalSample,
    EnamelOptions,
    EnamelSample,
    GrowthTable,
    IsotopeSample,
    KilloffOptions,
    KilloffSample,
    LehOptions,
    LehSample,
    LifeSample,
    LifeTableOptions,
    MixingOptions,
    MixingSample,
    MobilityOptions,
    MobilitySample,
    ModelName,
)
from .simulate import SimulationScenario, SweepParam, run_simulation, sweep


# The shape of each request (checked by pydantic)
class AnalyzeIn(BaseModel):
    samples: list[IsotopeSample] = Field(min_length=1)
    options: AnalysisOptions | None = None


class BoneAnalyzeIn(BaseModel):
    samples: list[BoneSample] = Field(min_length=1)
    options: BoneOptions | None = None


class SimulateBoneIn(BaseModel):
    scenario: BoneScenario = BoneScenario()
    options: BoneOptions | None = None
    sweep_param: BoneSweepParam | None = None
    sweep_values: list[float] = Field(default=[], max_length=8)


class AggregateIn(BaseModel):
    estimates: list[dict[str, Any]]
    group_by: list[str] = Field(default=["site", "species"], min_length=1, max_length=4)  # site, species, period or a kept column
    milestone: Literal["onset", "midpoint", "completion"] = "midpoint"
    model: ModelName | Literal["average"] | None = None
    bayes: bool | Literal["two_stage", "one_stage"] = True
    results: list[dict[str, Any]] | None = None  # needed by the one-stage model
    transition_threshold: float = Field(default=0.05, gt=0, lt=0.5)


class CalibrateIn(BaseModel):
    species: str
    tooth: str
    points: list[CalibrationPoint] = Field(min_length=3)
    method: Method = "linear"
    n_knots: int = Field(default=6, ge=2, le=50)
    source: str = ""


class SimulateIn(BaseModel):
    scenario: SimulationScenario = SimulationScenario()
    options: AnalysisOptions | None = None
    sweep_param: SweepParam | None = None
    sweep_values: list[float] = Field(default=[], max_length=12)


# Settings and data
def defaults(calc):
    options = calc.options()
    return (with_diet_defaults(options) if isinstance(options, MixingOptions) else options).model_dump()


def get_config():
    saved = config.saved_growth_tables()
    return {
        "version": __version__,
        "defaults": config.default_options().model_dump(),
        "models": MODEL_CATALOG,
        "growth_tables": [{**t.model_dump(), "saved": key in saved} for key, t in config.growth_tables().items()],
        "user_tables_path": str(config.user_tables_path()),
        "qc_flags": FLAG_DESCRIPTIONS,
        "qc_presets": config.qc_config().get("presets", {}),
        "examples": [{"name": key, "label": label} for key, (_, label, _) in EXAMPLES.items()],
        "tbd": config.tbd_items(),
        "bone_defaults": BoneOptions().model_dump(),
        "bone_examples": [{"name": key, "label": label} for key, (_, label, _) in BONE_EXAMPLES.items()],
        "turnover_tables": [t.model_dump() for t in config.turnover_tables()],
        "bone_priors": config.bone_priors(),
        "calculations": {name: {"defaults": defaults(c), "examples": [{"name": key, "label": label} for key, (_, label, _) in c.examples.items()]}
                         for name, c in CALCULATIONS.items()},
    }


def report_json(report):
    return {**report, "samples": [s.model_dump() for s in report["samples"]]}


def read_upload(filename, content):
    try:
        return report_json(ingest_file(content, filename))
    except Exception as err:
        raise ValueError(f"Could not read file: {err}") from err


def check_records(rows):
    return report_json(ingest_records(rows))


# The example datasets offered in the app: file name, menu label and the message shown on loading.
EXAMPLES = {
    "synthetic": ("synthetic_example.csv", "Synthetic example (simulated)",
                  "Loaded SYNTHETIC example data (simulated, not real measurements)."),
    "isoarch_cattle": ("isoarch_cattle_khami_bornais.csv", "Real cattle: Khami & Bornais (IsoArcH)",
                       "Loaded real cattle data from IsoArcH (CC-BY 4.0; Dyvart et al. 2018; Griffith & Mulville "
                       "2020). Slice positions are ASSUMED: see each sample's notes."),
    "cima_teeth_mikulcice": ("cima_teeth_mikulcice.csv", "Real human teeth: Mikulčice (CIMA)",
                             "Loaded real human first molars from Mikulčice, 9th-10th c. AD (Kaupová et al. 2024, via CIMA, "
                             "CC BY-SA). Section positions are ASSUMED (ten equal sections per tooth) and the human tooth age "
                             "model is provisional."),
}


def example_dataset(name="synthetic"):
    if name not in EXAMPLES:
        raise ValueError(f"unknown example {name!r}")
    return {**report_json(ingest_file(config.DATA_DIR / "examples" / EXAMPLES[name][0])), "message": EXAMPLES[name][2]}


# Bone data: many animals that died at different ages
BONE_EXAMPLES = {
    "synthetic_bone": ("synthetic_bone_example.csv", "Synthetic cattle bones (simulated)",
                       "Loaded SYNTHETIC bone data (simulated, not real measurements): Site A weans at "
                       "3–9 months, Site B at 1–4 months."),
    "cima_wharram_percy": ("cima_bone_wharram_percy.csv", "Real human bones: Wharram Percy (CIMA)",
                           "Loaded medieval rib collagen from Wharram Percy, England (Richards, Mays & Fuller 2002, via CIMA, "
                           "CC BY-SA). The authors placed the end of weaning at about 2 years."),
    "cima_york_fishergate": ("cima_bone_york_fishergate.csv", "Real human bones: York, Fishergate House (CIMA)",
                             "Loaded late medieval bone collagen from Fishergate House, York (Burt 2013, via CIMA, CC BY-SA). "
                             "Burt found weaning complete by about 2 years."),
    "cima_newark_bay": ("cima_bone_newark_bay.csv", "Real human bones: Newark Bay, Orkney (CIMA)",
                        "Loaded medieval bone collagen from Newark Bay, Orkney (Richards, Fuller & Molleson 2006, via CIMA, "
                        "CC BY-SA). Phases are pooled, as in the original weaning comparison."),
}


def read_bone_upload(filename, content):
    try:
        return report_json(ingest_bone_dataframe(read_table(content, filename)))
    except Exception as err:
        raise ValueError(f"Could not read file: {err}") from err


def check_bone_records(rows):
    if not rows:
        return {"samples": [], "issues": [], "groups": []}
    return report_json(ingest_bone_dataframe(pd.DataFrame(rows)))


def bone_example(name="synthetic_bone"):
    if name not in BONE_EXAMPLES:
        raise ValueError(f"unknown bone example {name!r}")
    table = read_table(config.DATA_DIR / "examples" / BONE_EXAMPLES[name][0])
    return {**report_json(ingest_bone_dataframe(table)), "message": BONE_EXAMPLES[name][2]}


def run_bone_analysis(body: BoneAnalyzeIn, progress=None):
    return {"results": analyze_bones(body.samples, body.options or BoneOptions(), progress)}


def run_bone_planner(body: SimulateBoneIn, progress=None):
    return run_bone_plan(body.scenario, body.options, body.sweep_param, body.sweep_values, progress)


# Calculations that take one table of samples and one set of settings: enamel, kill-off, diet mixing.
class Calculation(NamedTuple):
    sample: type[BaseModel]
    options: type[BaseModel]
    ingest: Callable  # DataFrame -> {"samples", "issues", ...}
    analyze: Callable  # (samples, options, progress) -> results
    examples: dict  # name -> (csv file, label, message on loading)


CALCULATIONS = {
    "enamel": Calculation(EnamelSample, EnamelOptions, ingest_enamel_dataframe, analyze_enamel, {
        "synthetic_enamel": ("synthetic_enamel_example.csv", "Synthetic cattle M2 enamel (simulated)",
                             "Loaded SYNTHETIC enamel data (simulated, not real measurements): Site A calved within "
                             "about a month, Site B over about seven; three Site B animals moved as calves (87Sr/86Sr)."),
    }),
    "killoff": Calculation(KilloffSample, KilloffOptions, ingest_killoff_dataframe, analyze_killoff, {
        "synthetic_killoff": ("synthetic_killoff_example.csv", "Synthetic sheep/goat mandibles (simulated)",
                              "Loaded SYNTHETIC mandibles (simulated, not real data): Site A was drawn with most deaths "
                              "in stages A–B, Site B in C–D."),
    }),
    "mixing": Calculation(MixingSample, MixingOptions, ingest_mixing_dataframe, analyze_mixing, {
        "synthetic_mixing": ("synthetic_mixing_example.csv", "Synthetic human bone collagen (simulated)",
                             "Loaded SYNTHETIC collagen values (simulated, not real measurements) from the placeholder "
                             "food sources: an inland and a coastal site."),
    }),
    "dental": Calculation(DentalSample, DentalOptions, ingest_dental_dataframe, analyze_dental, {
        "synthetic_dental": ("synthetic_dental_example.csv", "Synthetic children's teeth (simulated)",
                             "Loaded SYNTHETIC tooth formation stages (simulated) for 24 children; the true ages are "
                             "in the notes. The formation ages are placeholders."),
    }),
    "leh": Calculation(LehSample, LehOptions, ingest_leh_dataframe, analyze_leh, {
        "synthetic_hypoplasia": ("synthetic_hypoplasia_example.csv", "Synthetic enamel hypoplasia (simulated)",
                                 "Loaded SYNTHETIC enamel hypoplasia defects (simulated) for 15 people, most formed at "
                                 "2-4 years."),
    }),
    "lifetable": Calculation(LifeSample, LifeTableOptions, ingest_life_dataframe, analyze_lifetable, {
        "synthetic_cemetery": ("synthetic_cemetery_example.csv", "Synthetic cemeteries (simulated)",
                               "Loaded SYNTHETIC skeletal ages (simulated) from two cemeteries; Site B lost most of "
                               "its infant burials."),
    }),
    "mobility": Calculation(MobilitySample, MobilityOptions, ingest_mobility_dataframe, analyze_mobility, {
        "synthetic_mobility": ("synthetic_mobility_example.csv", "Synthetic enamel δ18O and Sr (simulated)",
                               "Loaded SYNTHETIC enamel values (simulated): 30 people and 12 local animals; five people "
                               "grew up elsewhere."),
    }),
}


def calculation(name):
    if name not in CALCULATIONS:
        raise ValueError(f"unknown calculation {name!r}")
    return CALCULATIONS[name]


def read_calculation_upload(name, filename, content):
    try:
        return report_json(calculation(name).ingest(read_table(content, filename)))
    except Exception as err:
        raise ValueError(f"Could not read file: {err}") from err


def check_calculation_records(name, rows):
    if not rows:
        return {"samples": [], "issues": []}
    return report_json(calculation(name).ingest(pd.DataFrame(rows)))


def calculation_example(name, example=None):
    examples = calculation(name).examples
    example = example or next(iter(examples))
    if example not in examples:
        raise ValueError(f"unknown example {example!r}")
    file, _, message = examples[example]
    return {**report_json(calculation(name).ingest(read_table(config.DATA_DIR / "examples" / file))), "message": message}


def run_calculation(name, body: dict, progress=None):
    """body: {"samples": [...], "options": {...} or None}; checked against the calculation's shapes."""
    calc = calculation(name)
    samples = [calc.sample(**row) for row in body.get("samples") or []]
    if not samples:
        raise ValueError("no samples to analyse")
    return calc.analyze(samples, calc.options(**(body.get("options") or {})), progress)


def save_table(table: GrowthTable):
    config.save_growth_table(table)
    return table.model_dump()


def delete_table(species, tooth):
    return {"deleted": config.delete_saved_growth_table(f"{species.lower()}:{tooth}")}


def calibrate(body: CalibrateIn):
    return calibrate_growth_table(body.species, body.tooth, body.points, body.method, body.n_knots, body.source)


# Analysis, simulation, comparison
# `progress(done, total)` is called as work finishes, for the progress bar.
def run_analysis(body: AnalyzeIn, progress=None, workers=None):
    results = analyze(body.samples, body.options or config.default_options(), progress=progress, workers=workers)
    return {"results": results, "estimates": estimate_rows(results)}


def run_planner(body: SimulateIn, progress=None):
    if body.sweep_param and body.sweep_values:
        runs = sweep(body.scenario, body.sweep_param, body.sweep_values, body.options, progress)
    else:
        runs = [run_simulation(body.scenario, body.options, progress)]
    return {"sweep_param": body.sweep_param, "runs": runs}


def compare(body: AggregateIn):
    known = {key for row in body.estimates for key in row}
    unknown = [g for g in body.group_by if g not in known]
    if unknown:
        raise ValueError(f"no estimates have {', '.join(unknown)} to group by")
    return {
        "summary": records(aggregate(body.estimates, body.group_by, body.milestone, body.model)),
        "disagreement": records(model_disagreement(body.estimates, body.milestone)),
        "validation": records(validate(body.estimates, body.milestone)),
        "tests": compare_groups(body.estimates, body.group_by, body.milestone, body.model, body.bayes,
                                results=body.results, threshold=body.transition_threshold),
    }
