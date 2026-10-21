"""Weaning age from the bone collagen δ15N of many animals that died at different ages.

This follows WARN (Tsutaya & Yoneda 2013), which was built for human skeletons, adapted for
animal bones. A tooth records one animal's own childhood; bone cannot, because its collagen is
replaced throughout life. So each young animal's δ15N at death is one point, and the model asks
which weaning ages would produce the pattern of all the points against age at death.

The model (equation numbers from Tsutaya & Yoneda 2013):
1. Diet (Eq. 7-8, after Millard 2000). Collagen made from milk is E ‰ above the mother (the
   adult-female mean); collagen made from weaning food has δ15N W. The share of non-milk food
   p(t) is 0 before weaning starts (t1), 1 after it ends (t2), and in between rises as
   ((t - t1) / (t2 - t1))², slowly at first ("parabolic", WARN's default). "linear" and
   "reverse" (fast at first) are WARN's other forms; its "sigmoid" form is not included.
2. Bone (Eq. 9-10). At birth the bone matches the mother. In each step a share of the bone
   collagen is newly made from the current diet: high while the skeleton grows, lower later
   (the turnover table). So bone δ15N follows the diet with a delay.
3. Fit. t1, t2, E and W, the mothers' mean and the scatter between animals (σ) are estimated
   together. Ages at death given as a range (e.g. from tooth wear) are sampled within the range,
   so their uncertainty carries into the weaning ages.

What the ages mean: δ15N falls when suckling stops, not as the amount of milk slowly drops, so
t2 is best read as the end of suckling (Balasse et al. 2001; Díez-Canseco & Tornero 2026 for
sheep). Forage rich in protein can blur this.

Differences from WARN: WARN fits by approximate Bayesian computation (sequential Monte Carlo);
here the same model is fitted with a likelihood-based sampler (Metropolis with differential-
evolution moves). WARN treats the mothers' mean as known; here it is estimated, with its
standard error from the adult females. WARN assumes newborn bone equals the mothers' mean; here
the newborn offset is estimated with a species prior, because foetal tissue is enriched over the
mother in other mammals (bone_priors.json gives the sources). Priors for the nursing enrichment
also come per species from bone_priors.json (WARN's 1.9 ± 0.9‰ is for humans). WARN's priors for t1 and t2 are normal in years for
humans; here they are flat between 0 and the latest possible end of weaning. Turnover comes from
bone_turnover.json: WARN's human rib values are included, livestock values are placeholders
(TBD-LAB). WARN is meant for fast-turnover bone such as ribs; the same applies here.
"""

import math

import numpy as np
from scipy import stats

from . import config
from .inference import middle95, split_rhat
from .ingest import is_blank, issue, squash
from .qc import passes_qc, qc_flags
from .schema import BoneOptions, BoneSample

STEP = 0.25  # months per step of the bone simulation
MIN_YOUNG = 10  # fewer non-adults than this rarely pin down a weaning age
PARAMS = ["t1", "t2", "enrichment", "weaning_food", "female_mean", "log_sigma", "newborn_offset"]


# ───────────── reading bone data ─────────────
ALIASES = {
    "specimen_id": ["specimen", "specimenid", "sampleid", "individual", "individualid", "animal", "animalid"],
    "site": ["sitename"],
    "species": ["taxon"],
    "element": ["bone", "skeletalelement"],
    "age_class": ["ageclass", "agegroup", "adult", "agecategory"],
    "sex": ["sexestimate"],
    "age_months": ["age", "ageatdeath", "ageatdeathmonths", "agemo", "ageestimatemonths"],
    "age_min_months": ["agemin", "minage", "minagemonths", "ageminmonths"],
    "age_max_months": ["agemax", "maxage", "maxagemonths", "agemaxmonths"],
    "d15N": ["δ15n", "delta15n", "d15nair"],
    "d13C": ["δ13c", "delta13c", "d13cvpdb"],
    "pct_N": ["n", "percentn"],
    "pct_C": ["c", "percentc"],
    "cn_ratio": ["cn", "atomiccn"],
    "collagen_yield_pct": ["collagenyield", "yield", "yieldpct"],
    "period": ["phase"],
    "notes": ["comment"],
}
LOOKUP = {squash(field): field for field in BoneSample.model_fields}
for field, spellings in ALIASES.items():
    for spelling in spellings:
        LOOKUP[squash(spelling)] = field


def ingest_bone_dataframe(df):
    """Check a table of bone samples; returns samples, problems and a summary per group."""
    from pydantic import ValidationError

    renames, unknown = {}, []
    for column in df.columns:
        field = LOOKUP.get(squash(column))
        if field and field not in renames.values():
            renames[column] = field
        else:
            unknown.append(str(column))
    df = df.rename(columns=renames)[list(renames.values())]
    missing = [f for f in ["specimen_id", "site", "species", "d15N"] if f not in df]
    if missing:
        return {"samples": [], "issues": [issue(f"Missing required column(s): {', '.join(missing)}")],
                "groups": [], "unrecognised_columns": unknown}
    for column in ["specimen_id", "site", "species", "element", "period", "notes", "sex", "age_class"]:
        if column in df:  # IDs like 001 must stay text
            df[column] = df[column].map(lambda v: None if is_blank(v) else str(v))
    samples, issues = [], []
    for row_number, raw in enumerate(df.to_dict(orient="records"), start=1):
        row = {key: (None if is_blank(value) else value) for key, value in raw.items()}
        try:
            samples.append(BoneSample(**row))
        except ValidationError as err:
            for e in err.errors():
                issues.append(issue(e["msg"].removeprefix("Value error, "), row_number,
                                    ".".join(str(p) for p in e["loc"]) or None))
    if unknown:
        issues.append(issue(f"Ignored unrecognised column(s): {', '.join(unknown)}", severity="warning"))
    issues += bone_checks(samples)
    return {"samples": samples, "issues": issues, "groups": summarise(samples), "unrecognised_columns": unknown}


def group_key(s):
    return (s.site, s.species, s.period)


def group_name(key):
    site, species, period = key
    return f"{site} · {species}" + (f" · {period}" if period else "")


def summarise(samples):
    groups: dict[tuple, list[BoneSample]] = {}
    for s in samples:
        groups.setdefault(group_key(s), []).append(s)
    return [{"group": group_name(key), "site": key[0], "species": key[1], "period": key[2],
             "n_young": sum(not s.is_adult for s in rows),
             "n_adult_females": sum(s.is_adult and s.sex == "f" for s in rows),
             "n_adults": sum(s.is_adult for s in rows),
             "has_turnover": config.find_turnover_table(key[1]) is not None}
            for key, rows in groups.items()]


def bone_checks(samples):
    issues = []
    ids = [s.specimen_id for s in samples]
    for repeated in sorted({i for i in ids if ids.count(i) > 1}):
        issues.append(issue(f"Specimen {repeated} appears more than once; each row is treated as a separate animal",
                            field="specimen_id", severity="warning"))
    for g in summarise(samples):
        if g["n_young"] < MIN_YOUNG:
            issues.append(issue(f"{g['group']}: {g['n_young']} non-adults; at least {MIN_YOUNG}, spread from birth to "
                                "past weaning, are needed for a useful estimate", severity="warning"))
        if not g["n_adult_females"]:
            issues.append(issue(f"{g['group']}: no adult females (age_class adult, sex F); "
                                + ("all adults will stand in for the mothers" if g["n_adults"] else
                                   "enter the mothers' δ15N in Settings"), severity="warning"))
        if not g["has_turnover"]:
            issues.append(issue(f"{g['group']}: no bone turnover table for {g['species']}", field="species"))
    return issues


# ───────────── the model ─────────────
def milk_share(t, t1, t2, form="parabolic"):
    """Share of the diet that is still milk: 1 before weaning starts, 0 after it ends (WARN Eq. 8)."""
    x = np.clip((t - t1) / np.maximum(t2 - t1, 1e-6), 0, 1)  # how far through weaning
    food = {"linear": x, "parabolic": x ** 2, "reverse": 1 - (1 - x) ** 2}[form]
    return 1 - food


def renewal(table, grid):
    """Share of the bone collagen newly made in each STEP of the grid."""
    per_month = np.interp(grid, table.ages_months, table.renewed_per_month)
    return 1 - (1 - per_month) ** STEP


def bone_curve(grid, renewed, t1, t2, enrichment, weaning_food, female_mean, form="parabolic", newborn_offset=0.0):
    """Bone δ15N at each age of the grid, and the δ15N of collagen made from the diet at that age.

    Each step: bone = (1 - renewed) × bone + renewed × diet, starting from the newborn's value:
    the mothers' mean plus the newborn offset (0 in WARN, which assumes newborns equal their mothers).
    Written with cumulative sums so the whole curve is computed at once. The parameters may be
    columns (one row per chain) to compute several curves together.
    """
    milk = milk_share(grid, t1, t2, form)
    diet = milk * (female_mean + enrichment) + (1 - milk) * weaning_food  # WARN Eq. 7
    kept = np.concatenate([[1.0], np.cumprod(1 - renewed[:-1])])  # share of birth collagen still there
    steps = (renewed * diet)[..., :-1] / kept[1:]
    added = np.concatenate([np.zeros(steps.shape[:-1] + (1,)), np.cumsum(steps, axis=-1)], axis=-1)
    return kept * (female_mean + newborn_offset + added), diet


def curves_for(fit, p):
    """Bone and diet curves for parameter rows p (one row per chain or draw)."""
    column = lambda i: p[:, i:i + 1]  # noqa: E731
    return bone_curve(fit.grid, fit.renewed, *(column(i) for i in range(5)), fit.options.weaning_form, column(6))


class BoneFit:
    """Everything one group's sampler needs: the data, the priors and the age grid."""

    def __init__(self, young, mothers, table, options):
        self.y = np.array([s.d15N for s in young])
        self.low = np.array([s.age_min_months for s in young])
        self.high = np.array([s.age_max_months for s in young])
        self.options = options
        self.f_mean, self.f_se = mothers
        end = max(options.max_weaning_age_months * 1.5, float(self.high.max()) + 1)
        self.grid = np.arange(0, end + STEP, STEP)
        self.renewed = renewal(table, self.grid)

    def curves(self, p):
        """Bone δ15N on the grid for each row (chain) of parameters."""
        return curves_for(self, p)[0]

    def log_prior(self, p):
        """One value per chain; -inf where a parameter is outside its allowed range."""
        t1, t2, e, w, f, log_sigma, b = p.T
        o = self.options
        allowed = (0 <= t1) & (t1 <= t2) & (t2 <= o.max_weaning_age_months) & (e >= 0) & (np.abs(log_sigma + 1) < 4)
        value = (-0.5 * ((e - o.enrichment_prior_mean) / o.enrichment_prior_sd) ** 2
                 - 0.5 * ((w - self.f_mean) / o.weaning_food_prior_sd) ** 2
                 - 0.5 * ((f - self.f_mean) / self.f_se) ** 2
                 - 0.5 * ((b - o.newborn_offset_mean) / o.newborn_offset_sd) ** 2
                 - 0.5 * np.exp(2 * log_sigma) + log_sigma)  # half-normal(1) on σ, sampled as log σ
        return np.where(allowed, value, -np.inf)

    def places(self, ages):
        """Where each age falls on the evenly spaced grid: the point to its left, and how far on."""
        place = np.clip(ages / STEP, 0, len(self.grid) - 1.000001)
        left = place.astype(int)
        return left, place - left

    def pointwise(self, p, bone, places):
        """Log-likelihood of each animal (rows: chains, columns: animals)."""
        left, share = places
        rows = np.arange(len(bone))[:, None]
        predicted = (1 - share) * bone[rows, left] + share * bone[rows, left + 1]
        return -0.5 * ((self.y - predicted) / np.exp(p[:, 5:6])) ** 2 - p[:, 5:6]


def run_chains(fit, rng, chains, warmup, keep):
    """Metropolis sampler, all chains at once. Each step tries a new value for one parameter at a time,
    then t1 and t2 shifted together (on every fifth step only), then a jump along the difference between
    two other chains (which follows the links between parameters: differential evolution, ter Braak
    2006), then each animal's age within its range."""
    o = fit.options
    top = o.max_weaning_age_months
    p = np.column_stack([rng.uniform(0.05, 0.3, chains) * top, rng.uniform(0.4, 0.7, chains) * top,
                         np.full(chains, o.enrichment_prior_mean), np.full(chains, fit.f_mean),
                         np.full(chains, fit.f_mean), np.full(chains, math.log(0.5)),
                         np.full(chains, o.newborn_offset_mean)])
    ages = np.tile((fit.low + fit.high) / 2, (chains, 1))
    uncertain = fit.high > fit.low
    scale = np.array([top / 10, top / 10, 0.3, 0.3, max(fit.f_se, 0.05), 0.2, 0.3, top / 20])  # last: the joint shift
    accepted = np.zeros(len(scale))
    bone = fit.curves(p)
    where = fit.places(ages)
    current = fit.log_prior(p) + fit.pointwise(p, bone, where).sum(1)
    halves = [np.arange(chains)[: chains // 2], np.arange(chains)[chains // 2:]]
    draws = np.empty((chains, keep, len(PARAMS)))
    for step in range(warmup + keep):
        for i in range(len(scale) if step % 5 == 0 else 0):  # the one-at-a-time sweep on every fifth step
            proposal = p.copy()
            if i < len(PARAMS):
                proposal[:, i] += rng.normal(0, scale[i], chains)
            else:
                proposal[:, :2] += rng.normal(0, scale[i], (chains, 1))
            prior = fit.log_prior(proposal)
            ok = np.isfinite(prior)
            new_bone = fit.curves(proposal)
            new = np.where(ok, prior + fit.pointwise(proposal, new_bone, where).sum(1), -np.inf)
            move = np.log(rng.uniform(size=chains)) < new - current
            p[move], bone[move], current[move] = proposal[move], new_bone[move], new[move]
            accepted[i] += move.mean()
        for mine, others in (halves, halves[::-1]):  # each half jumps using two chains of the other half
            first = rng.integers(len(others), size=len(mine))
            a = others[first]
            b = others[(first + 1 + rng.integers(len(others) - 1, size=len(mine))) % len(others)]
            size = 1.0 if step % 10 == 9 else 2.38 / math.sqrt(2 * len(PARAMS))  # sometimes a full jump between modes
            proposal = p.copy()
            proposal[mine] += size * (p[a] - p[b]) + rng.normal(0, 1e-3, (len(mine), len(PARAMS)))
            prior = fit.log_prior(proposal[mine])
            new_bone = fit.curves(proposal[mine])
            mine_where = (where[0][mine], where[1][mine])
            new = np.where(np.isfinite(prior), prior + fit.pointwise(proposal[mine], new_bone, mine_where).sum(1), -np.inf)
            move = np.log(rng.uniform(size=len(mine))) < new - current[mine]
            p[mine[move]], bone[mine[move]], current[mine[move]] = proposal[mine][move], new_bone[move], new[move]
        if uncertain.any():  # each animal's age within its range; animals are independent given the curve
            proposed = np.where(uncertain, rng.uniform(fit.low, fit.high, ages.shape), ages)
            gain = fit.pointwise(p, bone, fit.places(proposed)) - fit.pointwise(p, bone, where)
            ages = np.where(np.log(rng.uniform(size=ages.shape)) < gain, proposed, ages)
            where = fit.places(ages)
            current = fit.log_prior(p) + fit.pointwise(p, bone, where).sum(1)
        if step < warmup and step % 250 == 249:  # tune step sizes towards ~35 % acceptance (50 sweeps)
            scale *= np.exp(np.clip(accepted / 50 - 0.35, -0.5, 0.5))
            accepted[:] = 0
        if step >= warmup:
            draws[:, step - warmup] = p
    return draws


def summary(values):
    low, high = middle95(values)
    return {"estimate": float(np.median(values)), "ci_low": low, "ci_high": high}


def fit_group(young, mothers, table, options, rng):
    fit = BoneFit(young, mothers, table, options)
    chains = run_chains(fit, rng, options.chains, options.warmup, options.keep)
    flat = chains.reshape(-1, len(PARAMS))
    t1, t2 = flat[:, 0], flat[:, 1]
    estimates = {
        "onset": summary(t1), "midpoint": summary((t1 + t2) / 2), "completion": summary(t2),
        "enrichment_permil": summary(flat[:, 2]), "weaning_food_d15N": summary(flat[:, 3]),
        "female_mean_d15N": summary(flat[:, 4]), "sigma_permil": summary(np.exp(flat[:, 5])),
        "newborn_offset_permil": summary(flat[:, 6]),
    }
    rhat = max(split_rhat(chains[:, :, i]) for i in range(len(PARAMS)))
    # Curves for the chart: the median and 95 % band of bone δ15N, and the median diet.
    picks = flat[rng.choice(len(flat), min(300, len(flat)), replace=False)]
    bones, diets = curves_for(fit, picks)
    shown = fit.grid <= max(float(fit.high.max()), options.max_weaning_age_months) + STEP
    every = max(1, int(shown.sum()) // 200)
    pick = lambda values: values[shown][::every].round(3).tolist()  # noqa: E731
    curve = {"age": pick(fit.grid), "bone": pick(np.median(bones, 0)),
             "bone_low": pick(np.percentile(bones, 2.5, 0)), "bone_high": pick(np.percentile(bones, 97.5, 0)),
             "diet": pick(np.median(diets, 0))}
    return estimates, rhat, curve


def group_warnings(estimates, rhat, young, options, table, mothers_note, check, prior_entry):
    warnings = []
    if table.placeholder:
        warnings.append("Bone turnover uses a PLACEHOLDER table (TBD-LAB); estimates are illustrative only")
    if prior_entry.get("placeholder"):
        warnings.append("Nursing enrichment and newborn priors are PLACEHOLDER values for this species (TBD-LAB)")
    if check["p_value"] is None:
        warnings.append("Too few young animals or adults to test for a nursing signal")
    elif check["p_value"] >= 0.05:
        warnings.append(f"The youngest third of the young are not clearly above the mothers "
                        f"({check['difference_permil']:+.2f}‰, p = {check['p_value']:.2f}): the data may hold no nursing "
                        "signal, and the model fits one anyway (Reynard & Tuross 2015)")
    if mothers_note:
        warnings.append(mothers_note)
    if rhat > 1.1:
        warnings.append(f"The sampler's chains disagree (R̂ = {rhat:.2f}); the estimates are not reliable")
    if len(young) < MIN_YOUNG:
        warnings.append(f"Only {len(young)} non-adults; WARN-type estimates need many animals spread from birth "
                        "to past weaning")
    completion = estimates["completion"]
    ages = [s.age_months for s in young]
    if not any(a < completion["estimate"] for a in ages):
        warnings.append("No non-adult died before the estimated end of suckling, so the nursing level is not observed")
    if not any(a > completion["estimate"] for a in ages):
        warnings.append("No non-adult died after the estimated end of suckling; the completion age is an extrapolation")
    if completion["ci_high"] - completion["ci_low"] > 0.8 * options.max_weaning_age_months:
        warnings.append("The completion interval covers most of the allowed range: the data barely constrain it, "
                        "so the result mostly reflects the prior")
    e = estimates["enrichment_permil"]["estimate"]
    if e < 1:
        warnings.append(f"Nursing enrichment of {e:.1f}‰ is small: little or no suckling signal")
    return warnings


def priors_for(species, options):
    """The options with any blank prior filled in from the species' entry in bone_priors.json."""
    entry = config.species_priors(species)
    filled = {field: entry[key] for field, key in config.PRIOR_FIELDS.items() if getattr(options, field) is None}
    return options.model_copy(update=filled), entry


def nursing_check(young, mothers_values, options):
    """Are the youngest animals clearly above their mothers?

    Bone collagen δ15N of the very young is usually raised above the adult mean, but whether a
    dataset holds enough of a signal to date weaning varies (Reynard & Tuross 2015). WARN-type
    models fit something regardless (Tsutaya & Yoneda 2013), so this is tested first: a one-sided
    Welch t-test of the youngest third of the young against the mothers.
    """
    youngest_first = sorted(young, key=lambda s: s.age_months)
    early = [s.d15N for s in youngest_first[: max(3, len(young) // 3)]]  # the youngest third
    if len(young) < 3 or len(mothers_values) < 2:
        return {"n_young": len(early), "difference_permil": None, "p_value": None}
    test = stats.ttest_ind(early, mothers_values, equal_var=False, alternative="greater")
    return {"n_young": len(early), "difference_permil": float(np.mean(early) - np.mean(mothers_values)),
            "p_value": float(test.pvalue)}


def mothers_for(rows, options):
    """Mean δ15N of the mothers and its uncertainty, with a note on where it came from."""
    females = [s.d15N for s in rows if s.is_adult and s.sex == "f"]
    adults = [s.d15N for s in rows if s.is_adult]
    if len(females) >= 2:
        return (float(np.mean(females)), max(float(np.std(females, ddof=1)), 0.1) / math.sqrt(len(females))), None
    if len(adults) >= 2:
        return ((float(np.mean(adults)), max(float(np.std(adults, ddof=1)), 0.1) / math.sqrt(len(adults))),
                f"No adult females: all {len(adults)} adults stand in for the mothers")
    if options.female_mean is not None:
        return (options.female_mean, options.female_sd), "Mothers' δ15N taken from Settings"
    return None, None


def analyze_bones(samples: list[BoneSample], options: BoneOptions | None = None, progress=None):
    """Fit the bone model to each site × species (× period) group."""
    options = options or BoneOptions()
    groups: dict[tuple, list[BoneSample]] = {}
    for s in samples:
        groups.setdefault(group_key(s), []).append(s)
    rng = np.random.default_rng(options.random_seed)
    results = []
    for done, (key, rows) in enumerate(groups.items()):
        site, species, period = key
        group_options, prior_entry = priors_for(species, options)
        table = config.find_turnover_table(species, options.turnover_tables)
        points, young = [], []
        for s in rows:
            flags = qc_flags(s, options.qc)
            used = passes_qc(flags) or not options.qc.exclude_failed
            role = ("adult female" if s.sex == "f" else "adult") if s.is_adult else "non-adult"
            points.append({"specimen_id": s.specimen_id, "role": role, "age_months": s.age_months,
                           "age_min": s.age_min_months, "age_max": s.age_max_months, "d15N": s.d15N,
                           "d13C": s.d13C, "qc_flags": flags, "used_in_fit": used})
            if used and not s.is_adult:
                young.append(s)
        used_rows = [s for s, p in zip(rows, points) if p["used_in_fit"]]
        mothers, note = mothers_for(used_rows, group_options)
        females = [s.d15N for s in used_rows if s.is_adult and s.sex == "f"]
        check = nursing_check(young, females or [s.d15N for s in used_rows if s.is_adult], group_options)
        result = {"group": group_name(key), "site": site, "species": species, "period": period,
                  "points": points, "n_young": len(young), "turnover": table.label if table else None,
                  "turnover_placeholder": bool(table and table.placeholder), "estimates": None, "rhat": None,
                  "curve": None, "warnings": [], "message": "", "nursing_check": check,
                  "priors": {field: getattr(group_options, field) for field in config.PRIOR_FIELDS},
                  "priors_source": prior_entry.get("source", ""), "priors_placeholder": prior_entry.get("placeholder", False)}
        excluded = sum(not p["used_in_fit"] for p in points)
        if excluded:
            result["warnings"].append(f"{excluded} sample{'s' if excluded > 1 else ''} failed collagen QC and "
                                      f"{'were' if excluded > 1 else 'was'} left out")
        if table is None:
            result["message"] = f"No bone turnover table for {species}"
        elif mothers is None:
            result["message"] = "No adults to stand in for the mothers: enter the mothers' δ15N in Settings"
        elif len(young) < 3:
            result["message"] = f"Only {len(young)} usable non-adults; at least 3 are needed to fit anything"
        else:
            estimates, rhat, curve = fit_group(young, mothers, table, group_options, rng)
            result.update(estimates=estimates, rhat=rhat, curve=curve,
                          female_mean_data=mothers[0])
            result["warnings"] += group_warnings(estimates, rhat, young, group_options, table, note, check,
                                                 prior_entry)
        results.append(result)
        if progress:
            progress(done + 1, len(groups))
    return results
