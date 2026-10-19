"""Loading of bundled reference data and the registry of lab-pending (TBD-LAB) values."""

from __future__ import annotations

import json
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from .schema import AnalysisOptions, GrowthTable, QCThresholds


def package_dir() -> Path:
    """Directory holding ``data/`` and ``web/`` (works inside a PyInstaller bundle)."""
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        return Path(bundle) / "weanage"
    return Path(__file__).resolve().parent


DATA_DIR = package_dir() / "data"
WEB_DIR = package_dir() / "web"


def _read_json(name: str) -> dict[str, Any]:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def user_dir() -> Path:
    """Per-user data directory (``$WEANAGE_HOME`` or ``~/.weanage``)."""
    return Path(os.environ.get("WEANAGE_HOME") or Path.home() / ".weanage")


def user_tables_path() -> Path:
    return user_dir() / "growth_tables.json"


def bundled_growth_tables() -> dict[str, GrowthTable]:
    tables = [GrowthTable(**t) for t in _read_json("growth_tables.json")["tables"]]
    return {t.key: t for t in tables}


def saved_growth_tables() -> dict[str, GrowthTable]:
    path = user_tables_path()
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {t.key: t for t in (GrowthTable(**row) for row in data.get("tables", []))}


@lru_cache
def growth_tables() -> dict[str, GrowthTable]:
    """Bundled tables, overridden by any the user has saved from the app."""
    return {**bundled_growth_tables(), **saved_growth_tables()}


def save_growth_table(table: GrowthTable) -> Path:
    """Persist an edited/calibrated table to the user directory (never the package)."""
    saved = saved_growth_tables()
    saved[table.key] = table
    path = user_tables_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"tables": [t.model_dump() for t in saved.values()]}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    growth_tables.cache_clear()
    return path


def delete_saved_growth_table(key: str) -> bool:
    saved = saved_growth_tables()
    if key not in saved:
        return False
    del saved[key]
    user_tables_path().write_text(
        json.dumps({"tables": [t.model_dump() for t in saved.values()]}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    growth_tables.cache_clear()
    return True


def find_growth_table(
    species: str, tooth: str, extra: list[GrowthTable] | None = None
) -> GrowthTable | None:
    """Look up a table, preferring ``extra`` (per-analysis) over saved and bundled ones."""
    wanted = (species.lower(), tooth.lower())
    for table in [*(extra or []), *growth_tables().values()]:
        if (table.species.lower(), table.tooth.lower()) == wanted:
            return table
    return None


@lru_cache
def qc_config() -> dict[str, Any]:
    return _read_json("qc_thresholds.json")


@lru_cache
def lab_parameters() -> dict[str, Any]:
    return {k: v for k, v in _read_json("lab_parameters.json").items() if not k.startswith("_")}


def default_options() -> AnalysisOptions:
    """Analysis options seeded from the bundled config files."""
    qc_fields = set(QCThresholds.model_fields)
    qc = QCThresholds(**{k: v for k, v in qc_config().items() if k in qc_fields})
    lab = lab_parameters()
    kwargs: dict[str, Any] = {"qc": qc}
    for name in (
        "analytical_sd_permil",
        "min_weaning_drop_permil",
        "transition_threshold",
        "growth_layer_offset_mm",
        "inner_dentine_weight",
    ):
        value = lab.get(name, {}).get("value")
        if value is not None:
            kwargs[name] = value
    return AnalysisOptions(**kwargs)


def tbd_items() -> list[dict[str, str]]:
    """Every value still flagged as a placeholder awaiting lab work."""
    items: list[dict[str, str]] = []
    for table in growth_tables().values():
        if table.placeholder:
            items.append(
                {
                    "id": f"growth:{table.key}",
                    "area": "Tooth growth table",
                    "label": table.label,
                    "note": table.tbd_note or "",
                    "file": "src/weanage/data/growth_tables.json",
                }
            )
    qc = qc_config()
    if qc.get("placeholder"):
        items.append(
            {
                "id": "qc:thresholds",
                "area": "Collagen QC",
                "label": "Quality-control thresholds",
                "note": qc.get("tbd_note", ""),
                "file": "src/weanage/data/qc_thresholds.json",
            }
        )
    for key, entry in lab_parameters().items():
        if entry.get("placeholder"):
            items.append(
                {
                    "id": f"lab:{key}",
                    "area": "Lab / method parameter",
                    "label": key,
                    "note": entry.get("tbd_note", ""),
                    "file": "src/weanage/data/lab_parameters.json",
                }
            )
    return items
