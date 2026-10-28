"""The methods paragraph written from the settings used."""

from fastapi.testclient import TestClient

from weanage.api import app
from weanage.methods import REFERENCES, write_methods


def test_every_calculation_writes_a_paragraph_with_its_references():
    runs = {name: {"options": {}, "n": 10} for name in
            ["tooth", "bone", "enamel", "killoff", "mixing", "dental", "leh", "lifetable", "mobility"]}
    out = write_methods(runs)
    assert len(out["paragraphs"]) >= 10 and out["placeholders"]
    for reference in out["references"]:
        assert reference in REFERENCES.values()
    cited_years = {r.split("(")[1][:4] for r in out["references"] if "(" in r}
    assert {"2002", "1963", "1973", "2012"} <= cited_years


def test_text_follows_the_settings():
    plain = write_methods({"dental": {"options": {"method": "midpoint"}}})["text"]
    assert "transition analysis" not in plain and "Boldsen" not in plain
    transition = write_methods({"dental": {"options": {}}})["text"]
    assert "transition analysis" in transition and "Boldsen JL" in transition
    strontium_only = write_methods({"mobility": {"options": {}, "details": {"d18O": False, "sr": True, "origins": False}}})
    assert "δ18O was converted" not in strontium_only["text"] and "Chenery" not in strontium_only["text"]
    tooth = write_methods({"tooth": {"options": {"models": ["logistic"], "time_averaging": True},
                                      "details": {"growth_tables": ["Human - permanent first molar"]}}})
    assert "Logistic curves" in tooth["text"] and "Tsutaya 2020" in tooth["text"]
    assert [p["label"] for p in tooth["placeholders"] if p["area"] == "Tooth growth table"] == ["Human - permanent first molar"]


def test_api():
    client = TestClient(app)
    assert "WeanAge" in client.post("/api/methods", json={"runs": {"lifetable": {"options": {}}}}).json()["text"]
    assert client.post("/api/methods", json={"runs": {"nothing": {}}}).status_code == 400
