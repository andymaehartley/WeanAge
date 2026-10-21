# Related tools and what WeanAge takes from them

| | WARN | MDSS | WEAN | **WeanAge** |
|---|---|---|---|---|
| Reference | Tsutaya & Yoneda 2013, *PLoS ONE* 8:e72327 | Tsutaya 2020, *AJPA* 173:748–759 | Ganiatsou et al. 2023, *Archaeol. Anthropol. Sci.* 15:50 | this project |
| Language / licence | R, GPL-3 | R, GPL-3 | Python | Python + web UI, MIT |
| Data | bulk **bone** collagen, one value per individual, cross-sectional population | dentine section geometry | incremental **dentine**, one series per individual | incremental dentine, one series per tooth |
| Taxa | humans | human incisors, canines, molars | humans | **cattle, pig, horse** (extensible) |
| Ages | user-estimated skeletal ages | modelled from dentine microstructure | user-assigned per increment | **from tooth position** via species/tooth growth tables |
| Estimation | ABC, curve forms linear/parabolic/reverse/sigmoid | age range of each section | 4th-degree polynomial + elbow | logistic, piecewise, exponential, two-phase **and** WEAN-style elbow, compared by AICc and averaged |
| Uncertainty | posterior credible intervals | age range per section | none (R², derivative) | covariance or bootstrap 95 % intervals with shared age-model error; hierarchical Bayesian group comparison |
| Validation | — | — | RMSE vs. 130 visually estimated published individuals | bias/MAE/RMSE/coverage vs. **known-age animals** and **published estimates** |

## What was taken from each

**WEAN**
* `elbow` model (`models.fit_elbow`): 4th-degree polynomial fit; weaning completion
  is the point farthest below the line from the fitted δ¹⁵N peak to the last
  sample. By default the axes are first rescaled to [0, 1]
  (`elbow_normalise`), because the raw distance depends on the units. Turn this off
  to match WEAN's raw-unit calculation.
* The slope at the elbow is checked, and a rising curve there is flagged as a
  possible false estimate.
* Whole profiles that *rise* with age (WEAN notes this is seen in malnourished
  individuals) are flagged (`analysis.rising_profile_warning`).
* The re-estimation test is reproduced: supply `published_weaning_age_months` and the
  Compare view reports agreement with the published values for each model.

**MDSS / Tsutaya 2020**
* Optional **time averaging** (`time_averaging`): each slice is integrated over its
  height (`increment_width_mm`) and over the dentine depth, where oblique growth layers
  add later-formed dentine (`growth_layer_offset_mm`, TBD-LAB) and inner dentine counts
  for less volume (`inner_dentine_weight`, TBD-LAB). Each sample is fitted as the
  curve's weighted average over that grid, so the milestones refer to the underlying
  diet change. Unlike MDSS, growth layers are straight and the cross-section circular,
  and MDSS's parameters are for human teeth, so livestock values still have to be measured.

**WARN**
* An **adult-female baseline** (`adult_baselines`, per site and species) acts as the
  maternal reference. It is used to report nursing enrichment (nursing plateau minus
  the female mean, WARN's *E*) and, optionally, to hold the adult plateau within
  ±2 SD of it (`constrain_adult_plateau`).
* WARN's curve forms (linear, sigmoid, and parabolic as a smooth decline) are covered
  by the piecewise, logistic and exponential models.
* Bayesian inference is used at the group level: a hierarchical model pools specimen
  estimates within sites and species (two-stage), or fits every specimen's raw δ¹⁵N
  values together with the group means (one-stage), and gives direct probabilities
  such as P(pigs weaned earlier than cattle). For teeth, WARN's bone-collagen turnover
  model does not apply: dentine does not remodel after it forms.
* The **bone calculation** (`bone.py`) is WARN's own method, adapted for animals: the same
  diet model (Eq. 7–8, parabolic by default, also linear and reverse), the same bone
  turnover model (Eq. 9–10) and WARN's default priors for E, W and σ. It differs in fitting
  the likelihood with an MCMC sampler instead of ABC-SMC, in estimating the mothers' mean
  rather than fixing it, in flat t1/t2 priors up to a user-set limit, and in taking
  turnover from a per-species table (WARN's human rib values are included as `human`;
  livestock values are placeholders). WARN's sigmoid form is not included.

## Licensing note

WARN and MDSS are GPL-3. Nothing here was copied from their source. The methods were
re-implemented from the published descriptions, so WeanAge can stay MIT-licensed. If
code from either package is ever ported directly, the project would have to move to
the GPL.
