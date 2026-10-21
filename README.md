# <img src="src/weanage/web/logo.svg" width="36" alt=""> WeanAge

An open-source tool for estimating **age at weaning** in livestock (cattle, pigs, horses)
from sequentially sampled **incremental dentine δ¹⁵N**. You give it isotope values
measured along a tooth. It returns modelled weaning curves and weaning ages with
uncertainty, compares curve models, sites and species, and helps plan sampling before
any tooth is cut.

The aim is one documented, validated method that any zooarchaeology lab can use
without writing its own statistical model, so that weaning ages are comparable across
sites, species and research groups.

> ⚠️ **Status: pre-lab-data.** All tooth growth tables and several method parameters
> are **placeholders**. They are marked `TBD-LAB` in the data files and highlighted in
> yellow in the app, and results are illustrative until they are filled in. See
> [`docs/LAB_DATA_TBD.md`](docs/LAB_DATA_TBD.md).

## Quick start

```bash
pip install -e .          # Python 3.11–3.14 (or: poetry install)
weanage                   # opens http://127.0.0.1:8765/app/ in your browser
```

A guided tour runs on first use, and every technical term has a **?** button with a
plain-language explanation. The app has five tabs:

1. **Data**: drop in a CSV or Excel file, load the synthetic example, or type samples
   in by hand. Problems are reported straight away, row by row.
2. **Settings**: choose curve models, uncertainty method, quality-control limits,
   time averaging, the seasonal term and adult-female baselines. You can also edit,
   calibrate and save tooth growth tables here.
3. **Results**: a curve chart for each specimen (drag to zoom, δ¹³C overlay,
   tooth-position axis), the best and model-averaged weaning ages, warnings and a
   model-comparison table.
4. **Compare**: group summaries, formal tests (random-effects, permutation and a
   hierarchical Bayesian model), how much the models disagree, and validation.
5. **Plan sampling**: simulate teeth with known weaning ages to compare sampling
   intervals, sample sizes or noise levels.

The app opens in a **high-contrast dark theme**; *Light mode* and *Larger text* in the
header switch it, and the choice is remembered. All text meets WCAG AAA contrast (7:1),
curves are at least 4.5:1 and also differ by dash pattern (checked by `tests/test_contrast.py`).
Saved charts and reports always use the light colours so they print well.

**Save** and **Open** store the whole project in a file, and work is also kept in the
browser automatically. **Report** downloads a self-contained HTML report (print it to
get a PDF).

### Browser version (nothing to install)

The same app can run entirely inside a web browser: the page downloads Python
(Pyodide, about 40 MB the first time, then cached) and does every calculation on the
user's own computer. No data leaves the computer, and there is no server to maintain.

```bash
python scripts/build_browser.py --serve   # build dist/browser/ and preview it at http://localhost:8000
```

`dist/browser/` is a folder of plain files that can go on any static web host. Pushing to
`main` publishes it to GitHub Pages automatically (`.github/workflows/pages.yml`; one-time
setup: *Settings → Pages → Source: GitHub Actions*).

Differences from the local app:
* the first visit needs internet and takes a little while to load; after that it starts quickly,
* analyses use one processor core, so large datasets are slower,
* saved growth tables and autosaved work are kept in that browser only.

Without the app:

```bash
weanage analyze my_data.csv -o estimates.csv      # CSV or .xlsx
weanage validate reference.csv                    # accuracy on known-age animals
weanage isoarch export.xlsx                       # list sequential dentine series in an IsoArcH export
weanage isoarch export.xlsx --site Khami -o khami.csv   # ... and convert them to WeanAge input
weanage --host 0.0.0.0 --no-browser               # shared server on a lab machine
```

## Input columns

One row per dentine slice. Common spellings (`δ15N (‰)`, `C:N`, `%C`, `Animal`, …) are
recognised. A blank template is under *Data → Download blank template*.

| column | required | meaning |
|---|---|---|
| `specimen_id` | ✔ | one tooth |
| `site`, `species`, `tooth` | ✔ | species `cattle`, `pig`, `horse` (others need an age model) |
| `position_mm` | ✔ | distance from the **cusp apex** to the middle of the slice |
| `d15N` | ✔ | δ¹⁵N, ‰ AIR |
| `individual_id` | | teeth sharing it (e.g. M1 + M2) are joined into one timeline |
| `position_reference`, `crown_height_mm` | | set `cervix` if measured from the crown base |
| `d13C`, `pct_C`, `pct_N`, `cn_ratio`, `collagen_yield_pct` | | collagen QC and the seasonality check |
| `increment_width_mm` | | slice height if not 1 mm (time averaging) |
| `sample_index`, `period`, `notes` | | |
| `known_weaning_age_months` | | known-age reference animals (validation) |
| `published_weaning_age_months` | | a published estimate, for comparison |

## How it works

```
file / form ─► check the data (pydantic) ─► collagen QC (C:N, %C, %N, yield)
            ─► position → age (growth table per species and tooth; teeth of one animal joined)
            ─► fit curves: logistic, piecewise, exponential, two-phase, WEAN-style elbow
                 (optional: time averaging, yearly seasonal term, adult-female baseline)
            ─► weaning ages with 95 % intervals (covariance or bootstrap, shared age-model error)
            ─► AICc weights, model average, seasonality and rising-profile checks
            ─► group comparison (random effects, permutation, two- or one-stage hierarchical Bayes)
            ─► validation against known-age animals
```

**Bone calculation.** For bone collagen from many young animals that died at different ages,
the Data page offers a second calculation after WARN (Tsutaya & Yoneda 2013): a diet model
(milk giving way to weaning food between ages t1 and t2) and age-dependent bone turnover are
fitted to δ¹⁵N against age at death, giving t1, t2, the nursing enrichment and the weaning-food
δ¹⁵N with credible intervals. Livestock turnover rates are still placeholders (TBD-LAB).

[`docs/METHODS.md`](docs/METHODS.md) gives the equations.
[`docs/RELATED_TOOLS.md`](docs/RELATED_TOOLS.md) compares WeanAge with WARN, MDSS and WEAN.
[`docs/VALIDATION.md`](docs/VALIDATION.md) explains how to test it on known-age animals.
[`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) is a step-by-step guide with screenshots, and
[`docs/brief/`](docs/brief/) a printable two-page summary of the methods for events.

### Research the method builds on

| finding | where it is used |
|---|---|
| Cattle M1/M2 crown start and end ages (Brown et al. 1960) | cattle growth tables |
| δ¹⁵N falls while δ¹³C rises at weaning in known-age calves (Balasse et al. 2001) | δ¹³C weaning check; validation |
| Modern collagen needs C:N 3.00–3.28 (Guiry & Szpak 2020) | "modern" QC preset |
| Coarse slices blur and delay the weaning signal (Tsutaya 2020; MDSS) | time averaging |
| Stress and starvation raise δ¹⁵N (Beaumont & Montgomery 2016) | rising-profile warning |
| Prehistoric cattle calved seasonally (Balasse et al. 2021) | seasonal term and checks |
| Weaning-age curves and elbow (WARN, WEAN) | curve models, adult-female baseline |

## Code layout

Everything is written to be readable by someone new to programming: plain functions,
results as ordinary dictionaries, and comments in everyday language.

```
src/weanage/
  schema.py      the shape of the input data and settings (checked by pydantic)
  config.py      reads the data files; saved growth tables; the TBD-LAB list
  ingest.py      reads CSV/Excel/form rows and checks them
  qc.py          collagen quality flags
  growth.py      position on the tooth → age
  models.py      the curves, fitting, uncertainty, model averaging, seasonal test
  analysis.py    the step-by-step analysis of each specimen (runs in parallel)
  aggregate.py   group summaries, model disagreement, validation metrics
  inference.py   group tests and the hierarchical Bayesian model
  bone.py        the bone calculation (after WARN): many animals, δ15N against age at death
  simulate.py    the sampling planner
  calibrate.py   growth tables from known-age reference points
  service.py     everything the app can ask for, as plain functions
  api.py         the local web server (and background jobs with progress)
  browser.py     the same requests for the browser version (Python inside the page)
  cli.py         the `weanage` command
  data/          growth and bone-turnover tables, QC limits, lab parameters, templates, examples
  web/           the app: HTML, CSS and plain JavaScript (pyworker.js runs Python in the browser version)
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

GitHub Actions runs the checks on every push. Pushing a tag such as `v0.2.0` builds the
single-file apps for Linux, Windows and macOS and publishes the package to PyPI (after
the repository is registered as a trusted publisher on pypi.org).

## Citing

See [`CITATION.cff`](CITATION.cff). Archiving a release on Zenodo (metadata in
`.zenodo.json`) gives a DOI. A draft software paper is in [`paper/`](paper/).

## Licence

MIT
