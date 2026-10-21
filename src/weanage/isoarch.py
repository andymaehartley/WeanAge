"""Read sequential dentine series from an IsoArcH export (https://isoarch.eu).

IsoArcH exports are Excel workbooks with linked sheets: Materials (the animal), Samples
(the tooth) and Organic measures (one row per dentine slice, with a "Sampled zone
identifier" such as 1, 2, 3 or a, b, c). This module joins them and turns each slice
into a WeanAge row.

IsoArcH records the ORDER of the slices but not where they were cut, so two things must
be assumed (and should be checked against the original publication):
* `zone_order`: whether zone 1 / "a" is at the crown tip ("crown_first") or at the
  cervix, where the crown meets the root ("cervix_first");
* `spacing_mm`: the distance between slice centres. If None, the slices are assumed to
  be evenly spread over the whole crown (the length of the tooth's growth table).
Every row produced says which assumptions were used.
"""

import pandas as pd

from .config import find_growth_table

# IsoArcH species names -> WeanAge species
SPECIES = {
    "bos taurus": "cattle", "cattle": "cattle", "cow": "cattle",
    "sus scrofa": "pig", "sus scrofa domesticus": "pig", "pig": "pig",
    "equus caballus": "horse", "horse": "horse",
    "ovis aries": "sheep", "sheep": "sheep", "capra hircus": "goat", "goat": "goat",
    "ovis aries/capra hircus": "sheep/goat", "sheep/goat": "sheep/goat",
}


def species_name(reported):
    words = " ".join(str(reported).replace("_x000D_", " ").split()).lower()
    return SPECIES.get(words, words)


def zone_key(zone):
    """Sort zones in their natural order: 1 < 2 < 10, and a < b < z < aa."""
    text = str(zone).strip()
    try:
        return (0, float(text), "")
    except ValueError:
        return (1, len(text), text.lower())


def read_series(path):
    """Every sequentially sampled dentine series in the export, one row per slice."""
    sheets = pd.read_excel(path, sheet_name=["Organic measures", "Samples", "Materials", "Datasets"])
    measures = sheets["Organic measures"]
    measures = measures[measures["Sampled zone identifier"].notna() & measures["δ15N (‰air)"].notna()]
    rows = (measures.merge(sheets["Samples"], on="Sample identifier", how="left")
            .merge(sheets["Materials"], on="Material identifier", how="left")
            .merge(sheets["Datasets"][["Dataset DOI", "Dataset license"]], on="Dataset DOI", how="left"))
    rows = rows[rows["Tooth fraction"].fillna("dentine") == "dentine"].copy()
    rows["species"] = rows["Reported biological identification"].map(species_name)
    rows["tooth"] = rows.apply(lambda r: tooth_name(r["Tooth category"], r["Tooth numbering"]), axis=1)
    return rows


def tooth_name(category, number):
    if pd.isna(category) or pd.isna(number):
        return None
    return {"molar": "M", "premolar": "P", "incisor": "I"}.get(str(category).lower(), "?") + str(int(number))


def summary(path):
    """One line per site and species: how many teeth and slices there are."""
    rows = read_series(path)
    table = rows.groupby(["Location name", "species"]).agg(
        animals=("Material identifier", "nunique"), teeth=("Sample identifier", "nunique"),
        slices=("Sampled zone identifier", "count"), reference=("Short references", "first"),
        licence=("Dataset license", "first"))
    return table.reset_index().sort_values("slices", ascending=False)


def to_weanage(path, sites, species=None, zone_order="cervix_first", spacing_mm=None):
    """WeanAge input rows for the chosen sites (and species), as a DataFrame."""
    rows = read_series(path)
    rows = rows[rows["Location name"].isin(sites) & rows["tooth"].notna()]
    if species:
        rows = rows[rows["species"].isin(species)]
    out = []
    for _, tooth_rows in rows.groupby("Sample identifier"):
        first = tooth_rows.iloc[0]
        ordered = sorted(tooth_rows.to_dict("records"), key=lambda r: zone_key(r["Sampled zone identifier"]))
        table = find_growth_table(first["species"], first["tooth"])
        length = table.knots[-1].position_mm if table else None
        step = spacing_mm or (length / len(ordered) if length else 1.0)
        assumption = (f"ASSUMED: zone order {zone_order}, {'spacing ' + format(step, '.2f') + ' mm'}"
                      f"{' (slices spread over the crown)' if not spacing_mm and length else ''}")
        animal = str(first["Original material identifier"])
        for i, r in enumerate(ordered):
            centre = (i + 0.5) * step  # distance from the first slice's edge
            position = centre if zone_order == "crown_first" else (length or len(ordered) * step) - centre
            out.append({
                "specimen_id": f"{animal}-{first['tooth']}",
                "individual_id": animal,
                "site": first["Location name"],
                "species": first["species"],
                "tooth": first["tooth"],
                "sample_index": i + 1,
                "position_mm": round(max(position, 0.0), 2),
                "increment_width_mm": round(step, 2),
                "d15N": r["δ15N (‰air)"],
                "d13C": r["δ13C (‰vpdb)"],
                "period": period(first),
                "notes": f"zone {r['Sampled zone identifier']}; {assumption}; {first['Short references']}; "
                         f"IsoArcH {first['Dataset DOI']} ({first['Dataset license']})",
            })
    return pd.DataFrame(out)


def period(row):
    low, high = row["Relative dating - lower limit"], row["Relative dating - upper limit"]
    if pd.notna(low) and pd.notna(high):
        return f"AD {int(low)}-{int(high)}"
    return row["Archaeological period"] if pd.notna(row["Archaeological period"]) else None
