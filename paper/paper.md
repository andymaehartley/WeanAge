---
title: 'WeanAge: weaning-age estimation for livestock from incremental dentine nitrogen isotopes'
tags: [Python, zooarchaeology, stable isotopes, weaning, livestock, Bayesian statistics]
authors:
  - name: Annabelle Hartley
    affiliation: 1
affiliations:
  - name: TBD
    index: 1
date: TBD
bibliography: paper.bib
---

<!-- Draft for the Journal of Open Source Software. Items marked TBD still need filling in. -->

# Summary

When and how young animals were weaned tells archaeologists how herds were managed: early
weaning frees milk for people, staged weaning points to dairying, and seasonal patterns
reflect when animals were born. While a young mammal suckles, its tissues carry the higher
nitrogen-isotope value (δ¹⁵N) of its mother's milk, one step up the food chain; after
weaning, δ¹⁵N falls to the adult level [@deniro1981; @minagawa1984; @fuller2006]. Tooth
dentine grows in layers and does not remodel, so a series of thin slices cut along a tooth
records this fall month by month [@balasse2001; @beaumont2013].

WeanAge turns such a series into a weaning age with an honest uncertainty. It converts each
slice's position on the tooth into an age, checks collagen quality, fits five candidate
shapes of weaning curve, compares and averages them, corrects for the blurring caused by
slicing, and compares weaning ages between sites, species and periods. A simulation-based
planner shows, before any tooth is cut, how sampling choices affect accuracy. It runs as a
local web app, from the command line, or entirely inside a web browser.

# Statement of need

Existing weaning-age tools were built for humans. WARN [@tsutaya2013] models
cross-sectional bone collagen values of a population; WEAN [@ganiatsou2023] fits a
polynomial to incremental dentine whose ages have already been assigned; MDSS
[@tsutaya2020] describes how slicing blurs dentine time series. Zooarchaeologists working
on cattle, pigs and horses still write their own models, so weaning ages from different
studies are hard to compare.

WeanAge provides one documented and tested method for livestock:

* **Position to age** from species- and tooth-specific growth tables, with the age-model
  error propagated as one shared shift per tooth. Cattle tables use the crown chronology of
  @brown1960; values still to be measured are flagged in the interface.
* **Five curve models** (logistic, piecewise linear, exponential, two-phase staged weaning,
  and a WEAN-style polynomial elbow), compared with AICc and combined by Akaike weights
  [@hurvich1989; @burnham2002].
* **Slice geometry**: each slice is integrated over its height and dentine depth with oblique
  growth layers, following @tsutaya2020.
* **Checks** for collagen quality [@deniro1985; @vanklinken1999; @guiry2020], implausible
  δ¹⁵N drops, seasonal cycles [@balasse2021], rising profiles that suggest physiological
  stress [@beaumont2016], and the δ¹³C rise that accompanied weaning in known-age calves
  [@balasse2001].
* **Group comparison** by random-effects meta-analysis [@dersimonian1986], permutation and
  Holm-corrected tests [@holm1979], and hierarchical Bayesian models: a two-stage model on
  the specimen estimates and a one-stage model fitted to the raw δ¹⁵N values of every tooth,
  with half-Cauchy priors [@gelman2006] and split-R̂ convergence checks [@vehtari2021].
* **Validation** against known-age animals or published estimates [@balasse2001; @balasse2002].
* A **browser version** built on Pyodide [@pyodide], so nothing has to be installed.

# Acknowledgements

TBD

# References
