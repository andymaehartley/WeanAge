"""Age at death of children from the formation stages of their teeth.

Each tooth is scored in one of the Moorrees et al. (1963) stages, from crown initiation (Ci) to apex
closed (Ac). A tooth in a stage is between the age it reached that stage and the age it reaches the
next, so its age is taken as the middle of that span, with an SD from the span (uniform) and from
the spread between children (data/dental_stages.json). A tooth whose apex is closed only gives a
minimum age. The teeth of one child are combined by an inverse-variance weighted mean; because teeth
of one child develop together and are not independent, the combined SD is not narrowed by √n
(it is the SD of a typical single tooth). Teeth far from the combined age are flagged: they may be
mis-scored, or from another individual.

The bundled formation ages are placeholders until replaced by a published standard (e.g. AlQahtani
et al. 2010; Smith 1991), so the ages are illustrative.
"""

import math

from . import config
from .ingest import check_rows, column_lookup, match_columns
from .schema import MOORREES_STAGES, DentalOptions, DentalSample

ALIASES = {
    "specimen_id": ["individual", "individualid", "skeleton", "burial", "sampleid"],
    "stage": ["moorrees", "moorreesstage", "formationstage", "developmentstage"],
    "tooth": ["element"],
}
LOOKUP = column_lookup(DentalSample, ALIASES)


def ingest_dental_dataframe(df):
    df, issues = match_columns(df, LOOKUP, DentalSample)
    if df is None:
        return {"samples": [], "issues": issues, "individuals": []}
    samples, row_issues = check_rows(DentalSample, df.to_dict(orient="records"))
    counts: dict[str, int] = {}
    for s in samples:
        counts[s.specimen_id] = counts.get(s.specimen_id, 0) + 1
    return {"samples": samples, "issues": row_issues + issues,
            "individuals": [{"specimen_id": k, "n_teeth": n} for k, n in counts.items()]}


def stage_ages(tooth, table):
    """Age (months) at which the tooth reaches each Moorrees stage, from its four formation ages."""
    t = table["teeth"][tooth]
    crown = [t["initiation"] + (t["crown"] - t["initiation"]) * k / 5 for k in range(6)]  # Ci .. Crc
    root = [t["crown"] + (t["root"] - t["crown"]) * k for k in (0.05, 0.25, 0.5, 0.75, 1.0)]  # Ri .. Rc
    apex = [t["root"] + (t["apex"] - t["root"]) * k for k in (0.5, 1.0)]  # A1/2, Ac
    return dict(zip(MOORREES_STAGES, crown + root + apex))


def tooth_age(tooth, stage, table):
    """{estimate, sd} for a tooth in a stage, or {minimum} for a finished tooth."""
    ages = stage_ages(tooth, table)
    i = MOORREES_STAGES.index(stage)
    if i == len(MOORREES_STAGES) - 1:
        return {"minimum": ages[stage]}
    start, end = ages[stage], ages[MOORREES_STAGES[i + 1]]
    middle = (start + end) / 2
    spread = max(table["sd"]["fraction"] * abs(middle), table["sd"]["minimum_months"])
    return {"estimate": middle, "sd": math.sqrt((end - start) ** 2 / 12 + spread ** 2), "from": start, "to": end}


def estimate_individual(teeth, options, table):
    """Combine the teeth of one individual."""
    rows = [{"tooth": s.tooth, "stage": s.stage, **tooth_age(s.tooth, s.stage, table)} for s in teeth]
    first = teeth[0]
    out = {"specimen_id": first.specimen_id, "site": first.site, "species": first.species, "period": first.period,
           "teeth": rows, "warnings": [], "estimate_months": None, "sd_months": None, "age_min_months": None,
           "age_max_months": None}
    minimum = max((r["minimum"] for r in rows if "minimum" in r), default=None)
    bounded = [r for r in rows if "estimate" in r]
    if first.species != "human":
        out["warnings"].append("The formation ages are for human teeth")
    if not bounded:
        out["age_min_months"] = minimum
        out["warnings"].append(f"Every tooth scored is complete: at least {minimum / 12:.1f} years old")
        return out
    weights = [1 / r["sd"] ** 2 for r in bounded]
    estimate = sum(w * r["estimate"] for w, r in zip(weights, bounded)) / sum(weights)
    sd = math.sqrt(len(bounded) / sum(weights))  # a typical tooth's SD: teeth of one child are not independent
    for r in bounded:
        r["z"] = (r["estimate"] - estimate) / r["sd"]
        if abs(r["z"]) > options.discordance_z:
            out["warnings"].append(f"{r['tooth']} ({r['stage']}) suggests {r['estimate'] / 12:.1f} years, "
                                   f"{abs(r['z']):.1f} SD from the estimate: check its stage")
    if minimum is not None and estimate < minimum:
        out["warnings"].append(f"A complete tooth means at least {minimum / 12:.1f} years, older than the estimate")
    low = max(estimate - options.interval_z * sd, minimum if minimum is not None else -10.0)
    out.update(estimate_months=estimate, sd_months=sd, age_min_months=max(low, 0.0),
               age_max_months=max(estimate + options.interval_z * sd, 0.1))
    if estimate < 0:
        out["warnings"].append("The estimate is before birth: a foetal or perinatal individual")
    return out


def analyze_dental(samples, options=None, progress=None):
    options = options or DentalOptions()
    table = config.dental_stages()
    people: dict[str, list] = {}
    for s in samples:
        people.setdefault(s.specimen_id, []).append(s)
    results = []
    for i, teeth in enumerate(people.values()):
        results.append(estimate_individual(teeth, options, table))
        if progress:
            progress(i + 1, len(people))
    return {"results": results, "placeholder": bool(table.get("placeholder")), "stages": MOORREES_STAGES}
