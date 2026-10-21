"""Command-line entry point.

    weanage                       start the app and open it in the browser
    weanage --no-browser          start the server only (e.g. on a shared lab machine)
    weanage analyze data.csv -o results.csv
    weanage validate reference.csv    how accurate each model is on known-age animals
    weanage isoarch export.xlsx       list (or convert) sequential dentine series in an IsoArcH export
"""

import argparse
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
    from .ingest import ingest_csv

    report = ingest_csv(path)  # also reads .xlsx
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
    args = parser.parse_args(argv)
    if args.command == "isoarch":
        isoarch_file(args.xlsx, args.site, args.species, args.zone_order, args.spacing, args.output)
    elif args.command == "analyze":
        analyze_file(args.csv, args.output)
    elif args.command == "validate":
        validate_file(args.csv)
    else:
        serve(args.host, args.port, not args.no_browser)


if __name__ == "__main__":
    main()
