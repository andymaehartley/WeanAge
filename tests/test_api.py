from fastapi.testclient import TestClient

from weanage.api import app

client = TestClient(app)


def test_config_lists_tbd_items():
    body = client.get("/api/config").json()
    assert body["tbd"], "placeholders should be reported until lab values are filled in"
    assert {m["name"] for m in body["models"]} == {"logistic", "piecewise", "exponential", "elbow"}


def test_full_round_trip():
    example = client.get("/api/example").json()
    samples = [s for s in example["samples"] if s["specimen_id"] in {"SYN-C01", "SYN-C04"}]
    out = client.post("/api/analyze", json={"samples": samples, "options": {"monte_carlo_draws": 100}})
    assert out.status_code == 200, out.text
    estimates = out.json()["estimates"]
    agg = client.post("/api/aggregate", json={"estimates": estimates, "group_by": ["site"]})
    assert agg.status_code == 200
    assert len(agg.json()["summary"]) == 2


def test_upload_and_manual_records():
    csv = b"specimen_id,site,species,tooth,position_mm,d15N\nA,S,cattle,M2,0.5,8\n"
    r = client.post("/api/ingest/csv", files={"file": ("x.csv", csv, "text/csv")})
    assert r.status_code == 200 and len(r.json()["samples"]) == 1
    r = client.post("/api/ingest/records", json={"records": [{"specimen_id": "A", "d15N": "x"}]})
    assert r.json()["issues"]


def test_rejects_bad_aggregate_args():
    r = client.post("/api/aggregate", json={"estimates": [], "group_by": ["drop table"]})
    assert r.status_code == 400


def test_frontend_served():
    r = client.get("/app/")
    assert r.status_code == 200 and "WeanAge" in r.text
