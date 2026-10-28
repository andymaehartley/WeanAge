"""The command line: detect and run any calculation, with its methods paragraph."""

import json

from weanage import config
from weanage.cli import main

EXAMPLES = config.DATA_DIR / "examples"


def test_detect(capsys):
    main(["detect", str(EXAMPLES / "marj_rabba_killoff.csv")])
    out = capsys.readouterr().out
    assert "killoff    42 rows" in out and "tooth      no:" in out


def test_run_with_settings_and_methods(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"expected_infant_share": 0.3, "bootstrap_draws": 50}))
    results, methods = tmp_path / "out.json", tmp_path / "methods.md"
    main(["run", "lifetable", str(EXAMPLES / "muensingen_lifetable.csv"), "--settings", str(settings),
          "-o", str(results), "--methods", str(methods)])
    group = json.loads(results.read_text())["results"][0]
    assert abs(group["corrected"]["summary"]["infant_share"] - 0.3) < 1e-9
    text = methods.read_text()
    assert "71 skeletons" in text and "30% of all deaths" in text and "Siler W (1979)" in text


def test_run_every_one_table_calculation(tmp_path):
    files = {"killoff": "marj_rabba_killoff.csv", "mixing": "cima_mixing_wales_man.csv", "dental": "synthetic_dental_example.csv",
             "leh": "synthetic_hypoplasia_example.csv", "mobility": "cima_mobility_bamburgh.csv", "enamel": "synthetic_enamel_example.csv"}
    for name, file in files.items():
        out = tmp_path / f"{name}.json"
        main(["run", name, str(EXAMPLES / file), "-o", str(out)])
        assert json.loads(out.read_text())["results"], name
