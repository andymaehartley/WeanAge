"""Season of birth (δ18O) and rumen development (δ13C) from enamel."""

import numpy as np
import pandas as pd

from weanage import config
from weanage.enamel import analyze_enamel, circular_mean, ingest_enamel_dataframe, smallest_arc
from weanage.schema import EnamelOptions, EnamelSample

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
        true_share = float(notes.split("true C4 share ")[1].split(";")[0])
        share = r["diet"]["share_c4"]
        assert r["diet"]["after_rumen"] and abs(share["estimate"] - true_share) < 0.05
        assert share["ci_low"] <= true_share <= share["ci_high"]
        moved = "true Sr shift" in notes
        assert bool(r["strontium"]["shifts"]) == moved, r["specimen_id"]
        if moved:  # the move from older rocks: 87Sr/86Sr falls as the enamel formed
            (shift,) = r["strontium"]["shifts"]
            assert abs(shift["position"] - float(notes.split("true Sr shift ")[1].split(" mm")[0])) < 3 and shift["size"] < 0
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
    assert not report["samples"] and "d18O, d13C or sr87_86" in report["issues"][0]["message"]


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


def test_calendar_months():
    """A tooth whose δ18O peaks 10 mm above the rumen transition, a quarter of a 40 mm year."""
    from weanage.enamel import calendar

    season = {"birth_index": {"estimate": 0.25}, "x0_mm": 30.0, "period_mm": 40.0, "draws": None}
    rumen = {"detected": True, "transition_mm": {"estimate": 20.0}, "draws": None}
    rows = [EnamelSample(specimen_id="T", site="S", species="cattle", tooth="M2", erj_distance_mm=1, d18O=-5,
                         weaning_age_months=9)]
    rng = np.random.default_rng(0)
    alone = calendar(season, rumen, rows, EnamelOptions(d18O_max_month=7), rng)
    assert abs(alone["rumen_month"]["estimate"] - 10) < 1e-9 and alone["birth_month"] is None  # July + 3 months
    # A reference tooth born at the start of April with index 0.25: this tooth, also 0.25, was born then too.
    dated = calendar(season, rumen, rows, EnamelOptions(reference_birth_index=0.25, reference_birth_month=4), rng)
    assert abs(dated["birth_month"]["estimate"] - 4) < 1e-9
    assert abs(dated["weaning_month"]["estimate"] - 1) < 1e-9  # April + 9 months = January


def test_smoothing_correction():
    rows = pd.read_csv(EXAMPLE).query("specimen_id == 'A01'")
    samples = ingest_enamel_dataframe(rows)["samples"]
    plain = analyze_enamel(samples)["results"][0]
    fixed = analyze_enamel(samples, EnamelOptions(mineralisation_length_mm=8))["results"][0]
    # The example was smoothed over 8 mm of a 46 mm year; sinc(8/46) restores about 5% of the amplitude.
    assert fixed["season"]["amplitude_restored_permil"] > plain["season"]["amplitude_permil"]
    assert abs(fixed["season"]["amplitude_restored_permil"] - 2.4) < 0.15
    assert fixed["rumen"]["width_restored_mm"] < fixed["rumen"]["width_mm"]
