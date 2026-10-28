"""The browser version: the Python entry point it calls, and the build script."""

import json
import subprocess
import sys
import zipfile
from pathlib import Path

from weanage import browser

ROOT = Path(__file__).parents[1]


def ask(name, request=None, **extra):
    return json.loads(browser.call(name, json.dumps(request or {}), **extra))


def test_requests_give_the_same_answers_as_the_server():
    assert ask("config")["result"]["models"]
    synthetic = (ROOT / "tests" / "data" / "synthetic_example.csv").read_bytes()
    samples = ask("upload", {"filename": "synthetic.csv"}, content=synthetic)["result"]["samples"]
    cattle = [s for s in samples if s["specimen_id"] in {"SYN-C01", "SYN-C04"}]
    steps = []
    options = {"models": ["logistic"], "monte_carlo_draws": 50}
    out = ask("analyze", {"samples": cattle, "options": options}, progress=lambda done, total: steps.append(done))
    assert out["ok"] and len(out["result"]["results"]) == 2 and steps == [1, 2]
    json.dumps(out)  # plain JSON: no NaN or numpy values left
    compared = ask("aggregate", {"estimates": out["result"]["estimates"], "bayes": False})
    assert compared["ok"] and compared["result"]["summary"]


def test_uploads_and_errors():
    csv = b"specimen_id,site,species,tooth,position_mm,d15N\nA,S,cattle,M2,0.5,8\n"
    assert len(ask("upload", {"filename": "x.csv"}, content=csv)["result"]["samples"]) == 1
    bad = ask("aggregate", {"estimates": [], "milestone": "never"})
    assert not bad["ok"] and "milestone" in bad["error"]


def test_build_script():
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_browser.py")], check=True, capture_output=True)
    out = ROOT / "dist" / "browser"
    assert 'name="weanage-mode" content="browser"' in (out / "index.html").read_text()
    names = zipfile.ZipFile(out / "weanage.zip").namelist()
    assert "weanage/browser.py" in names and "weanage/data/growth_tables.json" in names
    assert not any(n.startswith("weanage/web/") for n in names)
    assert (out / "pyworker.js").exists() and (out / "weanage_template.csv").exists()
