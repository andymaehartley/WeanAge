"""Command-line entry point.

    weanage                       start the app and open it in the browser
    weanage --no-browser          start the server only (e.g. on a shared lab machine)
    weanage analyze data.csv -o results.csv
    weanage validate reference.csv    how accurate each model is on known-age animals
    weanage isoarch export.xlsx       list (or convert) sequential dentine series in an IsoArcH export
    weanage detect data.csv           which calculations a table can be used for
    weanage run mobility data.csv -o results.json --settings settings.json --methods methods.md
                                      run any calculation (tooth, bone, enamel, killoff, mixing, dental,
                                      leh, lifetable, mobility) and optionally write its methods paragraph
"""

import argparse
import json
import socket
import threading
import webbrowser

import pandas as pd


def free_port(preferred):
    """Use the preferred port if nothing else is using it, otherwise any free one."""
    with socket.socket() as s:
        if s.connect_ex(("127.0.0.1", preferred)) != 0:
            return preferred
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def serve(host, port, open_browser):
    import uvicorn

    from .api import app

    port = free_port(port)
    url = f"http://{host}:{port}/app/"
    print(f"WeanAge running at {url}  (Ctrl+C to stop)")
    if open_browser:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    uvicorn.run(app, host=host, port=port, log_level="warning")


def estimates_for(path):
    """Read a CSV or Excel file, print any problems, and return one row per specimen and model."""
    from .analysis import analyze, estimate_rows
    from .config import default_options
    from .ingest import ingest_file

    report = ingest_file(path)  # also reads .xlsx
    for problem in report["issues"]:
        where = f"row {problem['row']}: " if problem["row"] else ""
        print(f"[{problem['severity']}] {where}{problem['message']}")
    if not report["samples"]:
        raise SystemExit("No valid samples to analyse.")
    return estimate_rows(analyze(report["samples"], default_options()))


def analyze_file(path, output):
    table = pd.DataFrame(estimates_for(path))
    if output:
        table.to_csv(output, index=False)
        print(f"Wrote {len(table)} estimates to {output}")
    else:
        print(table.to_string(index=False))


def validate_file(path):
    """Score every model against known (or published) weaning ages; see docs/VALIDATION.md."""
    from .aggregate import validate
    from .config import lab_parameters

    path = path or lab_parameters()["reference_dataset"]["value"]
    if not path:
        raise SystemExit("Give a reference CSV, or set reference_dataset in lab_parameters.json (see docs/VALIDATION.md).")
    table = validate(estimates_for(path))
    if table.empty:
        raise SystemExit("No known_weaning_age_months or published_weaning_age_months values found in the file.")
    print(table.round(2).to_string(index=False))


def isoarch_file(path, sites, species, zone_order, spacing, output):
    """List the dentine series in an IsoArcH export, or convert chosen sites to a WeanAge CSV."""
    from .isoarch import summary, to_weanage

    if not sites:
        print(summary(path).to_string(index=False))
        print("\nChoose sites with --site (and --species) to convert them.")
        return
    table = to_weanage(path, sites, species, zone_order, spacing)
    if table.empty:
        raise SystemExit("No sequential dentine series found for those sites/species.")
    if output:
        table.to_csv(output, index=False)
        print(f"Wrote {len(table)} slices from {table['specimen_id'].nunique()} teeth to {output}")
    else:
        print(table.to_string(index=False))
    print(f"Slice positions are ASSUMED (zone order: {zone_order}); check them against the original papers.")


CALCULATIONS = ["tooth", "bone", "enamel", "killoff", "mixing", "dental", "leh", "lifetable", "mobility"]
PER_INDIVIDUAL = {"dental", "enamel"}  # results are per individual or tooth; elsewhere count the rows


def detect_file(path):
    from pathlib import Path

    from .service import detect

    found = detect(Path(path).name, Path(path).read_bytes())
    print(f"{found['filename']}: {found['n_rows']} rows, {len(found['columns'])} columns")
    for name, d in found["calculations"].items():
        print(f"  {name:10} {str(d['rows']) + ' rows' if d['rows'] else 'no: ' + d['problem']}")


def run_file(name, path, settings, output, methods):
    """Run one calculation on a table, as the app does, and write the results as JSON."""
    from pathlib import Path

    from . import service
    from .browser import clean
    from .methods import write_methods

    options = json.loads(Path(settings).read_text()) if settings else {}
    content = Path(path).read_bytes()
    if name == "tooth":
        report = service.read_upload(Path(path).name, content)
        settings_used = service.AnalysisOptions(**{**service.config.default_options().model_dump(), **options})
        body = service.AnalyzeIn(samples=report["samples"], options=settings_used)
        result = service.run_analysis(body, workers=1)
        n = len(result["results"])
    elif name == "bone":
        report = service.read_bone_upload(Path(path).name, content)
        result = service.run_bone_analysis(service.BoneAnalyzeIn(samples=report["samples"], options=options or None))
        n = sum(s["age_class"] != "adult" for s in report["samples"])
    else:
        report = service.read_calculation_upload(name, Path(path).name, content)
        result = service.run_calculation(name, {"samples": report["samples"], "options": options})
        n = len(result["results"]) if name in PER_INDIVIDUAL else len(report["samples"])
    for problem in report["issues"]:
        print(f"[{problem['severity']}] {'row ' + str(problem['row']) + ': ' if problem['row'] else ''}{problem['message']}")
    if not report["samples"]:
        raise SystemExit("No valid rows to analyse.")
    text = json.dumps(clean(result), indent=1, ensure_ascii=False)
    if output:
        Path(output).write_text(text, encoding="utf-8")
        print(f"Wrote the {name} results to {output}")
    else:
        print(text)
    if methods:
        Path(methods).write_text(write_methods({name: {"options": options, "n": n}})["text"], encoding="utf-8")
        print(f"Wrote the methods paragraph to {methods}")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="weanage", description="Weaning-age estimation from dentine δ15N")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    commands = parser.add_subparsers(dest="command")
    analyse = commands.add_parser("analyze", help="analyse a CSV without the app")
    analyse.add_argument("csv")
    analyse.add_argument("-o", "--output")
    check = commands.add_parser("validate", help="score the models on known-age reference animals")
    check.add_argument("csv", nargs="?", help="defaults to reference_dataset in lab_parameters.json")
    convert = commands.add_parser("isoarch", help="list or convert sequential dentine data from an IsoArcH export")
    convert.add_argument("xlsx")
    convert.add_argument("--site", action="append", default=[], help="a site to convert (repeat for more)")
    convert.add_argument("--species", action="append", help="e.g. cattle (repeat for more)")
    convert.add_argument("--zone-order", choices=["cervix_first", "crown_first"], default="cervix_first",
                         help="where zone 1 / 'a' was cut (default: cervix_first)")
    convert.add_argument("--spacing", type=float, help="mm between slice centres (default: spread over the crown)")
    convert.add_argument("-o", "--output")
    find = commands.add_parser("detect", help="which calculations a table can be used for")
    find.add_argument("table")
    run = commands.add_parser("run", help="run any calculation on a table and write JSON results")
    run.add_argument("calculation", choices=CALCULATIONS)
    run.add_argument("table")
    run.add_argument("--settings", help="a JSON file of settings (as saved in a project's settings)")
    run.add_argument("-o", "--output", help="results file (.json); printed if omitted")
    run.add_argument("--methods", help="also write a methods paragraph with references to this file")
    args = parser.parse_args(argv)
    if args.command == "isoarch":
        isoarch_file(args.xlsx, args.site, args.species, args.zone_order, args.spacing, args.output)
    elif args.command == "analyze":
        analyze_file(args.csv, args.output)
    elif args.command == "validate":
        validate_file(args.csv)
    elif args.command == "detect":
        detect_file(args.table)
    elif args.command == "run":
        run_file(args.calculation, args.table, args.settings, args.output, args.methods)
    else:
        serve(args.host, args.port, not args.no_browser)


if __name__ == "__main__":
    main()
