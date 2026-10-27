"""Season of birth (δ18O) and rumen development (δ13C) from enamel."""

import numpy as np
import pandas as pd

from weanage import config
from weanage.enamel import analyze_enamel, circular_mean, ingest_enamel_dataframe, smallest_arc
from weanage.schema import EnamelSample

EXAMPLE = config.DATA_DIR / "examples" / "synthetic_enamel_example.csv"


def test_example_is_recovered():
    df = pd.read_csv(EXAMPLE)
    report = ingest_enamel_dataframe(df)
    assert not report["issues"] and len(report["teeth"]) == 12
    out = analyze_enamel(report["samples"])
    for r in out["results"]:
        notes = df[df.specimen_id == r["specimen_id"]].notes.iloc[0]
        true_index = float(notes.split("true birth index ")[1].split(";")[0])
        true_transition = float(notes.split("true rumen transition ")[1].split(" mm")[0])
        index = r["season"]["birth_index"]["estimate"]
        assert abs((index - true_index + 0.5) % 1 - 0.5) < 0.05, r["specimen_id"]
        assert r["rumen"]["detected"] and abs(r["rumen"]["transition_mm"]["estimate"] - true_transition) < 3
        true_share = float(notes.split("true C4 share ")[1])
        share = r["diet"]["share_c4"]
        assert r["diet"]["after_rumen"] and abs(share["estimate"] - true_share) < 0.05
        assert share["ci_low"] <= true_share <= share["ci_high"]
    groups = {g["site"]: g for g in out["groups"]}
    assert groups["Site A"]["spread_months"] < 2 < 6 < groups["Site B"]["spread_months"]  # calving within ~1 vs ~7 months
    assert groups["Site A"]["mean_share_c4"] < 0.1 and 0.25 < groups["Site B"]["mean_share_c4"] < 0.4


def test_c4_share_and_its_warnings():
    from weanage.enamel import diet_c4
    from weanage.schema import EnamelOptions

    rng = np.random.default_rng(0)
    x = np.linspace(50, 2, 12)
    pure_c4 = diet_c4(x, np.full(12, -11.0 + 14.1) + rng.normal(0, 0.1, 12), None, "M2", EnamelOptions(), rng)
    assert pure_c4["category"] == "C4 diet" and pure_c4["share_c4"]["estimate"] > 0.9
    m1 = diet_c4(x, np.full(12, -12.9), None, "M1", EnamelOptions(), rng)  # no rumen transition found in an M1
    assert m1["category"] == "C3 diet" and "suckled" in m1["warnings"][0]


def test_no_signal_gives_no_result():
    rng = np.random.default_rng(3)
    x = np.arange(50, 1, -2.5)
    samples = [EnamelSample(specimen_id="F1", site="S", species="cattle", tooth="M2", erj_distance_mm=xi,
                            d18O=-5 + rng.normal(0, 0.1), d13C=-13 + rng.normal(0, 0.1)) for xi in x]
    r = analyze_enamel(samples)["results"][0]
    assert r["season"]["birth_index"] is None and r["season"]["message"]
    assert not r["rumen"]["detected"] and r["rumen"]["message"]


def test_circular_summaries():
    mean = circular_mean([0.95, 0.05])
    assert min(mean, 1 - mean) < 1e-9  # the year end, not mid-year
    assert abs(smallest_arc([0.95, 0.05]) - 0.1) < 1e-9  # across the year end, not 0.9


def test_column_names_and_missing_values():
    df = pd.DataFrame({"Specimen": ["T1"], "Site": ["S"], "Taxon": ["Cattle"], "Tooth": ["M2"], "ERJ": [3.0]})
    report = ingest_enamel_dataframe(df)
    assert not report["samples"] and "d18O, d13C or both" in report["issues"][0]["message"]


def test_api_job():
    import time

    from fastapi.testclient import TestClient

    from weanage.api import app

    client = TestClient(app)
    example = client.get("/api/enamel/example").json()
    assert len(example["samples"]) == 252 and "SYNTHETIC" in example["message"]
    job = client.post("/api/jobs/enamel", json={"samples": example["samples"][:42], "options": {"draws": 100}}).json()
    for _ in range(200):
        state = client.get(f"/api/jobs/{job['id']}").json()
        if state["status"] in {"done", "error"}:
            break
        time.sleep(0.05)
    assert state["status"] == "done" and len(state["result"]["results"]) == 2
    assert client.get("/api/enamel/template.csv").status_code == 200
