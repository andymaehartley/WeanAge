# <img src="src/weanage/web/logo.svg" width="36" alt=""> WeanAge

[![tests](https://github.com/andymaehartley/repotest/actions/workflows/tests.yml/badge.svg)](https://github.com/andymaehartley/repotest/actions/workflows/tests.yml)
[![browser version](https://github.com/andymaehartley/repotest/actions/workflows/pages.yml/badge.svg)](https://andymaehartley.github.io/repotest/)

WeanAge estimates age at weaning from δ¹⁵N in archaeological animals and people. It works
from δ¹⁵N measured along a tooth (incremental dentine), or from the bone collagen of many
young individuals who died at different ages (after WARN). It reports weaning ages with
95% intervals, compares curve models, sites and species, and simulates sampling designs
before teeth are cut or bones sampled. For cattle it also estimates season of birth (enamel
δ¹⁸O) and rumen development (enamel δ¹³C) along a molar.

Browser version (no installation): <https://andymaehartley.github.io/repotest/>

Status: the tooth growth tables and several method parameters are placeholders, marked
`TBD-LAB` in the data files and highlighted in the app. Results are illustrative until
they are replaced; see [`docs/LAB_DATA_TBD.md`](docs/LAB_DATA_TBD.md).

## Install and run

```bash
pip install -e .          # Python 3.11–3.14 (or: poetry install)
weanage                   # opens http://127.0.0.1:8765/app/ in your browser
```

Command line, without the app:

```bash
weanage analyze my_data.csv -o estimates.csv      # CSV or .xlsx
weanage validate reference.csv                    # accuracy on known-age animals
weanage isoarch export.xlsx                       # list sequential dentine series in an IsoArcH export
weanage isoarch export.xlsx --site Khami -o khami.csv   # ... and convert them to WeanAge input
weanage --host 0.0.0.0 --no-browser               # shared server on a lab machine
```

The app has five tabs (Data, Settings, Results, Compare, Plan sampling). The
[user guide](docs/USER_GUIDE.md) walks through them, and [`docs/METHODS.md`](docs/METHODS.md)
gives the models, equations and checks. Examples bundled with the app: a synthetic tooth
dataset, a synthetic bone dataset, cattle dentine from Khami and Bornais (IsoArcH), and
human bone and dentine from Wharram Percy, York Fishergate House, Newark Bay and Mikulčice
(CIMA).

### Browser version

The browser version runs Python in the page (Pyodide, about 40 MB on the first visit,
then cached). All calculations run on the user's computer and no data are uploaded.

```bash
python scripts/build_browser.py --serve   # build dist/browser/ and preview it at http://localhost:8000
```

`dist/browser/` is a folder of static files; pushing to `main` publishes it to GitHub Pages
(`.github/workflows/pages.yml`). Differences from the installed app:

* the first visit needs an internet connection;
* large analyses are split across up to three engines (web workers), depending on the
  processor cores and memory available;
* saved growth tables and autosaved work are kept in that browser only.

## Input columns

Tooth data: one row per dentine slice. Common spellings (`δ15N (‰)`, `C:N`, `%C`, `Animal`, …)
are recognised. A blank template is under *Data → Download blank template*.

| column | required | meaning |
|---|---|---|
| `specimen_id` | yes | one tooth |
| `site`, `species`, `tooth` | yes | bundled growth tables: cattle M1 and M2, pig M1, horse M1, human M1; other teeth need a table |
| `position_mm` | yes | distance from the cusp apex to the middle of the slice |
| `d15N` | yes | δ¹⁵N, ‰ AIR |
| `individual_id` | | teeth sharing it (e.g. M1 + M2) are joined into one timeline |
| `position_reference`, `crown_height_mm` | | set `cervix` if measured from the crown base |
| `d13C`, `pct_C`, `pct_N`, `cn_ratio`, `collagen_yield_pct` | | collagen QC and the δ¹³C checks |
| `increment_width_mm` | | slice height if not 1 mm (time averaging) |
| `sample_index`, `period`, `notes` | | |
| `known_weaning_age_months` | | known-age reference animals (validation) |
| `published_weaning_age_months` | | a published estimate, for comparison |

Bone data: one row per animal, with `specimen_id`, `site`, `species`, `d15N` and, for
young animals, the age at death (`age_months`, or `age_min_months` + `age_max_months`);
adults are marked with `age_class` and `sex`. Bone turnover tables and priors are included
for cattle, sheep, goat, pig and human (the livestock values are placeholders). See the
[user guide](docs/USER_GUIDE.md#bone-instead-of-teeth).

Enamel data (cattle): one row per enamel sample, with `specimen_id`, `site`, `species`,
`tooth`, `erj_distance_mm` (distance from the enamel-root junction) and `d18O` and/or `d13C`
(enamel carbonate, ‰ VPDB). See the
[user guide](docs/USER_GUIDE.md#season-of-birth-and-rumen-development-enamel).

## Further documentation

* [`docs/guide/WeanAge_user_guide.pdf`](docs/guide/WeanAge_user_guide.pdf): the PDF guide to how
  each part works, with citations (also under Help in the app; rebuilt with `scripts/build_guide.py`).
* [`docs/LAB_CHECKLIST.md`](docs/LAB_CHECKLIST.md): what still has to be measured or checked in the lab.
* [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md): step-by-step guide with screenshots.
* [`docs/METHODS.md`](docs/METHODS.md): methods and references.
* [`docs/VALIDATION.md`](docs/VALIDATION.md): testing on known-age animals.
* [`docs/RELATED_TOOLS.md`](docs/RELATED_TOOLS.md): comparison with WARN, MDSS and WEAN.
* [`docs/BONE_LITERATURE.md`](docs/BONE_LITERATURE.md): sources for the bone calculation.
* [`docs/brief/`](docs/brief/): printable two-page methods summary.

## Research the method builds on

| finding | where it is used |
|---|---|
| Cattle M1/M2 crown start and end ages (Brown et al. 1960) | cattle growth tables |
| δ¹⁵N falls while δ¹³C rises at weaning in known-age calves (Balasse et al. 2001) | δ¹³C weaning check; validation |
| Modern collagen needs C:N 3.00–3.28 (Guiry & Szpak 2020) | "modern" QC preset |
| Coarse slices blur and delay the weaning signal (Tsutaya 2020; MDSS) | time averaging |
| Stress and starvation raise δ¹⁵N (Beaumont & Montgomery 2016) | rising-profile warning |
| Prehistoric cattle calved seasonally (Balasse et al. 2021) | seasonal term and checks |
| Weaning curves and elbow (WARN: Tsutaya & Yoneda 2013; WEAN: Ganiatsou et al. 2023) | curve models, adult-female baseline, bone calculation |

## Code layout

```
src/weanage/
  schema.py      input data and settings (checked by pydantic)
  config.py      reads the data files; saved growth tables; the TBD-LAB list
  ingest.py      reads CSV/Excel/form rows and checks them
  qc.py          collagen quality flags
  growth.py      position on the tooth → age
  models.py      curves, fitting, uncertainty, model averaging, seasonal test
  analysis.py    analysis of each specimen (runs in parallel)
  aggregate.py   group summaries, model disagreement, validation metrics
  inference.py   group tests and the hierarchical Bayesian model
  joint.py       one-stage Bayesian model
  bone.py        bone calculation (after WARN)
  enamel.py      season of birth (δ18O) and rumen development (δ13C) from enamel
  simulate.py    tooth sampling planner
  bone_planner.py  bone sampling planner
  calibrate.py   growth tables from known-age reference points
  service.py     the requests the app can make
  api.py         local web server and background jobs
  browser.py     the same requests for the browser version
  isoarch.py     converts IsoArcH exports
  cli.py         the `weanage` command
  data/          growth and bone-turnover tables, priors, QC limits, lab parameters, templates, examples
  web/           the app (HTML, CSS, JavaScript; pyworker.js runs Python in the browser version)
tests/           pytest suite, including a browser test (needs Playwright)
packaging/       single-file app (PyInstaller)
paper/           JOSS paper draft
```

## Development

```bash
pip install -e . pytest httpx ruff mypy
pytest                       # add `pip install playwright && playwright install chromium` for the browser test
ruff check src tests && mypy src
python scripts/make_synthetic_example.py      # regenerate the example data
python scripts/build_browser.py               # browser version in dist/browser/
pyinstaller packaging/weanage.spec            # single-file app in dist/
```

GitHub Actions runs the tests on every push. A version tag (e.g. `v0.2.0`) builds the
single-file apps for Linux, Windows and macOS and publishes the package to PyPI.

## Citing

See [`CITATION.cff`](CITATION.cff). Release metadata for Zenodo is in `.zenodo.json`. A draft
software paper is in [`paper/`](paper/).

## Licence

The code is MIT-licensed ([`LICENSE`](LICENSE)). The bundled example data keep their own
licences (IsoArcH: CC BY 4.0; CIMA: CC BY-SA); see
[`src/weanage/data/examples/README.md`](src/weanage/data/examples/README.md).

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and the [code of conduct](CODE_OF_CONDUCT.md).
