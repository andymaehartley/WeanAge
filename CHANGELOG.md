# Changelog

## Unreleased

### Added
* Enamel calculation for cattle: season of birth from sequential enamel δ¹⁸O (cosine fit, birth
  index x₀/X, after Balasse et al. 2012) and rumen development from enamel δ¹³C (a rising step
  beyond the seasonal wave, kept only if AICc supports it), with a synthetic example, a template,
  group summaries of calving spread, and tests.
* A PDF user guide (`docs/guide/WeanAge_user_guide.pdf`, also under Help in the app): how each
  part of the calculation works and where it comes from, with references.

### Changed
* One Next: settings button, in the Load isotope data box.
* Accessibility (WCAG 2.2 AA, checked with axe-core on every page in both themes): result lists
  and scrollable tables work with screen readers and the keyboard; 24 px help buttons and larger
  checkboxes; error messages stay until closed and are announced; the chart can be zoomed by typing
  an age range as well as by dragging; focused fields are not hidden under the sticky bars; pages
  reflow without sideways scrolling at 320 px.
* Every curve model reports no weaning age when δ¹⁵N falls by less than the minimum (1‰ by
  default) or the fall is centred before birth. The fitted curve is still drawn. The model
  average is given only when the models that report an age hold at least half the support.
* Ages later than the last sample (or earlier than the first) are reported as "after X
  months" (or "before X months") with no interval, and are left out of group comparisons.
* The midpoint (half the δ¹⁵N fall) is the default reported milestone. Completion (95% of
  the fall) depends on how slowly δ¹⁵N levels off and is often much later than the end of
  suckling.

### Fixed
* Planner sweep values are checked like the form, so 0 or negative values give a message
  instead of a crash.
* The bone planner works with an edited turnover table.
* Growth tables saved with capital letters in the species name can be deleted.

### Removed
* The `/api/ingest/csv` alias and the blocking `/api/analyze` route. Use `/api/jobs/analyze`.

## 0.2.0 (not yet released)

### Added
* Bone calculation after WARN (Tsutaya & Yoneda 2013): weaning ages from the bone collagen
  δ¹⁵N of many young animals that died at different ages, with age-dependent turnover, ages
  at death as ranges, species priors for nursing enrichment and newborn offset, and a
  nursing-signal check (Reynard & Tuross 2015). Livestock turnover values are placeholders
  (TBD-LAB). Sources are listed in `docs/BONE_LITERATURE.md`.
* Bone sampling planner: simulates sites with a known end of suckling under a planned
  design and scores error, interval width, coverage and how often the nursing signal is found.
* Hand entry of animals in bone mode.
* One-stage Bayesian model (`joint.py`): logistic curves for every specimen and the group
  comparison estimated together from the raw δ¹⁵N values (*Compare → Bayesian model*).
* Nursing-enrichment check: drops larger than one food-chain step (default 5‰), or nursing
  δ¹⁵N far above the adult-female baseline, are flagged.
* δ¹³C across weaning check, and QC presets from the literature (Guiry & Szpak 2020).
* Planner curve shapes: simulated teeth can follow piecewise, exponential, two-phase or a
  random mix of curves.
* Ages in months or years (header switch).
* Human option: a human first-molar growth table (Beaumont et al. 2013; London Atlas;
  TBD-LAB), WARN's priors and turnover for human bone, and human weaning ranges in the planner.
* Browser version (Pyodide), published to GitHub Pages; works offline after the first visit.
* Real-data examples: Khami and Bornais cattle dentine from IsoArcH (CC BY 4.0); human bone
  from Wharram Percy, York Fishergate House and Newark Bay and human dentine from Mikulčice,
  from CIMA (CC BY-SA). `weanage isoarch` converts IsoArcH exports.
* `weanage validate` command and `docs/VALIDATION.md`.
* User guide (`docs/USER_GUIDE.md`) and a printable methods brief (`docs/brief/`).
* About panel with citation and licences, and a tooth diagram explaining the terms used.

### Changed
* Cattle M1/M2 growth tables use the crown start and end ages of Brown et al. (1960).
* Time averaging integrates each slice over its height and the dentine depth, with oblique
  growth layers and volume weights (after Tsutaya 2020 and MDSS).
* The elbow (WEAN-style) model reports no age when there is no real δ¹⁵N fall, the elbow is
  before birth, or its interval spans most of the series.
* The model average is flagged when most of its support comes from models that put the
  weaning age outside the samples.
* Interface: dark theme by default with light mode and larger text (WCAG AAA text contrast);
  less-used settings under *Advanced settings*; 95% intervals drawn as bars above the age
  axis; bundled Atkinson Hyperlegible and IBM Plex Mono fonts.

## 0.1.0

First version: five curve models, AICc model averaging, uncertainty with age-model error,
group comparison, sampling planner, local web app and command line.
