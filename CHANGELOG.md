# Changelog

## Unreleased

### Added
* Data tab: drop a table first; WeanAge lists every calculation with the rows it can use or what is
  missing, and any number can be ticked and run from the same file. Buttons at the top switch
  between the ticked calculations. Examples of every calculation are in one list.
* Breast-milk share at each dentine increment (tooth calculation), from the adult-female baseline
  (δ¹⁵N, optionally δ¹³C) and the nursing enrichment, with an optional third weaning food.
* Dental age (new calculation): age at death from Moorrees stages, combined over a child's teeth,
  with discordant teeth flagged; the ages can be passed to the bone calculation and life tables.
  Formation ages are placeholders (`data/dental_stages.json`).
* Enamel hypoplasia timing (new calculation): defect ages from their height on the crown, set
  against the same individual's weaning interval and stress episodes.
* Life tables (new calculation): Dx, dx, lx, qx, Lx, Tx, ex, infant and under-5 shares and the
  juvenility index with bootstrap intervals, an interval-censored Siler fit, and a permutation test.
* Mobility from bulk enamel (new calculation): δ¹⁸O to drinking water (Chenery et al. 2012; Daux et
  al. 2008) and ⁸⁷Sr/⁸⁶Sr against a local range from baseline samples, Settings or Tukey fences.
* Compare can group by any other column of the tooth table (for example sex or burial type).
* Kill-off profiles (new calculation): aged mandibles as Payne (1973) stages or age ranges, shared
  between stages as Payne did; deaths and survivorship by age class with bootstrap intervals; shares
  killed before 6 months, at 6–36 months and alive at 4 years; permutation test between groups; a
  synthetic sheep/goat example.
* Diet mixing (new calculation): shares of 2–6 food groups from collagen δ¹³C, δ¹⁵N and δ³⁴S by
  importance sampling of a flat Dirichlet prior (FRUITS-style), with outside-the-mixing-space and
  underdetermined warnings, a δ¹³C–δ¹⁵N biplot, editable food groups and offsets (placeholders in
  `data/diet_sources.json`), and a synthetic example.
* Enamel: ⁸⁷Sr/⁸⁶Sr shifts along the crown (BIC change points, local range); the month of the rumen
  transition and of strontium shifts from the δ¹⁸O cycle; birth and weaning months from a reference
  tooth and each animal's weaning age (taken from the tooth calculation when IDs match); an optional
  correction of the δ¹⁸O amplitude and rumen step width for mineralisation smoothing.
* Dentine: stress episodes (δ¹⁵N above the weaning curve while δ¹³C is below its expected level) and
  δ³⁴S shifts from an optional `d34S` column.
* C3 or C4 diet from enamel δ¹³C: the share of C4 plants by mixing a C3 and a C4 end member
  (enamel-diet spacing 14.1‰, Cerling & Harris 1999), using enamel formed after the rumen
  transition, with a 95% interval, pre-industrial or modern plant values, and group means.
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
