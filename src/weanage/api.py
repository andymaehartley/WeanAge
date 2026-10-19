"""FastAPI service exposing the backend to the web frontend.

The API is stateless: the browser holds the dataset and sends it with each
request, so the same server works for a single desktop user or a shared lab install.
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
from .config import DATA_DIR, WEB_DIR, default_options, growth_tables, tbd_items
from .ingest import IngestReport, ingest_csv, ingest_records
from .models import MODEL_CATALOG, MODEL_NAMES
from .qc import FLAG_DESCRIPTIONS
from .schema import AnalysisOptions, EstimateRow, IsotopeSample, SpecimenResult
from .validation import validate

app = FastAPI(title="WeanAge", version=__version__)


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


ALLOWED_GROUPS = {"site", "species", "period"}
ALLOWED_MILESTONES = {"onset", "midpoint", "completion"}


@app.get("/api/config")
def get_config() -> dict[str, Any]:
    return {
        "version": __version__,
        "defaults": default_options().model_dump(),
        "models": MODEL_CATALOG,
        "growth_tables": [t.model_dump() for t in growth_tables().values()],
        "qc_flags": FLAG_DESCRIPTIONS,
        "tbd": tbd_items(),
    }


@app.post("/api/ingest/csv", response_model=IngestReport)
async def upload_csv(file: UploadFile = File(...)) -> IngestReport:
    content = await file.read()
    try:
        return ingest_csv(content)
    except Exception as exc:  # malformed files surface as a readable message
        raise HTTPException(status_code=400, detail=f"Could not read CSV: {exc}") from exc


@app.post("/api/ingest/records", response_model=IngestReport)
def validate_records(body: RecordsIn) -> IngestReport:
    return ingest_records(body.records)


@app.get("/api/example", response_model=IngestReport)
def example_dataset() -> IngestReport:
    return ingest_csv(DATA_DIR / "examples" / "synthetic_example.csv")


@app.get("/api/template.csv")
def template_csv() -> FileResponse:
    return FileResponse(
        DATA_DIR / "templates" / "isotope_template.csv",
        media_type="text/csv",
        filename="weanage_template.csv",
    )


@app.post("/api/analyze", response_model=AnalyzeOut)
def run_analysis(body: AnalyzeIn) -> AnalyzeOut:
    options = body.options or default_options()
    results = analyze(body.samples, options)
    return AnalyzeOut(results=results, estimates=estimate_rows(results))


@app.post("/api/aggregate")
def run_aggregate(body: AggregateIn) -> dict[str, Any]:
    if not set(body.group_by) <= ALLOWED_GROUPS or not body.group_by:
        raise HTTPException(400, f"group_by must be a non-empty subset of {sorted(ALLOWED_GROUPS)}")
    if body.milestone not in ALLOWED_MILESTONES:
        raise HTTPException(400, f"milestone must be one of {sorted(ALLOWED_MILESTONES)}")
    if body.model is not None and body.model not in MODEL_NAMES:
        raise HTTPException(400, f"unknown model {body.model!r}")
    summary = aggregate(
        body.estimates, group_by=body.group_by, milestone=body.milestone, model=body.model
    )
    return {
        "summary": frame_to_records(summary),
        "disagreement": frame_to_records(model_disagreement(body.estimates, body.milestone)),
        "validation": frame_to_records(validate(body.estimates, body.milestone)),
    }


@app.get("/", include_in_schema=False)
def index() -> RedirectResponse:
    return RedirectResponse("/app/")


app.mount("/app", StaticFiles(directory=WEB_DIR, html=True), name="web")
