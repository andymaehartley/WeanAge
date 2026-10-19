"""Position origin, multi-tooth animals, Excel, calibration, simulation, group inference, jobs."""

import io
import time

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from weanage import config
from weanage.analysis import analyze, estimate_rows
from weanage.calibrate import CalibrationPoint, calibrate_growth_table
from weanage.inference import compare_groups, holm, random_effects
from weanage.ingest import ingest_file, ingest_records
from weanage.schema import AnalysisOptions, IsotopeSample
from weanage.simulate import SimulationScenario, run_simulation, sweep

BASE = dict(specimen_id="T", site="S", species="cattle", tooth="M2", d15N=7.0)


# ── position origin ────────────────────────────────────────────────
def test_cervix_positions_converted_once():
    s = IsotopeSample(**BASE, position_mm=10, position_reference="Cervix", crown_height_mm=45)
    assert s.position_mm == 35 and s.position_measured_mm == 10 and s.position_reference == "apex"
    again = IsotopeSample(**s.model_dump())  # round trip through the UI must not re-convert
    assert again.position_mm == 35


def test_cervix_requires_crown_height():
    with pytest.raises(ValidationError):
        IsotopeSample(**BASE, position_mm=10, position_reference="cervix")


# ── multi-tooth individuals ────────────────────────────────────────
def test_teeth_of_one_animal_join_into_one_timeline(make_samples):
    m2 = make_samples("A-M2", tooth="M2")
    m1 = [s.model_copy(update={"specimen_id": "A-M1", "tooth": "M1"}) for s in make_samples("A-M1", n=30)]
    samples = [s.model_copy(update={"individual_id": "A"}) for s in m1 + m2]
    [res] = analyze(samples, AnalysisOptions(models=["logistic"], monte_carlo_draws=0))
    assert res.specimen_id == "A" and res.tooth == "M1+M2"
    assert {p.tooth for p in res.points} == {"M1", "M2"}
    ages = [p.age_months for p in res.points]
    assert ages == sorted(ages)


def test_individual_consistency_checks():
    rows = [dict(BASE, specimen_id="a", individual_id="X", position_mm=i) for i in range(6)]
    rows += [dict(BASE, specimen_id="b", individual_id="X", species="pig", tooth="M1", position_mm=i) for i in range(6)]
    msgs = [i.message for i in ingest_records(rows).issues]
    assert any("different speciess" in m or "different species" in m for m in msgs)


# ── Excel ─────────────────────────────────────────────────────────
def test_excel_upload():
    df = pd.DataFrame({"Specimen ID": ["A"] * 3, "Site": "S", "Species": "cattle", "Tooth": "M2",
                       "Position (mm)": [0.5, 1.5, 2.5], "δ15N (‰)": [8.0, 7.5, 7.0]})
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    report = ingest_file("data.xlsx", buf.getvalue())
    assert len(report.samples) == 3


# ── calibration & saved tables ─────────────────────────────────────
def test_calibration_recovers_linear_growth():
    rng = np.random.default_rng(0)
    pos = np.linspace(0, 40, 20)
    pts = [CalibrationPoint(position_mm=p, age_months=1 + p / 3 + rng.normal(0, 0.3)) for p in pos]
    res = calibrate_growth_table("cattle", "M2", pts, "linear")
    knots = res.table.knots
    assert knots[0].age_months == pytest.approx(1, abs=0.4)
    assert knots[-1].age_months == pytest.approx(1 + 40 / 3, abs=0.5)
    assert res.residual_sd == pytest.approx(0.3, abs=0.15)
    assert not res.table.placeholder
    iso = calibrate_growth_table("cattle", "M2", pts, "isotonic")
    ages = [k.age_months for k in iso.table.knots]
    assert ages == sorted(ages)


def test_saved_table_overrides_bundled_and_clears_tbd(tmp_path, monkeypatch):
    monkeypatch.setenv("WEANAGE_HOME", str(tmp_path))
    config.growth_tables.cache_clear()
    try:
        table = config.find_growth_table("cattle", "M2").model_copy(update={"placeholder": False, "label": "lab"})
        config.save_growth_table(table)
        assert config.find_growth_table("cattle", "M2").label == "lab"
        assert "growth:cattle:M2" not in {i["id"] for i in config.tbd_items()}
        assert config.delete_saved_growth_table("cattle:M2")
        assert config.find_growth_table("cattle", "M2").placeholder
    finally:
        config.growth_tables.cache_clear()


# ── simulation ────────────────────────────────────────────────────
def test_simulation_scores_models():
    sc = SimulationScenario(n_specimens=8, seed=3)
    res = run_simulation(sc, AnalysisOptions(models=["logistic", "piecewise"], monte_carlo_draws=100))
    logistic = next(s for s in res.scores if s.model == "logistic")
    assert logistic.success_rate == 1 and logistic.mae < 0.6


def test_sweep_worse_with_noise():
    sc = SimulationScenario(n_specimens=10, seed=4)
    runs = sweep(sc, "noise_sd", [0.05, 0.6], AnalysisOptions(models=["logistic"], monte_carlo_draws=0))
    maes = [next(s.mae for s in r.scores if s.model == "logistic") for r in runs]
    assert maes[0] < maes[1]


def test_simulated_age_model_error_increases_error():
    opts = AnalysisOptions(models=["logistic"], monte_carlo_draws=0)
    clean = run_simulation(SimulationScenario(n_specimens=20, seed=5), opts).scores[0].mae
    noisy = run_simulation(SimulationScenario(n_specimens=20, seed=5, age_model_error_sd=1.5), opts).scores[0].mae
    assert noisy > clean + 0.4


# ── group inference ───────────────────────────────────────────────
def test_random_effects_and_holm():
    mu, se, tau = random_effects(np.array([5.0, 5.0, 5.0]), np.array([1.0, 1.0, 1.0]))
    assert mu == 5 and tau == 0 and se == pytest.approx(1 / np.sqrt(3))
    _, _, tau = random_effects(np.array([2.0, 8.0, 5.0, 11.0]), np.array([0.2] * 4))
    assert tau > 2
    assert holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])


def test_group_comparison_detects_difference(make_samples):
    samples = []
    for i in range(4):
        samples += make_samples(f"A{i}", site="A", t_mid=8.5 + 0.2 * i, seed=i)
        samples += make_samples(f"B{i}", site="B", t_mid=4.5 + 0.2 * i, seed=10 + i)
    rows = estimate_rows(analyze(samples, AnalysisOptions(models=["logistic"], monte_carlo_draws=200)))
    cmp = compare_groups(rows, group_by=["site"])
    assert cmp.q_p < 0.001 and cmp.pairwise[0].p_holm < 0.001
    assert cmp.permutation_p < 0.05
    pair = cmp.bayes.pairs[0]
    assert {pair.group_a, pair.group_b} == {"A", "B"}
    prob_b_earlier = 1 - pair.prob_a_earlier if pair.group_a == "A" else pair.prob_a_earlier
    assert prob_b_earlier > 0.99
    assert cmp.bayes.rhat_max < 1.1


# ── API jobs ──────────────────────────────────────────────────────
def test_analysis_job_reports_progress():
    from weanage.api import app

    client = TestClient(app)
    samples = [s for s in client.get("/api/example").json()["samples"] if s["specimen_id"] in {"SYN-C01", "SYN-C02"}]
    job = client.post("/api/jobs/analyze", json={"samples": samples, "options": {"monte_carlo_draws": 50}}).json()
    for _ in range(200):
        state = client.get(f"/api/jobs/{job['id']}").json()
        if state["status"] in {"done", "error"}:
            break
        time.sleep(0.05)
    assert state["status"] == "done", state
    assert state["done"] == state["total"] == 2
    assert len(state["result"]["results"]) == 2
