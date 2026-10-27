"""Reads isotope data from CSV/Excel files or the manual-entry form and checks it."""

import io
import math
import re
from pathlib import Path

import pandas as pd
from pydantic import ValidationError

from .config import find_growth_table
from .schema import IsotopeSample

MIN_SAMPLES = 6  # fewer than this is too few to fit a curve

# Other ways people write each column name (compared without spaces, case or symbols).
COMMON_ALIASES = {
    "site": ["sitename"],
    "species": ["taxon"],
    "d15N": ["δ15n", "delta15n", "d15nair"],
    "d13C": ["δ13c", "delta13c", "d13cvpdb"],
    "d34S": ["δ34s", "delta34s", "d34svcdt"],
    "pct_N": ["n", "percentn"],
    "pct_C": ["c", "percentc"],
    "cn_ratio": ["cn", "atomiccn"],
    "collagen_yield_pct": ["collagenyield", "yield", "yieldpct"],
    "period": ["phase"],
    "notes": ["comment"],
}
TOOTH_ALIASES = {
    "specimen_id": ["specimen", "specimenid", "sampleid", "toothid"],
    "individual_id": ["individual", "individualid", "animal", "animalid"],
    "tooth": ["element"],
    "sample_index": ["increment", "sampleno"],
    "position_mm": ["position", "distancemm", "distancefromapexmm", "heightmm"],
    "position_reference": ["measuredfrom", "positionorigin"],
    "crown_height_mm": ["crownheight"],
    "increment_width_mm": ["incrementwidth", "incrementheightmm"],
    "known_weaning_age_months": ["knownweaningage"],
    "published_weaning_age_months": ["publishedweaningage"],
}


def squash(name):
    """Lower-case a column name and drop spaces, brackets, %, ‰ etc."""
    return re.sub(r"[\s_\-().%‰:/]+", "", str(name).lower()).replace("permil", "")


def column_lookup(model, aliases):
    """Squashed column name -> field of `model`, for the field names and all their aliases."""
    lookup = {squash(field): field for field in model.model_fields}
    for field, spellings in {**COMMON_ALIASES, **aliases}.items():
        for spelling in spellings:
            lookup[squash(spelling)] = field
    return lookup


LOOKUP = column_lookup(IsotopeSample, TOOTH_ALIASES)


def canonical_column(name):
    return LOOKUP.get(squash(name))


def issue(message, row=None, field=None, severity="error"):
    return {"row": row, "field": field, "message": message, "severity": severity}


def is_blank(value):
    return value is None or (isinstance(value, float) and math.isnan(value))


def check_rows(model, records):
    """Turn row dictionaries into `model` objects; rows that fail become issues."""
    samples, issues = [], []
    for row_number, raw in enumerate(records, start=1):
        row = {key: (None if is_blank(value) else value) for key, value in raw.items()}
        try:
            samples.append(model(**row))
        except ValidationError as err:
            for e in err.errors():
                field = ".".join(str(part) for part in e["loc"]) or None
                issues.append(issue(e["msg"].removeprefix("Value error, "), row_number, field))
    return samples, issues


def match_columns(df, lookup, model):
    """Rename the table's columns to field names.

    Returns the renamed table (or None if a required column is missing) and the issues found.
    """
    renames, unknown = {}, []
    for column in df.columns:
        field = lookup.get(squash(column))
        if field and field not in renames.values():
            renames[column] = field
        else:
            unknown.append(str(column))
    df = df.rename(columns=renames)[list(renames.values())]
    missing = [f for f, info in model.model_fields.items() if info.is_required() and f not in df]
    if missing:
        return None, [issue(f"Missing required column(s): {', '.join(missing)}")]
    for column, info in model.model_fields.items():
        if column in df and info.annotation in (str, str | None):  # IDs like 001 must stay text, not become 1
            df[column] = df[column].map(lambda v: None if is_blank(v) else str(v))
    if unknown:
        return df, [issue(f"Ignored unrecognised column(s): {', '.join(unknown)}", severity="warning")]
    return df, []


def ingest_records(records):
    """Check a list of row dictionaries; returns samples, problems and a per-specimen summary."""
    samples, issues = check_rows(IsotopeSample, records)
    issues += dataset_checks(samples)
    return {"samples": samples, "issues": issues, "specimens": summarise(samples)}


def ingest_dataframe(df):
    df, issues = match_columns(df, LOOKUP, IsotopeSample)
    if df is None:
        return {"samples": [], "issues": issues, "specimens": []}
    report = ingest_records(df.to_dict(orient="records"))
    report["issues"] += issues
    return report


def is_excel(name):
    return Path(str(name)).suffix.lower() in {".xlsx", ".xlsm", ".xls"}


def read_table(source, filename=""):
    """A CSV or Excel file (a path, or the bytes of an upload) as a table. The CSV separator is detected."""
    uploaded = isinstance(source, bytes)
    if is_excel(filename if uploaded else source):  # Excel: the first sheet
        return pd.read_excel(io.BytesIO(source) if uploaded else source)
    return pd.read_csv(io.StringIO(source.decode("utf-8-sig")) if uploaded else source, sep=None, engine="python")


def ingest_file(source, filename=""):
    return ingest_dataframe(read_table(source, filename))


def group(samples, attribute):
    groups = {}
    for s in samples:
        groups.setdefault(getattr(s, attribute), []).append(s)
    return groups


def summarise(samples):
    return [{"specimen_id": sid, "individual_id": rows[0].individual_id, "site": rows[0].site,
             "species": rows[0].species, "tooth": rows[0].tooth, "n_samples": len(rows)}
            for sid, rows in group(samples, "specimen_id").items()]


def dataset_checks(samples):
    """Problems that only show up when looking at a whole specimen or animal."""
    issues = []
    per_animal = {animal: len(rows) for animal, rows in group(samples, "individual_id").items() if animal}
    for sid, rows in group(samples, "specimen_id").items():
        for attr in ["site", "species", "tooth"]:
            values = sorted({getattr(r, attr) for r in rows})
            if len(values) > 1:
                issues.append(issue(f"Specimen {sid} has more than one {attr}: {values}", field=attr))
        positions = [r.position_mm for r in rows]
        if len(set(positions)) < len(positions):
            issues.append(issue(f"Specimen {sid} has duplicate positions; repeats are fitted as separate points",
                                field="position_mm", severity="warning"))
        # Teeth of one animal are fitted together, so the count that matters is per animal.
        if max(len(rows), per_animal.get(rows[0].individual_id, 0)) < MIN_SAMPLES:
            issues.append(issue(f"Specimen {sid} has only {len(rows)} samples; at least {MIN_SAMPLES} are needed "
                                "for curve fitting", severity="warning"))
        if find_growth_table(rows[0].species, rows[0].tooth) is None:
            issues.append(issue(f"No growth table for {rows[0].species} {rows[0].tooth} (specimen {sid}); "
                                "supply a custom age model in Settings", field="tooth", severity="warning"))

    animals = group([s for s in samples if s.individual_id], "individual_id")
    for animal, rows in animals.items():
        for attr in ["site", "species"]:
            values = sorted({getattr(r, attr) for r in rows})
            if len(values) > 1:
                issues.append(issue(f"Individual {animal} has teeth with different {attr} values: {values}", field=attr))
        for tooth, tooth_rows in group(rows, "tooth").items():
            ids = sorted({r.specimen_id for r in tooth_rows})
            if len(ids) > 1:
                issues.append(issue(f"Individual {animal} has several {tooth} specimens ({', '.join(ids)}); "
                                    "left and right teeth will be fitted together", field="tooth", severity="warning"))
    return issues
