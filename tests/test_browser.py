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
