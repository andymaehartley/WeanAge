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

Fitting uses `scipy.optimize.curve_fit` (trust-region reflective, bounded) from about
ten starting points spread across the sampled age range, keeping the lowest-SSE
solution. If an analytical SD is set, it is used as an absolute per-point σ.

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
of the 95 % intervals. The pytest suite includes a simulation study on synthetic
animals with known weaning ages.

## Limitations / future work

* **Increment averaging**: each 1 mm sample integrates weeks of growth, which flattens
  and delays the apparent transition. A forward model that convolves the curve with the
  sampling window could be added once extension rates are known (`TBD-LAB`).
* **Dentine apposition geometry**: horizontal sections cut across obliquely oriented
  growth layers. Correcting for this needs tooth-specific geometry data.
* **Maternal baseline**: the nursing offset relative to the mother is not modelled
  explicitly. Adult or maternal reference values could constrain `post`.
* **Bayesian alternative**: a hierarchical model (for example, pooling specimens within
  a site) could be added alongside the current least-squares models.
