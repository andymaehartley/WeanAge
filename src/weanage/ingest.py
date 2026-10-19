"""Ingestion of isotope data from CSV files or manually entered form rows."""

from __future__ import annotations

import io
import math
import re
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
from pydantic import BaseModel, Field, ValidationError

from .config import find_growth_table
from .schema import IsotopeSample

# Minimum samples per specimen for a 4-parameter curve plus an AICc comparison.
MIN_SAMPLES_PER_SPECIMEN = 6

# Lower-cased, punctuation-stripped header -> canonical field name.
COLUMN_ALIASES: dict[str, str] = {
    "specimen": "specimen_id",
    "specimenid": "specimen_id",
    "sampleid": "specimen_id",
    "individual": "specimen_id",
    "toothid": "specimen_id",
    "site": "site",
    "sitename": "site",
    "species": "species",
    "taxon": "species",
    "tooth": "tooth",
    "element": "tooth",
    "sampleindex": "sample_index",
    "increment": "sample_index",
    "sampleno": "sample_index",
    "positionmm": "position_mm",
    "position": "position_mm",
    "distancemm": "position_mm",
    "distancefromapexmm": "position_mm",
    "heightmm": "position_mm",
    "d15n": "d15N",
    "δ15n": "d15N",
    "delta15n": "d15N",
    "d15nair": "d15N",
    "d13c": "d13C",
    "δ13c": "d13C",
    "delta13c": "d13C",
    "d13cvpdb": "d13C",
    "pctn": "pct_N",
    "n": "pct_N",
    "percentn": "pct_N",
    "pctc": "pct_C",
    "c": "pct_C",
    "percentc": "pct_C",
    "cn": "cn_ratio",
    "cnratio": "cn_ratio",
    "atomiccn": "cn_ratio",
    "collagenyield": "collagen_yield_pct",
    "collagenyieldpct": "collagen_yield_pct",
    "yield": "collagen_yield_pct",
    "yieldpct": "collagen_yield_pct",
    "period": "period",
    "phase": "period",
    "notes": "notes",
    "comment": "notes",
    "knownweaningagemonths": "known_weaning_age_months",
    "knownweaningage": "known_weaning_age_months",
}


class RowIssue(BaseModel):
    row: int | None = Field(description="1-based data row (header excluded)")
    field: str | None = None
    message: str
    severity: str = "error"


class SpecimenSummary(BaseModel):
    specimen_id: str
    site: str
    species: str
    tooth: str
    n_samples: int
    has_growth_table: bool


class IngestReport(BaseModel):
    samples: list[IsotopeSample]
    issues: list[RowIssue]
    specimens: list[SpecimenSummary]
    unrecognised_columns: list[str] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)


def canonical_column(name: str) -> str | None:
    if name in IsotopeSample.model_fields:
        return name
    key = re.sub(r"[\s_\-().%‰:/]+", "", str(name).strip().lower())
    key = key.replace("permil", "")
    return COLUMN_ALIASES.get(key)


def _clean(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


def ingest_records(records: Iterable[dict[str, Any]]) -> IngestReport:
    """Validate already-keyed rows (e.g. from the manual-entry form)."""
    samples: list[IsotopeSample] = []
    issues: list[RowIssue] = []
    for i, raw in enumerate(records, start=1):
        row = {k: _clean(v) for k, v in raw.items()}
        try:
            samples.append(IsotopeSample(**row))
        except ValidationError as exc:
            for err in exc.errors():
                field = ".".join(str(p) for p in err["loc"]) or None
                issues.append(RowIssue(row=i, field=field, message=err["msg"]))
    issues.extend(_dataset_checks(samples))
    return IngestReport(samples=samples, issues=issues, specimens=summarise(samples))


def ingest_dataframe(df: pd.DataFrame) -> IngestReport:
    mapping: dict[str, str] = {}
    unrecognised: list[str] = []
    for col in df.columns:
        canon = canonical_column(col)
        if canon and canon not in mapping.values():
            mapping[col] = canon
        else:
            unrecognised.append(str(col))
    df = df.rename(columns=mapping)[list(mapping.values())]
    missing = [
        f for f, info in IsotopeSample.model_fields.items() if info.is_required() and f not in df
    ]
    if missing:
        issue = RowIssue(row=None, message=f"Missing required column(s): {', '.join(missing)}")
        return IngestReport(samples=[], issues=[issue], specimens=[], unrecognised_columns=unrecognised)

    for text_col in ("specimen_id", "site", "species", "tooth", "period", "notes"):
        if text_col in df:
            df[text_col] = df[text_col].map(lambda v: None if pd.isna(v) else str(v))
    report = ingest_records(df.to_dict(orient="records"))
    report.unrecognised_columns = unrecognised
    if unrecognised:
        report.issues.append(
            RowIssue(
                row=None,
                message=f"Ignored unrecognised column(s): {', '.join(unrecognised)}",
                severity="warning",
            )
        )
    return report


def ingest_csv(source: str | Path | bytes) -> IngestReport:
    """Read a CSV from a path or raw bytes (as uploaded through the UI)."""
    if isinstance(source, bytes):
        text = source.decode("utf-8-sig")
        df = pd.read_csv(io.StringIO(text), sep=None, engine="python")
    else:
        df = pd.read_csv(source, sep=None, engine="python", encoding="utf-8-sig")
    return ingest_dataframe(df)


def samples_to_dataframe(samples: list[IsotopeSample]) -> pd.DataFrame:
    return pd.DataFrame([s.model_dump() for s in samples])


def summarise(samples: list[IsotopeSample]) -> list[SpecimenSummary]:
    groups: dict[str, list[IsotopeSample]] = {}
    for s in samples:
        groups.setdefault(s.specimen_id, []).append(s)
    return [
        SpecimenSummary(
            specimen_id=sid,
            site=rows[0].site,
            species=rows[0].species,
            tooth=rows[0].tooth,
            n_samples=len(rows),
            has_growth_table=find_growth_table(rows[0].species, rows[0].tooth) is not None,
        )
        for sid, rows in groups.items()
    ]


def _dataset_checks(samples: list[IsotopeSample]) -> list[RowIssue]:
    issues: list[RowIssue] = []
    groups: dict[str, list[IsotopeSample]] = {}
    for s in samples:
        groups.setdefault(s.specimen_id, []).append(s)
    for sid, rows in groups.items():
        for attr in ("site", "species", "tooth"):
            values = {getattr(r, attr) for r in rows}
            if len(values) > 1:
                issues.append(
                    RowIssue(
                        row=None,
                        field=attr,
                        message=f"Specimen {sid} has more than one {attr}: {sorted(values)}",
                    )
                )
        positions = [r.position_mm for r in rows]
        if len(set(positions)) != len(positions):
            issues.append(
                RowIssue(
                    row=None,
                    field="position_mm",
                    message=f"Specimen {sid} has duplicate positions; replicate measurements will be fitted as separate points",
                    severity="warning",
                )
            )
        if len(rows) < MIN_SAMPLES_PER_SPECIMEN:
            issues.append(
                RowIssue(
                    row=None,
                    message=f"Specimen {sid} has only {len(rows)} samples; at least {MIN_SAMPLES_PER_SPECIMEN} are needed for curve fitting",
                    severity="warning",
                )
            )
        if find_growth_table(rows[0].species, rows[0].tooth) is None:
            issues.append(
                RowIssue(
                    row=None,
                    field="tooth",
                    message=f"No growth table for {rows[0].species} {rows[0].tooth} (specimen {sid}); supply a custom age model in Settings",
                    severity="warning",
                )
            )
    return issues
