"""When linear enamel hypoplasia (LEH) defects formed, and whether they line up with weaning.

Enamel grows from the cusp to the cemento-enamel junction (CEJ), so a defect's height on the crown
gives the age at which the disruption happened. As commonly done (Goodman & Rose 1990), the crown is
taken to form at an even rate on its surface:

    age = initiation + cuspal time + (1 − defect height / crown height) × (crown completion − initiation − cuspal time)

where the cuspal time is the enamel formed under the cusp before the surface layers show (Reid & Dean
2006). In fact formation slows towards the CEJ (Reid & Dean 2006), so even-rate ages are too young
near the cusp and too old near the CEJ; the formation ages are also placeholders
(data/dental_stages.json). Uncertainty comes from random draws of the formation ages (their SD as in
dental_age) and of the height measurement.

When the same individual has a tooth-calculation result, each defect is set against the weaning
interval (onset to completion of the δ15N fall) and any stress episodes found in the dentine.
"""

import numpy as np

from . import config
from .ingest import check_rows, column_lookup, match_columns
from .models import interval
from .schema import LehOptions, LehSample

ALIASES = {
    "specimen_id": ["individual", "individualid", "skeleton", "burial", "sampleid"],
    "defect_mm": ["defect", "defectheight", "heightfromcej", "distancefromcej", "cejdistance", "lehheight"],
    "crown_height_mm": ["crownheight", "unworncrownheight"],
    "defect_id": ["defectno", "leh", "lehid"],
    "tooth": ["element"],
}
LOOKUP = column_lookup(LehSample, ALIASES)


def ingest_leh_dataframe(df):
    df, issues = match_columns(df, LOOKUP, LehSample)
    if df is None:
        return {"samples": [], "issues": issues, "individuals": []}
    samples, row_issues = check_rows(LehSample, df.to_dict(orient="records"))
    counts: dict[str, int] = {}
    for s in samples:
        counts[s.specimen_id] = counts.get(s.specimen_id, 0) + 1
    return {"samples": samples, "issues": row_issues + issues,
            "individuals": [{"specimen_id": k, "n_defects": n} for k, n in counts.items()]}


def defect_age(sample, table, options, rng):
    t = table["teeth"][sample.tooth]
    spread = lambda age: max(table["sd"]["fraction"] * abs(age), table["sd"]["minimum_months"])  # noqa: E731
    n = options.draws
    start = rng.normal(t["initiation"], spread(t["initiation"]), n)
    end = rng.normal(t["crown"], spread(t["crown"]), n)
    cuspal = t.get("cuspal_months") or 0.0
    height = np.clip(rng.normal(sample.defect_mm, options.measurement_sd_mm, n), 0, sample.crown_height_mm)
    share = 1 - height / sample.crown_height_mm  # share of the visible crown formed before the defect
    draws = start + cuspal + share * np.clip(end - start - cuspal, 1, None)
    exact = t["initiation"] + cuspal + (1 - sample.defect_mm / sample.crown_height_mm) * (t["crown"] - t["initiation"] - cuspal)
    low, high = interval(draws)
    return {"estimate": float(exact), "ci_low": low, "ci_high": high}


def overlaps(a, b):
    return a[0] <= b[1] and b[0] <= a[1]


def against_dentine(age, context):
    """Where the defect falls against the weaning interval and stress episodes of the same individual."""
    if context is None:
        return None
    span = (age["ci_low"] if age["ci_low"] is not None else age["estimate"],
            age["ci_high"] if age["ci_high"] is not None else age["estimate"])
    weaning = None
    if context.onset is not None and context.completion is not None:
        weaning = ("during" if overlaps(span, (context.onset, context.completion))
                   else "before" if span[1] < context.onset else "after")
    stress = [list(e) for e in context.stress if overlaps(span, e)]
    return {"weaning": weaning, "stress_episodes": stress}


def analyze_leh(samples, options=None, progress=None):
    options = options or LehOptions()
    table = config.dental_stages()
    rng = np.random.default_rng(options.random_seed)
    results = []
    for i, s in enumerate(samples):
        age = defect_age(s, table, options, rng)
        results.append({"specimen_id": s.specimen_id, "site": s.site, "species": s.species, "period": s.period,
                        "tooth": s.tooth, "defect_id": s.defect_id, "defect_mm": s.defect_mm,
                        "crown_height_mm": s.crown_height_mm, "age": age,
                        "dentine": against_dentine(age, options.dentine.get(s.specimen_id))})
        if progress:
            progress(i + 1, len(samples))
    people: dict[str, list] = {}
    for r in results:
        people.setdefault(r["specimen_id"], []).append(r)
    individuals = []
    for sid, defects in people.items():
        context = options.dentine.get(sid)
        individuals.append({"specimen_id": sid, "site": defects[0]["site"], "n_defects": len(defects),
                            "ages": sorted(d["age"]["estimate"] for d in defects),
                            "weaning": context.model_dump() if context else None,
                            "during_weaning": sum(bool(d["dentine"] and d["dentine"]["weaning"] == "during") for d in defects),
                            "with_stress": sum(bool(d["dentine"] and d["dentine"]["stress_episodes"]) for d in defects)})
    linked = [d for d in results if d["dentine"] and d["dentine"]["weaning"]]
    warnings = []
    if not options.dentine:
        warnings.append("No tooth-calculation results for these individuals: run the tooth calculation with the same "
                        "specimen IDs to set the defects against weaning")
    if any(s.species != "human" for s in samples):
        warnings.append("The formation ages are for human teeth")
    return {"results": results, "individuals": individuals, "warnings": warnings,
            "share_during_weaning": (sum(d["dentine"]["weaning"] == "during" for d in linked) / len(linked)) if linked else None,
            "placeholder": bool(table.get("placeholder"))}
