"""The collagen diet mixing model."""

import numpy as np
import pandas as pd

from weanage import config
from weanage.mixing import analyze_mixing, ingest_mixing_dataframe
from weanage.schema import DietSource, MixingOptions, MixingSample

EXAMPLE = config.DATA_DIR / "examples" / "synthetic_mixing_example.csv"
TWO_FOODS = MixingOptions(sources=[DietSource(name="plants", d13C=-25, d13C_sd=0.3, d15N=3, d15N_sd=0.3),
                                   DietSource(name="fish", d13C=-13, d13C_sd=0.3, d15N=13, d15N_sd=0.3)],
                          offset_d13C=1, offset_d13C_sd=0.1, offset_d15N=4, offset_d15N_sd=0.1, draws=20000)


def sample(d13c, d15n, **extra):
    return MixingSample(specimen_id="P", site="S", species="human", d13C=d13c, d15N=d15n, **extra)


def test_known_mix_is_recovered():
    # 30% fish: δ13C = 0.7·-25 + 0.3·-13 + 1, δ15N = 0.7·3 + 0.3·13 + 4.
    (result,) = analyze_mixing([sample(-20.4, 10.0)], TWO_FOODS)["results"]
    fish = result["shares"]["fish"]
    assert abs(fish["estimate"] - 0.3) < 0.03 and fish["ci_low"] < 0.3 < fish["ci_high"]
    assert not result["warnings"]


def test_outside_the_mixing_space_warns():
    (result,) = analyze_mixing([sample(-30, 20)], TWO_FOODS)["results"]
    assert "outside the mixing space" in result["warnings"][0]


def test_example_sites_and_placeholders():
    df = pd.read_csv(EXAMPLE)
    report = ingest_mixing_dataframe(df)
    assert not report["issues"] and len(report["samples"]) == 30
    out = analyze_mixing(report["samples"])
    groups = {g["group"]: g["shares"] for g in out["groups"]}
    assert groups["Coast · human"]["Marine fish"] > 0.25 > groups["Inland · human"]["Marine fish"]
    assert out["placeholder"] and out["isotopes_used"] == ["d13C", "d15N", "d34S"]
    truths = [float(n.split("Marine fish ")[1]) for n in df.notes]
    estimates = [r["shares"]["Marine fish"]["estimate"] for r in out["results"]]
    assert np.corrcoef(truths, estimates)[0, 1] > 0.8
    # Four food groups but three isotopes is fine; without δ34S it is underdetermined and says so.
    no_sulphur = analyze_mixing([sample(-20, 9)])["results"][0]
    assert any("not fixed by the data" in w for w in no_sulphur["warnings"])


def test_api_job():
    import time

    from fastapi.testclient import TestClient

    from weanage.api import app

    client = TestClient(app)
    example = client.get("/api/calc/mixing/example").json()
    job = client.post("/api/calc/mixing/jobs", json={"samples": example["samples"][:3], "options": {"draws": 2000}}).json()
    for _ in range(200):
        state = client.get(f"/api/jobs/{job['id']}").json()
        if state["status"] in {"done", "error"}:
            break
        time.sleep(0.05)
    assert state["status"] == "done" and len(state["result"]["results"]) == 3
    assert client.get("/api/calc/killoff/template.csv").text.startswith("specimen_id,site,species,payne_stage")
    assert client.get("/api/calc/nothing/example").status_code == 400
    assert "mixing" in client.get("/api/config").json()["calculations"]
