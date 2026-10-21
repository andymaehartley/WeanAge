"""Drives the real app in a browser (skipped if Playwright or a browser is not installed).

    pip install playwright && playwright install chromium
"""

import os
import socket
import threading
import time

import pytest

playwright = pytest.importorskip("playwright.sync_api")


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


def test_whole_workflow(page):
    page.wait_for_selector(".tour-card")
    page.keyboard.press("Escape")  # close the first-visit tour
    page.click("#btn-help")  # the Help menu: tour, and the PDF guide (not written yet)
    assert page.is_visible("#help-menu") and page.get_attribute("#btn-help", "aria-expanded") == "true"
    page.wait_for_function("document.querySelector('#menu-guide').textContent.includes('coming soon')")
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
    click(page, "#btn-example")
    page.wait_for_selector("#specimens-card:not([hidden])")
    click(page, '.step[data-view="settings"]')
    click(page, "#btn-run")
    page.wait_for_selector("#view-results.active", timeout=60000)
    assert "Best-supported model" in page.text_content("#res-summary")
    click(page, '.step[data-view="compare"]')
    page.wait_for_selector("#tests-body .summary", timeout=30000)
    assert "Do groups differ" in page.text_content("#tests-body")
    with page.expect_download() as download:
        click(page, "#btn-report")
    assert download.value.path().read_text().count("<svg") > 5


@pytest.mark.skipif(not os.environ.get("WEANAGE_TEST_PYODIDE"), reason="needs internet: set WEANAGE_TEST_PYODIDE=1")
def test_browser_version():
    """The browser build, with Python running inside the page (downloads Pyodide from its CDN)."""
    import functools
    import http.server
    import subprocess
    import sys
    from pathlib import Path

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
            page.fill("#opt-draws", "100")
            click(page, "#btn-run")  # 11 specimens: shared between several engines on a multi-core machine
            page.wait_for_selector("#view-results.active", timeout=600000)
            assert "Best-supported model" in page.text_content("#res-summary")
            ids = page.eval_on_selector_all("#result-list [data-specimen]", "els => els.map(e => e.dataset.specimen)")
            assert ids[0] == "SYN-C01" and len(ids) == 11  # every specimen, in the original order

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
