"""The web server: the browser sends data here and gets results back as JSON.

The server keeps no data of its own (apart from saved growth tables and short-lived
background jobs), so it works for one person or a whole lab.
"""

import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
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

app = FastAPI(title="WeanAge", version=__version__)


# ───────────── request bodies ─────────────
class AnalyzeIn(BaseModel):
    samples: list[IsotopeSample] = Field(min_length=1)
    options: Optional[AnalysisOptions] = None


class AggregateIn(BaseModel):
    estimates: list[dict[str, Any]]
    group_by: list[str] = ["site", "species"]
    milestone: str = "completion"
    model: Optional[str] = None
    bayes: bool = True


class CalibrateIn(BaseModel):
    species: str
    tooth: str
    points: list[CalibrationPoint] = Field(min_length=3)
    method: Method = "linear"
    n_knots: int = Field(default=6, ge=2, le=50)
    source: str = ""


class SimulateIn(BaseModel):
    scenario: SimulationScenario = SimulationScenario()
    options: Optional[AnalysisOptions] = None
    sweep_param: Optional[SweepParam] = None
    sweep_values: list[float] = Field(default=[], max_length=12)


# ───────────── background jobs (so long runs can show a progress bar) ─────────────
JOBS = {}
WORKERS = ThreadPoolExecutor(max_workers=2)


def start_job(kind, work):
    """Run work(progress) in the background; the browser polls /api/jobs/<id>."""
    job = {"id": uuid.uuid4().hex[:12], "kind": kind, "status": "queued", "done": 0, "total": 0, "error": None}
    JOBS[job["id"]] = job
    while len(JOBS) > 50:  # forget the oldest jobs
        JOBS.pop(next(iter(JOBS)))

    def progress(done, total):
        job["done"], job["total"] = done, total

    def run():
        job["status"] = "running"
        try:
            job["result"] = work(progress)
            job["status"] = "done"
        except Exception as err:
            job["status"], job["error"] = "error", f"{type(err).__name__}: {err}"
            traceback.print_exc()

    WORKERS.submit(run)
    return {k: v for k, v in job.items() if k != "result"}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(404, "unknown job")
    job = dict(JOBS[job_id])
    if job["status"] != "done":
        job.pop("result", None)
    return job


# ───────────── settings and data ─────────────
@app.get("/api/config")
def get_config():
    saved = config.saved_growth_tables()
    return {
        "version": __version__,
        "defaults": config.default_options().model_dump(),
        "models": MODEL_CATALOG,
        "growth_tables": [{**t.model_dump(), "saved": key in saved} for key, t in config.growth_tables().items()],
        "user_tables_path": str(config.user_tables_path()),
        "qc_flags": FLAG_DESCRIPTIONS,
        "tbd": config.tbd_items(),
    }


def report_json(report):
    return {**report, "samples": [s.model_dump() for s in report["samples"]]}


@app.post("/api/ingest/file")
@app.post("/api/ingest/csv")  # older name, kept so existing scripts still work
async def upload_file(file: UploadFile = File(...)):
    try:
        return report_json(ingest_file(file.filename or "upload.csv", await file.read()))
    except Exception as err:
        raise HTTPException(400, f"Could not read file: {err}") from err


@app.post("/api/ingest/records")
def validate_records(body: dict):
    return report_json(ingest_records(body.get("records", [])))


@app.get("/api/example")
def example_dataset():
    return report_json(ingest_csv(config.DATA_DIR / "examples" / "synthetic_example.csv"))


@app.get("/api/template.csv")
def template_csv():
    return FileResponse(config.DATA_DIR / "templates" / "isotope_template.csv", media_type="text/csv",
                        filename="weanage_template.csv")


@app.post("/api/growth-tables")
def save_table(table: GrowthTable):
    config.save_growth_table(table)
    return table


@app.delete("/api/growth-tables/{species}/{tooth}")
def delete_table(species: str, tooth: str):
    return {"deleted": config.delete_saved_growth_table(f"{species.lower()}:{tooth}")}


@app.post("/api/growth-tables/calibrate")
def calibrate(body: CalibrateIn):
    try:
        return calibrate_growth_table(body.species, body.tooth, body.points, body.method, body.n_knots, body.source)
    except ValueError as err:
        raise HTTPException(400, str(err)) from err


# ───────────── analysis, simulation, comparison ─────────────
def run_analysis(body, progress=None):
    results = analyze(body.samples, body.options or config.default_options(), progress=progress)
    return {"results": results, "estimates": estimate_rows(results)}


@app.post("/api/analyze")
def analyze_now(body: AnalyzeIn):
    return run_analysis(body)


@app.post("/api/jobs/analyze")
def analyze_in_background(body: AnalyzeIn):
    return start_job("analyze", lambda progress: run_analysis(body, progress))


@app.post("/api/jobs/simulate")
def simulate_in_background(body: SimulateIn):
    def work(progress):
        if body.sweep_param and body.sweep_values:
            runs = sweep(body.scenario, body.sweep_param, body.sweep_values, body.options, progress)
        else:
            runs = [run_simulation(body.scenario, body.options, progress)]
        return {"sweep_param": body.sweep_param, "runs": runs}

    return start_job("simulate", work)


@app.post("/api/aggregate")
def compare(body: AggregateIn):
    if not body.group_by or not set(body.group_by) <= {"site", "species", "period"}:
        raise HTTPException(400, "group_by must be a non-empty subset of ['period', 'site', 'species']")
    if body.milestone not in {"onset", "midpoint", "completion"}:
        raise HTTPException(400, "milestone must be onset, midpoint or completion")
    if body.model is not None and body.model not in MODEL_NAMES + ["average"]:
        raise HTTPException(400, f"unknown model {body.model!r}")
    return {
        "summary": records(aggregate(body.estimates, body.group_by, body.milestone, body.model)),
        "disagreement": records(model_disagreement(body.estimates, body.milestone)),
        "validation": records(validate(body.estimates, body.milestone)),
        "tests": compare_groups(body.estimates, body.group_by, body.milestone, body.model, body.bayes),
    }


@app.get("/", include_in_schema=False)
def index():
    return RedirectResponse("/app/")


app.mount("/app", StaticFiles(directory=config.WEB_DIR, html=True), name="web")
