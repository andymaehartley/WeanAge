"""Drives the real app in a browser (skipped if Playwright or a browser is not installed).

    pip install playwright && playwright install chromium
"""

import os
import socket
import threading
import time
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")

TEST_DATA = Path(__file__).parent / "data"


@pytest.fixture(scope="module")
def server():
    import uvicorn

    from weanage.api import app

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    config = uvicorn.Config(app, port=port, log_level="warning")
    runner = uvicorn.Server(config)
    threading.Thread(target=runner.run, daemon=True).start()
    while not runner.started:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}/app/"
    runner.should_exit = True


@pytest.fixture(scope="module")
def page(server):
    with playwright.sync_playwright() as p:
        try:  # CHROMIUM_PATH lets the test use a browser installed somewhere else
            browser = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH"))
        except Exception as err:
            pytest.skip(f"no browser available: {err}")
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(server)
        yield page
        browser.close()
        assert not errors, errors


def click(page, selector):
    page.evaluate(f"document.querySelector({selector!r}).click()")


def load_example(page, value, card):
    page.select_option("#example-choice", value)
    click(page, "#btn-example")
    page.wait_for_selector(f"{card}:not([hidden])")


def test_whole_workflow(page):
    page.wait_for_selector(".tour-card")
    page.keyboard.press("Escape")  # close the first-visit tour
    page.click("#btn-help")  # the Help menu: tour, and the PDF guide
    assert page.is_visible("#help-menu") and page.get_attribute("#btn-help", "aria-expanded") == "true"
    page.wait_for_load_state("networkidle")  # the guide link is checked once the page has loaded
    assert page.get_attribute("#menu-guide", "href") == "guide/WeanAge_user_guide.pdf"
    page.click("#menu-tour")
    page.wait_for_selector(".tour-card")
    assert page.is_hidden("#help-menu")
    page.keyboard.press("Escape")
    click(page, "#btn-about")
    assert "Hartley" in page.text_content("#about-citation") and page.evaluate("document.querySelector('#about-dialog').open")
    page.keyboard.press("Escape")
    click(page, "#btn-tooth")
    assert "Cusp apex" in page.text_content("#tooth-dialog")
    page.keyboard.press("Escape")
    # Drop a file: the calculations it can feed are offered, and ticked ones get its rows.
    page.set_input_files("#csv-input", str(TEST_DATA / "synthetic_example.csv"))
    page.wait_for_selector("#file-status:not([hidden])")
    assert page.is_enabled('input[name="calc"][value="tooth"]') and page.is_disabled('input[name="calc"][value="dental"]')
    assert "Not with this file" in page.text_content("#calc-list")
    page.check('input[name="calc"][value="tooth"]')
    page.wait_for_selector("#specimens-card:not([hidden])")
    page.check('input[name="calc"][value="mixing"]')
    page.wait_for_selector("#mixing-samples-card:not([hidden])")
    assert page.is_visible("#calc-tabs") and page.is_hidden("#specimens-card")
    click(page, '#calc-tabs [data-calc="tooth"]')
    page.wait_for_selector("#specimens-card:not([hidden])")
    click(page, '.step[data-view="settings"]')
    page.evaluate("document.querySelector('.baseline-block').closest('details').open = true")
    page.fill('.baseline-row[data-key="Site A:cattle"] .bl-mean', "6.5")  # adult females: gives the milk share
    click(page, "#btn-run")
    page.wait_for_selector("#view-results.active", timeout=60000)
    assert "Best-supported model" in page.text_content("#res-summary")
    assert "Breast milk" in page.text_content("#milk-summary") and page.is_visible("#milk-chart svg")
    click(page, '.step[data-view="compare"]')
    page.wait_for_selector("#tests-body .summary", timeout=30000)
    assert "Do groups differ" in page.text_content("#tests-body")
    with page.expect_download() as download:
        click(page, "#btn-report")
    assert download.value.path().read_text().count("<svg") > 5

    # The bone calculation: its own data, settings and results; the tooth results are kept.
    click(page, '.step[data-view="data"]')
    load_example(page, "bone:cima_wharram_percy", "#bone-groups-card")
    assert page.is_hidden("#manual-form")
    assert page.is_hidden("#specimens-card")  # the tooth table does not show under the bone data
    assert "Wharram Percy" in page.text_content("#bone-group-table")
    click(page, "#btn-next-settings")
    assert page.evaluate("document.querySelector('#qc-card').closest('section').id") == "view-bone-settings"
    page.click("#view-bone-settings details.advanced > summary")  # the sampler settings are under Advanced
    page.fill("#bone-warmup", "500")
    page.fill("#bone-keep", "500")
    click(page, "#btn-bone-run")
    page.wait_for_selector("#view-bone-results.active", timeout=120000)
    assert "suckling ends" in page.text_content("#bone-res-summary .readout")
    assert page.is_disabled('.step[data-view="compare"]')
    # Ages can be shown in years; the readout and chart follow.
    click(page, "#btn-units")
    assert "years" in page.text_content("#bone-res-summary .readout")
    click(page, "#btn-units")
    # Add an animal by hand (ages typed in the chosen unit).
    click(page, '.step[data-view="data"]')
    page.fill('#bone-form [name="specimen_id"]', "HAND-1")
    page.fill('#bone-form [name="site"]', "Site A")
    page.fill('#bone-form [name="age_from"]', "2")
    page.fill('#bone-form [name="age_to"]', "4")
    page.fill('#bone-form [name="d15N"]', "8.1")
    page.click('#bone-form button[type="submit"]')
    page.wait_for_function("document.querySelector('#bone-form-msg').textContent.includes('Added HAND-1')")
    assert "HAND-1" in page.text_content("#bone-sample-table")
    # Plan a bone study.
    click(page, '.step[data-view="plan"]')
    assert page.is_visible("#bone-plan-form")
    page.click("#view-bone-plan details.advanced > summary")
    page.fill("#bp-reps", "2")
    page.fill("#bp-values", "15, 30")
    click(page, "#bp-run")
    page.wait_for_selector("#bp-results:not([hidden])", timeout=120000)
    assert "simulated site" in page.text_content("#bp-summary")
    # Enamel: season of birth and rumen development.
    click(page, '.step[data-view="data"]')
    load_example(page, "enamel:synthetic_enamel", "#enamel-teeth-card")
    assert page.is_hidden("#bone-groups-card") and page.is_disabled('.step[data-view="plan"]')
    click(page, "#btn-next-settings")
    page.fill("#enamel-draws", "100")
    click(page, "#btn-enamel-run")
    page.wait_for_selector("#view-enamel-results.active", timeout=120000)
    summary = page.text_content("#enamel-res-summary")
    assert "birth index" in summary and "Rumen development" in summary and "C3 diet" in summary
    assert "Site B" in page.text_content("#enamel-group-table")
    assert "rumen transition in" in summary and "no shift in ⁸⁷Sr/⁸⁶Sr" in summary
    page.click('#enamel-result-list [data-tooth="B01"]')
    assert "⁸⁷Sr/⁸⁶Sr shifts from 0.712" in page.text_content("#enamel-res-summary")
    assert page.is_visible("#enamel-sr-chart svg")
    # The one-table calculations, each with its example.
    for mode, card, run_text in [("killoff", "#killoff-groups-card", "Marj Rabba"), ("mixing", "#mixing-samples-card", "Marine fish"),
                                 ("dental", "#dental-card", "C24"), ("leh", "#leh-card", "H15"),
                                 ("lifetable", "#lifetable-card", "Juvenility"), ("mobility", "#mobility-card", "non-local")]:
        click(page, '.step[data-view="data"]')
        example = page.eval_on_selector(f'#example-choice option[value^="{mode}:"]', "o => o.value")
        load_example(page, example, card)
        click(page, "#btn-next-settings")
        click(page, f"#btn-{mode}-run")
        page.wait_for_selector(f"#view-{mode}-results.active", timeout=120000)
        assert run_text in page.text_content(f"#view-{mode}-results")
        assert page.is_visible(f"#view-{mode}-results svg")
    assert page.is_visible("#mobility-chart svg") and page.is_visible("#calc-tabs")
    # Every chart downloads as a figure: light colours on white, with its caption.
    with page.expect_download() as download:
        page.click('#mobility-chart [data-figure="svg"]')
    figure = download.value.path().read_text()
    assert figure.startswith("<svg") and 'fill="#ffffff"' in figure and "fall outside the local range" in figure
    # Everything about one individual, and the methods paragraph for all that was run.
    click(page, '.step[data-view="individuals"]')
    page.wait_for_selector("#view-individuals.active")
    assert page.text_content("#individual-title") and "open" in page.text_content("#individual-findings")
    click(page, "#btn-methods")
    page.wait_for_selector("#methods-dialog[open]")
    methods = page.text_content("#methods-body")
    assert "Weaning ages were estimated" in methods and "Payne S (1973)" in methods and "Moorrees" in methods
    page.keyboard.press("Escape")
    click(page, '.step[data-view="data"]')
    page.click("text=Tooth calculation")
    assert not page.is_disabled('.step[data-view="compare"]') and page.is_visible("#specimens-card")


@pytest.mark.skipif(not os.environ.get("WEANAGE_TEST_PYODIDE"), reason="needs internet: set WEANAGE_TEST_PYODIDE=1")
def test_browser_version():
    """The browser build, with Python running inside the page (downloads Pyodide from its CDN)."""
    import functools
    import http.server
    import subprocess
    import sys
    root = Path(__file__).parents[1]
    subprocess.run([sys.executable, str(root / "scripts" / "build_browser.py")], check=True)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=root / "dist" / "browser")
    static = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=static.serve_forever, daemon=True).start()
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH"))
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.add_init_script("localStorage.setItem('weanage-tour-done', '1')")
        url = f"http://127.0.0.1:{static.server_port}/"

        def run_example():
            page.wait_for_selector("#model-options input", state="attached", timeout=240000)  # the engine has loaded
            click(page, "#btn-example")
            page.wait_for_selector("#specimens-card:not([hidden])", timeout=60000)
            click(page, '.step[data-view="settings"]')
            page.click("#view-settings .grid-3 > article:first-child details.advanced > summary")  # draws are under Advanced
            page.fill("#opt-draws", "100")
            click(page, "#btn-run")  # 11 specimens: shared between several engines on a multi-core machine
            page.wait_for_selector("#view-results.active", timeout=600000)
            assert "Best-supported model" in page.text_content("#res-summary")
            ids = page.eval_on_selector_all("#result-list [data-specimen]", "els => els.map(e => e.dataset.specimen)")
            assert ids[0] == "BO01" and len(ids) == 11  # every animal of the IsoArcH example, in the original order

        page.goto(url)
        run_example()
        click(page, '.step[data-view="compare"]')
        page.wait_for_selector("#tests-body .summary", timeout=120000)
        # Offline: the saved copies of the app and of Python should be enough.
        page.context.set_offline(True)
        page.reload()
        run_example()
        browser.close()
    static.shutdown()
    assert not errors, errors
