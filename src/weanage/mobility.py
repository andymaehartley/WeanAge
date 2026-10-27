"""Who grew up elsewhere: enamel δ18O as drinking water, and 87Sr/86Sr against the local range.

Oxygen. Enamel δ18O follows the water drunk while the tooth formed. Carbonate values (‰ VPDB) are put
on the VSMOW scale (δ18O_VSMOW = 1.03091·δ18O_VPDB + 30.91; Coplen et al. 1983) and converted to
drinking water with δ18O_dw = 1.590·δ18O_c − 48.634 (Chenery et al. 2012); phosphate values (‰ VSMOW)
with δ18O_dw = 1.54·δ18O_p − 33.72 (Daux et al. 2008), the equation Chenery's combines with their
carbonate-phosphate relation. The prediction error of such conversions is large (Pollard et al.
2011), so each value carries an SD (default 1‰).

Strontium. 87Sr/86Sr follows the bioavailable strontium where the person ate as a child (Bentley 2006).
The local range is set in Settings, or taken as the mean ± 2 SD of baseline samples (role = baseline,
e.g. fauna) from the same site (Price et al. 2002).

Without a local range, values are compared with the rest of the site's people using Tukey fences
(outside 1.5 × the interquartile range), which Lightfoot & O'Connell (2016) prefer to ± 2 SD; this
finds only the most unusual people and needs at least 8 of them.

First molars and deciduous teeth form partly while the child is breastfed, and breast milk is richer in
18O than the water the mother drinks, so their δ18O can be raised (Wright & Schwarcz 1998).
"""

import numpy as np

from .ingest import check_rows, column_lookup, match_columns
from .schema import MobilityOptions, MobilitySample

ALIASES = {
    "specimen_id": ["individual", "individualid", "skeleton", "burial", "sampleid"],
    "d18O": ["δ18o", "delta18o", "d18ovpdb", "d18ocarbonate", "d18ophosphate", "d18ovsmow"],
    "d18O_material": ["material", "d18omaterial", "fraction"],
    "sr87_86": ["87sr86sr", "sr8786", "srratio", "sr"],
    "role": ["type", "sampletype"],
    "tooth": ["element"],
}
LOOKUP = column_lookup(MobilitySample, ALIASES)
MIN_FOR_FENCES = 8
EARLY_TEETH = {"m1", "di1", "di2", "dc", "dm1", "dm2"}


def ingest_mobility_dataframe(df):
    df, issues = match_columns(df, LOOKUP, MobilitySample)
    if df is None:
        return {"samples": [], "issues": issues, "sites": []}
    samples, row_issues = check_rows(MobilitySample, df.to_dict(orient="records"))
    sites: dict[str, list] = {}
    for s in samples:
        sites.setdefault(s.site, [0, 0])[s.role == "baseline"] += 1
    return {"samples": samples, "issues": row_issues + issues,
            "sites": [{"site": k, "n_samples": v[0], "n_baseline": v[1]} for k, v in sites.items()]}


def drinking_water(sample):
    if sample.d18O is None:
        return None
    if sample.d18O_material == "phosphate":
        return 1.54 * sample.d18O - 33.72
    return 1.590 * (1.03091 * sample.d18O + 30.91) - 48.634


def fences(values):
    q1, q3 = np.percentile(values, [25, 75])
    return float(q1 - 1.5 * (q3 - q1)), float(q3 + 1.5 * (q3 - q1))


def classify(value, low, high, sd=0.0):
    """'local' if the value (± 1.96 SD) can fall in the range, 'non-local' if it cannot."""
    if value is None or low is None:
        return None
    return "local" if value + 1.96 * sd >= low and value - 1.96 * sd <= high else "non-local"


def analyze_site(site, rows, options):
    people = [r for r in rows if r.role == "sample"]
    baseline = [r.sr87_86 for r in rows if r.role == "baseline" and r.sr87_86 is not None]
    out = {"site": site, "n": len(people), "warnings": []}
    # Strontium: Settings, then baseline samples, then Tukey fences among the people.
    if options.local_sr_min is not None and options.local_sr_max is not None:
        sr_range, sr_from = (options.local_sr_min, options.local_sr_max), "settings"
    elif len(baseline) >= 3:
        m, s = float(np.mean(baseline)), float(np.std(baseline, ddof=1))
        sr_range, sr_from = (m - options.baseline_sd_multiplier * s, m + options.baseline_sd_multiplier * s), f"{len(baseline)} baseline samples"
    else:
        values = [p.sr87_86 for p in people if p.sr87_86 is not None]
        sr_range, sr_from = (fences(values), "Tukey fences among the people") if len(values) >= MIN_FOR_FENCES else (None, None)
    water = {p.specimen_id: drinking_water(p) for p in people}
    if options.local_d18O_dw_min is not None and options.local_d18O_dw_max is not None:
        o_range, o_from = (options.local_d18O_dw_min, options.local_d18O_dw_max), "settings"
    else:
        values = [v for v in water.values() if v is not None]
        o_range, o_from = (fences(values), "Tukey fences among the people") if len(values) >= MIN_FOR_FENCES else (None, None)
    out.update(sr_range=sr_range, sr_range_from=sr_from, d18O_dw_range=o_range, d18O_dw_range_from=o_from)
    if sr_range is None and any(p.sr87_86 is not None for p in people):
        out["warnings"].append(f"{site}: no local strontium range (give one in Settings, add baseline samples, or "
                               f"measure at least {MIN_FOR_FENCES} people)")
    results = []
    for p in people:
        dw = water[p.specimen_id]
        sr_status = classify(p.sr87_86, *(sr_range or (None, None)))
        o_status = classify(dw, *(o_range or (None, None)), sd=options.drinking_water_sd)
        notes = []
        if p.tooth and p.tooth.lower().replace(" ", "") in EARLY_TEETH and dw is not None:
            notes.append("formed partly while breastfed: δ18O may be raised (Wright & Schwarcz 1998)")
        results.append({"specimen_id": p.specimen_id, "site": site, "species": p.species, "period": p.period,
                        "tooth": p.tooth, "d18O": p.d18O, "d18O_material": p.d18O_material, "sr87_86": p.sr87_86,
                        "d18O_dw": None if dw is None else {"estimate": dw, "ci_low": dw - 1.96 * options.drinking_water_sd,
                                                            "ci_high": dw + 1.96 * options.drinking_water_sd},
                        "sr_status": sr_status, "d18O_status": o_status,
                        "non_local": "non-local" in (sr_status, o_status), "notes": notes})
    out["n_non_local"] = sum(r["non_local"] for r in results)
    out["baseline_sr"] = baseline
    return out, results


def analyze_mobility(samples, options=None, progress=None):
    options = options or MobilityOptions()
    sites: dict[str, list] = {}
    for s in samples:
        sites.setdefault(s.site, []).append(s)
    summaries, results = [], []
    for i, (site, rows) in enumerate(sites.items()):
        summary, rows_out = analyze_site(site, rows, options)
        summaries.append(summary)
        results += rows_out
        if progress:
            progress(i + 1, len(sites))
    return {"results": results, "sites": summaries,
            "warnings": [w for s in summaries for w in s.pop("warnings")]}
