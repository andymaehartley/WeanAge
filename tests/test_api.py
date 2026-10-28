"""The web API, called the same way the browser calls it."""

import time
from pathlib import Path

from fastapi.testclient import TestClient

from weanage.api import app

client = TestClient(app)
SYNTHETIC = (Path(__file__).parent / "data" / "synthetic_example.csv").read_bytes()


def synthetic(ids):
    """Teeth from the simulated test dataset, read through the upload address."""
    samples = client.post("/api/ingest/file", files={"file": ("synthetic.csv", SYNTHETIC)}).json()["samples"]
    return [s for s in samples if s["specimen_id"] in ids]


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
    assert body["qc_presets"]["modern"]["cn_max"] == 3.28  # Guiry & Szpak (2020)


def test_examples():
    names = [e["name"] for e in client.get("/api/config").json()["examples"]]
    assert names == ["isoarch_cattle", "cima_teeth_mikulcice"]  # published data only
    real = client.get("/api/example?name=isoarch_cattle").json()
    assert len(real["samples"]) == 158 and "ASSUMED" in real["message"]
    assert client.get("/api/example?name=nope").status_code == 400


def test_upload_and_records():
    csv = b"specimen_id,site,species,tooth,position_mm,d15N\nA,S,cattle,M2,0.5,8\n"
    assert len(client.post("/api/ingest/file", files={"file": ("x.csv", csv)}).json()["samples"]) == 1
    assert client.post("/api/ingest/records", json={"records": [{"specimen_id": "A", "d15N": "x"}]}).json()["issues"]


def test_analysis_job_and_comparison():
    samples = synthetic({"SYN-C01", "SYN-C04"})
    job = client.post("/api/jobs/analyze", json={"samples": samples, "options": {"monte_carlo_draws": 50}}).json()
    state = wait_for(job)
    assert state["status"] == "done" and state["done"] == state["total"] == 2
    out = client.post("/api/aggregate", json={"estimates": state["result"]["estimates"], "group_by": ["site"]})
    assert out.status_code == 200 and len(out.json()["summary"]) == 2 and "tests" in out.json()
    assert client.post("/api/aggregate", json={"estimates": [], "group_by": ["bad"]}).status_code == 400  # no such column


def test_one_stage_comparison():
    samples = synthetic({"SYN-C01", "SYN-C03", "SYN-C04", "SYN-C05"})
    job = client.post("/api/jobs/analyze", json={"samples": samples, "options": {"models": ["logistic"], "monte_carlo_draws": 50}})
    result = wait_for(job.json())["result"]
    body = {"estimates": result["estimates"], "group_by": ["site"], "bayes": "one_stage", "results": result["results"]}
    bayes = client.post("/api/aggregate", json=body).json()["tests"]["bayes"]
    assert bayes["method"] == "one-stage" and len(bayes["specimens"]) == 4 and bayes["rhat_max"] < 1.1


def test_simulation_job_and_calibration():
    body = {"scenario": {"n_specimens": 3}, "options": {"models": ["logistic"], "monte_carlo_draws": 0}}
    assert wait_for(client.post("/api/jobs/simulate", json=body).json())["status"] == "done"
    points = [{"position_mm": p, "age_months": 1 + p / 3} for p in range(0, 40, 5)]
    assert client.post("/api/growth-tables/calibrate", json={"species": "cattle", "tooth": "M2", "points": points}).status_code == 200


def test_frontend_is_served():
    page = client.get("/app/")
    assert page.status_code == 200 and "WeanAge" in page.text


def test_bone_requests():
    body = client.get("/api/config").json()
    assert body["bone_examples"][0]["name"] == "cima_wharram_percy" and body["bone_defaults"]["max_weaning_age_months"] is None
    assert body["bone_priors"]["cattle"]["max_weaning_age_months"] == 24  # blank settings use the species priors
    assert any(item["id"] == "turnover:cattle" for item in body["tbd"])
    example = client.get("/api/bone/example").json()
    assert len(example["samples"]) == 60 and "Wharram Percy" in example["message"]
    assert client.get("/api/bone/template.csv").text.startswith("specimen_id,site,species")
    upload = client.post("/api/bone/ingest/file", files={"file": ("b.csv", b"specimen_id,site,species,age_months,d15N\na,S,cattle,2,8\n")})
    assert upload.json()["samples"][0]["age_months"] == 2
    samples = example["samples"]
    job = client.post("/api/jobs/bone", json={"samples": samples, "options": {"warmup": 500, "keep": 500}}).json()
    state = wait_for(job)
    for _ in range(10):
        if state["status"] == "done":
            break
        state = wait_for(job)
    assert state["status"] == "done" and state["result"]["results"][0]["estimates"]["completion"]["estimate"] > 0


def test_cima_tooth_example():
    data = client.get("/api/example?name=cima_teeth_mikulcice").json()
    assert {s["species"] for s in data["samples"]} == {"human"} and len({s["specimen_id"] for s in data["samples"]}) == 12
    assert "ASSUMED" in data["samples"][0]["notes"] and "CC BY-SA" in data["message"]


def test_bone_planner_job():
    body = {"scenario": {"replicates": 2, "n_young": 20}, "options": {"chains": 4, "warmup": 500, "keep": 500}}
    job = client.post("/api/jobs/bone-simulate", json=body).json()
    state = wait_for(job)
    for _ in range(20):
        if state["status"] in {"done", "error"}:
            break
        state = wait_for(job)
    assert state["status"] == "done" and len(state["result"]["runs"][0]["cases"]) == 2
