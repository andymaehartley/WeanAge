# Related tools and what WeanAge takes from them

| | WARN | MDSS | WEAN | **WeanAge** |
|---|---|---|---|---|
| Reference | Tsutaya & Yoneda 2013, *PLoS ONE* 8:e72327 | Tsutaya 2020, *AJPA* 173:748–759 | Ganiatsou et al. 2023, *Archaeol. Anthropol. Sci.* 15:50 | this project |
| Language / licence | R, GPL-3 | R, GPL-3 | Python | Python + web UI, MIT |
| Data | bulk **bone** collagen, one value per individual, cross-sectional population | dentine section geometry | incremental **dentine**, one series per individual | incremental dentine, one series per tooth |
| Taxa | humans | human incisors, canines, molars | humans | **cattle, pig, horse** (extensible) |
| Ages | user-estimated skeletal ages | modelled from dentine microstructure | user-assigned per increment | **from tooth position** via species/tooth growth tables |
| Estimation | ABC, curve forms linear/parabolic/reverse/sigmoid | age range of each section | 4th-degree polynomial + elbow | logistic, piecewise, exponential **and** WEAN-style elbow, compared by AICc |
| Uncertainty | posterior credible intervals | age range per section | none (R², derivative) | Monte Carlo 95 % intervals + age-model uncertainty |
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
* Optional **time averaging** (`time_averaging`): each sample covers an age window
  rather than a single age. The window is the increment's height
  (`increment_width_mm`) plus extra later-formed dentine picked up because growth
  layers are oblique (`growth_layer_offset_mm`, TBD-LAB). Each sample is fitted as
  the curve's average over its window, so the milestones refer to the underlying
  diet change. This is a simplification: MDSS weights growth layers by volume and
  models the curved tooth outline. Its parameters are for human teeth, so the
  livestock values still have to be measured.

**WARN**
* An **adult-female baseline** (`adult_baselines`, per site and species) acts as the
  maternal reference. It is used to report nursing enrichment (nursing plateau minus
  the female mean, WARN's *E*) and, optionally, to hold the adult plateau within
  ±2 SD of it (`constrain_adult_plateau`).
* WARN's curve forms (linear, sigmoid, and parabolic as a smooth decline) are covered
  by the piecewise, logistic and exponential models.
* Not adopted (yet): Approximate Bayesian Computation (ABC) and bone-collagen turnover
  modelling. Turnover does not apply to dentine, which does not remodel after it
  forms. A Bayesian fitting option remains possible future work.

## Licensing note

WARN and MDSS are GPL-3. Nothing here was copied from their source. The methods were
re-implemented from the published descriptions, so WeanAge can stay MIT-licensed. If
code from either package is ever ported directly, the project would have to move to
the GPL.
