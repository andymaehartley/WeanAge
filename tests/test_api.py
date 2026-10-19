"""The web API, called the same way the browser calls it."""

import time

from fastapi.testclient import TestClient

from weanage.api import app

client = TestClient(app)


def wait_for(job):
    for _ in range(300):
        state = client.get(f"/api/jobs/{job['id']}").json()
        if state["status"] in {"done", "error"}:
            return state
        time.sleep(0.05)
    return state


def test_config():
    body = client.get("/api/config").json()
    assert body["tbd"] and {m["name"] for m in body["models"]} == {"logistic", "piecewise", "exponential", "two_phase", "elbow"}


def test_upload_and_records():
    csv = b"specimen_id,site,species,tooth,position_mm,d15N\nA,S,cattle,M2,0.5,8\n"
    assert len(client.post("/api/ingest/file", files={"file": ("x.csv", csv)}).json()["samples"]) == 1
    assert client.post("/api/ingest/records", json={"records": [{"specimen_id": "A", "d15N": "x"}]}).json()["issues"]


def test_analysis_job_and_comparison():
    samples = [s for s in client.get("/api/example").json()["samples"] if s["specimen_id"] in {"SYN-C01", "SYN-C04"}]
    job = client.post("/api/jobs/analyze", json={"samples": samples, "options": {"monte_carlo_draws": 50}}).json()
    state = wait_for(job)
    assert state["status"] == "done" and state["done"] == state["total"] == 2
    out = client.post("/api/aggregate", json={"estimates": state["result"]["estimates"], "group_by": ["site"]})
    assert out.status_code == 200 and len(out.json()["summary"]) == 2 and "tests" in out.json()
    assert client.post("/api/aggregate", json={"estimates": [], "group_by": ["bad"]}).status_code == 400


def test_simulation_job_and_calibration():
    body = {"scenario": {"n_specimens": 3}, "options": {"models": ["logistic"], "monte_carlo_draws": 0}}
    assert wait_for(client.post("/api/jobs/simulate", json=body).json())["status"] == "done"
    points = [{"position_mm": p, "age_months": 1 + p / 3} for p in range(0, 40, 5)]
    assert client.post("/api/growth-tables/calibrate", json={"species": "cattle", "tooth": "M2", "points": points}).status_code == 200


def test_frontend_is_served():
    page = client.get("/app/")
    assert page.status_code == 200 and "WeanAge" in page.text
