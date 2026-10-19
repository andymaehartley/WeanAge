# Methods

## 1. From tooth position to age

Each sample's `position_mm` (distance from the cusp apex) is converted to an age at
formation (months after birth). This uses a piecewise-linear growth table for the
species and tooth, or a user-supplied linear model:

    age = initiation_age + position_mm / extension_rate

Positions outside the table are extrapolated linearly from the end segments and flagged.

## 2. Collagen QC

A sample is flagged if its atomic C:N, %C, %N or collagen yield falls outside the
configured thresholds (see `qc_thresholds.json`). By default, flagged samples are
plotted but **not fitted**. If %C and %N are given and C:N is not, atomic C:N is
computed as `(%C / %N) × (14.007 / 12.011)`.

## 3. Curve models

δ¹⁵N during nursing is raised above the mother's tissue by roughly one trophic step.
As the young animal moves onto solid food, it falls to an adult-diet plateau. All
three models share the same two level parameters:

* `post`: the adult (post-weaning) plateau
* `drop`: the nursing enrichment above it (constrained ≥ 0), so the nursing plateau = `post + drop`

They differ only in the **shape** of the transition:

| model | equation | onset | midpoint | completion |
|---|---|---|---|---|
| Logistic | `post + drop / (1 + exp((t − t_mid)/s))` | `t_mid − s·ln((1−q)/q)` | `t_mid` | `t_mid + s·ln((1−q)/q)` |
| Piecewise linear | flat → straight-line decline over `duration` → flat | `t_start` | `t_start + duration/2` | `t_start + duration` |
| Exponential | flat, then `post + drop·exp(−(t − t_start)/τ)` | `t_start` | `t_start + τ·ln 2` | `t_start + τ·ln(1/q)` |

Here `q` is the *transition threshold* (default 0.05). For the smooth models, weaning
counts as *begun* once 5 % of the drop has happened and *complete* once 95 % has.

**Elbow (WEAN-style).** This is a re-implementation of Ganiatsou et al. (2023). A
4th-degree polynomial is fitted. Weaning *completion* is the point on that curve
farthest below the straight line from its δ¹⁵N peak to the last sample, and the
reported *onset* is the age of the peak. There is no midpoint. By default both axes
are rescaled to [0, 1] first so the answer does not depend on units; WEAN measures
the distance in raw units. A curve that is rising at the elbow, or a polynomial that
overshoots the data by more than 0.5‰, is flagged.

**Rising profiles.** If δ¹⁵N rises with age (Spearman ρ > 0.3, p < 0.05), the
specimen is flagged. That pattern points to something other than weaning, such as
physiological stress or a diet change (cf. WEAN).

Fitting uses `scipy.optimize.curve_fit` (trust-region reflective, bounded) from about
ten starting points spread across the sampled age range, keeping the lowest-SSE
solution. If an analytical SD is set, it is used as an absolute per-point σ.

## 3a. Time averaging (optional)

This follows Tsutaya (2020) and the MDSS package. A horizontal section of height `w`
centred on position `p` holds dentine laid down while the growth front moved through
`p ± w/2`. Because growth layers run at an angle, it also holds later-formed inner
dentine, modelled as a further `growth_layer_offset_mm` of growth. With
`time_averaging` on, each sample's window is split into 15 evenly spaced positions,
each converted to an age, and the sample is fitted as the **mean** of the curve over
those ages. The fitted curve and its milestones then describe the underlying diet
change, which is sharper and earlier than the blurred sampled profile. This is a
simplified, livestock-agnostic version of MDSS, which weights growth layers by volume
using measured human tooth geometry.

## 3b. Adult-female baseline (optional)

This follows WARN's maternal baseline. For each site and species you can enter the
mean and SD of adult-female δ¹⁵N. Results then include the **nursing enrichment**:
the nursing plateau minus the female mean. With `constrain_adult_plateau`, the
adult plateau is bounded to mean ± 2 SD, which helps when a series ends before the
adult value is reached.

## 4. Uncertainty

Milestone 95 % intervals come from Monte Carlo draws (default 1000) from the fitted
parameter covariance. The growth table's `age_uncertainty_months` is then added in
quadrature (±1.96 SD).

## 5. Model comparison

Each specimen is fitted with every selected model. The models are compared by AICc
(least-squares form, with residual variance counted as a parameter), giving ΔAICc
and Akaike weights. The *best* model per specimen is the one with the lowest AICc.
The **Compare** view reports the per-specimen range of estimates across models.
That range answers the thesis question: how much do weaning-age estimates depend on
the method?

## 6. Aggregation

Estimates are grouped by site, species and/or period with pandas. Each group gets n,
mean, SD, median, range and a t-based 95 % CI of the mean. Groups can use the best
model for each specimen, or one chosen model throughout.

## 7. Validation

If `known_weaning_age_months` is present (for known-age reference animals), the
following are reported for each model: bias, MAE, RMSE, Pearson r and the coverage
of the 95 % intervals. If `published_weaning_age_months` is present, the same
metrics measure agreement with published estimates, such as WEAN outputs or visual
readings of the same profiles. This reproduces WEAN's re-estimation test. The pytest suite includes a simulation study on synthetic
animals with known weaning ages.

## Limitations / future work

* **Time-averaging geometry**: the optional model (3a) uses a single offset and
  uniform weighting. Livestock values for growth-layer obliqueness and changing
  extension rates still have to be measured (`TBD-LAB`). A full MDSS-style volume
  model per tooth type would be more realistic.
* **Bayesian alternative**: a hierarchical model (for example, pooling specimens within
  a site) could be added alongside the current least-squares models.
