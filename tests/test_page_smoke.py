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
import json
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


# Where a preinstalled Chromium usually lives when PW_CHROMIUM is not set.
# The vault's run_checks.sh gate runs this suite from a hook that carries no
# PW_CHROMIUM, and a pip-installed playwright then looks for a browser build it
# never downloaded. Probe the known path before giving up.
KNOWN_CHROMIUM = ("/opt/pw-browsers/chromium",)


def _chromium_path():
    exe = os.environ.get("PW_CHROMIUM")
    if exe:
        return exe
    for cand in KNOWN_CHROMIUM:
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return None


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        kwargs = {}
        exe = _chromium_path()
        if exe:
            kwargs["executable_path"] = exe
        try:
            b = p.chromium.launch(**kwargs)
        except Exception as e:  # no browser binary on this machine
            # run_checks.sh's contract: a test that needs a browser skips
            # cleanly when none is installed. This is an environment gap,
            # not a page result; CI installs the browser and runs it.
            pytest.skip(f"no Chromium available to launch: {e}".splitlines()[0])
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


# A data.json that reaches the page and then fails to DRAW used to be
# reported as "Can't reach data.json" (2026-09-05: renderBrief read .replace
# off a tooltip attribute the explanation sweep had deleted, on every
# browser, phone and desktop alike). The smoke tests above only ever see the
# fetch fail, so they cannot catch a render crash. This one hands the page a
# real-shaped payload and asserts the fetch is counted as a success, no
# render error is recorded, and the failure banner stays hidden.
FED_ODDS = {
    "as_of": "2026-09-04T19:33:31Z", "source": "Polymarket",
    "meeting_date": "2026-09-16", "days_to_meeting": 12,
    "hike_pct": 51.1, "hold_pct": 48.3, "cut_pct": 0.6,
    "grade": "HOSTILE", "alarm": True,
}
BRIEF_PAYLOAD = {
    "generated_at": "2026-09-04T20:20:52Z",
    "context_updated_at": "2026-09-04T20:20:52Z",
    "market_state": "afterhours",
    "session_date": "2026-09-04",
    "brief": {
        "date": "2026-09-04", "verdict": "CAUTIOUS", "score": 3,
        "plain_words": "test brief", "backdrop": None, "gap_note": None,
        "sectors": [], "retreat_watch": [], "havens": [], "havens_totals": None,
        "whales_hiding": [], "fed_hike": None, "semi_flow": None, "stale": False,
    },
    "fed_odds": FED_ODDS,
    "conviction": [], "swing": [], "big_orders": [], "etf_flow": [],
    "catalysts": [], "news": {"items": [], "by_ticker": {}}, "facts": {},
}


@pytest.mark.parametrize("width,height", WIDTHS)
def test_index_renders_a_delivered_data_json(browser, server, width, height):
    page = browser.new_page(viewport={"width": width, "height": height})
    page_errors: list[str] = []
    page.on("pageerror", lambda err: page_errors.append(str(err)))

    def route(r):
        url = r.request.url
        if "/data/data.json" in url:
            r.fulfill(status=200, content_type="application/json", body=json.dumps(BRIEF_PAYLOAD))
        elif url.startswith(server) or url.startswith("data:"):
            r.continue_()
        else:
            r.abort()

    page.route("**/*", route)
    page.goto(f"{server}/index.html", wait_until="load")
    page.wait_for_timeout(3000)
    try:
        assert page_errors == [], f"index.html @ {width}px threw: {page_errors}"
        st = page.evaluate(
            "({failures: FETCH_STATE.failures, renderError: FETCH_STATE.renderError,"
            " hasData: !!STATE.data, banner: document.getElementById('databanner').hidden,"
            " fed: document.getElementById('railfedtext').textContent})"
        )
        assert st["hasData"], "data.json was served but STATE.data is empty"
        assert st["renderError"] is None, f"renderAll threw: {st['renderError']}"
        assert st["failures"] == 0, "a delivered data.json was counted as a fetch failure"
        assert st["banner"] is True, "failure banner shown after a successful load"
        assert st["fed"].startswith("51%"), f"fed chip reads {st['fed']!r}"
    finally:
        page.close()


# ── Watchlist growth sorts (2026-09-07) ──────────────────────────────────────
# The rail's "rev growth" / "FCF growth" sorts read facts.<SYM>.framework
# .metrics.*_ttm_pct — the same numbers the Framework tab prints. Ranked rows
# lead, highest first; a name with no reading sinks below every ranked one and
# says which reading is missing, never a zero.

GROWTH_PAYLOAD = dict(BRIEF_PAYLOAD, facts={
    "MU":   {"framework": {"verdict": "HOLD", "filters": {}, "filter_flags": {"fcf_growth": "implausible_swing"},
                           "metrics": {"revenue_growth_ttm_pct": 41.3}}},
    "CRWD": {"framework": {"verdict": "BUY_4", "filters": {}, "filter_flags": {},
                           "metrics": {"revenue_growth_ttm_pct": 28.9, "fcf_growth_ttm_pct": 12.4}}},
    "V":    {"framework": {"verdict": "HOLD", "filters": {}, "filter_flags": {},
                           "metrics": {"revenue_growth_ttm_pct": -3.2, "fcf_growth_ttm_pct": 5.0}}},
    "SMH":  {"framework": {"verdict": "NOT_APPLICABLE", "filters": {}, "filter_flags": {}, "metrics": {}}},
})


@pytest.mark.parametrize("width,height", WIDTHS)
@pytest.mark.parametrize("sort_key,order,missing", [
    ("revg", ["MU", "CRWD", "V"], {"SMH": "rev fund"}),
    ("fcfg", ["CRWD", "V"], {"MU": "FCF data flagged", "SMH": "FCF fund"}),
])
def test_watchlist_sorts_by_growth(browser, server, width, height, sort_key, order, missing):
    page = browser.new_page(viewport={"width": width, "height": height})
    page_errors: list[str] = []
    page.on("pageerror", lambda err: page_errors.append(str(err)))
    page.add_init_script(f"localStorage.setItem('desk.wl.sort', {sort_key!r});"
                         "localStorage.setItem('desk.wl.collapsed', 'false');")

    def route(r):
        url = r.request.url
        if "/data/data.json" in url:
            r.fulfill(status=200, content_type="application/json", body=json.dumps(GROWTH_PAYLOAD))
        elif url.startswith(server) or url.startswith("data:"):
            r.continue_()
        else:
            r.abort()

    page.route("**/*", route)
    page.goto(f"{server}/index.html", wait_until="load")
    page.wait_for_timeout(3000)
    try:
        assert page_errors == [], f"index.html @ {width}px threw: {page_errors}"
        st = page.evaluate(
            "(function(){"
            " var rows=[].slice.call(document.querySelectorAll('#wl .wr[data-sym]'));"
            " return {sel: document.getElementById('wlsel') && document.getElementById('wlsel').value,"
            "  head: (document.querySelector('#wl .wg')||{}).textContent,"
            "  syms: rows.map(function(r){return r.dataset.sym;}),"
            "  grow: rows.map(function(r){var g=r.querySelector('.wlgrow'); return g? g.textContent.replace(/\\s+/g,' ').trim() : null;}),"
            "  wide: document.documentElement.scrollWidth > document.documentElement.clientWidth};"
            "})()"
        )
        assert st["sel"] == sort_key, f"select reads {st['sel']!r}"
        assert "GROWTH" in (st["head"] or "") and "HIGHEST FIRST" in st["head"], st["head"]
        assert not st["wide"], f"sideways scroll at {width}px"
        idx = {s: i for i, s in enumerate(st["syms"])}
        ranked = [idx[s] for s in order]
        assert ranked == sorted(ranked), f"ranked order wrong: {st['syms'][:8]}"
        # every ranked row precedes every no-reading row
        first_missing = min(i for i, g in enumerate(st["grow"]) if g and ("no reading" in g or "fund" in g or "flagged" in g))
        assert max(ranked) < first_missing, f"a no-reading row ranked above a reading: {list(zip(st['syms'], st['grow']))[:10]}"
        for sym, text in missing.items():
            assert st["grow"][idx[sym]] == text, f"{sym} reads {st['grow'][idx[sym]]!r}"
        top = st["grow"][idx[order[0]]]
        assert "+" in top and "TTM" in top and "-" not in top, top   # U+2212, never ASCII minus
        neg = st["grow"][idx["V"]] if sort_key == "revg" else None
        if neg: assert "−3.2%" in neg, neg
    finally:
        page.close()
