"""Build the printable methods brief: docs/brief/WeanAge_methods_brief.md -> .html and .pdf

    python scripts/build_brief.py

Needs pandoc (Markdown -> HTML) and Playwright with Chromium (HTML -> PDF).
Set CHROMIUM_PATH to use a Chromium installed somewhere else.
"""

import os
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright

BRIEF = Path(__file__).resolve().parents[1] / "docs" / "brief"
SOURCE = BRIEF / "WeanAge_methods_brief.md"


def main():
    html = SOURCE.with_suffix(".html")
    subprocess.run(["pandoc", str(SOURCE), "--standalone", "--css", "brief.css", "-o", str(html)], check=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH"))
        page = browser.new_page()
        page.goto(html.as_uri())
        page.wait_for_load_state("networkidle")
        page.pdf(path=str(SOURCE.with_suffix(".pdf")), format="A4", print_background=True, prefer_css_page_size=True)
        browser.close()
    print(f"Wrote {html.name} and {SOURCE.with_suffix('.pdf').name} in {BRIEF}")


if __name__ == "__main__":
    main()
