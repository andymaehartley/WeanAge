"""FastAPI service exposing the backend to the web frontend.

The API is stateless apart from saved growth tables (in the user directory) and
short-lived background jobs: the browser holds the dataset and sends it with each
request, so the same server works for one desktop user or a shared lab install.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__
from .aggregate import aggregate, frame_to_records, model_disagreement
from .analysis import analyze, estimate_rows
from .calibrate import CalibrationPoint, CalibrationResult, Method, calibrate_growth_table
from .config import (
    DATA_DIR, WEB_DIR, bundled_growth_tables, default_options, delete_saved_growth_table,
    growth_tables, save_growth_table, saved_growth_tables, tbd_items, user_tables_path,
)
from .inference import GroupComparison, compare_groups
from .ingest import IngestReport, ingest_csv, ingest_file, ingest_records
from .jobs import JobQueue
from .models import MODEL_CATALOG, MODEL_NAMES
from .qc import FLAG_DESCRIPTIONS
from .schema import AnalysisOptions, EstimateRow, GrowthTable, IsotopeSample, SpecimenResult
from .simulate import SimulationScenario, SweepParam, run_simulation, sweep
from .validation import validate

app = FastAPI(title="WeanAge", version=__version__)
jobs = JobQueue()

ALLOWED_GROUPS = {"site", "species", "period"}
ALLOWED_MILESTONES = {"onset", "midpoint", "completion"}
ESTIMATE_MODELS = MODEL_NAMES | {"average"}


class RecordsIn(BaseModel):
    records: list[dict[str, Any]]


class AnalyzeIn(BaseModel):
    samples: list[IsotopeSample] = Field(min_length=1)
    options: AnalysisOptions | None = None


class AnalyzeOut(BaseModel):
    results: list[SpecimenResult]
    estimates: list[EstimateRow]


class AggregateIn(BaseModel):
    estimates: list[EstimateRow]
    group_by: list[str] = Field(default_factory=lambda: ["site", "species"])
    milestone: str = "completion"
    model: str | None = None
    bayes: bool = True


class CalibrateIn(BaseModel):
    species: str
    tooth: str
    points: list[CalibrationPoint] = Field(min_length=3)
    method: Method = "linear"
    n_knots: int = Field(default=6, ge=2, le=50)
    source: str = ""


class SimulateIn(BaseModel):
    scenario: SimulationScenario = Field(default_factory=SimulationScenario)
    options: AnalysisOptions | None = None
    sweep_param: SweepParam | None = None
    sweep_values: list[float] = Field(default_factory=list, max_length=12)


def _check_aggregate(body: AggregateIn) -> None:
    if not set(body.group_by) <= ALLOWED_GROUPS or not body.group_by:
        raise HTTPException(400, f"group_by must be a non-empty subset of {sorted(ALLOWED_GROUPS)}")
    if body.milestone not in ALLOWED_MILESTONES:
        raise HTTPException(400, f"milestone must be one of {sorted(ALLOWED_MILESTONES)}")
    if body.model is not None and body.model not in ESTIMATE_MODELS:
        raise HTTPException(400, f"unknown model {body.model!r}")


# ───────────────────────── configuration & data ─────────────────────────
@app.get("/api/config")
def get_config() -> dict[str, Any]:
    saved = saved_growth_tables()
    return {
        "version": __version__,
        "defaults": default_options().model_dump(),
        "models": MODEL_CATALOG,
        "growth_tables": [{**t.model_dump(), "saved": t.key in saved} for t in growth_tables().values()],
        "bundled_table_keys": list(bundled_growth_tables()),
        "user_tables_path": str(user_tables_path()),
        "qc_flags": FLAG_DESCRIPTIONS,
        "tbd": tbd_items(),
    }


@app.post("/api/ingest/file", response_model=IngestReport)
async def upload_file(file: UploadFile = File(...)) -> IngestReport:
    content = await file.read()
    try:
        return ingest_file(file.filename or "upload.csv", content)
    except Exception as exc:  # malformed files surface as a readable message
        raise HTTPException(status_code=400, detail=f"Could not read file: {exc}") from exc


# Kept for scripts written against the first release.
app.post("/api/ingest/csv", response_model=IngestReport)(upload_file)


@app.post("/api/ingest/records", response_model=IngestReport)
def validate_records(body: RecordsIn) -> IngestReport:
    return ingest_records(body.records)


@app.get("/api/example", response_model=IngestReport)
def example_dataset() -> IngestReport:
    return ingest_csv(DATA_DIR / "examples" / "synthetic_example.csv")


@app.get("/api/template.csv")
def template_csv() -> FileResponse:
    return FileResponse(DATA_DIR / "templates" / "isotope_template.csv",
                        media_type="text/csv", filename="weanage_template.csv")


# ───────────────────────── growth tables ─────────────────────────
@app.post("/api/growth-tables", response_model=GrowthTable)
def save_table(table: GrowthTable) -> GrowthTable:
    save_growth_table(table)
    return table


@app.delete("/api/growth-tables/{species}/{tooth}")
def delete_table(species: str, tooth: str) -> dict[str, bool]:
    return {"deleted": delete_saved_growth_table(f"{species.lower()}:{tooth}")}


@app.post("/api/growth-tables/calibrate", response_model=CalibrationResult)
def calibrate(body: CalibrateIn) -> CalibrationResult:
    try:
        return calibrate_growth_table(body.species, body.tooth, body.points, body.method,
                                      body.n_knots, body.source)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


# ───────────────────────── analysis ─────────────────────────
def _analyze(body: AnalyzeIn, progress=None) -> dict:
    results = analyze(body.samples, body.options or default_options(), progress=progress)
    return AnalyzeOut(results=results, estimates=estimate_rows(results)).model_dump(mode="json")


@app.post("/api/analyze", response_model=AnalyzeOut)
def run_analysis(body: AnalyzeIn) -> dict:
    return _analyze(body)


@app.post("/api/jobs/analyze")
def start_analysis(body: AnalyzeIn) -> dict:
    job = jobs.submit("analyze", lambda progress: _analyze(body, progress))
    return job.snapshot()


@app.post("/api/jobs/simulate")
def start_simulation(body: SimulateIn) -> dict:
    def work(progress):
        if body.sweep_param and body.sweep_values:
            runs = sweep(body.scenario, body.sweep_param, body.sweep_values, body.options, progress)
        else:
            runs = [run_simulation(body.scenario, body.options, progress)]
        return {"sweep_param": body.sweep_param, "runs": [r.model_dump(mode="json") for r in runs]}

    return jobs.submit("simulate", work).snapshot()


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "unknown job")
    return job.snapshot()


# ───────────────────────── comparison ─────────────────────────
@app.post("/api/aggregate")
def run_aggregate(body: AggregateIn) -> dict[str, Any]:
    _check_aggregate(body)
    summary = aggregate(body.estimates, group_by=body.group_by, milestone=body.milestone, model=body.model)
    tests: GroupComparison = compare_groups(body.estimates, group_by=body.group_by,
                                            milestone=body.milestone, model=body.model, bayes=body.bayes)
    return {
        "summary": frame_to_records(summary),
        "disagreement": frame_to_records(model_disagreement(body.estimates, body.milestone)),
        "validation": frame_to_records(validate(body.estimates, body.milestone)),
        "tests": tests.model_dump(mode="json"),
    }


@app.get("/", include_in_schema=False)
def index() -> RedirectResponse:
    return RedirectResponse("/app/")


app.mount("/app", StaticFiles(directory=WEB_DIR, html=True), name="web")
