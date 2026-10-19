"""Command-line entry point.

    weanage                 # start the app and open it in the browser
    weanage --no-browser    # start the server only (e.g. on a shared lab machine)
    weanage analyze data.csv -o results.csv
"""

from __future__ import annotations

import argparse
import socket
import threading
import webbrowser


def _free_port(preferred: int) -> int:
    with socket.socket() as s:
        if s.connect_ex(("127.0.0.1", preferred)) != 0:
            return preferred
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def serve(host: str, port: int, open_browser: bool) -> None:
    import uvicorn

    from .api import app

    port = _free_port(port)
    url = f"http://{host}:{port}/app/"
    print(f"WeanAge running at {url}  (Ctrl+C to stop)")
    if open_browser:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    uvicorn.run(app, host=host, port=port, log_level="warning")


def analyze_file(path: str, output: str | None) -> None:
    import pandas as pd

    from .analysis import analyze, estimate_rows
    from .config import default_options
    from .ingest import ingest_csv

    report = ingest_csv(path)
    for issue in report.issues:
        where = f"row {issue.row}: " if issue.row else ""
        print(f"[{issue.severity}] {where}{issue.message}")
    if not report.samples:
        raise SystemExit("No valid samples to analyse.")
    results = analyze(report.samples, default_options())
    df = pd.DataFrame([r.model_dump() for r in estimate_rows(results)])
    if output:
        df.to_csv(output, index=False)
        print(f"Wrote {len(df)} estimates to {output}")
    else:
        print(df.to_string(index=False))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="weanage", description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    sub = parser.add_subparsers(dest="command")
    p_an = sub.add_parser("analyze", help="analyse a CSV without the GUI")
    p_an.add_argument("csv")
    p_an.add_argument("-o", "--output")
    args = parser.parse_args(argv)

    if args.command == "analyze":
        analyze_file(args.csv, args.output)
    else:
        serve(args.host, args.port, not args.no_browser)


if __name__ == "__main__":
    main()
