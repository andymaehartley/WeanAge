"""Build the browser version of WeanAge: a folder of plain files that runs in any modern browser.

    python scripts/build_browser.py           # builds dist/browser/
    python scripts/build_browser.py --serve   # builds, then previews it at http://localhost:8000

The folder can be put on any static web host (GitHub Pages, a university web space, ...).
Nobody needs to install anything: the page downloads Python (Pyodide) the first time it opens.
"""

import argparse
import functools
import http.server
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "weanage"
OUT = ROOT / "dist" / "browser"


def build():
    if OUT.exists():
        shutil.rmtree(OUT)
    # 1. The app's page, styles and scripts.
    shutil.copytree(PACKAGE / "web", OUT)
    # 2. Mark the page as the browser version, so api.js uses Python-in-the-page.
    page = OUT / "index.html"
    html = page.read_text(encoding="utf-8")
    html = html.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n  <meta name="weanage-mode" content="browser">', 1)
    page.write_text(html, encoding="utf-8")
    # 3. The Python code and its data files, zipped for the page to unpack.
    with zipfile.ZipFile(OUT / "weanage.zip", "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(PACKAGE.rglob("*")):
            relative = path.relative_to(PACKAGE)
            if path.is_file() and relative.parts[0] != "web" and "__pycache__" not in relative.parts:
                zf.write(path, Path("weanage") / relative)
    # 4. The blank data templates, as plain downloads.
    shutil.copy(PACKAGE / "data" / "templates" / "isotope_template.csv", OUT / "weanage_template.csv")
    shutil.copy(PACKAGE / "data" / "templates" / "bone_template.csv", OUT / "weanage_bone_template.csv")
    # 5. Tell the offline helper (sw.js) which of the app's files to keep copies of.
    files = ["./"] + sorted(p.relative_to(OUT).as_posix() for p in OUT.rglob("*")
                            if p.is_file() and p.name not in ("sw.js", ".nojekyll") and p.suffix != ".txt")
    worker = OUT / "sw.js"
    worker.write_text(worker.read_text(encoding="utf-8").replace(
        "const APP_FILES = [];", f"const APP_FILES = {json.dumps(files)};"), encoding="utf-8")
    (OUT / ".nojekyll").touch()  # tells GitHub Pages to serve the files exactly as they are
    print(f"Browser version built in {OUT}")


def serve(port=8000):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=OUT)
    print(f"Preview at http://localhost:{port}/  (Ctrl+C to stop)")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), handler).serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--serve", action="store_true", help="preview the result in a browser")
    args = parser.parse_args()  # first, so --help does not rebuild anything
    build()
    if args.serve:
        serve()
