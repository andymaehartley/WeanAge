# WeanAge

An open-source tool for estimating **age at weaning** in livestock (cattle, pigs, horses)
from sequentially sampled **incremental dentine δ¹⁵N**. You give it isotope values
measured along a tooth, and it returns modelled weaning curves and weaning-age
estimates with uncertainty. It also compares those estimates across curve models,
sites and species.

The aim is a single, documented, validated method that any zooarchaeology lab can
use without writing its own statistical model. That makes weaning ages comparable
across sites, species and research groups.

> ⚠️ **Status: pre-lab-data scaffold.** All tooth growth tables and several method
> parameters are **placeholders**. They are marked `TBD-LAB` in the code and data
> files, and highlighted in yellow in the app. Results are illustrative until those
> values are filled in. See [`docs/LAB_DATA_TBD.md`](docs/LAB_DATA_TBD.md).

---

## Quick start

```bash
# Python 3.11+
poetry install            # or: pip install -e .
poetry run weanage        # opens http://127.0.0.1:8765/app/ in your browser
```

In the app:

1. **Data**: upload a CSV (or *Load synthetic example*), or type samples in by hand.
   Validation runs straight away and points to problem rows.
2. **Settings**: choose curve models, the milestone to report (onset, midpoint or
   completion), QC thresholds and the tooth age model.
3. **Results**: for each specimen you get a curve plot (each model can be toggled),
   a model-comparison table and exports (CSV, JSON, SVG).
4. **Compare**: summaries by site, species and period, how much the models disagree,
   and validation against known-age animals.

To use it without the GUI:

```bash
weanage analyze my_data.csv -o estimates.csv
```

To run it as a shared server on a lab machine, use `weanage --host 0.0.0.0 --no-browser`.

## Input format

One row per dentine increment. Common header spellings are recognised
(`δ15N (‰)`, `d15N_AIR`, `C:N`, `%C` and so on). There is a blank template under
*Data → Download blank template*, and a copy at
`src/weanage/data/templates/isotope_template.csv`.

| column | required | meaning |
|---|---|---|
| `specimen_id` | ✔ | one tooth / individual |
| `site` | ✔ | |
| `species` | ✔ | `cattle`, `pig`, `horse` (others need a custom age model) |
| `tooth` | ✔ | e.g. `M2`; must match a growth table or a custom model |
| `position_mm` | ✔ | distance from the **cusp apex** to the increment midpoint |
| `d15N` | ✔ | δ¹⁵N, ‰ AIR |
| `d13C`, `pct_C`, `pct_N`, `cn_ratio`, `collagen_yield_pct` | | used for collagen QC (C:N is derived from %C/%N if missing) |
| `sample_index`, `period`, `notes` | | |
| `increment_width_mm` | | height of each section if not 1 mm (used by time averaging) |
| `known_weaning_age_months` | | known-age reference animals only, used for validation |
| `published_weaning_age_months` | | weaning age from a published study, for comparison |

## How it works

```
CSV / form ──► ingest (Pydantic validation, column aliasing)
           ──► QC flags (C:N, %C, %N, yield)
           ──► age model (position → age via species/tooth growth table)
           ──► [optional] time-averaging windows per sample (after MDSS)
           ──► curve fits (SciPy: logistic, piecewise, exponential; WEAN-style elbow)
           ──► milestones + Monte Carlo 95 % intervals, AICc model weights
           ──► aggregation (pandas groupby by site/species/period)
           ──► validation vs. known ages and published estimates (bias, MAE, RMSE, coverage)
```

See [`docs/METHODS.md`](docs/METHODS.md) for the model equations and how the
milestones are defined. [`docs/RELATED_TOOLS.md`](docs/RELATED_TOOLS.md) compares
WeanAge with WARN, MDSS and WEAN and lists what was adopted from each.

## Project layout

```
src/weanage/
  schema.py        Pydantic data models
  ingest.py        CSV / form ingestion and dataset checks
  qc.py            collagen quality-control flags
  growth.py        position → age conversion
  models.py        logistic, piecewise-linear, exponential, WEAN-style elbow + fitting
  analysis.py      per-specimen pipeline
  aggregate.py     site/species summaries, between-model disagreement
  validation.py    accuracy metrics against known-age animals
  api.py           FastAPI service used by the frontend
  cli.py           `weanage` command
  data/            growth tables, QC + lab parameters (TBD-LAB), template, synthetic example
  web/             frontend (HTML/CSS/vanilla JS, dependency-free SVG charts)
tests/             pytest suite (incl. a simulation-based accuracy study)
packaging/         PyInstaller spec for a single-file app
scripts/           helper scripts (synthetic data generator)
```

The frontend is plain HTML and JavaScript with no build step or external libraries,
so it runs offline and bundles straight into the single-file executable.

## Development

```bash
poetry install
poetry run pytest
python scripts/make_synthetic_example.py   # regenerate the bundled example
```

## Single-file app

```bash
poetry run pyinstaller packaging/weanage.spec
# → dist/weanage (or weanage.exe on Windows)
```

## Licence

MIT
