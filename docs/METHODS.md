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
* Calibration builds a growth table from known-age reference points
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
* The midpoint is the default reported milestone. The curve is steepest there, so it is
  dated most precisely. Completion depends on how slowly δ¹⁵N levels off and is often much
  later than the end of suckling. Onset and completion are reported alongside.
* Two-phase describes staged weaning: supplementary feeding while suckling
  continues, then final weaning, as expected where people took part of the milk. It
  reports the intermediate δ¹⁵N level and how long that stage lasted. AICc decides
  whether the extra step is supported.
* Elbow re-implements Ganiatsou et al. (2023). By default both axes are rescaled to
  0–1 before measuring distance, so the result does not depend on units (WEAN uses raw
  units). It warns when the curve is rising at the elbow or the polynomial overshoots
  the data by more than 0.5‰.

A curve can be fitted to any series, including a flat, noisy one. Each model therefore
reports no weaning age when its fitted fall is below `min_weaning_drop_permil` (default
1‰) or the fall is centred before birth (for the elbow: the elbow lies before birth). The
elbow model also reports none when δ¹⁵N never falls after its peak or its 95% interval
spans more than 80% of the sampled ages, because rescaling can make a 0.4‰ wobble look
like a 3‰ drop. The fitted curve is still drawn.

Fitting uses `scipy.optimize.curve_fit` (bounded trust-region) from 10–20 starting
points spread over the sampled ages, keeping the best result. A known analytical SD is
used as the measurement error of each point.

### Options

* Time averaging (after Tsutaya 2020 and MDSS). A slice is a disc of dentine with a
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
* Seasonal term. `a·sin(2πt/P) + b·cos(2πt/P)` is added to every parametric curve
  (default `P` = 12 months), so a yearly pasture or fodder cycle is not mistaken for
  weaning. Its amplitude is reported.
* Adult-female baseline (after WARN). Results report nursing enrichment (nursing
  level minus the female mean). Optionally the adult plateau is held within ±2 SD of
  the female mean.

## 4. Uncertainty

* Covariance (default): 1000 random parameter sets are drawn from the fit's
  covariance, and the weaning ages are recomputed for each.
* Bootstrap: the curve is refitted 200 times to the fitted values plus reshuffled
  residuals.
* The growth table's `age_uncertainty_months` is added as one shared random shift
  per draw, because an error in the age model moves every sample of a tooth
  together.

The 95 % interval is the middle 95 % of the draws.

## 5. Model comparison and averaging

Each model's AICc gives ΔAICc and Akaike weights (shares of support summing to 1).
The best model has the lowest AICc. The model average weights the estimates of the models
that report an age by their Akaike weights, rescaled to sum to 1. Its interval comes from
mixing those models' draws in the same proportions. No average is given when the models
that report an age hold less than half the total support. The Compare tab also lists,
for each specimen, the range of estimates across models.

### Ages beyond the samples

A curve can be extended past the samples, but its shape there is not measured. An age
later than the last sampled age (or earlier than the first) is therefore reported only
as a bound, "after X months" (or "before X months"), with no interval, and the estimates
table gives it in `<milestone>_beyond`. For the model average the bound is used when
models holding at least half of its support put the age beyond the samples. Bounded ages
are left out of group comparisons.

## 6. Warnings and diagnostics

* No clear weaning signal: the drop is below `min_weaning_drop_permil`.
* Implausibly large drop: above `max_plausible_drop_permil` (default 5‰). Suckling
  raises δ¹⁵N by about one food-chain step, 3–4‰ (DeNiro & Epstein 1981; Minagawa &
  Wada 1984), and measured nursing enrichment is usually 2–3‰ (Balasse et al. 2001;
  Fuller et al. 2006). A larger drop suggests another diet change, mixed-up samples or a
  badly fitting curve. The same limit applies to nursing δ¹⁵N above the adult-female
  baseline.
* A milestone before the first sample or after the last (reported as a bound; see section 5).
* Rising profile: δ¹⁵N increases with age (Spearman ρ > 0.3, p < 0.05). Stress and
  starvation can raise δ¹⁵N (Beaumont & Montgomery 2016).
* δ¹³C across weaning: the mean δ¹³C after weaning ends minus the mean before it
  starts (at least 2 samples each side, using the best model's onset and completion).
  In known-age calves δ¹³C rose as δ¹⁵N fell (Balasse et al. 2001), so for cattle a
  fall of 0.5‰ or more is flagged: the δ¹⁵N decline may be another diet change. For
  other species the value is only reported, because the expected direction is not
  yet established.
* Seasonality: an F-test for a yearly sine wave in the best fit's residuals, and
  in δ¹³C after removing a linear trend and the shape of the fitted weaning curve (so a
  one-off δ¹³C step at weaning is not mistaken for a season). A warning appears when p < 0.05 and the cycle
  is at least 0.2‰ (residuals) or 0.3‰ (δ¹³C). The test needs at least ¾ of a year of
  data, and its false-alarm rate on pure noise was checked to be about 5 %.
* Stress episodes (`changes.py`): starvation and illness raise δ¹⁵N without raising δ¹³C, while
  a change of food usually moves both the same way (Beaumont & Montgomery 2016). δ¹⁵N excess is
  observed minus the best fit; δ¹³C excess is the residual of δ¹³C regressed on a constant, age and
  the fitted weaning curve (so the weaning step itself is not counted). An episode is a run of at
  least two samples with δ¹⁵N excess ≥ `stress_d15N_permil` (0.5‰) and δ¹³C excess ≤ −
  `stress_d13C_permil` (0.3‰). Needs at least 6 δ¹³C values. The Spearman correlation of the two
  excesses is reported (negative = opposing covariance).
* δ³⁴S shifts (`changes.find_shifts`), when a `d34S` column is given (at least 4 values): the series
  is split into one, two or three flat stretches at the cuts that minimise the residual sum of
  squares, and the number is chosen by BIC (n·ln(SSE/n) + k·ln n, k = 2 × shifts + 1). Shifts below
  `d34S_min_shift_permil` (2‰) are not reported. Two steps the same way with at most three samples
  between them are reported as one gradual shift. δ³⁴S follows bedrock and sea spray, so a shift
  suggests a move or a change of diet (Nehlich 2015).

## 7. Comparing groups

Estimates are grouped by site, species and/or period. They can be each specimen's
best model, the model average, or one chosen model.

* Summary: n, mean, SD, median, range and a t-based 95 % CI.
* Random-effects means (DerSimonian & Laird 1986): each group's mean weaning age,
  allowing real between-animal variation τ on top of each estimate's SE (taken from
  its 95 % interval).
* Q-test for any difference between groups, and pairwise z-tests with Holm
  correction.
* Permutation test: 5000 shuffles of the group labels.
* Hierarchical Bayesian model:
  `estimate_i ~ N(θ_i, SE_i)`, `θ_i ~ N(μ_group, τ)`, `μ_group ~ N(mean, 50)`,
  `τ ~ half-Cauchy(3)`. It is fitted by Gibbs sampling (4 chains × 2000 kept draws,
  with τ updated by Metropolis). It gives group posteriors, the probability that one
  group weaned earlier than another, partially pooled specimen estimates, and split-R̂
  as a convergence check.

This is a two-stage model: it pools the specimen estimates rather than the raw δ¹⁵N
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

The planner invents teeth with known weaning curves, with midpoint, steepness and drop
drawn from user ranges. It then "cuts" them as the lab would:

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
(MAE, bias, RMSE, coverage, share fitted). An estimate beyond the simulated tooth counts as
not dated. Sweeping one setting with the same random
seed shows how accuracy depends on the protocol.

## 10. Bone calculation (`bone.py`), after WARN

Teeth record one animal's childhood; bone does not, because its collagen is renewed
throughout life. The bone calculation instead uses many young animals from one site that
died at different ages, as WARN does for human skeletons (Tsutaya & Yoneda 2013). Each
site × species (× period) group is fitted on its own.

### Model

Equation numbers are from Tsutaya & Yoneda (2013).

* *Diet* (Eq. 7–8, after Millard 2000). Collagen made now has
  δ¹⁵N_new(t) = (1 − p(t))(F + E) + p(t)·W, where F is the mothers' mean (adult females),
  E the nursing enrichment and W the δ¹⁵N of collagen made only from weaning food. The
  non-milk share p(t) is 0 before weaning starts (t1), 1 after it ends (t2), and in between
  ((t − t1)/(t2 − t1))² ("parabolic", WARN's default: slow, then fast). Linear and reverse
  parabolic are offered too; WARN's sigmoid form is not, because its formula is not given in
  the paper or manual.
* *Bone* (Eq. 9–10). At birth bone collagen equals the mothers' value plus a newborn offset
  b (WARN assumes b = 0). Every quarter month a share r(t) of it is rebuilt from the current
  diet: bone(t + Δ) = (1 − r)·bone(t) + r·δ¹⁵N_new(t). The shares come from
  `data/bone_turnover.json`. WARN gives T, the share of the bone replaced in each year of age
  (Eq. 9; 1 or more means all of it); WeanAge converts it to a monthly share as
  1 − (1 − min(T, 0.97))^(1/12), which reproduces WARN's 96.6% replaced by 31 weeks.
* *Fit.* t1, t2, E, W, F, b and the scatter between animals σ are estimated together, and
  each animal's age at death is sampled within its range (from tooth wear, fusion etc.).
  Priors: t1 and t2 flat with 0 ≤ t1 ≤ t2 ≤ the latest possible end of weaning; E ~ N(mean,
  SD) and b ~ N(mean, SD) per species from `data/bone_priors.json` (humans: WARN's E ~ N(1.9,
  0.9) and b ≈ 0; livestock: E ~ N(2.5–3.0, 1.0) and b ~ N(1.0, 1.0), placeholders drawn from
  the animal studies in [BONE_LITERATURE.md](BONE_LITERATURE.md)); W ~ N(F, 3) and σ ~ |N(0, 1)|
  as in WARN; F ~ N(mean of the adult females, its standard error). Values typed in Settings
  override the species entry.
* *Reading t2.* δ¹⁵N falls when suckling stops, rather than as the amount of milk slowly
  drops (Balasse et al. 2001 in cattle; Díez-Canseco & Tornero 2026 in sheep), so t2 is
  reported as the end of suckling.

### How it differs from WARN

WARN uses approximate Bayesian computation with sequential
Monte Carlo (Sisson et al. 2007). WeanAge writes down the likelihood (normal scatter σ around
the modelled bone value, the same individual error term as WARN's Eq. 12) and samples it with
Metropolis steps plus differential-evolution moves between chains (ter Braak 2006), checking
convergence with R̂. WARN treats the mothers' mean as known; WeanAge carries its uncertainty.
WARN's t1/t2 priors are normal distributions in years, set for humans; for livestock, flat
priors up to a user-set limit avoid importing human weaning ages.

### Turnover

WARN's human rib values (Table 1, "Collagen (QP)") are included as the
`human` table, so results can be checked against WARN. The livestock placeholders are anchored
to the one non-human benchmark found: complete turnover of young fur seals' bone collagen in
about 8–10 months (Newsome et al. 2006); they replace about 95% of a newborn's collagen by
9 months, close to the human rate in the first year. The quartic printed as Eq. 6 does not
reproduce Table 1 beyond about age 2, probably because its coefficients are rounded, so the
table values are used. No livestock turnover rates are established: the cattle, sheep,
goat and pig tables are placeholders (TBD-LAB). They should be derived as WARN derived the
human ones: skeletal growth (modelling) plus remodelling, corrected for mineralisation delay.
Like WARN, the method suits fast-turnover bone (ribs, other cancellous bone).

### Nursing-signal check

Reynard & Tuross (2015) showed that a raised δ¹⁵N in the very
young is common but that weaning ages are hard to extract, often because samples are small.
Before the fit, the youngest third of the young animals are compared with the mothers
(one-sided Welch t-test); if they are not clearly higher, a warning says the data may hold no
nursing signal.

### Checks

Warnings are raised for fewer than 10 young animals, no young animal dying
before or after the estimated end of weaning, a completion interval covering most of the
allowed range (the prior is doing the work), an enrichment under 1‰, R̂ above 1.1, and
missing adult females. As Tsutaya & Yoneda stress, the model always fits something, even
when the data hold no weaning signal, so look at the plot first.

### References

Tsutaya T, Yoneda M (2013) *PLoS ONE* 8: e72327 (WARN; arXiv:1304.2468);
WARN R package manual, version 1.2-5 (2025). Millard AR (2000) A model for the effect of
weaning on nitrogen isotope ratios in humans. In Goodfriend et al. (eds), *Perspectives in
Amino Acid and Protein Geochemistry*, Oxford University Press. Waters-Rist AL, Katzenberg MA
(2010) *Int. J. Osteoarchaeol.* 20: 172–191. Sisson SA, Fan Y, Tanaka MM (2007) *PNAS* 104:
1760–1765. ter Braak CJF (2006) *Statistics and Computing* 16: 239–249. Reynard LM, Tuross N
(2015) *J. Archaeol. Sci.* 53: 618–625. Jenkins SG et al. (2001) *Oecologia* 129: 336–341.
Newsome SD, Koch PL, Etnier MA, Aurioles-Gamboa D (2006) *Marine Mammal Science* 22: 556–572.
Balasse M et al. (2001) *J. Archaeol. Sci.* 28: 235–245. Díez-Canseco, Tornero (2026)
*J. Archaeol. Sci.: Reports* 71: 105651. The full list, with what each source changed, is in
[BONE_LITERATURE.md](BONE_LITERATURE.md).

### Test

`scripts/make_bone_example.py` simulates two cattle sites with the model itself
(true weaning 3–9 and 1–4 months, newborn offset 0.8‰; ages as ranges). The tests check that
both are recovered within their 95% intervals, and that a flat dataset with no nursing rise
is flagged.

## 11. Planning a bone study (`bone_planner.py`)

Before bones are sampled, the planner invents sites whose end of suckling (t2) is known, drawn
from a chosen range, with weaning starting at 20–60% of t2. Each site gets the planned design:
the number of young animals, their ages (spread evenly up to the oldest age, or mostly very young
as in most death assemblages), an ageing method that gives each age as a range of ± the stated
precision containing the true age, adult females, and a scatter between animals. Bone δ¹⁵N is
simulated with the bone model itself (section 10) and the species' turnover table, and the bone
calculation is run on each site with shorter sampler runs (8 chains, 800 + 800 steps).

Each design is scored on the end of suckling: mean absolute error, bias, RMSE, the share of
sites whose 95% interval contains the truth, the median interval width, the share of sites where
the nursing-signal check finds a signal, and the share fitted. One setting (number of young
animals, age precision, oldest age, number of adult females or scatter) can be compared across
several values with the same random seed. Because the data are simulated with the same model that
is fitted, the planner tests the design (how many animals, how well aged), not the model; with
placeholder turnover it is a guide to relative, not absolute, precision.

## 12. Season of birth, rumen development and C3/C4 diet from enamel (`enamel.py`)

A molar's enamel forms from the cusp tip down to the enamel-root junction (ERJ) over several
months, so samples drilled up the crown are a time series. Each sample's position is its distance
from the ERJ (`erj_distance_mm`): larger distances formed earlier in life. Values are enamel
carbonate δ¹⁸O and δ¹³C (‰ VPDB). The method is set up for cattle; other species give a warning.

### Season of birth (δ¹⁸O)

Enamel δ¹⁸O follows the δ¹⁸O of drinking water, which is higher in summer than in winter. Each
tooth's δ¹⁸O series is fitted with a cosine (Balasse et al. 2012):

```
δ18O(x) = M + A·cos(2π(x − x0)/X)
```

M is the mean, A the amplitude, X the crown length formed in a year (kept between
`period_min_mm` and `period_max_mm`, default 25–80 mm) and x0 the position of the δ¹⁸O maximum,
taken within one cycle. The **birth index** x0/X (0–1) places the summer maximum on the tooth.
Between animals with the same tooth, which starts forming at about the same age, differences in
x0/X reflect differences in season of birth (Balasse et al. 2012; for cattle Towers et al. 2014;
Balasse et al. 2021). It is a relative index, not a calendar date, and it is only compared within
one tooth type.

* Fitted by least squares from 24 starting points; the 95% interval comes from 1000 draws from the
  fit's covariance and is computed around the estimate, so it can cross the 0/1 boundary.
* No index is reported when the amplitude is below `min_amplitude_permil` (default 0.5‰) or the
  cosine does not fit clearly better than a flat line (ΔAICc < 2).
* A warning appears when the samples cover less than ¾ of a year's crown growth, because X and x0
  are then poorly fixed.
* Group summary (site × species × tooth × period): the circular mean of the indices and their
  spread, the shortest stretch of the cycle that holds them all. Spread × 12 approximates how many
  months births were spread over.

### Rumen development (δ¹³C)

A suckling calf's rumen is not yet working. As it develops, microbial fermentation (and the methane
it makes) enriches the carbon reaching the enamel in ¹³C: the diet-to-enamel enrichment is larger in
animals with more fermentation (Passey et al. 2005; about 14‰ in large ruminants, Cerling & Harris
1999). First molar enamel δ¹³C therefore rises as the rumen develops (Towers et al. 2014). Diet also
changes with the seasons, so δ¹³C is fitted with two models and compared by AICc:

```
seasonal only:   δ13C(x) = B + b·sin(2πx/X) + c·cos(2πx/X)
with rumen step: δ13C(x) = B + b·sin(2πx/X) + c·cos(2πx/X) + R / (1 + exp((x − xm)/w))
```

X is the period found from δ¹⁸O; the phase of the δ¹³C wave is free (δ¹³C need not peak in summer).
Without a δ¹⁸O cycle the background is a flat line. R ≥ 0 is the rise and xm the position of the
transition. The step is reported as **rumen development** only when it fits clearly better
(ΔAICc ≥ 2) and R is at least `min_rumen_rise_permil` (default 0.5‰). Reported: xm with a 95%
interval, R, and, when X is known, the crown growth time between the first sample and xm
((highest position − xm) / X × 12 months).

* A rise above `max_rumen_rise_permil` (default 3‰) is flagged: rumen development alone gives
  about 1–2‰, so a change of diet (for example to C4 plants) is probably involved.
* A transition at the top of the sampled crown may have begun before the first sample formed.
* M3 forms after weaning, so no rumen transition is expected in it.

### C3 or C4 diet (δ¹³C)

Most temperate plants use the C3 pathway; C4 plants (millet, maize, sorghum, and many tropical and
dry-country grasses) are about 15‰ higher in δ¹³C. Enamel δ¹³C in large ruminants is about 14.1‰ above
the diet's (ε*, Cerling & Harris 1999), so

```
diet δ13C  = enamel δ13C − spacing
share of C4 = (diet δ13C − C3 end member) / (C4 end member − C3 end member)
```

* Only enamel formed after the rumen transition is used when one was found, because milk and an
  undeveloped rumen lower enamel δ¹³C. In an M1 without a transition a warning says the C4 share may
  be underestimated.
* Defaults are for a pre-industrial atmosphere: C3 −27.0 ± 2.0‰ and C4 −11.0 ± 1.0‰, from modern means
  (C3 about −28.5‰, Kohn 2010; C4 about −12.5‰) made about 1.5‰ less negative, because burning fossil
  fuel has lowered atmospheric (and plant) δ¹³C since about 1850. Use modern values for modern animals.
  The spacing is 14.1 ± 0.5‰.
* The tooth's mean, the spacing and both end members are drawn 1000 times from their uncertainties,
  giving a 95% interval for the share (limited to 0–100%). The share is labelled a C3 diet (under 20%),
  a C4 diet (over 80%) or mixed. The range of the per-sample shares shows seasonal changes, such as
  C4 fodder in one season.
* C3 plants vary from about −20 to −37‰ with water stress, light and canopy (Kohn 2010), so intervals
  are wide (about ±20 percentage points with the defaults). Enamel below a pure C3 diet's value is
  flagged (closed forest, the canopy effect, or a different spacing). For modern enamel, Cerling et al.
  (1997) treat values above −8‰ as a conservative sign of C4 plants.

### Mobility (⁸⁷Sr/⁸⁶Sr)

Enamel strontium follows the bioavailable strontium of the rocks and soils where the animal fed
(Bentley 2006). Shifts in `sr87_86` along the crown are found as for δ³⁴S (section 6), in the order
the enamel formed (from the cusp down), with a minimum of `sr_min_shift` (0.0005). When the δ¹⁸O cycle
is known, each shift is given a month (below). With `local_sr_min`/`local_sr_max`, values outside the
local range are counted and flagged. Enamel averages strontium over months of maturation, so profiles
are damped and the true move was sharper, and may have been earlier, than the shift seen (Montgomery
et al. 2010).

### Months of the year

With the month of the δ¹⁸O maximum (`d18O_max_month`, default 7 = July; summer in the northern
hemisphere, to be checked locally), enamel at position x formed ((x0 − x)/X mod 1) of a year after the
maximum, so

```
month(x) = d18O_max_month + 12 · ((x0 − x)/X mod 1)      (wrapped to 1–13)
```

* Rumen transition month: from xm, with a circular 95% interval from paired draws of (x0, X) and xm.
* Strontium shift months: from the midpoint between the two samples either side of the shift.
* Birth month: needs `reference_birth_index` and `reference_birth_month` from a tooth of the same type
  with a known birth date. A birth one month later moves the δ¹⁸O maximum lower on the crown, lowering
  the birth index by 1/12, so birth month = reference month + 12·(reference index − index) (mod 12).
* Weaning month: birth month + `weaning_age_months` (± `weaning_age_sd_months`), from the enamel table
  or, in the app, from the tooth calculation's model-average age for the same specimen ID.
* Group summaries give the circular mean month of the rumen transition and the number of teeth with a
  strontium shift.

### Smoothing correction

Enamel takes months to mineralise at any one position (Zazzo et al. 2005), so the recorded signals
are smoothed. With `mineralisation_length_mm` = L > 0, each sample is treated as a moving average over
L mm of crown (a simplification of the maturation geometry modelled by Passey & Cerling 2002):

* a cosine of period X is damped by sinc(L/X) = sin(πL/X)/(πL/X), so the restored amplitude is A /
  sinc(L/X) (not attempted when sinc < 0.3);
* a logistic step of width w has variance π²w²/3 and the average adds L²/12, so the restored width is
  √(w² − L²/(4π²)). The rise's duration is reported as its 10–90% span, 2·ln 9·w, in mm and, with X,
  in months.

These are first-order corrections, not an inverse model.

### Limits

Positions are not converted into ages, because enamel formation tables for cattle molars are not yet
available; the x0/X index and crown-growth times avoid needing them. The synthetic example
(`scripts/make_enamel_example.py`, twelve M2, smoothed over 8 mm) is recovered within 0.05 of each
birth index, 3 mm of each rumen transition, 0.05 of each C4 share and 3 mm of each strontium shift in
the tests.

## 13. Kill-off profiles (`killoff.py`)

Mandibles are aged by tooth eruption and wear. For sheep and goats, Payne (1973) stages are converted to
age ranges: A 0–2 months, B 2–6, C 6–12, D 12–24, E 24–36, F 36–48, G 48–72, H 72–96, I 96–120. A stage
range ("D/E", "D-E") spans its stages. Other species are entered as `age_min_months`/`age_max_months`
(a warning appears if Payne stages are given for a species other than sheep or goat).

* **Classes**: `class_bounds_months`, by default the Payne stage boundaries.
* **Sharing ambiguous mandibles**: a mandible whose range lies in one class counts 1 there. One that
  spans several is shared among them in proportion to the number of mandibles found in only one of
  those classes (Payne 1973); if none are, in proportion to how much of each class its range covers.
  Mandibles outside every class are left out, with a warning.
* **Profile**: deaths per class (share of the group) and survivorship after each class (1 − cumulative
  deaths). 95% intervals from `bootstrap_draws` (1000) resamples of the mandibles.
* **Indicators**, assuming deaths spread evenly within a class: share killed before 6 months, share
  killed at 6–36 months, and share alive at 48 months. They correspond to Payne's (1973) milk, meat and
  wool models; see Vigne & Helmer (2007) for their use and limits. Real herds mix aims, and young
  mandibles are under-represented through differential preservation, so the indicators are not
  converted into a verdict.
* **Comparing groups**: for each pair, the statistic is half the summed absolute difference of the
  death shares (0–1); its p value is the share of `permutations` (1000) random reassignments of
  mandibles between the two groups giving a statistic at least as large ((hits + 1)/(N + 1)).
* A warning appears below 30 mandibles.

Tested on a synthetic example (`scripts/make_killoff_example.py`: 2 × 60 mandibles, 20% given as two
stages), on Payne-style sharing, and on two samples from one herd, which are not called different.

## 14. Diet mixing (`mixing.py`)

Collagen δ¹³C, δ¹⁵N and optionally δ³⁴S are modelled as a mix of 2–6 food groups (`sources`, each with a
mean and SD per isotope) plus a collagen-diet offset per isotope (mean and SD):

```
expected_i(p)  = Σ_s p_s·μ_{s,i} + Δ_i
variance_i(p)  = Σ_s p_s²·σ_{s,i}² + σ_Δi² + σ_measurement²
```

as in FRUITS (Fernandes et al. 2014) and MixSIAR-style models (Stock et al. 2018), with foods mixed
by their protein (no concentration dependence). The shares p have a flat Dirichlet(1, …, 1) prior.
`draws` (20000) diets are drawn from the prior once and, for each sample, weighted by the normal
likelihood of its values (importance sampling). Reported per sample: the posterior mean of each share
and its 95% interval (weighted 2.5% and 97.5% quantiles), and the effective number of draws
(1/Σw²; a warning below 200). Group results are the means of the samples' posterior means.

* δ³⁴S is used only when every food group and the offset have a δ³⁴S value, and for samples that
  have one.
* **Outside the mixing space**: if no drawn diet brings every isotope within 2.5 SD of the sample, a
  food group is missing or a value is wrong.
* **Underdetermined**: with more food groups than isotopes + 1 the shares are not fixed by the data;
  the intervals show this and a warning says so (Phillips et al. 2014).
* **Placeholders**: the food values and offsets in `data/diet_sources.json` are rough round values
  (C3 plants, C4 plants, terrestrial animals, marine fish; Δ¹³C 4.8 ± 0.5‰, Δ¹⁵N 5.5 ± 0.5‰, Δ³⁴S 0.5 ±
  1.0‰). Results say when they are in use. A controlled feeding study put the human diet-collagen
  δ¹⁵N offset at about 6‰ (O'Connell et al. 2012).

Tested on a two-food mix with a known 30% share, on a sample outside the mixing space, and on a
synthetic example (`scripts/make_mixing_example.py`: an inland and a coastal site of 15 people) whose
estimated marine shares follow the true ones (r > 0.8).

### References for sections 12–14

* Bentley RA (2006) Strontium isotopes from the earth to the archaeological skeleton: a review. *J. Archaeol. Method Theory* 13: 135–187.
* Fernandes R, Millard AR, Brabec M, Nadeau M-J, Grootes P (2014) Food reconstruction using isotopic transferred signals (FRUITS): a Bayesian model for diet reconstruction. *PLoS ONE* 9: e87436.
* Montgomery J, Evans JA, Horstwood MSA (2010) Evidence for long-term averaging of strontium in bovine enamel using TIMS and LA-MC-ICP-MS strontium isotope intra-molar profiles. *Environ. Archaeol.* 15: 32–42.
* Nehlich O (2015) The application of sulphur isotope analyses in archaeological research: a review. *Earth-Sci. Rev.* 142: 1–17.
* O'Connell TC, Kneale CJ, Tasevska N, Kuhnle GGC (2012) The diet-body offset in human nitrogen isotopic values: a controlled dietary study. *Am. J. Phys. Anthropol.* 149: 426–434.
* Payne S (1973) Kill-off patterns in sheep and goats: the mandibles from Aşvan Kale. *Anatolian Stud.* 23: 281–303.
* Phillips DL, Inger R, Bearhop S, Jackson AL, Moore JW, Parnell AC, Semmens BX, Ward EJ (2014) Best practices for use of stable isotope mixing models in food-web studies. *Can. J. Zool.* 92: 823–835.
* Stock BC, Jackson AL, Ward EJ, Parnell AC, Phillips DL, Semmens BX (2018) Analyzing mixing systems using a new generation of Bayesian tracer mixing models. *PeerJ* 6: e5096.
* Vigne J-D, Helmer D (2007) Was milk a "secondary product" in the Old World Neolithisation process? *Anthropozoologica* 42: 9–40.

## 15. Breast-milk share per increment (`milkshare.py`)

With an adult-female baseline for the site (mean and SD of δ¹⁵N, optionally δ¹³C), each used dentine
increment is treated as a mix of collagen made on breast milk alone and on the adult diet alone (the
WARN idea, Tsutaya & Yoneda 2013, applied increment by increment). For a milk share p (and an optional
third food share o, with the adult diet 1 − p − o):

```
expected  = (p + adult)·baseline + p·E + o·food
variance  = (p + adult)²·sd_baseline² + p²·sd_E² + o²·sd_food² + sd_measurement²
```

for δ¹⁵N, and for δ¹³C when the baseline has it. The baseline term is shared by milk and adult diet,
so its uncertainty is not split between them. E (δ¹⁵N) defaults to the species prior of the bone
calculation (humans: 1.9 ± 0.9‰, WARN); the δ¹³C enrichment is 1.0 ± 0.5‰ (Fuller et al. 2006). The
measurement SD is the lab precision, or 0.2‰ if not given. The shares have a flat prior and the
posterior is computed exactly on a grid (steps of 0.01). Reported per increment: the posterior mean
milk share and its 95% interval; and the first age after which the mean stays below one half. Posterior
means of a bounded share cannot reach 0 or 1, so lower thresholds are not dated. A third food needs δ¹³C
for both the food and the baseline, because one isotope cannot separate three foods; without it the food
is left out with a warning. Dentine increments average weeks to months and collagen lags the diet
(Beaumont et al. 2015; Tsutaya 2020), so the curve is smoothed and slightly late.

Tested on a simulated child weaned at 24 months: the half-way age is recovered within 4 months, and the
share falls from over 0.7 to under 0.3.

## 16. Dental age (`dental_age.py`)

Each tooth is scored in a Moorrees et al. (1963) stage: Ci, Cco, Coc, Cr½, Cr¾, Crc, Ri, R¼, R½, R¾, Rc,
A½, Ac (Cli is read as Ri; numbers 1–13 are accepted). For each tooth `data/dental_stages.json` gives four
ages (months from birth; negative before birth): crown initiation, crown complete, root length complete
and apex closed. Stage attainment ages are spaced evenly between them (Ci–Crc over the crown; Ri at 5%,
then R¼–Rc over the root; A½ and Ac over apex closure). **These are rounded placeholder values**, not a
checked standard; they should be replaced with stage ages from a published atlas (e.g. AlQahtani et al.
2010; Smith 1991).

* A tooth in a stage is between the attainment of that stage and of the next: its age is the midpoint,
  with SD² = width²/12 (uniform) + spread², spread = max(10% of the age, 2 months) (placeholder).
* A tooth at Ac gives only a minimum age.
* Teeth are combined by an inverse-variance weighted mean. Teeth of one child are not independent, so
  the combined SD is √(n / Σw), the SD of a typical tooth, rather than √(1 / Σw).
* Teeth more than 2 SD from the combined age are flagged; an estimate younger than a closed apex allows
  is flagged; an estimate before birth is noted.
* The range passed on is estimate ± 1.96 SD (`interval_z`), clipped at 0. In the app it can be written
  into the bone calculation (`age_min_months`/`age_max_months` of non-adults with the same specimen ID)
  or the life tables.

Tested on 24 simulated children (stages drawn from the same table with 8% developmental variation): mean
absolute error under 6 months and coverage of the range above 85%. This checks the arithmetic, not the
formation ages.

## 17. Enamel hypoplasia timing (`hypoplasia.py`)

A linear enamel hypoplasia (LEH) defect is dated from its height above the cemento-enamel junction (CEJ),
d, on a crown of unworn height H, assuming the visible crown forms at an even rate (Goodman & Rose 1990):

```
age = initiation + cuspal + (1 − d/H)·(crown completion − initiation − cuspal)
```

Initiation and completion come from `data/dental_stages.json`; `cuspal_months` (the enamel formed under
the cusp before the surface layers appear; Reid & Dean 2006) is 0 until set. Enamel in fact forms more
slowly towards the CEJ (Reid & Dean 2006), so even-rate ages are too young near the cusp and too old near
the CEJ. The 95% interval comes from 2000 draws of the formation ages (SD as in section 16) and of d (SD
0.2 mm). When the tooth calculation has results for the same specimen ID, each defect is classed as
before, during (its interval overlaps onset–completion of the model-average δ¹⁵N fall) or after weaning,
and as overlapping a dentine stress episode or not; the share of comparable defects formed during weaning
is reported.

## 18. Life tables (`lifetable.py`)

Each skeleton's age range (years; an open range runs to the last class boundary) is shared over the age
classes by overlap. Default classes: single years to 5, then 5–10, 10–15, 15–20, decades to 60, and
60–80. For each site × period (Chamberlain 2006):

```
Dx deaths, dx = Dx/N, lx = 1 − Σ earlier dx, qx = dx/lx, Lx = n·(lx + lx+n)/2, Tx = Σ_{≥x} Lx, ex = Tx/lx
```

* Summaries: e₀; share of deaths under 1 and under 5 years; juvenility index D5–14 / D20+
  (Bocquet-Appel & Masset 1977), with deaths spread evenly within classes. 95% intervals from 1000
  resamples of the skeletons.
* Siler (1979) hazard h(t) = a₁e^(−b₁t) + a₂ + a₃e^(b₃t), fitted by maximum likelihood with each age range
  interval-censored (an open range runs to 1.2 × the last boundary), with parameters bounded to plausible
  values (b₁ 0.05–10, b₃ 0.01–0.2 per year). Its e₀ is the area under the survival curve. With open-ended
  adult ages the senescent part is poorly fixed.
* Groups are compared with the permutation test of section 13 on the shares of deaths by class.
* Warnings: fewer than 30 skeletons; infants under 10% of the dead (pre-modern populations usually lost
  far more, so infant burials are probably missing; Bocquet-Appel & Masset 1982). Always: a life table
  describes a living population only if it was stationary and the dead are a fair sample (the
  osteological paradox, Wood et al. 1992).

Tested on a hand-checked ten-skeleton table and on two simulated cemeteries (Siler hazards, adult ages in
14-year ranges and 50+): e₀ within 6 years of the truth, and the cemetery that lost infant burials is
flagged.

## 19. Mobility from bulk enamel (`mobility.py`)

* **Oxygen.** Carbonate δ¹⁸O (‰ VPDB) is put on the VSMOW scale (δ¹⁸O_VSMOW = 1.03091·δ¹⁸O_VPDB + 30.91;
  Coplen et al. 1983) and converted to drinking water with δ¹⁸O_dw = 1.590·δ¹⁸O_c − 48.634 (Chenery et
  al. 2012). Phosphate (‰ VSMOW) uses δ¹⁸O_dw = 1.54·δ¹⁸O_p − 33.72 (Daux et al. 2008); Chenery's equation
  is their carbonate-to-phosphate relation (δ¹⁸O_p = 1.0322·δ¹⁸O_c − 9.6849) followed by Daux's, which the
  tests check. Each value carries an SD (default 1‰) for the conversion error, which Pollard et al. (2011)
  show can be larger.
* **Strontium.** The local range is, in order: the range in Settings; the mean ± 2 SD of baseline samples
  from the same site (`role` = baseline; Price et al. 2002); or Tukey fences (1.5 × IQR beyond the
  quartiles) among the site's people if there are at least 8, preferred to ± 2 SD by Lightfoot &
  O'Connell (2016). The drinking-water range is from Settings or Tukey fences.
* A value is **non-local** if it lies outside the range by more than 1.96 SD (δ¹⁸O) or at all (⁸⁷Sr/⁸⁶Sr).
  Outside means "not from here", not "from there".
* First molars and deciduous teeth form partly during breastfeeding, which raises δ¹⁸O (Wright & Schwarcz
  1998); they are noted.

Tested on the conversion equations (Chenery's worked value: −4.0‰ VPDB carbonate ≈ −6.0‰ drinking water)
and on a simulated site where exactly the five incomers are found.

## 20. Choosing calculations and grouping by other columns

The Data page sends a dropped table to `/api/detect`, which runs every calculation's reader on it and
reports the rows each would accept and, if none, the first problem. Ticked calculations receive the file.
In the tooth calculation, columns that are not used are kept as labels on each sample and passed into the
estimates, so Compare can group by them (any label with 2–20 values).

### References for sections 15–20

* AlQahtani SJ, Hector MP, Liversidge HM (2010) Brief communication: the London atlas of human tooth development and eruption. *Am. J. Phys. Anthropol.* 142: 481–490.
* Beaumont J, Montgomery J, Buckberry J, Jay M (2015) Infant mortality and isotopic complexity: new approaches to stress, maternal health, and weaning. *Am. J. Phys. Anthropol.* 157: 441–457.
* Bocquet-Appel J-P, Masset C (1977) Estimateurs en paléodémographie. *L'Homme* 17(4): 65–90.
* Bocquet-Appel J-P, Masset C (1982) Farewell to paleodemography. *J. Hum. Evol.* 11: 321–333.
* Chamberlain AT (2006) *Demography in Archaeology*. Cambridge University Press.
* Chenery CA, Pashley V, Lamb AL, Sloane HJ, Evans JA (2012) The oxygen isotope relationship between the phosphate and structural carbonate fractions of human bioapatite. *Rapid Commun. Mass Spectrom.* 26: 309–319.
* Coplen TB, Kendall C, Hopple J (1983) Comparison of stable isotope reference samples. *Nature* 302: 236–238.
* Daux V et al. (2008) Oxygen isotope fractionation between human phosphate and water revisited. *J. Hum. Evol.* 55: 1138–1147.
* Fuller BT, Fuller JL, Harris DA, Hedges REM (2006) Detection of breastfeeding and weaning in modern human infants with carbon and nitrogen stable isotope ratios. *Am. J. Phys. Anthropol.* 129: 279–293.
* Goodman AH, Rose JC (1990) Assessment of systemic physiological perturbations from dental enamel hypoplasias and associated histological structures. *Yearb. Phys. Anthropol.* 33: 59–110.
* Lightfoot E, O'Connell TC (2016) On the use of biomineral oxygen isotope data to identify human migrants in the archaeological record. *PLoS ONE* 11: e0153850.
* Moorrees CFA, Fanning EA, Hunt EE (1963) Age variation of formation stages for ten permanent teeth. *J. Dent. Res.* 42: 1490–1502.
* Pollard AM, Pellegrini M, Lee-Thorp JA (2011) Technical note: some observations on the conversion of dental enamel δ18Op values to δ18Ow to determine human mobility. *Am. J. Phys. Anthropol.* 145: 499–504.
* Price TD, Burton JH, Bentley RA (2002) The characterization of biologically available strontium isotope ratios for the study of prehistoric migration. *Archaeometry* 44: 117–135.
* Reid DJ, Dean MC (2006) Variation in modern human enamel formation times. *J. Hum. Evol.* 50: 329–346.
* Siler W (1979) A competing-risk model for animal mortality. *Ecology* 60: 750–757.
* Smith BH (1991) Standards of human tooth formation and dental age assessment. In Kelley MA, Larsen CS (eds) *Advances in Dental Anthropology*, pp. 143–168. Wiley-Liss.
* Wood JW, Milner GR, Harpending HC, Weiss KM (1992) The osteological paradox. *Curr. Anthropol.* 33: 343–370.
* Wright LE, Schwarcz HP (1998) Stable carbon and oxygen isotopes in human tooth enamel: identifying breastfeeding and weaning in prehistory. *Am. J. Phys. Anthropol.* 106: 1–18.

## Limitations / future work

* The slice geometry assumes straight growth layers and a circular cross-section. Real
  layers curve, and the livestock values must still be measured (`TBD-LAB`).
* The one-stage model uses the logistic curve only and no time averaging or seasonal
  term; it is a check on, not a replacement for, the per-specimen model comparison.
* The bone calculation needs livestock bone collagen turnover rates, which have not been
  established; until then its ages are illustrative. Its results are not yet part of the
  Compare page or the downloadable report.
* Results can be shown in months or years; the analysis always works in months.
