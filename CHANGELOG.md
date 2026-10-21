# Changelog

## 0.2.0 (unreleased)

### Methods
* **One-stage Bayesian model** (`joint.py`): logistic weaning curves for every specimen and
  the group comparison are estimated together from the raw δ¹⁵N values, with each tooth's
  age-model error as a random shift. Choose it under *Compare → Bayesian model*.
* **Nursing-enrichment check**: fitted drops larger than one food-chain step (default 5‰)
  are flagged, as is nursing δ¹⁵N far above the adult-female baseline.
* **Slice geometry**: time averaging now integrates each slice over its height *and* the
  dentine depth, with oblique growth layers and volume weights (after Tsutaya 2020 / MDSS).
* **Planner curve shapes**: simulated teeth can follow piecewise, exponential, two-phase or a
  random mix of curves, so the logistic model is no longer favoured by construction.
* **δ¹³C across weaning** and literature-based **QC presets** (Guiry & Szpak 2020).
* Cattle M1/M2 growth tables use the crown start and end ages of Brown et al. (1960).

### App
* High-contrast **dark theme by default**, light mode and larger text (WCAG AAA text contrast).
* **Interface redesign**: own colour palette, bundled Atkinson Hyperlegible and IBM Plex Mono fonts,
  an underlined tab strip, plain-text actions, flatter sections, labelled message lists, and a status line.
* **Identity**: a logo (five dentine slices falling like a weaning curve), `docs/IDENTITY.md`, an
  About panel (citation, licences, acknowledgements) and a tooth guide explaining the terms the app uses.
* **Browser version** (Pyodide): runs entirely in the web page, shares large analyses between
  several engines, and works offline after the first visit. Published to GitHub Pages.
* `weanage validate` command and `docs/VALIDATION.md`.
* `weanage isoarch` converts sequential dentine series from IsoArcH exports, and a real-data
  example (Khami and Bornais cattle, CC BY 4.0) can be loaded in the app.

### Project
* Known-answer tests pin the results on the synthetic example.
* `docs/USER_GUIDE.md` (step-by-step guide with screenshots) and a printable methods
  brief in `docs/brief/`.

## 0.1.0

First version: five curve models, AICc model averaging, uncertainty with age-model error,
group comparison, sampling planner, local web app and command line.
