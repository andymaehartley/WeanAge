# Methods

## 1. Position to age

Each slice's `position_mm` (distance from the cusp apex) becomes an age at formation
(months after birth). The conversion uses the growth table for that species and tooth:
straight lines between the table's points, continued past the ends with those
samples flagged. A simple linear model can be used instead:
`age = initiation_age + position / extension_rate`.

* The cattle tables use the crown start and end ages of Brown et al. (1960): M1 is
  complete at about 2–3 months; M2 starts at about 1 month and is complete at 12–13
  months. Crown heights, and whether growth is even along the crown, are still
  `TBD-LAB`.
* Positions measured from the cervix are converted with `crown_height_mm`.
* When several teeth share an `individual_id`, each is converted with its own table,
  and the teeth are then fitted as one timeline.
* **Calibration** builds a growth table from known-age reference points
  `(position, age)` using a linear, quadratic or isotonic (any increasing shape) fit.
  The residual SD becomes the table's age uncertainty.

## 2. Collagen quality control

A sample is flagged if its atomic C:N, %C, %N or yield is outside the limits in
`qc_thresholds.json`. By default flagged samples are plotted but not fitted. If %C and
%N are given and C:N is not, C:N is computed as `(%C / %N) × (14.007 / 12.011)`.

Two published sets of limits can be chosen in Settings:

| preset | C:N | use for |
|---|---|---|
| Archaeological (DeNiro 1985; van Klinken 1999) | 2.9–3.6 | archaeological teeth |
| Modern, mammals (Guiry & Szpak 2020) | 3.00–3.28 | modern known-age reference animals |

Guiry & Szpak showed that the wider archaeological range lets through modern collagen
whose isotope values are already skewed.

## 3. Curve models

While an animal suckles, its δ¹⁵N is raised by roughly one trophic step. It then falls
to the adult level. Every parametric model has `post` (adult plateau) and `drop`
(nursing enrichment, ≥ 0) and differs only in the shape of the fall.

| model | curve | onset | midpoint | completion |
|---|---|---|---|---|
| Logistic | `post + drop / (1 + exp((t − t_mid)/s))` | `t_mid − s·ln((1−q)/q)` | `t_mid` | `t_mid + s·ln((1−q)/q)` |
| Piecewise linear | flat → straight decline over `duration` → flat | `t_start` | `t_start + duration/2` | `t_start + duration` |
| Exponential | flat, then `post + drop·exp(−(t − t_start)/τ)` | `t_start` | `t_start + τ·ln 2` | `t_start + τ·ln(1/q)` |
| Two-phase | two logistic steps: a fraction `f` of the drop at `t1`, the rest at `t1 + gap` | first step's onset | half the total drop (found numerically) | second step's completion |
| Elbow (WEAN-style) | 4th-degree polynomial | age of the fitted peak | — | point farthest below the peak-to-end line |

* `q` is the *transition threshold* (default 0.05): onset is at 5 % of the drop and
  completion at 95 %.
* **Two-phase** describes staged weaning: supplementary feeding while suckling
  continues, then final weaning, as expected where people took part of the milk. It
  reports the intermediate δ¹⁵N level and how long that stage lasted. AICc decides
  whether the extra step is supported.
* **Elbow** re-implements Ganiatsou et al. (2023). By default both axes are rescaled to
  0–1 before measuring distance, so the result does not depend on units (WEAN uses raw
  units). It warns when the curve is rising at the elbow or the polynomial overshoots
  the data by more than 0.5‰. Because an elbow is found in *any* series, even a flat,
  noisy one (rescaling makes a 0.4‰ wobble look like a 3‰ drop), WeanAge reports **no
  weaning age** for this model when δ¹⁵N never falls after its peak, the fall is below
  the minimum weaning drop, the elbow lies before birth, or its 95% interval spans more
  than 80% of the sampled ages. The fitted curve is still drawn, and the model average
  then uses the other models only.

Fitting uses `scipy.optimize.curve_fit` (bounded trust-region) from 10–20 starting
points spread over the sampled ages, keeping the best result. A known analytical SD is
used as the measurement error of each point.

### Options

* **Time averaging** (after Tsutaya 2020 and MDSS). A slice is a disc of dentine with a
  height `w` (the slice width) and a depth (from the enamel inwards to the pulp). Growth
  layers run at an angle, so dentine at relative depth `d` (0 at the enamel, 1 at the
  pulp) was laid down when the growth front was `growth_layer_offset_mm × d` further
  along the tooth. The slice is covered by an 8 × 8 grid over height and depth, each
  point converted to an age. Inner dentine lies on a smaller circle, so there is less of
  it: weights fall from 1 at the enamel to `inner_dentine_weight` at the pulp (the ratio
  of inner to outer radius). The sample is fitted as the weighted average of the curve
  over the grid, so the fitted curve describes the underlying diet change, not the
  blurred one. In practice `growth_layer_offset_mm` = dentine thickness ÷ tan(angle of
  the growth layers to the tooth axis), both measurable on a thin section.
* **Seasonal term.** `a·sin(2πt/P) + b·cos(2πt/P)` is added to every parametric curve
  (default `P` = 12 months), so a yearly pasture or fodder cycle is not mistaken for
  weaning. Its amplitude is reported.
* **Adult-female baseline** (after WARN). Results report nursing enrichment (nursing
  level minus the female mean). Optionally the adult plateau is held within ±2 SD of
  the female mean.

## 4. Uncertainty

* **Covariance** (default): 1000 random parameter sets are drawn from the fit's
  covariance, and the weaning ages are recomputed for each.
* **Bootstrap**: the curve is refitted 200 times to the fitted values plus reshuffled
  residuals.
* The growth table's `age_uncertainty_months` is added as **one shared random shift
  per draw**, because an error in the age model moves every sample of a tooth
  together.

The 95 % interval is the middle 95 % of the draws.

## 5. Model comparison and averaging

Each model's AICc gives ΔAICc and **Akaike weights** (shares of support summing to 1).
The best model has the lowest AICc. The **model average** weights each model's
estimate by its Akaike weight. Its interval comes from mixing the models' draws in the
same proportions. The Compare tab also lists, for each specimen, the range of
estimates across models (thesis question 1).

## 6. Warnings and diagnostics

* No clear weaning signal: the drop is below `min_weaning_drop_permil`.
* **Implausibly large drop**: above `max_plausible_drop_permil` (default 5‰). Suckling
  raises δ¹⁵N by about one food-chain step, 3–4‰ (DeNiro & Epstein 1981; Minagawa &
  Wada 1984), and measured nursing enrichment is usually 2–3‰ (Balasse et al. 2001;
  Fuller et al. 2006). A larger drop suggests another diet change, mixed-up samples or a
  badly fitting curve. The same limit applies to nursing δ¹⁵N above the adult-female
  baseline.
* Onset before the first sample, or completion after the last (extrapolated).
* **Rising profile**: δ¹⁵N increases with age (Spearman ρ > 0.3, p < 0.05). Stress and
  starvation can raise δ¹⁵N (Beaumont & Montgomery 2016).
* **δ¹³C across weaning**: the mean δ¹³C after weaning ends minus the mean before it
  starts (at least 2 samples each side, using the best model's onset and completion).
  In known-age calves δ¹³C rose as δ¹⁵N fell (Balasse et al. 2001), so for cattle a
  fall of 0.5‰ or more is flagged: the δ¹⁵N decline may be another diet change. For
  other species the value is only reported, because the expected direction is not
  yet established.
* **Seasonality**: an F-test for a yearly sine wave in the best fit's residuals, and
  in δ¹³C after removing a linear trend and the shape of the fitted weaning curve (so a
  one-off δ¹³C step at weaning is not mistaken for a season). A warning appears when p < 0.05 and the cycle
  is at least 0.2‰ (residuals) or 0.3‰ (δ¹³C). The test needs at least ¾ of a year of
  data, and its false-alarm rate on pure noise was checked to be about 5 %.

## 7. Comparing groups

Estimates are grouped by site, species and/or period. They can be each specimen's
best model, the model average, or one chosen model.

* **Summary**: n, mean, SD, median, range and a t-based 95 % CI.
* **Random-effects means** (DerSimonian & Laird 1986): each group's mean weaning age,
  allowing real between-animal variation τ on top of each estimate's SE (taken from
  its 95 % interval).
* **Q-test** for any difference between groups, and pairwise z-tests with Holm
  correction.
* **Permutation test**: 5000 shuffles of the group labels.
* **Hierarchical Bayesian model**:
  `estimate_i ~ N(θ_i, SE_i)`, `θ_i ~ N(μ_group, τ)`, `μ_group ~ N(mean, 50)`,
  `τ ~ half-Cauchy(3)`. It is fitted by Gibbs sampling (4 chains × 2000 kept draws,
  with τ updated by Metropolis). It gives group posteriors, the probability that one
  group weaned earlier than another, partially pooled specimen estimates, and split-R̂
  as a convergence check.

This is a **two-stage** model: it pools the specimen estimates rather than the raw δ¹⁵N
values.

### One-stage model (`joint.py`)

The curves and the group comparison can instead be estimated together from the raw
values of every specimen (*Compare → Bayesian model → One-stage*):

```
δ15N_ij ~ N(post_i + drop_i / (1 + exp((age_ij − c_i)/s_i)), σ_i)
m_i = c_i + k·s_i + shift_i          (the milestone in true age; k = ±ln((1−q)/q) or 0)
m_i ~ N(μ_group, τ)      shift_i ~ N(0, age-model SD of the tooth)
μ_group ~ N(mean, 50)    τ ~ half-Cauchy(3)    s_i ~ log-N(0, 1)    drop_i ~ U(0, 20)    σ_i ∝ 1/σ
```

Writing the curve in the tooth's recorded ages (`c`, `s`), and the milestone as
`c + k·s + shift`, keeps the parameters that the data pin down separate from the ones
the hierarchy pins down, which lets the sampler mix well. Curve parameters are updated by
Metropolis steps tuned during warm-up; σ, the age shift and μ are drawn exactly; τ by a
Metropolis step on log τ. 4 chains × 3000 kept draws after 2000 warm-up; split-R̂ is
reported for τ, every μ and every specimen.

Compared with the two-stage model, the uncertainty in each curve's shape and in each
tooth's age model reaches the group comparison directly. It uses the logistic curve
only, and leaves out teeth whose own logistic milestone lies outside their sampled ages,
so that extrapolations do not drive the group means. They are listed in the results.

## 8. Validation

See [`VALIDATION.md`](VALIDATION.md) for how to run it (`weanage validate`) and which
published series to use.

When `known_weaning_age_months` is present (known-age animals), the following are
reported for each model: bias, MAE, RMSE, Pearson r and 95 % interval coverage. When
`published_weaning_age_months` is present, the same metrics measure agreement with
published estimates (WEAN's re-estimation test).

## 9. Sampling planner (simulation)

The planner invents teeth with known logistic weaning curves, with midpoint, steepness
and drop drawn from user ranges. It then "cuts" them as the lab would:

* slice spacing and height,
* growth-layer offset,
* measurement noise,
* missing samples,
* an optional per-animal age-model error,
* the shape of the true curves: logistic, piecewise, exponential, two-phase or a random
  mix. All shapes take about the same time from 5 % to 95 % of the drop, so they are
  comparable, and testing with non-logistic truths shows how each model copes when its
  shape is wrong.

It runs the full analysis and scores each model's completion age against the truth
(MAE, bias, RMSE, coverage, share fitted). Sweeping one setting with the same random
seed shows how accuracy depends on the protocol.

## Limitations / future work

* The slice geometry assumes straight growth layers and a circular cross-section. Real
  layers curve, and the livestock values must still be measured (`TBD-LAB`).
* The one-stage model uses the logistic curve only and no time averaging or seasonal
  term; it is a check on, not a replacement for, the per-specimen model comparison.
