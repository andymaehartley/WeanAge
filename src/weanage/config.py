"""Reads the bundled data files and keeps track of values still waiting on lab work (TBD-LAB)."""

import json
import os
import sys
from pathlib import Path

from .schema import AnalysisOptions, GrowthTable, QCThresholds

# Inside the single-file app (PyInstaller) files are unpacked to sys._MEIPASS.
HERE = Path(getattr(sys, "_MEIPASS", Path(__file__).parent.parent)) / "weanage"
DATA_DIR = HERE / "data"
WEB_DIR = HERE / "web"


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def user_tables_path():
    """Where tables saved from the app are kept: $WEANAGE_HOME or ~/.weanage."""
    home = os.environ.get("WEANAGE_HOME") or Path.home() / ".weanage"
    return Path(home) / "growth_tables.json"


def bundled_growth_tables():
    tables = [GrowthTable(**t) for t in read_json(DATA_DIR / "growth_tables.json")["tables"]]
    return {t.key: t for t in tables}


def saved_growth_tables():
    path = user_tables_path()
    if not path.exists():
        return {}
    tables = [GrowthTable(**t) for t in read_json(path)["tables"]]
    return {t.key: t for t in tables}


def growth_tables():
    """The bundled tables, replaced by any the user has saved."""
    return {**bundled_growth_tables(), **saved_growth_tables()}


def write_saved_tables(tables):
    path = user_tables_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [t.model_dump() for t in tables.values()]
    path.write_text(json.dumps({"tables": rows}, indent=2, ensure_ascii=False), encoding="utf-8")


def save_growth_table(table):
    tables = saved_growth_tables()
    tables[table.key] = table
    write_saved_tables(tables)


def delete_saved_growth_table(key):
    tables = saved_growth_tables()
    if key not in tables:
        return False
    del tables[key]
    write_saved_tables(tables)
    return True


def find_growth_table(species, tooth, extra_tables=()):
    """Find the table for a species and tooth; tables sent with an analysis win."""
    for table in list(extra_tables) + list(growth_tables().values()):
        if table.species.lower() == species.lower() and table.tooth.lower() == tooth.lower():
            return table
    return None


def qc_config():
    return read_json(DATA_DIR / "qc_thresholds.json")


def lab_parameters():
    data = read_json(DATA_DIR / "lab_parameters.json")
    return {key: value for key, value in data.items() if not key.startswith("_")}


def default_options():
    """Analysis settings, starting from the values in the data files."""
    qc = QCThresholds(**{k: v for k, v in qc_config().items() if k in QCThresholds.model_fields})
    settings = {"qc": qc}
    for name, entry in lab_parameters().items():
        if name in AnalysisOptions.model_fields and entry.get("value") is not None:
            settings[name] = entry["value"]
    return AnalysisOptions(**settings)


def tbd_items():
    """A list of every placeholder value, shown highlighted in the app."""
    items = []
    for table in growth_tables().values():
        if table.placeholder:
            items.append({"id": f"growth:{table.key}", "area": "Tooth growth table", "label": table.label,
                          "note": table.tbd_note or "", "file": "src/weanage/data/growth_tables.json"})
    qc = qc_config()
    if qc.get("placeholder"):
        items.append({"id": "qc:thresholds", "area": "Collagen QC", "label": "Quality-control thresholds",
                      "note": qc.get("tbd_note", ""), "file": "src/weanage/data/qc_thresholds.json"})
    for name, entry in lab_parameters().items():
        if entry.get("placeholder"):
            items.append({"id": f"lab:{name}", "area": "Lab / method parameter", "label": name,
                          "note": entry.get("tbd_note", ""), "file": "src/weanage/data/lab_parameters.json"})
    return items
