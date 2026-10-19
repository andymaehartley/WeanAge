"""Build the printable methods brief: docs/brief/WeanAge_methods_brief.md -> .pdf (A4, two pages)

    python scripts/build_brief.py            # rebuild the PDF from the Markdown
    python scripts/build_brief.py --figure   # also redraw example_curve.png with the current code

Needs pandoc (Markdown -> HTML) and Playwright with Chromium (HTML -> PDF).
Set CHROMIUM_PATH to use a Chromium installed somewhere else.
"""

import argparse
import os
import re
import socket
import subprocess
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BRIEF = Path(__file__).resolve().parents[1] / "docs" / "brief"
SOURCE = BRIEF / "WeanAge_methods_brief.md"
PAGES = 2


def launch(p):
    return p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH"))


def draw_figure():
    """Run the example in the app (light theme) and save the chart for SYN-C01, logistic and two-phase only."""
    import uvicorn

    from weanage.api import app

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.05)
    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_page(viewport={"width": 1100, "height": 900}, device_scale_factor=2)
        page.add_init_script("localStorage.setItem('weanage-tour-done', '1'); localStorage.setItem('weanage-theme', 'light')")
        page.goto(f"http://127.0.0.1:{port}/app/")
        page.wait_for_selector("#model-options input", state="attached")
        page.evaluate("document.querySelector('#btn-example').click()")
        page.wait_for_selector("#specimens-card:not([hidden])")
        page.evaluate("document.querySelector('#btn-run').click()")
        page.wait_for_selector("#view-results.active", timeout=120000)
        for model in ["piecewise", "exponential", "elbow", "average"]:
            page.evaluate(f"document.querySelector('#curve-toggles input[data-model=\"{model}\"]')?.click()")
        page.wait_for_timeout(400)
        page.locator("#res-chart").screenshot(path=str(BRIEF / "example_curve.png"))
        browser.close()
    server.should_exit = True


def build_pdf():
    html = SOURCE.with_suffix(".html")  # an intermediate file, not kept in git
    pdf = SOURCE.with_suffix(".pdf")
    subprocess.run(["pandoc", str(SOURCE), "--standalone", "--css", "brief.css", "-o", str(html)], check=True)
    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_page()
        page.goto(html.as_uri())
        page.evaluate("document.fonts.ready")  # wait for the bundled font, or the layout would differ
        page.pdf(path=str(pdf), format="A4", print_background=True, prefer_css_page_size=True, tagged=True)
        browser.close()
    pages = len(re.findall(rb"/Type\s*/Page[^s]", pdf.read_bytes()))
    if pages != PAGES:
        raise SystemExit(f"The brief is {pages} pages long; shorten it to {PAGES}.")
    print(f"Wrote {pdf} ({pages} pages)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--figure", action="store_true", help="redraw the example figure first")
    if parser.parse_args().figure:
        draw_figure()
    build_pdf()
