"""Everything the app can ask for, as plain Python functions.

Two front doors use these same functions:
* api.py      the local web server (FastAPI), used by `weanage`
* browser.py  the browser version, where Python runs inside the web page (Pyodide)

Bad requests raise ValueError; each front door turns that into an error message.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

from . import __version__, config
from .aggregate import aggregate, model_disagreement, records, validate
from .analysis import analyze, estimate_rows
from .calibrate import CalibrationPoint, Method, calibrate_growth_table
from .inference import compare_groups
from .ingest import ingest_csv, ingest_file, ingest_records
from .models import MODEL_CATALOG
from .qc import FLAG_DESCRIPTIONS
from .schema import MODEL_NAMES, AnalysisOptions, GrowthTable, IsotopeSample
from .simulate import SimulationScenario, SweepParam, run_simulation, sweep


# ───────────── the shape of each request (checked by pydantic) ─────────────
class AnalyzeIn(BaseModel):
    samples: list[IsotopeSample] = Field(min_length=1)
    options: AnalysisOptions | None = None


class AggregateIn(BaseModel):
    estimates: list[dict[str, Any]]
    group_by: list[str] = ["site", "species"]
    milestone: str = "completion"
    model: str | None = None
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


# ───────────── settings and data ─────────────
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
    }


def report_json(report):
    return {**report, "samples": [s.model_dump() for s in report["samples"]]}


def read_upload(filename, content):
    try:
        return report_json(ingest_file(filename or "upload.csv", content))
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
}


def example_dataset(name="synthetic"):
    if name not in EXAMPLES:
        raise ValueError(f"unknown example {name!r}")
    return {**report_json(ingest_csv(config.DATA_DIR / "examples" / EXAMPLES[name][0])), "message": EXAMPLES[name][2]}


def template_path():
    return config.DATA_DIR / "templates" / "isotope_template.csv"


def save_table(table: GrowthTable):
    config.save_growth_table(table)
    return table.model_dump()


def delete_table(species, tooth):
    return {"deleted": config.delete_saved_growth_table(f"{species.lower()}:{tooth}")}


def calibrate(body: CalibrateIn):
    return calibrate_growth_table(body.species, body.tooth, body.points, body.method, body.n_knots, body.source)


# ───────────── analysis, simulation, comparison ─────────────
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
    if not body.group_by or not set(body.group_by) <= {"site", "species", "period"}:
        raise ValueError("group_by must be a non-empty subset of ['period', 'site', 'species']")
    if body.milestone not in {"onset", "midpoint", "completion"}:
        raise ValueError("milestone must be onset, midpoint or completion")
    if body.model is not None and body.model not in MODEL_NAMES + ["average"]:
        raise ValueError(f"unknown model {body.model!r}")
    return {
        "summary": records(aggregate(body.estimates, body.group_by, body.milestone, body.model)),
        "disagreement": records(model_disagreement(body.estimates, body.milestone)),
        "validation": records(validate(body.estimates, body.milestone)),
        "tests": compare_groups(body.estimates, body.group_by, body.milestone, body.model, body.bayes,
                                results=body.results, threshold=body.transition_threshold),
    }
