"""Everything the app can ask for, as plain Python functions.

Two front doors use these same functions:
* api.py      the local web server (FastAPI), used by `weanage`
* browser.py  the browser version, where Python runs inside the web page (Pyodide)

Bad requests raise ValueError; each front door turns that into an error message.
"""

from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, Field

from . import __version__, config
from .aggregate import aggregate, model_disagreement, records, validate
from .analysis import analyze, estimate_rows
from .bone import analyze_bones, ingest_bone_dataframe
from .bone_planner import BoneScenario, BoneSweepParam, run_bone_plan
from .calibrate import CalibrationPoint, Method, calibrate_growth_table
from .enamel import analyze_enamel, ingest_enamel_dataframe
from .inference import compare_groups
from .ingest import ingest_file, ingest_records, read_table
from .models import MODEL_CATALOG
from .qc import FLAG_DESCRIPTIONS
from .schema import (
    AnalysisOptions,
    BoneOptions,
    BoneSample,
    EnamelOptions,
    EnamelSample,
    GrowthTable,
    IsotopeSample,
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


class EnamelAnalyzeIn(BaseModel):
    samples: list[EnamelSample] = Field(min_length=1)
    options: EnamelOptions | None = None


class SimulateBoneIn(BaseModel):
    scenario: BoneScenario = BoneScenario()
    options: BoneOptions | None = None
    sweep_param: BoneSweepParam | None = None
    sweep_values: list[float] = Field(default=[], max_length=8)


class AggregateIn(BaseModel):
    estimates: list[dict[str, Any]]
    group_by: list[Literal["site", "species", "period"]] = Field(default=["site", "species"], min_length=1)
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
        "enamel_defaults": EnamelOptions().model_dump(),
        "enamel_examples": [{"name": key, "label": label} for key, (_, label, _) in ENAMEL_EXAMPLES.items()],
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


# Enamel data: season of birth (δ18O) and rumen development (δ13C) along one molar
ENAMEL_EXAMPLES = {
    "synthetic_enamel": ("synthetic_enamel_example.csv", "Synthetic cattle M2 enamel (simulated)",
                         "Loaded SYNTHETIC enamel data (simulated, not real measurements): Site A calved within about "
                         "a month, Site B over about seven."),
}


def read_enamel_upload(filename, content):
    try:
        return report_json(ingest_enamel_dataframe(read_table(content, filename)))
    except Exception as err:
        raise ValueError(f"Could not read file: {err}") from err


def check_enamel_records(rows):
    if not rows:
        return {"samples": [], "issues": [], "teeth": []}
    return report_json(ingest_enamel_dataframe(pd.DataFrame(rows)))


def enamel_example(name="synthetic_enamel"):
    if name not in ENAMEL_EXAMPLES:
        raise ValueError(f"unknown enamel example {name!r}")
    table = read_table(config.DATA_DIR / "examples" / ENAMEL_EXAMPLES[name][0])
    return {**report_json(ingest_enamel_dataframe(table)), "message": ENAMEL_EXAMPLES[name][2]}


def run_enamel_analysis(body: EnamelAnalyzeIn, progress=None):
    return analyze_enamel(body.samples, body.options or EnamelOptions(), progress)


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
    return {
        "summary": records(aggregate(body.estimates, body.group_by, body.milestone, body.model)),
        "disagreement": records(model_disagreement(body.estimates, body.milestone)),
        "validation": records(validate(body.estimates, body.milestone)),
        "tests": compare_groups(body.estimates, body.group_by, body.milestone, body.model, body.bayes,
                                results=body.results, threshold=body.transition_threshold),
    }
