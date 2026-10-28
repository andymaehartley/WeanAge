---
title: 'WeanAge: weaning ages and life histories of archaeological animals and people from stable isotopes'
tags: [Python, zooarchaeology, bioarchaeology, stable isotopes, weaning, livestock, Bayesian statistics]
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
slicing, and compares weaning ages between sites, species and periods. It also estimates the end
of suckling from the bone collagen of many young individuals who died at different ages (after
WARN, @tsutaya2013). Simulation-based planners show, before any tooth is cut or bone sampled, how
sampling choices affect accuracy. Around weaning it offers the calculations that usually go with
it in a study (below), all from the same table. It runs as a local web app, from the command line,
or entirely inside a web browser.

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

Weaning ages are rarely interpreted alone, so WeanAge also provides, from the same data table:
kill-off profiles from aged mandibles [@payne1973]; a Bayesian diet-mixing model for collagen δ¹³C,
δ¹⁵N and δ³⁴S in the style of FRUITS [@fernandes2014], with concentration dependence
[@phillips2002]; for cattle, season of birth and rumen development from sequential enamel δ¹⁸O and
δ¹³C; and for people, the breast-milk share at each dentine increment, age at death from tooth
formation stages [@moorrees1963] by transition analysis [@boldsen2002], the timing of enamel
hypoplasia, life tables with a Siler hazard [@siler1979], and mobility from enamel δ¹⁸O
[@chenery2012] and ⁸⁷Sr/⁸⁶Sr with likely places of origin. A dropped table is checked against every
calculation; an *Individuals* page puts each person's or animal's results on one timeline; and a
methods paragraph with references is written from the settings used, so that analyses are reported
consistently. Every calculation ships with an example; most are published data from IsoArcH
[@salesse2018], CIMA [@cocozza2022] and two R packages, with their sources and assumptions documented.

WeanAge is tested with pytest (unit, known-answer and simulation tests, and a browser test of the
whole app with Playwright) and with Node's test runner for the interface's own logic.

# Acknowledgements

TBD

# References
