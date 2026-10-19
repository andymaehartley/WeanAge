"""Command-line entry point.

    weanage                       start the app and open it in the browser
    weanage --no-browser          start the server only (e.g. on a shared lab machine)
    weanage analyze data.csv -o results.csv
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


def analyze_file(path, output):
    from .analysis import analyze, estimate_rows
    from .config import default_options
    from .ingest import ingest_csv

    report = ingest_csv(path)
    for problem in report["issues"]:
        where = f"row {problem['row']}: " if problem["row"] else ""
        print(f"[{problem['severity']}] {where}{problem['message']}")
    if not report["samples"]:
        raise SystemExit("No valid samples to analyse.")
    table = pd.DataFrame(estimate_rows(analyze(report["samples"], default_options())))
    if output:
        table.to_csv(output, index=False)
        print(f"Wrote {len(table)} estimates to {output}")
    else:
        print(table.to_string(index=False))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="weanage", description="Weaning-age estimation from dentine δ15N")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    commands = parser.add_subparsers(dest="command")
    analyse = commands.add_parser("analyze", help="analyse a CSV without the app")
    analyse.add_argument("csv")
    analyse.add_argument("-o", "--output")
    args = parser.parse_args(argv)
    if args.command == "analyze":
        analyze_file(args.csv, args.output)
    else:
        serve(args.host, args.port, not args.no_browser)


if __name__ == "__main__":
    main()
