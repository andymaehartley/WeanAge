# Lab data still to be supplied (`TBD-LAB`)

Every value below is a **placeholder** for something that can only come from lab work,
known-age reference material or a methods decision. Each one is:

* marked `TBD-LAB` in the source/data file (search: `grep -rn TBD-LAB`),
* flagged with `"placeholder": true` in its JSON file, and
* **highlighted in yellow** in the app (top banner, Settings, and on every result
  that depends on it).

When you fill one in, set `"placeholder": false`. The highlight then disappears on its own.

## 1. Tooth growth tables: `src/weanage/data/growth_tables.json`

These convert position along the tooth (mm from the cusp apex) into age at dentine
formation. The cattle crown start and end **ages** come from Brown et al. (1960);
the crown **heights** and all pig and horse values are still illustrative.

| species | tooth | what is needed |
|---|---|---|
| cattle | M2 | crown height (45 mm is a guess), evenness of growth along the crown, root ages. Ages 1 → 12.5 months are cited (Brown et al. 1960) |
| cattle | M1 | start age before birth (−2 months is a guess), crown height, root ages. Completion at 2.5 months is cited |
| pig | M1 | as above |
| horse | M1 | as above (hypsodont; extension rate likely non-linear) |

Tables can be edited, calibrated from known-age reference points and saved directly
in the app (*Settings → Age models*); saved tables go to `~/.weanage/growth_tables.json`
and replace the bundled placeholder. For each table also supply `age_uncertainty_months` (1 SD), which is propagated into
the confidence intervals, and a `source` citation. You can add more species or teeth
(sheep, goat, deciduous teeth and so on) by appending entries.

Ideally, calibrate these against **known-age reference animals** sampled in the same
way (1 mm increments, from the apex).

## 2. Collagen QC thresholds: `src/weanage/data/qc_thresholds.json`

The defaults are common literature values: C:N 2.9–3.6 (DeNiro 1985); %C ≥ 13,
%N ≥ 4.8 and yield ≥ 1 % (van Klinken 1999). For modern reference animals use the
"modern" preset, C:N 3.00–3.28 (Guiry & Szpak 2020). Confirm them against the protocol
actually used: 0.5 M HCl demineralisation, gelatinisation at pH 3 and 70 °C, then
lyophilisation.

## 3. Lab and method parameters: `src/weanage/data/lab_parameters.json`

| key | what is needed |
|---|---|
| `analytical_sd_permil` | EA-IRMS δ¹⁵N precision (1 SD of replicate standards / check samples). Used to weight curve fits. |
| `min_weaning_drop_permil` | smallest nursing-to-adult δ¹⁵N drop accepted as a real weaning signal |
| `transition_threshold` | fraction of the drop that defines onset and completion for smooth curves (default 5 % / 95 %) |
| `reference_dataset` | CSV of known-age animals with `known_weaning_age_months`, for validation (see `docs/VALIDATION.md`) |
| `growth_layer_offset_mm` | extra growth (mm) each horizontal section captures because dentine growth layers are oblique. Used by the optional time-averaging model. MDSS values are for human teeth only, so measure from livestock thin sections |
| `inner_dentine_weight` | how much the innermost (latest) dentine in a slice counts compared with the earliest (1 = equal). Estimate from livestock thin-section geometry |
| `adult_baselines` | mean ± SD δ¹⁵N of adult females (bone collagen) for each site and species, entered in Settings. Gives nursing enrichment and can constrain the adult plateau |

## 4. Isotope data: `src/weanage/data/templates/isotope_template.csv`

Compile the sequential δ¹⁵N values and tooth-position metadata into this format.
Optional columns include `individual_id` (several teeth from one animal),
`position_reference` + `crown_height_mm` (positions measured from the cervix),
`increment_width_mm` (if sections differ from 1 mm) and `published_weaning_age_months`
(when re-analysing published series). The
bundled `examples/synthetic_example.csv` is **simulated**, not real.

## 5. Sampling conventions to confirm

* `position_mm` is measured to the **midpoint** of each increment, from the **cusp
  apex** by default. If the lab measures from the cervix, set
  `position_reference = cervix` and give `crown_height_mm`.
* Each 1 mm increment averages several weeks of growth, which smooths the true dietary
  transition. The optional time-averaging model (Settings → Time averaging; see
  `docs/METHODS.md` §3a) corrects for this once `growth_layer_offset_mm` and the
  extension rates are known.
