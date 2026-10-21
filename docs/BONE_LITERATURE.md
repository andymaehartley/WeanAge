# Bone δ¹⁵N and weaning in animals: what the literature supports

A short review behind the bone calculation (`src/weanage/bone.py`), gathered in October 2026.
For each source: what it found, and what WeanAge does because of it. Where a figure could
not be checked against the original paper, this says so.

## Methods for bone (cross-sectional) data

| source | finding | used in WeanAge |
|---|---|---|
| Tsutaya & Yoneda 2013, *PLoS ONE* 8: e72327 (WARN); WARN manual 1.2-5 | Diet model (Eq. 7–8: milk share falls parabolically between t1 and t2); bone collagen turnover model (Eq. 9–10) with human rib turnover per year (Table 1); newborns assumed equal to their mothers; priors E ~ N(1.9, 0.9), W ~ N(female mean, 3), σ ~ \|N(0, 1)\|; the model "will always attempt to fit", so inspect the data first | The core model, the weaning forms, the priors for E, W and σ, and the human turnover table. Turnover per year T is read as the share replaced that year (Eq. 9), so a monthly share is 1 − (1 − min(T, 0.97))^(1/12); this reproduces the paper's 96.6% replaced by 31 weeks |
| Millard 2000, in *Perspectives in Amino Acid and Protein Geochemistry* | Nitrogen mass-balance model of weaning with start and end ages; parabolic weaning | Via WARN |
| Reynard & Tuross 2015, *J. Archaeol. Sci.* 53: 618–625 | Across 56 sites (1,560 individuals), bone collagen δ¹⁵N is raised at 0–1 years and then falls to near the adult mean, but neither modelling nor inspection has yielded precise weaning ages; many studies have too few individuals; neonates fall both above and below the adult-female mean | A **nursing-signal check** (youngest third of the young against the mothers, one-sided Welch t-test) with a warning when there is no clear rise; warnings for fewer than 10 young animals and for intervals that only repeat the prior |

## Mother–offspring offsets in mammals

| source | finding | used in WeanAge |
|---|---|---|
| Jenkins et al. 2001, *Oecologia* 129: 336–341 | 11 mammal species: offspring plasma only c. 0.9‰ above maternal plasma, less than a full trophic step, because milk is lighter in ¹⁵N than maternal plasma | Livestock enrichment priors have a wide SD (1‰) that includes values near 1‰ |
| Bovid collagen, as summarised in sequential dentine studies (e.g. Tana del Barletta, *Archaeol. Anthropol. Sci.* 2021, following Balasse et al. 2001) | Mother and nursing calf c. 3–3.5‰ apart in collagen δ¹⁵N | Cattle enrichment prior 3.0 ± 1.0‰ (placeholder) |
| "Can the carbon and nitrogen isotope values of offspring be used as a proxy for their mother's diet?", *Conservation Physiology* 8: coaa060 (2020) | Foetal bulk δ¹⁵N 1.7 ± 0.5‰ (0.9–2.7‰) above the mother before birth (a marine mammal), from amino-acid shuttling between mother and foetus | A **newborn offset** parameter (newborn bone minus the mothers' mean), estimated with a prior of 1.0 ± 1.0‰ for livestock; WARN's 0 is kept for humans |
| Díez-Canseco & Tornero 2026, *J. Archaeol. Sci.: Reports* 71: 105651 (citing earlier work) | Calf and sheep foetal bone collagen reported 2.6–2.7‰ above the mother | Supports a positive newborn offset; **primary source not yet checked**, so not used as the prior's centre |
| Waters-Rist & Katzenberg 2010, *Int. J. Osteoarchaeol.* 20: 172–191 | Source of WARN's enrichment prior for humans | Human prior only |

## Bone turnover in young mammals

| source | finding | used in WeanAge |
|---|---|---|
| Newsome et al. 2006, *Marine Mammal Science* 22: 556–572 | Northern fur seal: nursing pups have ¹⁵N-enriched bone collagen, falling in animals aged 6–20 months; complete turnover of young-of-the-year bone collagen in c. 8–10 months. California sea lion: bone collagen pattern consistent with weaning at c. 12–14 months once turnover is accounted for | Livestock turnover placeholders re-anchored so that c. 95% of a newborn's collagen is replaced by 9 months. WARN's human values, read as above, give a similar rate in the first year (c. 37% per month) |
| Kosintsev et al. 2023 (Ural cave bear) | Bone collagen δ¹⁵N falls with age from newborns and yearlings, linked to weaning | Supports applying the method to non-human mammals |

No bone collagen turnover rates for cattle, sheep, goats or pigs were found. The livestock
tables remain placeholders (TBD-LAB) until they are derived as WARN derived the human ones:
skeletal growth plus remodelling, corrected for the delay in mineralisation.

## Reading the weaning ages

| source | finding | used in WeanAge |
|---|---|---|
| Balasse et al. 2001, *J. Archaeol. Sci.* 28: 235–245 (known-age steers, dentine) | When weaned onto a protein-poor diet, δ¹⁵N traces the **cessation of suckling** | The end of weaning (t2) is reported as "suckling ends" |
| Díez-Canseco & Tornero 2026 (early-weaned modern sheep, dentine) | First known-age reference set for sheep; δ¹⁵N records the end of suckling rather than the gradual fall in milk; protein-rich forage may blur this | Same wording; the caveat is in the method notes |
| Balasse & Tresset 2002, *J. Archaeol. Sci.* 29: 853–859 (Bercy) | Early weaning of Neolithic calves, perhaps imposed to keep milk for people | Context for interpreting early ages |

## Still needed

* Livestock bone collagen turnover rates (growth and remodelling data).
* Bone-collagen enrichment and newborn offsets from known-age calves, lambs, kids and piglets
  with their mothers; the primary source for the 2.6–2.7‰ foetal figure.
* Note that animals that died young are not a random sample of the herd (culled surplus
  calves in dairying, for example), just as children who died are not a random sample of the
  living (the osteological paradox). This affects which ages are represented.
