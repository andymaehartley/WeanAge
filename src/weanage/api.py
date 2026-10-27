"""The local web server: the browser sends data here and gets results back as JSON.

The work itself is done in service.py; this file only connects web addresses to it.
The server keeps no data of its own (apart from saved growth tables and short-lived
background jobs), so it works for one person or a whole lab.
"""

import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, config, service
from .schema import GrowthTable
from .service import AggregateIn, AnalyzeIn, BoneAnalyzeIn, CalibrateIn, SimulateBoneIn, SimulateIn

app = FastAPI(title="WeanAge", version=__version__)


def checked(work, *args):
    """Run service code, turning a ValueError into a '400 Bad Request' answer."""
    try:
        return work(*args)
    except ValueError as err:
        raise HTTPException(400, str(err)) from err


# Background jobs (so long runs can show a progress bar)
JOBS: dict = {}
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


# Settings and data
@app.get("/api/config")
def get_config():
    return service.get_config()


@app.post("/api/ingest/file")
async def upload_file(file: UploadFile = File(...)):
    return checked(service.read_upload, file.filename, await file.read())


@app.post("/api/ingest/records")
def validate_records(body: dict):
    return service.check_records(body.get("records", []))


@app.get("/api/example")
def example_dataset(name: str = "synthetic"):
    return checked(service.example_dataset, name)


@app.get("/api/template.csv")
def template_csv():
    return FileResponse(config.DATA_DIR / "templates" / "isotope_template.csv", media_type="text/csv", filename="weanage_template.csv")


@app.post("/api/bone/ingest/file")
async def upload_bone_file(file: UploadFile = File(...)):
    return checked(service.read_bone_upload, file.filename, await file.read())


@app.post("/api/bone/ingest/records")
def check_bone_records(body: dict):
    return checked(service.check_bone_records, body.get("records", []))


@app.get("/api/bone/example")
def bone_example(name: str = "synthetic_bone"):
    return checked(service.bone_example, name)


@app.get("/api/bone/template.csv")
def bone_template_csv():
    return FileResponse(config.DATA_DIR / "templates" / "bone_template.csv", media_type="text/csv", filename="weanage_bone_template.csv")


@app.post("/api/growth-tables")
def save_table(table: GrowthTable):
    return service.save_table(table)


@app.delete("/api/growth-tables/{species}/{tooth}")
def delete_table(species: str, tooth: str):
    return service.delete_table(species, tooth)


@app.post("/api/growth-tables/calibrate")
def calibrate(body: CalibrateIn):
    return checked(service.calibrate, body)


# Analysis, simulation, comparison
@app.post("/api/jobs/analyze")
def analyze_in_background(body: AnalyzeIn):
    return start_job("analyze", lambda progress: service.run_analysis(body, progress))


@app.post("/api/jobs/bone")
def bone_in_background(body: BoneAnalyzeIn):
    return start_job("bone", lambda progress: service.run_bone_analysis(body, progress))


@app.post("/api/jobs/bone-simulate")
def bone_simulate_in_background(body: SimulateBoneIn):
    return start_job("bone-simulate", lambda progress: service.run_bone_planner(body, progress))


@app.post("/api/jobs/simulate")
def simulate_in_background(body: SimulateIn):
    return start_job("simulate", lambda progress: service.run_planner(body, progress))


@app.post("/api/aggregate")
def compare(body: AggregateIn):
    return checked(service.compare, body)


# The one-table calculations (enamel, kill-off, diet mixing) share these addresses.
# They come last, so the addresses above are matched first.
@app.post("/api/calc/{name}/ingest/file")
async def upload_calculation_file(name: str, file: UploadFile = File(...)):
    return checked(service.read_calculation_upload, name, file.filename, await file.read())


@app.post("/api/calc/{name}/ingest/records")
def check_calculation_records(name: str, body: dict):
    return checked(service.check_calculation_records, name, body.get("records", []))


@app.get("/api/calc/{name}/example")
def calculation_example(name: str, example: str | None = None):
    return checked(service.calculation_example, name, example)


@app.get("/api/calc/{name}/template.csv")
def calculation_template_csv(name: str):
    checked(service.calculation, name)
    return FileResponse(config.DATA_DIR / "templates" / f"{name}_template.csv", media_type="text/csv",
                        filename=f"weanage_{name}_template.csv")


@app.post("/api/calc/{name}/jobs")
def calculation_in_background(name: str, body: dict):
    checked(service.calculation, name)
    return start_job(name, lambda progress: service.run_calculation(name, body, progress))


@app.get("/", include_in_schema=False)
def index():
    return RedirectResponse("/app/")


app.mount("/app", StaticFiles(directory=config.WEB_DIR, html=True), name="web")
