"""Make WeanAge's example datasets from the CIMA database (Compendium Isotoporum Medii Aevi).

    python scripts/make_cima_examples.py cima-humans-30.06.2025.xlsx

CIMA (Cocozza et al. 2022, Scientific Data; doi:10.48493/s9nf-1q80) collects published isotope
measurements from medieval Europe. It is shared under CC BY-SA, so the files this script writes
are CC BY-SA too: cite CIMA and the original studies (in each row's notes) when you use them.

Four examples are taken from the human data, each from a single published study:

* Bone calculation (bone collagen of children of known age, plus adult women for the mothers):
    Wharram Percy, England      Richards, Mays & Fuller 2002
    York, Fishergate House      Burt 2013
    Newark Bay, Orkney          Richards, Fuller & Molleson 2006
* Tooth calculation (dentine sections of first molars):
    Mikulčice, Czechia          Kaupová et al. 2024

CIMA's animal data were checked too, but hold no usable weaning series: the few young animals
with ages are older than one year and were sampled as whole teeth (see the examples README).
"""

import argparse
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "src" / "weanage" / "data" / "examples"
LICENCE = "CIMA (doi:10.48493/s9nf-1q80), CC BY-SA"
CHILD_MAX_YEARS = 10  # WARN uses non-adults up to 10 years
ADULT_MIN_YEARS = 18
M1_LENGTH_MM = 21  # the human M1 growth table: cusp apex to root apex

BONE_SITES = {  # file name: (CIMA site name, start of the reference, short citation)
    "cima_bone_wharram_percy.csv": ("Wharram Percy", "Richards, M.P., Mays", "Richards, Mays & Fuller 2002"),
    "cima_bone_york_fishergate.csv": ("York. Fishergate House", "Burt", "Burt 2013"),
    "cima_bone_newark_bay.csv": ("Orkney. Newark Bay", "Richards, M.P., Fuller", "Richards, Fuller & Molleson 2006"),
}
TOOTH_STUDY = ("Mikulčice", "Kaupová, S., Brůžek", "Kaupová et al. 2024")
TOOTH_INDIVIDUALS = 12  # the first 12 first molars (by ID) with all ten sections


def number(series):
    return pd.to_numeric(series, errors="coerce")


def read_cima(path):
    data = pd.read_excel(path)
    data = data[data["Excluded Entry?"].isna() & data["δ15N Collagen"].notna()].copy()
    data["min_years"] = number(data["Min. Age (yrs)"])
    data["max_years"] = number(data["Max. Age (yrs)"])
    data["d13C"] = number(data["IRMS δ13C Collagen"]).fillna(number(data["AMS δ13C Collagen"]))
    return data


def notes(row, citation):
    return f"{citation}; CIMA entry {row['CIMA Entry ID']}; {LICENCE}"


def bone_example(data, site, reference, citation):
    rows = data[(data["Site Name"] == site) & data["Reference"].str.startswith(reference, na=False)
                & (data["Tooth Increment?"] == "No")
                & data["Analysed Component"].str.lower().str.startswith("bone collagen", na=False)]
    out = []
    for _, r in rows.iterrows():
        child = r["max_years"] <= CHILD_MAX_YEARS
        adult = r["min_years"] >= ADULT_MIN_YEARS
        if not (child or adult):
            continue  # adolescents and unknown ages are left out
        sex = str(r["Sex"]).strip().upper()[:1]
        out.append({
            "specimen_id": f"{r['Individual ID']}", "site": site.split(". ")[-1], "species": "human",
            "element": r["Sampled Element"], "age_class": "adult" if adult else "non-adult",
            "sex": sex if sex in ("F", "M") else "",
            "age_min_months": None if adult else round(r["min_years"] * 12, 1),
            "age_max_months": None if adult else round(r["max_years"] * 12, 1),
            "d15N": r["δ15N Collagen"], "d13C": r["d13C"], "cn_ratio": r["Atomic C:N Ratio"],
            "pct_C": r["%C"], "pct_N": r["%N"], "collagen_yield_pct": r["Collagen Yield"],
            "notes": notes(r, citation),
        })
    table = pd.DataFrame(out)
    repeats = table["specimen_id"].duplicated(keep=False)
    table.loc[repeats, "specimen_id"] += "-" + table[repeats].groupby("specimen_id").cumcount().add(1).astype(str)
    return table


def tooth_example(data):
    site, reference, citation = TOOTH_STUDY
    rows = data[(data["Site Name"] == site) & data["Reference"].str.startswith(reference, na=False)
                & (data["Tooth Increment?"] == "Yes") & (data["Sampled Element"].astype(str).str.upper() == "M1")].copy()
    rows["section"] = number(rows["Sample ID"].astype(str).str.extract(r"(\d+)\s*$")[0])
    complete = rows.groupby("Individual ID")["section"].apply(lambda s: sorted(s.dropna()) == list(range(1, 11)))
    chosen = sorted(complete[complete].index, key=str)[:TOOTH_INDIVIDUALS]
    spacing = M1_LENGTH_MM / 10  # ASSUMED: ten equal sections from cusp apex to root apex
    out = []
    for _, r in rows[rows["Individual ID"].isin(chosen)].sort_values(["Individual ID", "section"]).iterrows():
        sex = str(r["Sex"]).strip().upper()[:1]
        out.append({
            "specimen_id": r["Individual ID"], "site": site, "species": "human", "tooth": "M1",
            "sample_index": int(r["section"]), "position_mm": round((r["section"] - 0.5) * spacing, 2),
            "increment_width_mm": spacing, "d15N": round(r["δ15N Collagen"], 2), "d13C": round(r["d13C"], 2),
            "cn_ratio": round(r["Atomic C:N Ratio"], 2) if pd.notna(r["Atomic C:N Ratio"]) else None,
            "collagen_yield_pct": round(number(pd.Series([r["Collagen Yield"]]))[0], 2),
            "period": "9th-10th c. AD",
            "notes": f"section {int(r['section'])} of 10 from the crown; ASSUMED: sections of equal height over a "
                     f"{M1_LENGTH_MM} mm tooth ({spacing:.1f} mm each); sex {sex if sex in 'FM' else 'unknown'}; "
                     + notes(r, citation),
        })
    return pd.DataFrame(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("humans", help="CIMA human data (.xlsx)")
    args = parser.parse_args()
    data = read_cima(args.humans)
    for name, (site, reference, citation) in BONE_SITES.items():
        table = bone_example(data, site, reference, citation)
        table.to_csv(OUT / name, index=False)
        young = (table["age_class"] == "non-adult").sum()
        women = ((table["age_class"] == "adult") & (table["sex"] == "F")).sum()
        print(f"{name}: {young} children, {women} adult women, {len(table) - young - women} other adults")
    teeth = tooth_example(data)
    teeth.to_csv(OUT / "cima_teeth_mikulcice.csv", index=False)
    print(f"cima_teeth_mikulcice.csv: {teeth['specimen_id'].nunique()} first molars, {len(teeth)} sections")


if __name__ == "__main__":
    main()
