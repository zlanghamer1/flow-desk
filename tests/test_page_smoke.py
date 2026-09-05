"""Headless page smoke test (added 2026-09-03).

Loads every root HTML page in headless Chromium from a local static server
with every external host blocked, and fails on any uncaught page error. The
desk is designed to keep rendering when its feeds are down ("a feed that
fails keeps its slot", "the price layer must survive a data.json outage"),
and until this file nothing automated ever checked that the page boots
without throwing. It also pins two standing layout rules that earlier review
rounds measured by hand: no horizontal page scroll at phone or desktop
width, and the footer link to the legal page resolves to a real file.

Run locally:

    python3 -m pip install pytest playwright
    python3 -m playwright install chromium        # or set PW_CHROMIUM
    python3 -m pytest tests -q

In a sandbox with a preinstalled browser, point PW_CHROMIUM at its binary
(for example /opt/pw-browsers/chromium) instead of downloading one.

Network policy: requests to the local server are served from the repo;
everything else is aborted. Chromium logs each aborted request as a
"Failed to load resource" console error, which is expected here and
filtered out. Any other console error, and any uncaught exception, fails
the test.
"""
from __future__ import annotations

import http.server
import os
import re
import socketserver
import threading
from pathlib import Path

import pytest
pytest.importorskip("playwright", reason="browser smoke test needs playwright")
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGES = sorted(p.name for p in ROOT.glob("*.html"))
WIDTHS = [(1440, 900), (390, 844)]

# Console errors Chromium emits for requests this test itself blocks.
EXPECTED_CONSOLE = re.compile(r"Failed to load resource|net::ERR_FAILED|net::ERR_ABORTED")


class _Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, *args):  # keep pytest output clean
        pass


@pytest.fixture(scope="module")
def server():
    srv = socketserver.TCPServer(("127.0.0.1", 0), _Handler)
    port = srv.server_address[1]
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        srv.shutdown()
        srv.server_close()


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        kwargs = {}
        exe = os.environ.get("PW_CHROMIUM")
        if exe:
            kwargs["executable_path"] = exe
        b = p.chromium.launch(**kwargs)
        try:
            yield b
        finally:
            b.close()


def _load(browser, server, page_name, width, height):
    page = browser.new_page(viewport={"width": width, "height": height})
    page_errors: list[str] = []
    console_errors: list[str] = []
    blocked: list[str] = []

    page.on("pageerror", lambda err: page_errors.append(str(err)))
    page.on(
        "console",
        lambda msg: console_errors.append(msg.text)
        if msg.type == "error" and not EXPECTED_CONSOLE.search(msg.text)
        else None,
    )

    def route(r):
        url = r.request.url
        if url.startswith(server) or url.startswith("data:"):
            r.continue_()
        else:
            blocked.append(url)
            r.abort()

    page.route("**/*", route)
    page.goto(f"{server}/{page_name}", wait_until="load")
    # Let boot timers fire and their fetches fail; the page's own fail-soft
    # branches run inside these callbacks, which is exactly what we test.
    page.wait_for_timeout(3000)
    return page, page_errors, console_errors, blocked


@pytest.mark.parametrize("page_name", PAGES)
@pytest.mark.parametrize("width,height", WIDTHS)
def test_page_boots_with_feeds_down(browser, server, page_name, width, height):
    page, page_errors, console_errors, blocked = _load(browser, server, page_name, width, height)
    try:
        assert page_errors == [], f"{page_name} @ {width}px threw: {page_errors}"
        assert console_errors == [], f"{page_name} @ {width}px console errors: {console_errors}"
        assert page.title(), f"{page_name} has no <title>"
        overflow = page.evaluate(
            "document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        assert overflow <= 0, f"{page_name} @ {width}px scrolls sideways by {overflow}px"
        if page_name == "index.html":
            # The desk boots by fetching its feeds. With every external host
            # blocked, at least one blocked request proves the boot ran and
            # its fail-soft branches were the code under test.
            assert blocked, "index.html made no external request; did the boot run?"
    finally:
        page.close()


def test_index_links_to_legal_page(browser, server):
    page, page_errors, _, _ = _load(browser, server, "index.html", 1440, 900)
    try:
        assert page_errors == []
        href = page.get_attribute("footer a[href$='legal.html']", "href")
        assert href, "footer has no link to legal.html"
        assert (ROOT / href).is_file(), f"footer links to {href}, which is not in the repo"
    finally:
        page.close()


def test_legal_page_sections_present(browser, server):
    page, page_errors, _, _ = _load(browser, server, "legal.html", 1440, 900)
    try:
        assert page_errors == []
        for sec in ("short", "risk", "terms", "privacy", "sources", "contact"):
            assert page.locator(f"#{sec}").count() == 1, f"legal.html is missing #{sec}"
        assert page.get_attribute("header a.back", "href") == "./"
    finally:
        page.close()
