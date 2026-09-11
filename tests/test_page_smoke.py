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


# ── Desk verdicts (2026-09-11) ───────────────────────────────────────────────
# The one decision layer: data.json.verdicts, read and never re-derived by the
# page. Four tickers exercise every call/coverage state at once: XLE (BUY,
# partial coverage), MU (SELL, one input missing — also carries a Conviction
# board row so the flow-board pill can be checked on the same fixture), LLY
# (HOLD via the earnings gate, full coverage), RAM (coverage gate failed,
# score/call null).

# Eight inputs and the 2026-09-11 attempt #3 table (market left the
# composite; the brief verdict is a chip on the board instead).
VERDICT_ORDER = ["trend", "rs63", "framework", "analyst_rating", "target_upside",
                 "flow_today", "flow_persist", "valuation"]
VERDICT_WEIGHTS = {"trend": 21, "rs63": 21, "framework": 20, "analyst_rating": 5,
                   "target_upside": 3, "flow_today": 5, "flow_persist": 5,
                   "valuation": 20}
VERDICT_NULL_NOTES = {
    "trend": "fewer than 200 sessions of history",
    "rs63": "fewer than 64 daily closes",
    "framework": "no framework score",
    "analyst_rating": "fewer than 5 analysts",
    "target_upside": "fewer than 5 analysts",
    "flow_today": "no conviction card",
    "flow_persist": "no swing card",
    "valuation": "no PEG reading",
}


def _verdict_inputs(resolved):
    """resolved: {key: (v, note)}. Every other key in VERDICT_ORDER gets v=null
    with its own reason, never a zero — same rule the page renders under."""
    out = {}
    for key in VERDICT_ORDER:
        if key in resolved:
            v, note = resolved[key]
            out[key] = {"v": v, "note": note}
        else:
            out[key] = {"v": None, "note": VERDICT_NULL_NOTES[key]}
    return out


CONVICTION_MU_ROW = {
    "ticker": "MU", "tv_symbol": "NASDAQ:MU", "direction": "BEAR", "firing": False,
    "score": 62, "spot": 976.49, "spot_at_alert": None,
    "net_flow": None, "cp_ratio": None, "flow_pct": None, "flow_side": None, "flow_pct_basis": None,
    "rvol": None, "change_pct": None, "tilt": None, "tilt_prem": None,
    "opt_rvol": None, "vol_collecting": False, "unusual_activity": False, "activity_tag": None,
    "popular_contract": None,
}

VERDICT_PAYLOAD = dict(
    BRIEF_PAYLOAD,
    generated_at_ct="2026-09-10 15:18 CT",
    conviction=[CONVICTION_MU_ROW],
    facts={"MU": {}, "XLE": {}, "LLY": {}, "RAM": {}, "ZZZ": {}},
    verdicts={
        "v": 2,
        "thresholds": {"buy": 35, "sell": -35},
        "min_weight": 50, "min_inputs": 3, "earnings_gate_days": 3,
        "horizon_days": 21,
        "order": VERDICT_ORDER,
        "weights": VERDICT_WEIGHTS,
        # 2026-09-11 attempt #3: the regime is a disclosure the board prints
        # as a chip (bear here, so the chip carries the hostile tint), the
        # analyst centers say which median the two analyst legs read against
        "regime": {"name": "bear", "spy_vs_200d": -0.0312, "basis": "SPY vs its 200-day average",
                   "note": "SPY \u22123.1% vs its 200-day"},
        "analyst_centers": {"rec_mark": 1.17, "target_upside": 0.38, "n_rec_mark": 38,
                            "n_target_upside": 38, "source": "desk"},
        "failed": 0,
        "counts": {"buy": 1, "sell": 1, "hold": 2, "none": 1},
        "by_ticker": {
            # Every score below is round-half-away-from-zero(100 * sum(w*v)
            # / weight) over that entry's OWN resolved inputs and the
            # payload's own weights -- checked by
            # test_verdict_payload_scores_match_own_inputs, not asserted by
            # eye (2026-09-11 fix: the old fixture's scores were arithmetic
            # the entries' own inputs could not produce).
            "XLE": {
                # 21*1.0 + 21*0.32 + 5*0.68 + 3*1.0 + 5*0.40 = 36.12 over
                # weight 55 -> 65.67 -> 66.
                "score": 66, "call": "BUY", "note": None, "n": 5, "n_total": 8, "weight": 55,
                "inputs": _verdict_inputs({
                    "trend": (1.0, "above 50d · above 200d"),
                    "rs63": (0.32, "+6.4pp vs SPY, 63 sessions"),
                    "analyst_rating": (0.68, "1.12 of 3 · 57 analysts"),
                    "target_upside": (1.0, "+61% to the average target"),
                    "flow_persist": (0.40, "BULL 40 on Swing"),
                }),
            },
            "MU": {
                # 21*-1.0 + 21*-0.5 + 5*-0.2 + 3*-0.3 + 5*-0.62 + 5*-0.50
                # + 20*-0.1 = -41.0 over weight 80 -> -51.25 -> -51.
                "score": -51, "call": "SELL", "note": None, "n": 7, "n_total": 8, "weight": 80,
                "inputs": _verdict_inputs({
                    "trend": (-1.0, "below 50d · below 200d"),
                    "rs63": (-0.5, "−10.2pp vs SPY, 63 sessions"),
                    "analyst_rating": (-0.2, "1.7 of 3 · 42 analysts"),
                    "target_upside": (-0.3, "+4% to the average target"),
                    "flow_today": (-0.62, "BEAR 62 on Conviction"),
                    "flow_persist": (-0.50, "BEAR 50 on Swing"),
                    "valuation": (-0.1, "PEG 1.6"),
                }),
            },
            "LLY": {
                # 21*0.6 + 21*0.2 + 20*0.4 + 5*0.5 + 3*0.6 + 5*0.2 + 5*0.3
                # + 20*0.5 = 41.6 over weight 100 -> 42 -- a real BUY-range
                # score (>= 35) that the earnings gate, not the threshold,
                # holds to HOLD.
                "score": 42, "call": "HOLD", "note": "earnings in 2d", "n": 8, "n_total": 8, "weight": 100,
                "inputs": _verdict_inputs({
                    "trend": (0.6, "above 50d · above 200d"),
                    "rs63": (0.2, "+4.0pp vs SPY, 63 sessions"),
                    "framework": (0.4, "ADD"),
                    "analyst_rating": (0.5, "1.2 of 3 · 30 analysts"),
                    "target_upside": (0.6, "+35% to the average target"),
                    "flow_today": (0.2, "BULL 20 on Conviction"),
                    "flow_persist": (0.3, "BULL 30 on Swing"),
                    "valuation": (0.5, "PEG 0.75"),
                }),
            },
            "RAM": {
                "score": None, "call": None, "note": "2 of 8 inputs · weight 26 of 100",
                "n": 2, "n_total": 8, "weight": 26,
                "inputs": _verdict_inputs({
                    "rs63": (0.1, "+2.0pp vs SPY, 63 sessions"),
                    "flow_today": (-0.1, "BEAR 10 on Conviction"),
                }),
            },
            "ZZZ": {
                # score 0 deliberately (LLY no longer holds this role — see
                # above): P2 pins that a score of exactly zero renders
                # neutral ("m"), never the green "u" a bare
                # `score<0 ? "d":"u"` two-way test used to paint it.
                # 21*0.0 + 21*0.25 + 20*0.0 + 5*-1.0 + 5*-0.05 = 0 over weight
                # 72 -- a plain HOLD, no earnings gate involved (2026-09-11
                # attempt #3 table).
                "score": 0, "call": "HOLD", "note": None, "n": 5, "n_total": 8, "weight": 72,
                "inputs": _verdict_inputs({
                    "trend": (0.0, "on 50d · on 200d"),
                    "rs63": (0.25, "+5.0pp vs SPY, 63 sessions"),
                    "framework": (0.0, "HOLD"),
                    "flow_today": (-1.0, "BEAR 100 on Conviction"),
                    "flow_persist": (-0.05, "BEAR 5 on Swing"),
                }),
            },
        },
    },
)


def test_verdict_payload_scores_match_own_inputs():
    """Every fixture score is round-half-away-from-zero(100 * sum(w*v) /
    weight) over that entry's own resolved inputs and VERDICT_WEIGHTS --
    the same rounding convention fetcher/verdict.py's compute_verdict uses.
    A fixture whose declared score its own inputs cannot produce is a bug in
    the TEST, not a real reading (2026-09-11 fix: this exact drift shipped
    for MU and LLY)."""
    import math

    def round_half_away_from_zero(x):
        return int(math.floor(x + 0.5)) if x >= 0 else int(-math.floor(-x + 0.5))

    for ticker, entry in VERDICT_PAYLOAD["verdicts"]["by_ticker"].items():
        if entry["score"] is None:
            continue
        wsum = 0.0
        weight = 0
        for key, inp in entry["inputs"].items():
            if inp["v"] is None:
                continue
            w = VERDICT_WEIGHTS[key]
            wsum += w * inp["v"]
            weight += w
        assert weight == entry["weight"], (ticker, weight, entry["weight"])
        expected = round_half_away_from_zero(100.0 * wsum / weight)
        assert entry["score"] == expected, (ticker, entry["score"], expected)


def _route_json(server, payload):
    def route(r):
        url = r.request.url
        if "/data/data.json" in url:
            r.fulfill(status=200, content_type="application/json", body=json.dumps(payload))
        elif url.startswith(server) or url.startswith("data:"):
            r.continue_()
        else:
            r.abort()
    return route


@pytest.mark.parametrize("width,height", WIDTHS)
def test_verdicts_board_renders(browser, server, width, height):
    page = browser.new_page(viewport={"width": width, "height": height})
    page_errors: list[str] = []
    page.on("pageerror", lambda err: page_errors.append(str(err)))
    page.route("**/*", _route_json(server, VERDICT_PAYLOAD))
    page.goto(f"{server}/index.html", wait_until="load")
    page.wait_for_timeout(3000)
    try:
        assert page_errors == [], f"index.html @ {width}px threw: {page_errors}"
        st = page.evaluate(
            "(function(){"
            " var rows=[].slice.call(document.querySelectorAll('#verd tr.rw[data-sym]'));"
            " var mu=document.querySelector('#verd tr[data-sym=\"MU\"]');"
            " var muChips=mu ? [].slice.call(mu.children[3].querySelectorAll('.vin')) : [];"
            " return {stat: document.getElementById('verdstat').textContent,"
            "  syms: rows.map(function(r){return r.dataset.sym;}),"
            "  roleOk: rows.every(function(r){return r.getAttribute('role')==='button' && r.getAttribute('tabindex')==='0';}),"
            "  note: (document.querySelector('#verd .boardcut')||{}).textContent,"
            "  muScore: mu ? mu.children[2].textContent : null,"
            "  muChips: muChips.map(function(c){return {cls:c.className, text:c.textContent, tip:c.getAttribute('data-tip')};}),"
            "  wide: document.documentElement.scrollWidth > document.documentElement.clientWidth};"
            "})()"
        )
        assert "1 buy" in st["stat"] and "1 sell" in st["stat"] and "2 hold" in st["stat"] and "1 no call" in st["stat"], st["stat"]
        # 2026-09-11 attempt #3: two dynamic disclosures on the header -- the
        # regime chip (bear here, with SPY's signed distance to its 200-day,
        # U+2212 never ASCII minus) and the brief-verdict chip (the brief
        # score left the composite; its word and score print instead).
        assert "bear · SPY −3.1% vs 200d" in st["stat"], st["stat"]
        assert "brief CAUTIOUS (+3)" in st["stat"], st["stat"]
        assert "-3.1" not in st["stat"], st["stat"]
        assert st["syms"] == ["XLE", "MU"], f"default cut should show only BUY/SELL, score desc: {st['syms']}"
        assert st["roleOk"], "every verdicts row needs role=button + tabindex=0"
        assert "show all 5" in st["note"], st["note"]
        assert st["muScore"] and "−51" in st["muScore"] and "-51" not in st["muScore"], st["muScore"]
        assert not st["wide"], f"sideways scroll at {width}px"

        # P1 (2026-09-11): a resolved input chip outside the display's neutral
        # band leads with its own sign, never hue alone (u/d chips); a chip
        # inside the band ("m") or with no reading at all ("x", dashed) stays
        # unsigned — MU's fixture exercises all three (u/d, m, and x chips).
        resolved_chips = [c for c in st["muChips"] if "x" not in c["cls"].split()]
        assert resolved_chips, "MU should have resolved input chips"
        signed_chips = [c for c in resolved_chips if "u" in c["cls"].split() or "d" in c["cls"].split()]
        neutral_chips = [c for c in resolved_chips if "m" in c["cls"].split()]
        assert signed_chips and neutral_chips, f"MU fixture should exercise both signed and neutral chips: {st['muChips']}"
        for c in signed_chips:
            assert c["text"][0] in ("+", "−"), f"chip {c['text']!r} ({c['cls']}) has no sign lead"
        for c in neutral_chips:
            assert c["text"][0] not in ("+", "−"), f"neutral chip {c['text']!r} should be unsigned"
        null_chips = [c for c in st["muChips"] if "x" in c["cls"].split()]
        for c in null_chips:
            assert c["text"][0] not in ("+", "−"), f"null chip {c['text']!r} should be unsigned"

        # P3 (2026-09-11): every resolved chip's own displayed points figure
        # sums EXACTLY to the row's own displayed score — largest-remainder
        # allocation (verdictPointsFor), not each chip rounding independently.
        pts_total = 0
        for c in resolved_chips:
            m = re.search(r"·\s*([+−]?\d+)\s*pt", c["tip"] or "")
            assert m, f"chip tip carries no points figure: {c['tip']!r}"
            pts_total += int(m.group(1).replace("−", "-"))
        mu_score_val = int(st["muScore"].strip().replace("−", "-"))
        assert pts_total == mu_score_val, f"chip points {pts_total} != displayed score {mu_score_val}"

        page.click("#showall-verd")
        page.wait_for_timeout(200)
        st2 = page.evaluate(
            "(function(){"
            " var rows=[].slice.call(document.querySelectorAll('#verd tr.rw[data-sym]'));"
            " var ram=document.querySelector('#verd tr[data-sym=\"RAM\"]');"
            " var lly=document.querySelector('#verd tr[data-sym=\"LLY\"]');"
            " var zzz=document.querySelector('#verd tr[data-sym=\"ZZZ\"]');"
            " var zzzScoreEl=zzz ? zzz.children[2].querySelector('b.vscore') : null;"
            " return {n: rows.length,"
            "  ramCall: ram ? ram.children[1].textContent : null,"
            "  llyCall: lly ? lly.children[1].textContent : null,"
            "  zzzScoreText: zzzScoreEl ? zzzScoreEl.textContent : null,"
            "  zzzScoreCls: zzzScoreEl ? zzzScoreEl.className : null};"
            "})()"
        )
        assert st2["n"] == 5, st2["n"]
        assert st2["ramCall"] and "NO CALL" in st2["ramCall"] and "2 of 8 inputs" in st2["ramCall"], st2["ramCall"]
        assert st2["llyCall"] and "HOLD" in st2["llyCall"] and "earnings in 2d" in st2["llyCall"], st2["llyCall"]

        # P2 (2026-09-11): a score of exactly 0 (ZZZ here — LLY's own score
        # moved to a real BUY-range number the earnings gate holds to HOLD,
        # 2026-09-11 fixture fix) renders neutral ("m"), never the green "u"
        # a bare `score<0 ? "d":"u"` two-way test used to paint it.
        assert st2["zzzScoreText"] == "0", st2["zzzScoreText"]
        zzz_cls = (st2["zzzScoreCls"] or "").split()
        assert "m" in zzz_cls and "u" not in zzz_cls and "d" not in zzz_cls, st2["zzzScoreCls"]
    finally:
        page.close()


@pytest.mark.parametrize("width,height", WIDTHS)
def test_verdict_pill_on_conviction_row(browser, server, width, height):
    page = browser.new_page(viewport={"width": width, "height": height})
    page_errors: list[str] = []
    page.on("pageerror", lambda err: page_errors.append(str(err)))
    page.route("**/*", _route_json(server, VERDICT_PAYLOAD))
    page.goto(f"{server}/index.html", wait_until="load")
    page.wait_for_timeout(3000)
    try:
        assert page_errors == [], f"index.html @ {width}px threw: {page_errors}"
        st = page.evaluate(
            "(function(){"
            " var el=document.querySelector('#conv tr[data-sym=\"MU\"] .pill.vs');"
            " return {found: !!el, text: el ? el.textContent : null};"
            "})()"
        )
        assert st["found"], "no .pill.vs on the Conviction MU row — MU scores 62 so it clears the default cut"
        assert st["text"] == "SELL", st["text"]
    finally:
        page.close()


@pytest.mark.parametrize("width,height", WIDTHS)
def test_watchlist_sorts_by_verdict(browser, server, width, height):
    page = browser.new_page(viewport={"width": width, "height": height})
    page_errors: list[str] = []
    page.on("pageerror", lambda err: page_errors.append(str(err)))
    # XLE isn't in RAIL_GROUPS — add it as a custom pin so its verdict has a
    # rail row to sort, same mechanism a real reader would use.
    page.add_init_script(
        "localStorage.setItem('desk.wl.sort', 'verd');"
        "localStorage.setItem('desk.wl.collapsed', 'false');"
        "localStorage.setItem('desk.wl.custom', JSON.stringify([{sym:'XLE'}]));"
    )
    page.route("**/*", _route_json(server, VERDICT_PAYLOAD))
    page.goto(f"{server}/index.html", wait_until="load")
    page.wait_for_timeout(3000)
    try:
        assert page_errors == [], f"index.html @ {width}px threw: {page_errors}"
        st = page.evaluate(
            "(function(){"
            " var rows=[].slice.call(document.querySelectorAll('#wl .wr[data-sym]'));"
            " return {sel: document.getElementById('wlsel') && document.getElementById('wlsel').value,"
            "  syms: rows.map(function(r){return r.dataset.sym;}),"
            "  verd: rows.map(function(r){var v=r.querySelector('.wlverd'); return v ? v.textContent.replace(/\\s+/g,' ').trim() : null;})};"
            "})()"
        )
        assert st["sel"] == "verd", f"select reads {st['sel']!r}"
        idx = {s: i for i, s in enumerate(st["syms"])}
        assert idx["XLE"] < idx["LLY"] < idx["MU"], f"ranked order wrong: {st['syms'][:10]}"
        # RAM has a verdict entry but a null score (coverage gate failed) — it
        # sinks below every ranked call, same as a name with no entry at all.
        assert idx["RAM"] > idx["MU"], f"RAM (no call) ranked above a scored call: {st['syms'][:10]}"
        no_verdict = [s for s in st["syms"] if s not in ("XLE", "MU", "LLY", "RAM")]
        assert no_verdict, "expected at least one rail name with no verdict entry at all"
        assert min(idx[s] for s in no_verdict) > idx["MU"], \
            f"a no-verdict row ranked above a scored call: {st['syms'][:10]}"
        xle_line = st["verd"][idx["XLE"]]
        assert "+66" in xle_line and "BUY" in xle_line, xle_line   # XLE fixture score under the attempt #3 table
        no_verdict_line = st["verd"][idx[no_verdict[0]]]
        assert no_verdict_line == "no verdict", no_verdict_line
    finally:
        page.close()


@pytest.mark.parametrize("width,height", WIDTHS)
def test_verdicts_absent_keeps_slot(browser, server, width, height):
    page = browser.new_page(viewport={"width": width, "height": height})
    page_errors: list[str] = []
    page.on("pageerror", lambda err: page_errors.append(str(err)))
    page.route("**/*", _route_json(server, BRIEF_PAYLOAD))  # no "verdicts" key
    page.goto(f"{server}/index.html", wait_until="load")
    page.wait_for_timeout(3000)
    try:
        assert page_errors == [], f"index.html @ {width}px threw: {page_errors}"
        st = page.evaluate(
            "(function(){"
            " return {stat: document.getElementById('verdstat').textContent,"
            "  msg: (document.querySelector('#verd .boardmsg')||{}).textContent};"
            "})()"
        )
        assert "No verdicts in this publish" in (st["msg"] or ""), st["msg"]
        # ageStampHTML(undefined, ...) prints "" either way (BRIEF_PAYLOAD carries
        # no generated_at_ct), so the stat is the bare "—" the empty branch
        # prints, with ageStampHTML's own age/stale text (if any) appended
        # after it — startswith rather than equality since which follows
        # depends on the wall-clock hour the suite runs at (2026-09-11 P9).
        assert st["stat"].startswith("—"), st["stat"]
    finally:
        page.close()


# ── P4 (2026-09-11) ──────────────────────────────────────────────────────────
# stageVerdictHTML's "no entry" branch must distinguish a PINNED name the
# fetcher simply missed this cycle from a searched name outside the desk's
# tracked universe entirely — the same pinned test stageFrameworkHTML already
# uses (railHasSym(sym) || facts[sym] present).

P4_PAYLOAD = dict(
    BRIEF_PAYLOAD,
    facts={"MU": {}},
    verdicts={
        "v": 1, "thresholds": {"buy": 35, "sell": -35},
        "min_weight": 50, "min_inputs": 3, "earnings_gate_days": 3,
        "order": VERDICT_ORDER, "weights": VERDICT_WEIGHTS,
        "counts": {"buy": 0, "sell": 0, "hold": 0, "none": 0},
        "by_ticker": {},   # MU is pinned (carries a facts entry) but scanner-missed this cycle
    },
)


@pytest.mark.parametrize("width,height", WIDTHS)
def test_stage_verdict_pinned_name_missing_this_cycle(browser, server, width, height):
    page = browser.new_page(viewport={"width": width, "height": height})
    page_errors: list[str] = []
    page.on("pageerror", lambda err: page_errors.append(str(err)))
    page.route("**/*", _route_json(server, P4_PAYLOAD))
    page.goto(f"{server}/index.html", wait_until="load")
    page.wait_for_timeout(3000)
    try:
        assert page_errors == [], f"index.html @ {width}px threw: {page_errors}"
        page.evaluate("stageShow('MU')")
        page.wait_for_timeout(300)
        text = page.evaluate("document.getElementById('stagetabbody').textContent")
        assert "in this publish" in text, text
        assert "outside" not in text, text
    finally:
        page.close()
