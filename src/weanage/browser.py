"""The browser version's entry point: Python running inside the web page (Pyodide).

The web page's helper (web/pyworker.js) calls `call(name, request_json)` and gets
JSON text back, the same answers the local server gives at its /api/ addresses.
"""

import json
import math

import numpy as np

from . import service
from .schema import GrowthTable
from .service import AggregateIn, AnalyzeIn, BoneAnalyzeIn, CalibrateIn, SimulateBoneIn, SimulateIn


def clean(value):
    """Make a result safe for JSON: numpy numbers -> Python numbers, NaN/infinity -> null."""
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, np.ndarray):
        return clean(value.tolist())
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


# Each request name -> what to do with the request (a dict) and a progress callback.
# Analyses run on one core: a web page cannot start extra Python processes.
REQUESTS = {
    "config": lambda r, progress: {**service.get_config(), "user_tables_path": "this browser's storage"},
    "example": lambda r, progress: service.example_dataset(r.get("name", "synthetic")),
    "upload": lambda r, progress: service.read_upload(r["filename"], bytes(r["content"])),
    "records": lambda r, progress: service.check_records(r["records"]),
    "analyze": lambda r, progress: service.run_analysis(AnalyzeIn(**r), progress, workers=1),
    "simulate": lambda r, progress: service.run_planner(SimulateIn(**r), progress),
    "aggregate": lambda r, progress: service.compare(AggregateIn(**r)),
    "save_table": lambda r, progress: service.save_table(GrowthTable(**r)),
    "delete_table": lambda r, progress: service.delete_table(r["species"], r["tooth"]),
    "calibrate": lambda r, progress: service.calibrate(CalibrateIn(**r)),
    "bone_example": lambda r, progress: service.bone_example(r.get("name", "synthetic_bone")),
    "bone_records": lambda r, progress: service.check_bone_records(r["records"]),
    "bone_upload": lambda r, progress: service.read_bone_upload(r["filename"], bytes(r["content"])),
    "bone_analyze": lambda r, progress: service.run_bone_analysis(BoneAnalyzeIn(**r), progress),
    "bone_simulate": lambda r, progress: service.run_bone_planner(SimulateBoneIn(**r), progress),
    "calc_example": lambda r, progress: service.calculation_example(r["calc"], r.get("example")),
    "calc_records": lambda r, progress: service.check_calculation_records(r["calc"], r["records"]),
    "calc_upload": lambda r, progress: service.read_calculation_upload(r["calc"], r["filename"], bytes(r["content"])),
    "calc_analyze": lambda r, progress: service.run_calculation(r["calc"], r, progress),
}


def call(name, request_json="{}", progress=None, content=None):
    """Answer one request. `content` carries an uploaded file's bytes, which are not JSON."""
    request = json.loads(request_json)
    if content is not None:
        request["content"] = content.to_py() if hasattr(content, "to_py") else content  # JavaScript bytes -> Python
    try:
        return json.dumps({"ok": True, "result": clean(REQUESTS[name](request, progress))})
    except Exception as err:  # bad input, or a ValueError from the service
        return json.dumps({"ok": False, "error": str(err)})
