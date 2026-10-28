"""A methods paragraph for a paper or thesis, written from the settings that were actually used.

`write_methods(runs)` takes, for each calculation that was run, its settings and a few counts, and
returns the text, the references it cites, and the placeholder values still in use (which must be
reported, or replaced, before publication).
"""

from . import __version__, config
from .schema import (
    AnalysisOptions,
    BoneOptions,
    DentalOptions,
    EnamelOptions,
    KilloffOptions,
    LehOptions,
    LifeTableOptions,
    MixingOptions,
    MobilityOptions,
)

REFERENCES = {
    "balasse2012": "Balasse M, Obein G, Ughetto-Monfrin J, Mainland I (2012) Investigating seasonality and season of birth in past herds: a reference set of sheep enamel stable oxygen isotope ratios. Archaeometry 54: 349–368.",
    "bentley2006": "Bentley RA (2006) Strontium isotopes from the earth to the archaeological skeleton: a review. Journal of Archaeological Method and Theory 13: 135–187.",
    "bocquet1977": "Bocquet-Appel J-P, Masset C (1977) Estimateurs en paléodémographie. L'Homme 17(4): 65–90.",
    "boldsen2002": "Boldsen JL, Milner GR, Konigsberg LW, Wood JW (2002) Transition analysis: a new method for estimating age from skeletons. In Hoppa RD, Vaupel JW (eds) Paleodemography: Age Distributions from Skeletal Samples, 73–106. Cambridge University Press.",
    "burnham2002": "Burnham KP, Anderson DR (2002) Model Selection and Multimodel Inference, 2nd ed. Springer.",
    "cerling1999": "Cerling TE, Harris JM (1999) Carbon isotope fractionation between diet and bioapatite in ungulate mammals and implications for ecological and paleoecological studies. Oecologia 120: 347–363.",
    "chamberlain2006": "Chamberlain AT (2006) Demography in Archaeology. Cambridge University Press.",
    "chenery2012": "Chenery CA, Pashley V, Lamb AL, Sloane HJ, Evans JA (2012) The oxygen isotope relationship between the phosphate and structural carbonate fractions of human bioapatite. Rapid Communications in Mass Spectrometry 26: 309–319.",
    "coplen1983": "Coplen TB, Kendall C, Hopple J (1983) Comparison of stable isotope reference samples. Nature 302: 236–238.",
    "daux2008": "Daux V et al. (2008) Oxygen isotope fractionation between human phosphate and water revisited. Journal of Human Evolution 55: 1138–1147.",
    "deniro1985": "DeNiro MJ (1985) Postmortem preservation and alteration of in vivo bone collagen isotope ratios in relation to palaeodietary reconstruction. Nature 317: 806–809.",
    "efron1993": "Efron B, Tibshirani RJ (1993) An Introduction to the Bootstrap. Chapman & Hall.",
    "fernandes2014": "Fernandes R, Millard AR, Brabec M, Nadeau M-J, Grootes P (2014) Food reconstruction using isotopic transferred signals (FRUITS): a Bayesian model for diet reconstruction. PLoS ONE 9: e87436.",
    "fuller2006": "Fuller BT, Fuller JL, Harris DA, Hedges REM (2006) Detection of breastfeeding and weaning in modern human infants with carbon and nitrogen stable isotope ratios. American Journal of Physical Anthropology 129: 279–293.",
    "goodman1990": "Goodman AH, Rose JC (1990) Assessment of systemic physiological perturbations from dental enamel hypoplasias and associated histological structures. Yearbook of Physical Anthropology 33: 59–110.",
    "hurvich1989": "Hurvich CM, Tsai C-L (1989) Regression and time series model selection in small samples. Biometrika 76: 297–307.",
    "konigsberg1992": "Konigsberg LW, Frankenberg SR (1992) Estimation of age structure in anthropological demography. American Journal of Physical Anthropology 89: 235–256.",
    "lightfoot2016": "Lightfoot E, O'Connell TC (2016) On the use of biomineral oxygen isotope data to identify human migrants in the archaeological record. PLoS ONE 11: e0153850.",
    "moorrees1963": "Moorrees CFA, Fanning EA, Hunt EE (1963) Age variation of formation stages for ten permanent teeth. Journal of Dental Research 42: 1490–1502.",
    "payne1973": "Payne S (1973) Kill-off patterns in sheep and goats: the mandibles from Aşvan Kale. Anatolian Studies 23: 281–303.",
    "phillips2002": "Phillips DL, Koch PL (2002) Incorporating concentration dependence in stable isotope mixing models. Oecologia 130: 114–125.",
    "phillips2014": "Phillips DL, Inger R, Bearhop S, Jackson AL, Moore JW, Parnell AC, Semmens BX, Ward EJ (2014) Best practices for use of stable isotope mixing models in food-web studies. Canadian Journal of Zoology 92: 823–835.",
    "pollard2011": "Pollard AM, Pellegrini M, Lee-Thorp JA (2011) Technical note: some observations on the conversion of dental enamel δ18Op values to δ18Ow to determine human mobility. American Journal of Physical Anthropology 145: 499–504.",
    "price2002": "Price TD, Burton JH, Bentley RA (2002) The characterization of biologically available strontium isotope ratios for the study of prehistoric migration. Archaeometry 44: 117–135.",
    "reid2006": "Reid DJ, Dean MC (2006) Variation in modern human enamel formation times. Journal of Human Evolution 50: 329–346.",
    "siler1979": "Siler W (1979) A competing-risk model for animal mortality. Ecology 60: 750–757.",
    "towers2014": "Towers J, Gledhill A, Bond J, Montgomery J (2014) An investigation of cattle birth seasonality using δ13C and δ18O profiles within first molar enamel. Archaeometry 56 (S1): 208–236.",
    "tsutaya2013": "Tsutaya T, Yoneda M (2013) Quantitative reconstruction of weaning ages in archaeological human populations using bone collagen nitrogen isotope ratios and approximate Bayesian computation. PLoS ONE 8: e72327.",
    "tsutaya2020": "Tsutaya T (2020) Blurred time resolution of tooth dentin serial sections. American Journal of Physical Anthropology 173: 748–759.",
    "weanage": f"WeanAge {__version__}: estimating weaning age from δ15N in dentine and bone collagen. https://github.com/andymaehartley/WeanAge",
    "wood1992": "Wood JW, Milner GR, Harpending HC, Weiss KM (1992) The osteological paradox: problems of inferring prehistoric health from skeletal samples. Current Anthropology 33: 343–370.",
    "wright1998": "Wright LE, Schwarcz HP (1998) Stable carbon and oxygen isotopes in human tooth enamel: identifying breastfeeding and weaning in prehistory. American Journal of Physical Anthropology 106: 1–18.",
}

# Which placeholder areas (config.tbd_items) each calculation depends on.
PLACEHOLDER_AREAS = {
    "tooth": ("Tooth growth table", "Collagen QC", "Lab / method parameter"),
    "bone": ("Bone collagen turnover", "Bone model priors", "Collagen QC"),
    "dental": ("Dental age and hypoplasia",),
    "leh": ("Dental age and hypoplasia",),
    "mixing": ("Diet mixing",),
}
MODEL_NAMES = {"logistic": "logistic", "piecewise": "piecewise linear", "exponential": "exponential decay",
               "two_phase": "two-phase", "elbow": "elbow (WEAN)"}


def listing(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def first_upper(text):
    return text[:1].upper() + text[1:]


def counted(run, noun):
    n = run.get("n")
    return f"{n} {noun}" if n is not None else noun


def tooth(run):
    o = AnalysisOptions(**run.get("options", {}))
    q = o.qc
    tables = run.get("details", {}).get("growth_tables") or []
    text = (f"Weaning ages were estimated from serial dentine collagen δ15N ({counted(run, 'teeth or individuals')}). "
            f"Positions along each tooth were converted to ages with the growth table{'s' if len(tables) != 1 else ''} "
            f"{listing(tables) if tables else 'for each species and tooth'}. "
            f"Samples outside the collagen quality limits (atomic C:N {q.cn_min}–{q.cn_max}, DeNiro 1985; ≥ {q.pct_C_min}% C, "
            f"≥ {q.pct_N_min}% N, ≥ {q.collagen_yield_min}% yield) were {'excluded' if q.exclude_failed else 'flagged'}. "
            f"{first_upper(listing(MODEL_NAMES[m] for m in o.models))} curves were fitted to each individual and compared by "
            f"AICc (Hurvich & Tsai 1989), and milestone ages were averaged over the models with Akaike weights "
            f"(Burnham & Anderson 2002). Uncertainty was propagated with "
            + (f"{o.monte_carlo_draws} random draws from each fit's parameter covariance. " if o.uncertainty == "covariance"
               else f"{o.bootstrap_draws} bootstrap resamples (Efron & Tibshirani 1993). ") +
            f"The {o.reported_milestone} of the δ15N fall is reported (onset and completion at {o.transition_threshold:.0%} "
            f"and {1 - o.transition_threshold:.0%} of the fall); no age was reported where δ15N fell by less than "
            f"{o.min_weaning_drop_permil}‰, and ages beyond the sampled part of the tooth are given as bounds.")
    refs = ["deniro1985", "hurvich1989", "burnham2002"]
    if o.time_averaging:
        text += f" Each section was modelled as an average over its {o.increment_width_mm} mm height (Tsutaya 2020)."
        refs.append("tsutaya2020")
    if o.seasonal_term:
        text += f" A {o.season_period_months}-month seasonal term was included in the curves."
    if o.adult_baselines:
        text += (" The share of breast milk at each increment was estimated against the adult-female δ15N baseline, with a "
                 "nursing enrichment as in WARN (Tsutaya & Yoneda 2013) and about 1‰ in δ13C (Fuller et al. 2006).")
        refs += ["tsutaya2013", "fuller2006"]
    return text, refs


def bone(run):
    o = BoneOptions(**run.get("options", {}))
    text = (f"Weaning in {counted(run, 'young individuals')} was modelled from bone collagen δ15N against age at death "
            f"following WARN (Tsutaya & Yoneda 2013): a {o.weaning_form} change from milk to weaning food, bone collagen "
            "renewed at age-dependent turnover rates, and the start and end of weaning, the nursing enrichment and the "
            f"weaning-food δ15N estimated together by Markov chain Monte Carlo ({o.chains} chains, {o.warmup} warm-up and "
            f"{o.keep} kept iterations each).")
    return text, ["tsutaya2013"]


def enamel(run):
    o = EnamelOptions(**run.get("options", {}))
    text = (f"Sequential enamel δ18O ({counted(run, 'teeth')}) was fitted with a cosine to place each animal's season of "
            "birth (birth index x0/X; Balasse et al. 2012), and a rise in δ13C beyond the seasonal wave was taken as rumen "
            "development when supported by AICc (Towers et al. 2014). The share of C4 plants was estimated from enamel "
            f"formed after the rumen transition (enamel–diet spacing {o.enamel_diet_spacing_permil}‰, Cerling & Harris 1999; "
            f"C3 {o.c3_plants_d13C}‰, C4 {o.c4_plants_d13C}‰). Level shifts in 87Sr/86Sr of at least {o.sr_min_shift} were "
            f"sought by BIC (Bentley 2006). Calendar months assume the δ18O maximum in month {o.d18O_max_month:g}.")
    if o.mineralisation_length_mm:
        text += f" Amplitudes and widths were corrected for {o.mineralisation_length_mm} mm of mineralisation averaging."
    return text, ["balasse2012", "towers2014", "cerling1999", "bentley2006"]


def killoff(run):
    o = KilloffOptions(**run.get("options", {}))
    system = (f"the stage ages of {o.stage_source}" if o.stage_ages and o.stage_source
              else "stage ages entered by the user" if o.stage_ages else "Payne's (1973) stages")
    text = (f"Kill-off profiles were built from {counted(run, 'mandibles')} aged by tooth wear, using {system}; mandibles "
            "that could belong to two stages were shared between them as Payne (1973) did. Deaths and survivorship per "
            f"age class have 95% intervals from {o.bootstrap_draws} bootstrap resamples (Efron & Tibshirani 1993), and groups "
            f"were compared with {o.permutations} permutations.")
    return text, ["payne1973", "efron1993"]


def mixing(run):
    o = MixingOptions(**run.get("options", {}))
    names = [s.name for s in o.sources] if o.sources else ["the food groups in the settings"]
    concentration = any(s.conc_N or s.conc_C for s in o.sources or [])
    prior = any(s.prior != 1 for s in o.sources or [])
    text = (f"Diet was estimated for {counted(run, 'collagen samples')} with a Bayesian mixing model of {listing(names)} "
            f"(as in FRUITS, Fernandes et al. 2014), with {o.draws} draws from a "
            f"{'weighted' if prior else 'flat'} Dirichlet prior weighted by their likelihood")
    text += (", mixing each isotope in proportion to the element each food supplies (Phillips & Koch 2002)."
             if concentration else ".")
    text += (" With more food groups than isotopes + 1 the shares are not uniquely determined, so the 95% intervals are "
             "reported (Phillips et al. 2014).")
    return text, ["fernandes2014", "phillips2014"] + (["phillips2002"] if concentration else [])


def dental(run):
    o = DentalOptions(**run.get("options", {}))
    if o.method == "transition":
        how = ("by transition analysis: the probability of each tooth's stage at each age was combined over the teeth "
               f"({'treated as independent given age' if o.teeth == 'independent' else 'counted as one tooth'}), with a "
               "flat prior over age (Boldsen et al. 2002; Konigsberg & Frankenberg 1992)")
        refs = ["moorrees1963", "boldsen2002", "konigsberg1992"]
    else:
        how = "as the inverse-variance weighted mean of the midpoints of each tooth's stage"
        refs = ["moorrees1963"]
    return (f"Age at death of {counted(run, 'individuals')} was estimated from Moorrees et al. (1963) formation stages "
            f"{how}."), refs


def leh(run):
    LehOptions(**run.get("options", {}))
    return (f"The ages at which {counted(run, 'enamel hypoplasia defects')} formed were estimated from their height above "
            "the cemento-enamel junction, assuming even crown growth (Goodman & Rose 1990); enamel forms more slowly near "
            "the junction (Reid & Dean 2006), so these ages are approximate."), ["goodman1990", "reid2006"]


def lifetable(run):
    o = LifeTableOptions(**run.get("options", {}))
    text = (f"Life tables were built from the age-at-death ranges of {counted(run, 'skeletons')}, shared over age classes "
            "by overlap (Chamberlain 2006), with the juvenility index D5–14/D20+ (Bocquet-Appel & Masset 1977) and 95% "
            f"intervals from {o.bootstrap_draws} bootstrap resamples.")
    refs = ["chamberlain2006", "bocquet1977", "wood1992"]
    if o.siler:
        text += " A Siler (1979) hazard was fitted to the ranges by maximum likelihood."
        refs.append("siler1979")
    if o.expected_infant_share:
        text += f" Missing infant burials were corrected for by adding infant deaths to {o.expected_infant_share:.0%} of all deaths."
    text += " The results describe the burial sample, which may not represent the living population (Wood et al. 1992)."
    return text, refs


def mobility(run):
    o = MobilityOptions(**run.get("options", {}))
    has = {"d18O": True, "sr": True, "origins": bool(o.regions or o.origins_from_sites), **run.get("details", {})}
    parts, refs = [], []
    if has["d18O"]:
        parts.append(f"Enamel δ18O was converted to drinking water with the equations of Chenery et al. (2012; carbonate, "
                     f"after conversion to VSMOW, Coplen et al. 1983) and Daux et al. (2008; phosphate), with an SD of "
                     f"{o.drinking_water_sd}‰ (Pollard et al. 2011); first molars and deciduous teeth may carry a "
                     "breastfeeding signal in δ18O (Wright & Schwarcz 1998).")
        refs += ["chenery2012", "coplen1983", "daux2008", "pollard2011", "wright1998"]
    if has["sr"]:
        local = ("the range given" if o.local_sr_min is not None else
                 "baseline samples (mean ± 2 SD; Price et al. 2002) or, without them, Tukey fences (Lightfoot & O'Connell 2016)")
        parts.append(f"Enamel 87Sr/86Sr was compared with a local range from {local} (Bentley 2006).")
        refs += ["price2002", "lightfoot2016", "bentley2006"]
    if has["origins"]:
        parts.append("Possible origins of non-local individuals were ranked by their likelihood under each candidate place.")
    return f"Mobility was assessed for {counted(run, 'enamel samples')}. " + " ".join(parts), refs


WRITERS = {"tooth": tooth, "bone": bone, "enamel": enamel, "killoff": killoff, "mixing": mixing, "dental": dental,
           "leh": leh, "lifetable": lifetable, "mobility": mobility}


def write_methods(runs):
    """runs: {calculation: {"options": {...}, "n": count, "details": {...}}} for each calculation that was run."""
    unknown = [name for name in runs if name not in WRITERS]
    if unknown:
        raise ValueError(f"unknown calculation(s): {', '.join(unknown)}")
    paragraphs, cited = [f"Calculations were carried out in WeanAge {__version__}."], ["weanage"]
    for name in WRITERS:
        if name in runs:
            text, refs = WRITERS[name](runs[name])
            paragraphs.append(text)
            cited += [r for r in refs if r not in cited]
    areas = {area for name in runs for area in PLACEHOLDER_AREAS.get(name, ())}
    tables_used = set(runs.get("tooth", {}).get("details", {}).get("growth_tables") or [])

    def relevant(item):  # of the growth tables, only those the teeth actually used
        if item["area"] == "Tooth growth table" and tables_used:
            return item["label"] in tables_used
        return item["area"] in areas

    placeholders = [item for item in config.tbd_items() if relevant(item)]
    if placeholders:
        paragraphs.append(f"{len(placeholders)} values used were provisional (marked TBD-LAB in WeanAge): "
                          + "; ".join(item["label"] for item in placeholders) + ".")
    references = sorted((REFERENCES[r] for r in cited), key=str.lower)
    return {"paragraphs": paragraphs, "references": references, "placeholders": placeholders,
            "text": "\n\n".join(paragraphs) + "\n\nReferences\n\n" + "\n".join(references)}
