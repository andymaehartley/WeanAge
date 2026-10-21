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
* The **elbow (WEAN-style) model reports no age** when there is no real δ¹⁵N fall, the elbow
  lies before birth, or its interval spans most of the series, instead of an arbitrary point
  on noise. The model average then uses the other models.

* **Bone calculation** (`bone.py`): weaning ages from the bone collagen δ¹⁵N of many young
  animals that died at different ages, after WARN (Tsutaya & Yoneda 2013): WARN's diet forms
  and priors, age-dependent collagen turnover (WARN's human rib values included; livestock
  values are TBD-LAB placeholders), ages at death as ranges, and a Bayesian sampler.
* **Bone method updated from the animal literature** (`docs/BONE_LITERATURE.md`): species
  priors for nursing enrichment and newborn offset (`data/bone_priors.json`); the newborn offset
  is estimated, as foetal tissue is enriched over the mother in other mammals; livestock turnover
  placeholders anchored to young-mammal turnover (Newsome et al. 2006); WARN's yearly turnover
  converted as the share replaced per year; a nursing-signal check (Reynard & Tuross 2015); the
  end of weaning reported as the end of suckling (Balasse et al. 2001).
* The **model average is flagged** "beyond the sampled teeth" when most of its support comes
  from models that put the weaning age outside the samples.

### App
* **Bone sampling planner** (*Plan sampling* in bone mode, `bone_planner.py`): simulates sites with a
  known end of suckling under the planned design (young animals, their ages and age precision, adult
  females, scatter), runs the bone calculation and scores error, interval width, coverage and how often
  the nursing signal is found; one setting can be compared across values.
* **Hand entry in bone mode**: add animals one at a time (young, adult female, adult male), with ages in
  the chosen unit; checked like a file.
* **Ages in months or years**: a header switch shows every result, chart, table and report in years;
  boxes that hold ages convert with it.
* **Human option**: humans in the species lists, a human first-molar growth table (birth to about
  9.5 years; Beaumont et al. 2013 and the London Atlas; to be checked, TBD-LAB), WARN's priors for
  human bone, and human weaning ranges in the planner.
* **Tidier pages**: less-used settings are folded under *Advanced settings* in each box (for example
  the adult-female baseline, the transition threshold and the uncertainty options), the loaded-data
  summary and *Next* button sit under the file box, tables and charts size themselves to the window,
  and the Run button stays in view. At 1440×860 every page fits without scrolling.
* The Data page offers **Tooth calculation** or **Bone calculation**; the bone calculation has
  its own settings and results pages, a synthetic example and a blank template.
* High-contrast **dark theme by default**, light mode and larger text (WCAG AAA text contrast).
* **Interface redesign**: own colour palette, bundled Atkinson Hyperlegible and IBM Plex Mono fonts,
  an underlined tab strip, plain-text actions, flatter sections, labelled message lists, and a status line.
* **Identity**: a logo (five dentine slices falling like a weaning curve), `docs/IDENTITY.md`, an
  About panel (citation, licences, acknowledgements) and a tooth guide explaining the terms the app uses.
* **Browser version** (Pyodide): runs entirely in the web page, shares large analyses between
  several engines, and works offline after the first visit. Published to GitHub Pages.
* The **Help** button opens a menu: the guided tour, or the PDF user guide (shown as
  "coming soon" until `src/weanage/web/guide/WeanAge_user_guide.pdf` is added).
* `weanage validate` command and `docs/VALIDATION.md`.
* `weanage isoarch` converts sequential dentine series from IsoArcH exports, and a real-data
  example (Khami and Bornais cattle, CC BY 4.0) can be loaded in the app.

* **Real human examples from CIMA**: bone collagen from Wharram Percy, York Fishergate House and Newark Bay
  (bone calculation) and dentine sections of Mikulčice first molars (tooth calculation), made by
  `scripts/make_cima_examples.py` (CC BY-SA). Wharram Percy reproduces the published weaning age.
* **Interface review** against the web-design-engineer skill (garden-skills), in "preserve" mode: warmer
  neutral greys instead of a code-editor near-black (still WCAG AAA), a large headline figure for each
  result, 95% intervals drawn as bars above the age axis instead of overlapping shaded bands, no
  left-border accent blocks, a 4 px spacing scale, `text-wrap: pretty`, tabular numerals, larger small
  buttons, and the version number moved out of the header into About.

### Project
* Known-answer tests pin the results on the synthetic example.
* `docs/USER_GUIDE.md` (step-by-step guide with screenshots) and a printable methods
  brief in `docs/brief/`.

## 0.1.0

First version: five curve models, AICc model averaging, uncertainty with age-model error,
group comparison, sampling planner, local web app and command line.
