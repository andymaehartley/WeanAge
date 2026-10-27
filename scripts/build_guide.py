"""Build the PDF user guide: docs/guide/WeanAge_user_guide.md -> .pdf (A4)

    python scripts/build_guide.py            # rebuild the PDF from the Markdown
    python scripts/build_guide.py --figures  # also redraw the figures with the current code

The PDF is copied to src/weanage/web/guide/, where the app's Help menu links to it.
Needs pandoc (Markdown -> HTML) and Playwright with Chromium (HTML -> PDF).
Set CHROMIUM_PATH to use a Chromium installed somewhere else.
"""

import argparse
import math
import os
import re
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs" / "guide"
SOURCE = GUIDE / "WeanAge_user_guide.md"
FIGURES = GUIDE / "figures"
APP_COPY = ROOT / "src" / "weanage" / "web" / "guide" / "WeanAge_user_guide.pdf"


def launch(p):
    return p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH"))


def milestone_figure():
    """A logistic weaning curve with its three milestones, as SVG (no plotting library needed)."""
    post, drop, mid, scale, q = 5.5, 2.8, 7.0, 0.9, 0.05
    half = scale * math.log((1 - q) / q)
    ages = [i / 10 for i in range(0, 161)]
    curve = [post + drop / (1 + math.exp((t - mid) / scale)) for t in ages]
    x = lambda t: 60 + t * 30  # noqa: E731  16 months over 480 px
    y = lambda v: 230 - (v - 5) * 55  # noqa: E731  5-9 per mil over 220 px
    points = " ".join(f"{x(t):.1f},{y(v):.1f}" for t, v in zip(ages, curve))
    marks = [(mid - half, "onset (5%)"), (mid, "midpoint (50%)"), (mid + half, "completion (95%)")]
    lines = "".join(
        f'<line x1="{x(t):.1f}" y1="20" x2="{x(t):.1f}" y2="230" stroke="#0b5a70" stroke-dasharray="4 3"/>'
        f'<text x="{x(t) + 4:.1f}" y="{30 + 14 * i}" font-size="11" fill="#0b5a70">{label}</text>'
        for i, (t, label) in enumerate(marks))
    ticks = "".join(f'<text x="{x(t):.0f}" y="248" font-size="10" text-anchor="middle">{t}</text>' for t in range(0, 17, 2))
    vticks = "".join(f'<text x="52" y="{y(v) + 4:.0f}" font-size="10" text-anchor="end">{v}</text>' for v in range(5, 10))
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 560 270" font-family="Atkinson Hyperlegible, Arial, sans-serif">
<rect width="560" height="270" fill="#fff"/>
<line x1="60" y1="230" x2="540" y2="230" stroke="#47505c"/><line x1="60" y1="20" x2="60" y2="230" stroke="#47505c"/>
{ticks}{vticks}
<text x="300" y="266" font-size="11" text-anchor="middle">age (months)</text>
<text x="16" y="125" font-size="11" text-anchor="middle" transform="rotate(-90 16 125)">δ15N (‰)</text>
<line x1="60" y1="{y(post + drop):.1f}" x2="540" y2="{y(post + drop):.1f}" stroke="#c9d1d9"/>
<line x1="60" y1="{y(post):.1f}" x2="540" y2="{y(post):.1f}" stroke="#c9d1d9"/>
<text x="536" y="{y(post + drop) - 5:.1f}" font-size="10" text-anchor="end" fill="#47505c">nursing level = post + drop</text>
<text x="536" y="{y(post) - 5:.1f}" font-size="10" text-anchor="end" fill="#47505c">adult level = post</text>
{lines}<polyline points="{points}" fill="none" stroke="#14181f" stroke-width="2.2"/>
</svg>"""
    (FIGURES / "milestones.svg").write_text(svg)


def app_screenshots():
    """Run the bundled examples in the app (light theme) and save the result views."""
    import uvicorn

    from weanage.api import app

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.05)
    click = lambda page, sel: page.evaluate("s => document.querySelector(s).click()", sel)  # noqa: E731
    shot = lambda page, sel, name: (page.evaluate("document.querySelector('#toast').hidden = true"),  # noqa: E731
                                    page.locator(sel).screenshot(path=str(FIGURES / name)))
    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_page(viewport={"width": 1280, "height": 860}, device_scale_factor=2)
        page.add_init_script("localStorage.setItem('weanage-tour-done', '1'); localStorage.setItem('weanage-theme', 'light')")
        page.goto(f"http://127.0.0.1:{port}/app/")
        page.wait_for_selector("#model-options input", state="attached")
        page.add_style_tag(content=".statusbar { display: none; } .topbar { position: static; }")  # not over tall figures
        page.select_option("#example-choice", "isoarch_cattle")
        click(page, "#btn-example")
        page.wait_for_selector("#specimens-card:not([hidden])")
        page.evaluate("document.querySelector('#toast').hidden = true")
        page.screenshot(path=str(FIGURES / "app_data.png"))
        click(page, '.step[data-view="settings"]')
        click(page, "#btn-run")
        page.wait_for_selector("#view-results.active", timeout=300000)
        page.click('[data-specimen="KNPM121"]')
        page.wait_for_timeout(400)
        shot(page, "#view-results .results-layout > :last-child", "tooth_result.png")
        click(page, '.step[data-view="compare"]')
        page.wait_for_selector("#tests-body .summary", timeout=120000)
        page.wait_for_timeout(400)
        page.screenshot(path=str(FIGURES / "app_compare.png"))
        click(page, '.step[data-view="data"]')
        page.check('input[name="calc"][value="bone"]')
        page.select_option("#example-choice", "cima_wharram_percy")
        click(page, "#btn-example")
        page.wait_for_timeout(1000)
        click(page, '.step[data-view="settings"]')
        click(page, "#btn-bone-run")
        page.wait_for_selector("#bone-res-chart svg", timeout=300000)
        page.wait_for_timeout(400)
        shot(page, "#view-bone-results .results-layout > :last-child", "bone_result.png")
        click(page, '.step[data-view="data"]')
        page.check('input[name="calc"][value="enamel"]')
        click(page, "#btn-example")
        page.wait_for_selector("#enamel-teeth-card:not([hidden])")
        click(page, '.step[data-view="settings"]')
        click(page, "#btn-enamel-run")
        page.wait_for_selector("#view-enamel-results.active", timeout=300000)
        page.wait_for_timeout(400)
        shot(page, "#view-enamel-results .results-main > :first-child", "enamel_result.png")
        browser.close()
    server.should_exit = True


def build_pdf():
    html = SOURCE.with_suffix(".html")  # an intermediate file, not kept in git
    pdf = SOURCE.with_suffix(".pdf")
    subprocess.run(["pandoc", str(SOURCE), "--standalone", "--toc", "--toc-depth=2", "--css", "guide.css",
                    "-o", str(html)], check=True)
    footer = ('<div style="font: 8px Arial, sans-serif; color: #47505c; width: 100%; padding: 0 14mm; '
              'display: flex; justify-content: space-between;"><span>WeanAge user guide</span>'
              '<span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>')
    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_page()
        page.goto(html.as_uri())
        page.evaluate("document.fonts.ready")  # wait for the bundled font, or the layout would differ
        page.pdf(path=str(pdf), format="A4", print_background=True, prefer_css_page_size=True, tagged=True,
                 display_header_footer=True, header_template="<span></span>", footer_template=footer)
        browser.close()
    html.unlink()
    APP_COPY.parent.mkdir(exist_ok=True)
    shutil.copyfile(pdf, APP_COPY)
    pages = len(re.findall(rb"/Type\s*/Page[^s]", pdf.read_bytes()))
    print(f"Wrote {pdf} and {APP_COPY.relative_to(ROOT)} ({pages} pages)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--figures", action="store_true", help="redraw the figures first")
    if parser.parse_args().figures:
        FIGURES.mkdir(exist_ok=True)
        milestone_figure()
        app_screenshots()
    build_pdf()
