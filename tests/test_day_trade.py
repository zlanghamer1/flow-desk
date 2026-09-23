"""Independent tests for the day-trade tools feature (added 2026-09-23).

Written from the SPEC —
`docs/superpowers/specs/2026-09-23-day-trade-tools-design.md`, whose
"Architect review" and "Build contract" sections are binding — not from the
implementation, which another session is writing into index.html at the same
time. This file never imports or reads index.html's new code; it only relies
on the DOM ids, globals and storage keys the Build contract promises.

Network policy, unchanged from tests/test_page_smoke.py: every request to the
local static server is served from fixtures; the TradingView scanner
(scanner.tradingview.com, both /america/scan and /global/scan) is answered
from an in-memory fixture keyed by REQUESTED COLUMN NAME (never by column
index), so these tests stay correct however the real implementation orders or
extends its `columns` arrays; every other external host is aborted. A page
test never reaches the network.

Clock: pure functions in the Build contract (dtSize, dtLevels, dtJournalAdd,
dtJournalVoid, dayState, dayCapsSet, dtPhase, gapMode) all take an explicit
`now` argument, so most scenarios pass a `new Date(<epoch ms>)` literal built
from a fixed CT wall-clock time and need no browser clock at all. Tests that
exercise real rendering/interaction (the dt tab, day limits form, gappers
board, hotkeys, layout) pin Playwright's page.clock instead. IMPORTANT: with
page.clock installed, requestAnimationFrame is faked along with every other
timer (confirmed against this Playwright build — the default "raf" polling
mode of wait_for_function never resolves), so every wait_for_function call
made after `page.clock.install(...)` passes an explicit numeric `polling=`
value. page.wait_for_timeout(...) is unaffected (it is a real, driver-side
wait) and is used for small settle pauses.

Run locally the same way as test_page_smoke.py:

    python3 -m pip install pytest playwright
    python3 -m playwright install chromium        # or set PW_CHROMIUM
    python3 -m pytest tests/test_day_trade.py -q

These tests are expected to FAIL until the implementation lands — that is
the point of writing them from the spec ahead of time. `--collect-only` must
succeed regardless.
"""
from __future__ import annotations

import http.server
import json
import os
import re
import socketserver
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
pytest.importorskip("playwright", reason="browser test needs playwright")
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
WIDTHS = [(1440, 900), (390, 844)]

EXPECTED_CONSOLE = re.compile(r"Failed to load resource|net::ERR_FAILED|net::ERR_ABORTED")


# ── server/browser fixtures (copied from test_page_smoke.py on purpose — this
#    file must not import from it) ──────────────────────────────────────────

class _Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, *args):
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
        except Exception as e:
            pytest.skip(f"no Chromium available to launch: {e}".splitlines()[0])
        try:
            yield b
        finally:
            b.close()


# ── CT wall-clock helpers ────────────────────────────────────────────────────
# US Central is UTC-5 (CDT) in September, UTC-6 (CST) after the first Sunday
# in November. Pass dst=False for the 2026-11-27 half-day scenario.

def ct_ms(y, mo, d, hh, mm, dst=True):
    offset = 5 if dst else 6
    dt = datetime(y, mo, d, hh, mm, tzinfo=timezone.utc) + timedelta(hours=offset)
    return int(dt.timestamp() * 1000)


def ct_s(y, mo, d, hh, mm, dst=True):
    return ct_ms(y, mo, d, hh, mm, dst) // 1000


def now_js(y, mo, d, hh, mm, dst=True):
    """A JS `new Date(...)` literal for a CT wall-clock time, for passing as
    the explicit `now` argument every pure Build-contract function takes."""
    return "new Date(%d)" % ct_ms(y, mo, d, hh, mm, dst)


# ── bars.json fixture (v4 shape: quints + sessions + bar_dates) ─────────────
# 250 flat closes (so a 50/200-day average lands close to 1000 regardless of
# whether seriesFull's existing "append today's live close" behavior kicks
# in, which depends on the REAL wall-clock day the suite happens to run on,
# not on any `now` these tests pass in) with the single most-recent row
# (2026-09-22, the trading day immediately before the 2026-09-23 "today" used
# everywhere below) overridden to distinct, individually-checkable OHLCV.

def _weekdays_ending(end_y, end_mo, end_d, n):
    d = datetime(end_y, end_mo, end_d)
    out = []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.strftime("%Y-%m-%d"))
        d -= timedelta(days=1)
    out.reverse()
    return out


PREV_DAY_OPEN, PREV_DAY_HIGH, PREV_DAY_LOW, PREV_DAY_CLOSE, PREV_DAY_VOL = (
    1030.10, 1042.50, 1028.10, 1036.50, 21_000_000)


def build_bars_payload(n=250):
    sessions = _weekdays_ending(2026, 9, 22, n)
    assert sessions[-1] == "2026-09-22", sessions[-1]
    rows = [[1000.0, 1004.0, 996.0, 1000.0, 20_000_000] for _ in sessions]
    rows[-1] = [PREV_DAY_OPEN, PREV_DAY_HIGH, PREV_DAY_LOW, PREV_DAY_CLOSE, PREV_DAY_VOL]
    return {"built": "2026-09-22", "v": 4, "sessions": sessions, "bar_dates": {},
            "bars": {"MU": rows}}


# ── TradingView scanner fixtures, looked up by COLUMN NAME ──────────────────

MU_TV = "NASDAQ:MU"


def mu_row(**over):
    """Default scanner row for MU: an "open" phase on 2026-09-23 where `time`
    already reads today (the delayed feed has rolled over), matching Levels
    scenario (a). Callers override individual columns per scenario."""
    row = {
        "rtc": 1050.25, "change": 1.31, "close": 1050.25,
        "open": 1045.00, "high": 1058.30, "low": 1041.10, "volume": 9_000_000,
        "change_abs": 13.75,
        "premarket_close": 1042.10, "premarket_change": 0.54, "premarket_volume": 120_000,
        "premarket_high": 1043.00, "premarket_low": 1038.50,
        "premarket_time": ct_s(2026, 9, 23, 3, 0),
        "postmarket_close": None, "postmarket_change": None,
        "ATR": 24.50,
        "time": ct_s(2026, 9, 23, 8, 30),
        "VWAP|5": 1049.30,
        "time|5": ct_s(2026, 9, 23, 9, 25),
        "relative_volume_10d_calc": 1.10,
    }
    row.update(over)
    return row


def gap_row(**over):
    row = {
        "name": "TICK", "description": "Test Co", "close": 50.0, "change": 3.0,
        "premarket_change": None, "premarket_volume": None,
        "postmarket_change": None, "postmarket_volume": None,
        "volume": 2_000_000, "relative_volume_10d_calc": 1.5,
        "float_shares_outstanding_current": 5.0e8,
        "gap": 1.0, "change_from_open": 0.5,
        "earnings_release_date": None, "earnings_release_next_date": None,
        "type": "stock", "typespecs": ["common"],
        "time": ct_s(2026, 9, 23, 8, 30),
    }
    row.update(over)
    return row


GAPPERS_GOOD = {
    "NASDAQ:AAA": gap_row(name="AAA", description="Alpha Co", close=42.0, change=9.5, volume=5_000_000),
    "NASDAQ:BBB": gap_row(name="BBB", description="Beta Co", close=18.0, change=-7.2, volume=6_000_000),
    "NASDAQ:CCC": gap_row(name="CCC", description="Gamma Co", close=101.0, change=5.5, volume=4_000_000),
}


def _cols(body):
    return body.get("columns") or []


def _scan_reply(cols, rows_by_tv):
    data = [{"s": s, "d": [f.get(c) for c in cols]} for s, f in rows_by_tv.items()]
    return {"totalCount": len(data), "data": data}


def make_scan_handler(poll_fixtures=None, gappers=None):
    """poll_fixtures: {tv_symbol: {col_name: value}} answers the symbols.tickers
    30-second poll. gappers: callable(call_number, body) -> {tv_symbol: {...}}
    (a real reply, possibly {} for a 0-row miss) or None (abort the request,
    simulating a hard network failure) — answers the filter-array gappers
    scan. Every symbol not present in poll_fixtures is simply omitted from the
    reply, matching the real scanner's own behavior for an unresolved row."""
    state = {"n": 0}

    def handler(body):
        cols = _cols(body)
        want = (body.get("symbols") or {}).get("tickers")
        if want is not None:
            fx = poll_fixtures or {}
            rows = {s: fx[s] for s in want if s in fx}
            return _scan_reply(cols, rows)
        if "filter" in body:
            state["n"] += 1
            if gappers is None:
                return {"totalCount": 0, "data": []}
            rows = gappers(state["n"], body)
            if rows is None:
                return None
            return _scan_reply(cols, rows)
        return {"totalCount": 0, "data": []}

    return handler


def _gappers_provider(good_rows):
    """First gappers scan returns good_rows; every later one is a 0-row miss
    (the spec's own example: a good scan, then an empty one)."""
    def provider(call_n, body):
        return good_rows if call_n == 1 else {}
    return provider


def make_route(server, data_payload=None, bars_payload=None, bars_intraday=None, scan_handler=None):
    def route(r):
        url = r.request.url
        if "/data/data.json" in url:
            if data_payload is None:
                r.abort()
            else:
                r.fulfill(status=200, content_type="application/json", body=json.dumps(data_payload))
        elif "/data/bars_intraday.json" in url:
            if bars_intraday is None:
                r.abort()
            else:
                r.fulfill(status=200, content_type="application/json", body=json.dumps(bars_intraday))
        elif "/data/bars.json" in url:
            if bars_payload is None:
                r.abort()
            else:
                r.fulfill(status=200, content_type="application/json", body=json.dumps(bars_payload))
        elif "scanner.tradingview.com" in url and r.request.method == "POST":
            if scan_handler is None:
                r.abort()
                return
            try:
                body = json.loads(r.request.post_data or "{}")
            except Exception:
                body = {}
            reply = scan_handler(body)
            if reply is None:
                r.abort()
            else:
                r.fulfill(status=200, content_type="application/json", body=json.dumps(reply))
        elif url.startswith(server) or url.startswith("data:"):
            r.continue_()
        else:
            r.abort()
    return route


# Minimal data.json — trimmed from test_page_smoke.py's BRIEF_PAYLOAD shape.
DT_DATA = {
    "generated_at": "2026-09-23T14:00:00Z", "generated_at_ct": "2026-09-23 09:00 CT",
    "market_state": "open", "session_date": "2026-09-23",
    "brief": {"date": "2026-09-23", "verdict": "CAUTIOUS", "score": 0, "plain_words": "t",
              "backdrop": None, "gap_note": None, "sectors": [], "retreat_watch": [],
              "havens": [], "havens_totals": None, "whales_hiding": [], "fed_hike": None,
              "semi_flow": None, "stale": False},
    "fed_odds": None, "fund_flows": None, "fund_flows_history": None,
    "conviction": [], "swing": [], "big_orders": [], "etf_flow": [],
    "catalysts": [], "news": {"items": [], "by_ticker": {}}, "facts": {"MU": {}},
}


# ── helpers to load a page ───────────────────────────────────────────────────

def _pure_page(browser, server):
    """A page for calling pure Build-contract functions via page.evaluate.
    data.json is served (minimal); bars.json and the scanner are aborted by
    default — tests that need them build their own route instead."""
    page = browser.new_page()
    page_errors = []
    page.on("pageerror", lambda e: page_errors.append(str(e)))
    page.route("**/*", make_route(server, data_payload=DT_DATA))
    page.goto(f"{server}/index.html", wait_until="load")
    return page, page_errors


def _dt_page(browser, server, bars_payload=None, poll_fixtures=None, gappers=None,
             viewport=None, pin_ms=None):
    """A page wired for DOM-level day-trade checks: data.json, bars.json and
    the scanner all served from fixtures. Pins page.clock when pin_ms is
    given (must happen before goto)."""
    page = browser.new_page(viewport=viewport) if viewport else browser.new_page()
    page_errors = []
    console_errors = []
    page.on("pageerror", lambda e: page_errors.append(str(e)))
    page.on("console", lambda m: console_errors.append(m.text)
            if m.type == "error" and not EXPECTED_CONSOLE.search(m.text) else None)
    page.route("**/*", make_route(
        server, data_payload=DT_DATA, bars_payload=bars_payload,
        scan_handler=make_scan_handler(poll_fixtures=poll_fixtures, gappers=gappers)))
    if pin_ms is not None:
        # Playwright's Python clock takes a number as SECONDS since the epoch
        # (a datetime works too). Passing milliseconds put every pinned page
        # in the year 58698 — a "closed" day — so no DOM test ran in the
        # session phase it named. Pinned by test_pinned_clock_lands_on_the_ct_time.
        page.clock.install(time=pin_ms / 1000)
    page.goto(f"{server}/index.html", wait_until="load")
    return page, page_errors, console_errors


def _open_dt_tab(page, sym="MU"):
    page.evaluate("stageShow(%r)" % sym)
    page.click('#stagetabs button[data-tab="dt"]')
    page.wait_for_function(
        "(s) => { var w=document.getElementById('dtwrap'); return w && w.dataset.dtsym===s; }",
        arg=sym, timeout=8000, polling=100)


# =============================================================================
# 1. dtSize — the size calculator (pure function)
# =============================================================================

def test_dt_size_long_entry_stop_and_targets(browser, server):
    page, errs = _pure_page(browser, server)
    try:
        r = page.evaluate("dtSize({acct:10000, riskPct:1, side:'long', entry:100, stop:98})")
        assert r["ok"] is True, r
        assert r["shares"] == 50, r
        assert r["risk"] == 100, r
        assert r["pos"] == 5000, r
        assert r["targets"] == [102, 104, 106], r
        assert r["slip2"] == 200, r
        assert errs == [], errs
    finally:
        page.close()


def test_dt_size_short_entry_stop_and_targets(browser, server):
    page, errs = _pure_page(browser, server)
    try:
        r = page.evaluate("dtSize({acct:10000, riskPct:1, side:'short', entry:50, stop:51})")
        assert r["ok"] is True, r
        assert r["shares"] == 100, r
        assert r["risk"] == 100, r
        assert r["pos"] == 5000, r
        assert r["targets"] == [49, 48, 47], r
        assert errs == [], errs
    finally:
        page.close()


def test_dt_size_short_3r_target_at_or_below_zero_is_null(browser, server):
    page, errs = _pure_page(browser, server)
    try:
        # entry 10, stop 14 -> diff 4 -> 1R=6, 2R=2, 3R=-2 (below zero -> null)
        r = page.evaluate("dtSize({acct:10000, riskPct:1, side:'short', entry:10, stop:14})")
        assert r["ok"] is True, r
        assert r["targets"][0] == 6 and r["targets"][1] == 2, r["targets"]
        assert r["targets"][2] is None, r["targets"]
        assert errs == [], errs
    finally:
        page.close()


DT_SIZE_REFUSALS = [
    ("stop missing", "dtSize({acct:10000, riskPct:1, side:'long', entry:100})"),
    ("stop equals entry", "dtSize({acct:10000, riskPct:1, side:'long', entry:100, stop:100})"),
    ("stop wrong side (long)", "dtSize({acct:10000, riskPct:1, side:'long', entry:100, stop:105})"),
    ("stop wrong side (short)", "dtSize({acct:10000, riskPct:1, side:'short', entry:100, stop:95})"),
    ("entry null", "dtSize({acct:10000, riskPct:1, side:'long', entry:null, stop:98})"),
    ("entry NaN", "dtSize({acct:10000, riskPct:1, side:'long', entry:NaN, stop:98})"),
    ("entry <= 0", "dtSize({acct:10000, riskPct:1, side:'long', entry:0, stop:-2})"),
    ("acct <= 0", "dtSize({acct:0, riskPct:1, side:'long', entry:100, stop:98})"),
    ("risk <= 0", "dtSize({acct:10000, riskPct:0, side:'long', entry:100, stop:98})"),
    ("risk budget smaller than one share's risk",
     "dtSize({acct:100, riskPct:1, side:'long', entry:100, stop:98})"),
]


@pytest.mark.parametrize("label,expr", DT_SIZE_REFUSALS, ids=[l for l, _ in DT_SIZE_REFUSALS])
def test_dt_size_refusals(browser, server, label, expr):
    page, errs = _pure_page(browser, server)
    try:
        r = page.evaluate(expr)
        assert r.get("ok") is False, f"{label}: expected ok:false, got {r}"
        assert isinstance(r.get("err"), str) and r["err"], f"{label}: expected a non-empty err string, got {r}"
        assert errs == [], errs
    finally:
        page.close()


# =============================================================================
# dtPhase / gapMode — the phase table, across every named example time
# =============================================================================

def test_dt_phase_and_gap_mode_across_sessions(browser, server):
    page, errs = _pure_page(browser, server)
    try:
        phase_cases = [
            (now_js(2026, 9, 23, 7, 0), "pre"),          # pre-market
            (now_js(2026, 9, 23, 9, 30), "open"),         # regular session
            (now_js(2026, 9, 23, 20, 0), "plan"),         # evening
            (now_js(2026, 9, 26, 12, 0), "plan"),         # Saturday: closed -> plan
            (now_js(2026, 11, 27, 12, 30, dst=False), "plan"),  # half day, after the noon close
        ]
        for now_expr, expected in phase_cases:
            phase = page.evaluate("dtPhase(%s)" % now_expr)
            assert phase == expected, f"dtPhase({now_expr}) = {phase!r}, expected {expected!r}"

        gap_cases = [
            (now_js(2026, 9, 23, 7, 0), "pre"),
            (now_js(2026, 9, 23, 9, 30), "open"),
            (now_js(2026, 9, 23, 17, 0), "post"),
            (now_js(2026, 9, 23, 20, 0), "last"),
        ]
        for now_expr, expected in gap_cases:
            gm = page.evaluate("gapMode(%s)" % now_expr)
            assert gm == expected, f"gapMode({now_expr}) = {gm!r}, expected {expected!r}"
        assert errs == [], errs
    finally:
        page.close()


# =============================================================================
# 2. Journal + day limits (pure functions, explicit `now`)
# =============================================================================

def test_day_limits_loss_cap_done_and_void_latches(browser, server):
    page, errs = _pure_page(browser, server)
    try:
        now = now_js(2026, 9, 23, 7, 0)  # pre-market, before any trade today

        caps_r = page.evaluate("dayCapsSet({loss:200, trades:3}, %s)" % now)
        assert caps_r.get("ok") is True, caps_r

        add1 = page.evaluate(
            "dtJournalAdd({sym:'MU', side:'long', shares:10, entry:100, exit:90, plan:true, note:''}, %s)" % now)
        assert add1.get("ok") is True and add1.get("id"), add1

        st1 = page.evaluate("dayState(%s)" % now)
        assert st1["n"] == 1, st1
        assert st1["pnl"] == -100, st1
        assert st1["budgetLeft"] == 100, st1
        assert st1["done"] is False, st1

        add2 = page.evaluate(
            "dtJournalAdd({sym:'MU', side:'long', shares:10, entry:100, exit:90, plan:true, note:''}, %s)" % now)
        assert add2.get("ok") is True, add2

        st2 = page.evaluate("dayState(%s)" % now)
        assert st2["done"] is True and st2["reason"] == "loss", st2

        page.evaluate("dtJournalVoid(%r, %s)" % (add1["id"], now))
        st3 = page.evaluate("dayState(%s)" % now)
        assert st3["done"] is True, "DONE must latch for the CT day even after voiding a today row"
        assert errs == [], errs
    finally:
        page.close()


def test_day_limits_trade_cap_and_zero_dollar_trade(browser, server):
    page, errs = _pure_page(browser, server)
    try:
        now = now_js(2026, 9, 23, 7, 0)
        page.evaluate("dayCapsSet({loss:100000, trades:3}, %s)" % now)

        # $0, win, $0 — three trades total, hitting the trade cap without
        # ever touching the (huge) loss cap.
        for exit_px in (100, 110, 100):
            r = page.evaluate(
                "dtJournalAdd({sym:'MU', side:'long', shares:10, entry:100, exit:%s, plan:true, note:''}, %s)"
                % (exit_px, now))
            assert r.get("ok") is True, r

        st = page.evaluate("dayState(%s)" % now)
        assert st["n"] == 3, st
        assert st["done"] is True and st["reason"] == "trades", st

        # dtJournalStats(rows)'s exact return shape is not in the Build
        # contract (unlike dtSize/dtLevels/dayState/dayCapsSet, which are
        # fully specified there), so this introspects generically for
        # win/loss-like numeric fields rather than asserting exact key names:
        # of the three logged trades, exactly one is a win and none is a
        # loss, so a $0 trade must be counted in neither bucket.
        rows = page.evaluate("dtJournal()")
        stats = page.evaluate("(r) => dtJournalStats(r)", rows)
        wins = losses = None
        for k, v in (stats or {}).items():
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                continue
            lk = k.lower()
            if "rate" in lk or "avg" in lk or "share" in lk:
                continue
            if "win" in lk:
                wins = v
            elif "loss" in lk:
                losses = v
        assert wins == 1, f"expected exactly 1 win among 3 trades incl. two $0 rows: {stats}"
        assert losses == 0, f"expected 0 losses (a $0 trade is neither): {stats}"
        assert errs == [], errs
    finally:
        page.close()


def test_day_caps_raise_locked_after_first_trade_lower_still_ok(browser, server):
    page, errs = _pure_page(browser, server)
    try:
        now = now_js(2026, 9, 23, 7, 0)
        r0 = page.evaluate("dayCapsSet({loss:500, trades:5}, %s)" % now)
        assert r0.get("ok") is True, r0

        page.evaluate(
            "dtJournalAdd({sym:'MU', side:'long', shares:1, entry:100, exit:99, plan:true, note:''}, %s)" % now)

        raise_r = page.evaluate("dayCapsSet({loss:1000, trades:5}, %s)" % now)
        assert raise_r.get("ok") is False, raise_r
        assert raise_r.get("err") == "locked until tomorrow", raise_r

        lower_r = page.evaluate("dayCapsSet({loss:100, trades:5}, %s)" % now)
        assert lower_r.get("ok") is True, lower_r
        assert errs == [], errs
    finally:
        page.close()


def test_day_caps_raise_locked_in_open_phase_even_with_no_trades(browser, server):
    page, errs = _pure_page(browser, server)
    try:
        pre_now = now_js(2026, 9, 23, 7, 0)
        page.evaluate("dayCapsSet({loss:200, trades:3}, %s)" % pre_now)

        open_now = now_js(2026, 9, 23, 9, 30)   # after 08:30 CT, no trades logged
        raise_r = page.evaluate("dayCapsSet({loss:300, trades:3}, %s)" % open_now)
        assert raise_r.get("ok") is False, raise_r
        assert raise_r.get("err") == "locked until tomorrow", raise_r
        assert errs == [], errs
    finally:
        page.close()


def test_day_state_profit_never_enlarges_budget_left(browser, server):
    page, errs = _pure_page(browser, server)
    try:
        now = now_js(2026, 9, 23, 7, 0)
        page.evaluate("dayCapsSet({loss:200, trades:5}, %s)" % now)
        page.evaluate(
            "dtJournalAdd({sym:'MU', side:'long', shares:10, entry:100, exit:110, plan:true, note:''}, %s)" % now)
        st = page.evaluate("dayState(%s)" % now)
        assert st["pnl"] == 100, st
        assert st["budgetLeft"] == 200, "a profit must never push budgetLeft past the cap: %r" % st
        assert errs == [], errs
    finally:
        page.close()


def test_day_journal_rows_key_by_ct_date_not_utc(browser, server):
    page, errs = _pure_page(browser, server)
    try:
        # 23:30 CT on 2026-09-23 is already 2026-09-24 04:30 UTC.
        late_now = now_js(2026, 9, 23, 23, 30)
        page.evaluate("dayCapsSet({loss:1000, trades:5}, %s)" % late_now)
        add = page.evaluate(
            "dtJournalAdd({sym:'MU', side:'long', shares:10, entry:100, exit:90, plan:true, note:''}, %s)"
            % late_now)
        assert add.get("ok") is True, add

        same_day = page.evaluate("dayState(%s)" % late_now)
        assert same_day["n"] == 1, same_day

        next_ct_day = now_js(2026, 9, 24, 7, 0)   # a genuinely new CT calendar day
        next_day = page.evaluate("dayState(%s)" % next_ct_day)
        assert next_day["n"] == 0, (
            "a trade logged at 23:30 CT rolled into the next UTC day's count: %r" % next_day)
        assert errs == [], errs
    finally:
        page.close()


# =============================================================================
# 3. dtLevels(sym, now) — the levels sheet per phase
# =============================================================================

def _boot_levels_page(browser, server, bars_payload, fixture):
    page = browser.new_page()
    page_errors = []
    page.on("pageerror", lambda e: page_errors.append(str(e)))
    page.route("**/*", make_route(
        server, data_payload=DT_DATA, bars_payload=bars_payload,
        scan_handler=make_scan_handler(poll_fixtures={MU_TV: fixture})))
    page.goto(f"{server}/index.html", wait_until="load")
    page.evaluate("() => pollTvPrices()")
    page.evaluate("() => ensureBars()")
    return page, page_errors


def test_dt_levels_open_phase_today_in_feed(browser, server):
    page, errs = _boot_levels_page(browser, server, build_bars_payload(), mu_row())
    try:
        levels = page.evaluate("dtLevels('MU', %s)" % now_js(2026, 9, 23, 9, 30))
        assert levels["phase"] == "open", levels
        rows = {r["k"]: r for r in levels["rows"]}

        for k, expected in (("open", 1045.00), ("hi", 1058.30), ("lo", 1041.10), ("vwap", 1049.30)):
            assert k in rows, f"missing row {k!r}: {levels['rows']}"
            assert rows[k]["px"] == pytest.approx(expected), (k, rows[k])
            # These describe the session forming right now, so they need no
            # date stamp of their own (spec: "label (dated, never
            # 'yesterday')" is about never being mistaken for an OLDER
            # session) — but they must never carry yesterday's date either.
            assert "22" not in rows[k]["label"], f"{k} must not read like yesterday's value: {rows[k]}"

        for k, expected in (("pdh", PREV_DAY_HIGH), ("pdl", PREV_DAY_LOW), ("pdc", PREV_DAY_CLOSE)):
            assert k in rows, f"missing row {k!r}: {levels['rows']}"
            assert rows[k]["px"] == pytest.approx(expected), (k, rows[k])
            assert "22" in rows[k]["label"], f"{k} label should be dated the prior day (22nd): {rows[k]}"
        assert errs == [], errs
    finally:
        page.close()


def test_dt_levels_open_phase_time_lag_no_today_dated_high_low(browser, server):
    fixture = mu_row(
        time=ct_s(2026, 9, 22, 8, 30),
        open=PREV_DAY_OPEN, high=PREV_DAY_HIGH, low=PREV_DAY_LOW, close=PREV_DAY_CLOSE,
        **{"VWAP|5": 1035.00, "time|5": ct_s(2026, 9, 22, 9, 25)},
    )
    page, errs = _boot_levels_page(browser, server, build_bars_payload(), fixture)
    try:
        levels = page.evaluate("dtLevels('MU', %s)" % now_js(2026, 9, 23, 8, 35))
        assert levels["phase"] == "open", levels
        rows = levels["rows"]

        hilo = [r for r in rows if r["k"] in ("hi", "lo")]
        assert hilo, f"expected hi/lo rows even before today reaches the feed: {rows}"
        for r in hilo:
            assert "23" not in r["label"], f"{r} must not be dated today while `time` is still yesterday"
            assert "22" in r["label"], f"{r} should carry yesterday's date"

        # There is no second, deeper "previous day" to show while today's own
        # session has not posted at all yet — if the implementation still
        # emits pdh/pdl/pdc rows here they must not carry a stale value.
        for r in rows:
            if r["k"] in ("pdh", "pdl", "pdc"):
                assert r["px"] is None, f"no real previous-previous-day value should print here: {r}"
        assert errs == [], errs
    finally:
        page.close()


def test_dt_levels_premarket_dated_check(browser, server):
    bars = build_bars_payload()
    base = dict(
        time=ct_s(2026, 9, 22, 8, 30),
        open=PREV_DAY_OPEN, high=PREV_DAY_HIGH, low=PREV_DAY_LOW, close=PREV_DAY_CLOSE,
    )
    base["VWAP|5"] = 1035.00
    base["time|5"] = ct_s(2026, 9, 22, 9, 25)

    # (c1) premarket_time dated TODAY -> pmh/pml present with the right px.
    fixture_today = mu_row(premarket_time=ct_s(2026, 9, 23, 3, 0),
                            premarket_high=1043.00, premarket_low=1038.50, **base)
    page1, errs1 = _boot_levels_page(browser, server, bars, fixture_today)
    try:
        levels = page1.evaluate("dtLevels('MU', %s)" % now_js(2026, 9, 23, 7, 0))
        assert levels["phase"] == "pre", levels
        rows = {r["k"]: r for r in levels["rows"]}
        assert rows["pmh"]["px"] == pytest.approx(1043.00), rows.get("pmh")
        assert rows["pml"]["px"] == pytest.approx(1038.50), rows.get("pml")
        assert errs1 == [], errs1
    finally:
        page1.close()

    # (c2) premarket_time dated YESTERDAY -> pmh/pml missing, never a stale px.
    fixture_stale = mu_row(premarket_time=ct_s(2026, 9, 22, 3, 0),
                            premarket_high=1043.00, premarket_low=1038.50, **base)
    page2, errs2 = _boot_levels_page(browser, server, bars, fixture_stale)
    try:
        levels = page2.evaluate("dtLevels('MU', %s)" % now_js(2026, 9, 23, 7, 0))
        rows = {r["k"]: r for r in levels["rows"]}
        assert rows["pmh"]["px"] is None, rows.get("pmh")
        assert isinstance(rows["pmh"].get("miss"), str) and rows["pmh"]["miss"], rows.get("pmh")
        assert rows["pml"]["px"] is None, rows.get("pml")
        assert isinstance(rows["pml"].get("miss"), str) and rows["pml"]["miss"], rows.get("pml")
        assert errs2 == [], errs2
    finally:
        page2.close()


def test_dt_levels_missing_vwap_never_zero_and_moving_averages_present(browser, server):
    fixture = mu_row(time=ct_s(2026, 9, 23, 8, 30), open=1045.00, high=1058.30, low=1041.10,
                      close=1050.25, change_abs=13.75)
    fixture.pop("VWAP|5", None)   # vendor did not answer this column this cycle
    page, errs = _boot_levels_page(browser, server, build_bars_payload(), fixture)
    try:
        levels = page.evaluate("dtLevels('MU', %s)" % now_js(2026, 9, 23, 20, 0))  # plan phase
        assert levels["phase"] == "plan", levels
        rows = {r["k"]: r for r in levels["rows"]}

        assert rows["vwap"]["px"] is None, rows.get("vwap")
        assert rows["vwap"]["px"] != 0, "a missing VWAP must never render as zero"
        assert isinstance(rows["vwap"].get("miss"), str) and rows["vwap"]["miss"], rows.get("vwap")

        assert "m50" in rows and rows["m50"]["px"] is not None, rows.get("m50")
        assert "m200" in rows and rows["m200"]["px"] is not None, rows.get("m200")
        # bars.json's MU closes are flat at 1000.0 (see build_bars_payload's
        # docstring) precisely so this doesn't need to hand-simulate
        # whichever live/synthetic bar seriesFull may or may not append.
        assert abs(rows["m50"]["px"] - 1000.0) < 10, rows["m50"]
        assert abs(rows["m200"]["px"] - 1000.0) < 10, rows["m200"]
        assert errs == [], errs
    finally:
        page.close()


# =============================================================================
# 4. Day trade tab DOM
# =============================================================================

def test_dt_tab_renders_calculator_and_stop_buttons(browser, server):
    pin_ms = ct_ms(2026, 9, 23, 9, 30)
    page, errs, cerrs = _dt_page(browser, server, bars_payload=build_bars_payload(),
                                  poll_fixtures={MU_TV: mu_row()}, pin_ms=pin_ms)
    try:
        page.wait_for_function(
            "() => window.LIVE && window.LIVE['NASDAQ:MU'] && window.LIVE['NASDAQ:MU'].px != null",
            timeout=8000, polling=100)
        _open_dt_tab(page, "MU")

        assert page.locator("#dtwrap .dtrow").count() > 0, "expected at least one level row"
        assert page.locator("#dtcalc").count() == 1
        for sel in ("#dtacct", "#dtrisk", "#dtentry", "#dtstopin"):
            assert page.locator(sel).count() == 1, f"missing calculator input {sel}"

        page.fill("#dtacct", "10000")
        page.fill("#dtrisk", "1")
        page.fill("#dtentry", "100")
        page.fill("#dtstopin", "98")
        page.wait_for_function(
            "() => { var e=document.querySelector('#dtout .dtres[data-k=\"shares\"]');"
            " return e && e.textContent.trim().length>0; }", timeout=5000, polling=100)
        shares_text = page.locator('#dtout .dtres[data-k="shares"]').inner_text()
        assert "50" in shares_text, shares_text

        non_atr_stops = page.locator('#dtwrap .dtrow:not([data-lv="atr"]):not(.miss) button.dtstop')
        assert non_atr_stops.count() > 0, "expected at least one clickable .dtstop button"
        px = non_atr_stops.first.get_attribute("data-px")
        assert px, "a .dtstop button needs a data-px to copy into the calculator"
        non_atr_stops.first.click()
        # Compare numerically, not as strings: the input may re-format the
        # copied price (trailing zeros, decimal places) rather than echoing
        # data-px verbatim, which the Build contract does not pin either way.
        page.wait_for_function(
            "(v) => { var el=document.getElementById('dtstopin');"
            " var n=parseFloat(el.value); return isFinite(n) && Math.abs(n-parseFloat(v))<0.005; }",
            arg=px, timeout=5000, polling=100)

        atr_row = page.locator('#dtwrap .dtrow[data-lv="atr"]')
        if atr_row.count():
            assert atr_row.locator("button.dtstop").count() == 0, "ATR is not a settable stop level"

        # Typing survives the 30-second re-render (focus and value both).
        page.fill("#dtentry", "123.45")
        page.evaluate("document.getElementById('dtentry').focus()")
        page.clock.run_for(31000)
        page.wait_for_timeout(300)
        val = page.evaluate("document.getElementById('dtentry').value")
        focused = page.evaluate("document.activeElement && document.activeElement.id")
        assert val == "123.45", f"input value did not survive the 30s re-render: {val!r}"
        assert focused == "dtentry", f"focus did not survive the 30s re-render: {focused!r}"

        assert errs == [], errs
        assert cerrs == [], cerrs
    finally:
        page.close()


# =============================================================================
# 5. Day limits section DOM
# =============================================================================

def test_day_limits_dom_log_form_and_done_badge(browser, server):
    pin_ms = ct_ms(2026, 9, 23, 7, 0)
    page, errs, cerrs = _dt_page(browser, server, bars_payload=build_bars_payload(),
                                  poll_fixtures={MU_TV: mu_row()}, pin_ms=pin_ms)
    try:
        assert page.locator("#s-day").count() == 1
        for sel in ("#daycaploss", "#daycaptrades", "#daycapsave", "#dtl-sym", "#dtl-side",
                    "#dtl-sh", "#dtl-en", "#dtl-ex", "#dtl-add", "#daytoday", "#daystats"):
            assert page.locator(sel).count() >= 1, f"missing day-limits element {sel}"

        page.fill("#daycaploss", "200")
        page.fill("#daycaptrades", "3")
        page.click("#daycapsave")
        page.wait_for_function(
            "() => (document.getElementById('daycapmsg').textContent||'').length>0",
            timeout=5000, polling=100)

        page.fill("#dtl-sym", "MU")
        page.select_option("#dtl-side", "long")
        page.fill("#dtl-sh", "10")
        page.fill("#dtl-en", "100")
        page.fill("#dtl-ex", "90")
        page.click("#dtl-add")
        page.wait_for_function(
            "() => document.querySelectorAll('#daytoday tr[data-id]').length >= 1",
            timeout=5000, polling=100)
        before_stat = page.locator("#daystat").inner_text()
        assert before_stat.strip(), "expected a non-empty day-limits header stat"

        page.fill("#dtl-sh", "10")
        page.fill("#dtl-en", "100")
        page.fill("#dtl-ex", "90")
        # This trade reaches the $200 cap, so the first click only asks for a
        # confirmation (the typo guard: a mistyped exit would otherwise lock
        # the day, and a void never refunds the cap).
        page.click("#dtl-add")
        page.wait_for_function(
            "() => /confirm/.test(document.getElementById('dtl-msg').textContent||'')",
            timeout=5000, polling=100)
        assert page.evaluate("document.querySelectorAll('#daytoday tr[data-id]').length") == 1, \
            "a cap-reaching trade must not log on the first click"
        page.click("#dtl-add")
        page.wait_for_function(
            "() => document.querySelectorAll('#daytoday tr[data-id]').length >= 2",
            timeout=5000, polling=100)

        after_stat = page.locator("#daystat").inner_text()
        assert after_stat != before_stat, "the header stat should change once the loss cap is hit"
        assert "DONE" in page.locator("#day").inner_text().upper(), "expected the DONE badge once the cap is hit"

        assert errs == [], errs
        assert cerrs == [], cerrs
    finally:
        page.close()


# =============================================================================
# 6. Gappers & movers section DOM
# =============================================================================

def test_gappers_dom_renders_rows_and_click_focuses_and_opens_dt_tab(browser, server):
    pin_ms = ct_ms(2026, 9, 23, 9, 30)
    page, errs, cerrs = _dt_page(browser, server, bars_payload=build_bars_payload(),
                                  poll_fixtures={MU_TV: mu_row()},
                                  gappers=_gappers_provider(GAPPERS_GOOD), pin_ms=pin_ms)
    try:
        assert page.locator("#s-gap").count() == 1
        page.wait_for_function(
            "() => document.querySelectorAll('#gap tr.rw[data-sym]').length>0",
            timeout=8000, polling=100)
        rows = page.locator("#gap tr.rw[data-sym]")
        n = rows.count()
        assert n >= 3, f"expected the fixture's 3 rows to render, got {n}"
        for i in range(n):
            r = rows.nth(i)
            assert r.get_attribute("role") == "button", "every gappers row needs role=button"
            assert r.get_attribute("tabindex") == "0", "every gappers row needs tabindex=0"

        stat = page.locator("#gapstat").inner_text().lower()
        assert "delayed" in stat, stat

        first_sym = rows.first.get_attribute("data-sym")
        rows.first.click()
        page.wait_for_function(
            "(s) => window.STAGE && STAGE.sym === s", arg=first_sym, timeout=5000, polling=100)
        page.wait_for_function(
            "() => window.STAGE && STAGE.tab === 'dt'", timeout=5000, polling=100)

        assert errs == [], errs
        assert cerrs == [], cerrs
    finally:
        page.close()


def test_gappers_dom_empty_scan_on_first_load_shows_reason(browser, server):
    pin_ms = ct_ms(2026, 9, 23, 9, 30)
    page, errs, cerrs = _dt_page(browser, server, bars_payload=build_bars_payload(),
                                  poll_fixtures={MU_TV: mu_row()}, gappers=lambda n, b: {},
                                  pin_ms=pin_ms)
    try:
        assert page.locator("#s-gap").count() == 1
        page.wait_for_function(
            "() => (document.getElementById('gapnote').textContent||'').length>0",
            timeout=8000, polling=100)
        assert page.locator("#gap tr.rw[data-sym]").count() == 0
        assert errs == [], errs
        assert cerrs == [], cerrs
    finally:
        page.close()


def test_gappers_dom_empty_rescan_keeps_last_good_rows(browser, server):
    pin_ms = ct_ms(2026, 9, 23, 9, 30)
    page, errs, cerrs = _dt_page(browser, server, bars_payload=build_bars_payload(),
                                  poll_fixtures={MU_TV: mu_row()},
                                  gappers=_gappers_provider(GAPPERS_GOOD), pin_ms=pin_ms)
    try:
        page.wait_for_function(
            "() => document.querySelectorAll('#gap tr.rw[data-sym]').length>0",
            timeout=8000, polling=100)
        first_count = page.locator("#gap tr.rw[data-sym]").count()
        assert first_count >= 3, first_count

        # Advance past the 60-second gappers refresh; the fixture's second
        # (and every later) scan is a 0-row miss.
        page.clock.run_for(61_000)
        page.wait_for_timeout(500)

        rows_after = page.locator("#gap tr.rw[data-sym]")
        assert rows_after.count() >= 3, "an empty rescan must keep the previously-rendered good rows"
        note = page.locator("#gapnote").inner_text()
        assert note.strip(), "expected a non-empty reason line after a miss"
        assert errs == [], errs
        assert cerrs == [], cerrs
    finally:
        page.close()


# =============================================================================
# 7. Hotkeys
# =============================================================================

def test_hotkeys_bracket_nav_digit_interval_and_input_guard(browser, server):
    pin_ms = ct_ms(2026, 9, 23, 9, 30)
    page, errs, cerrs = _dt_page(browser, server, bars_payload=build_bars_payload(),
                                  poll_fixtures={MU_TV: mu_row()}, pin_ms=pin_ms)
    try:
        page.evaluate("stageShow('MU')")
        page.locator("body").click(position={"x": 2, "y": 2})
        assert page.evaluate("STAGE.sym") == "MU"

        page.keyboard.press("]")
        page.wait_for_function("() => STAGE.sym !== 'MU'", timeout=5000, polling=100)
        moved = page.evaluate("STAGE.sym")
        rail_syms = page.evaluate(
            "[].slice.call(document.querySelectorAll('#wl [data-sym]')).map(e => e.dataset.sym)")
        assert moved in rail_syms, f"']' should move focus to another rail name, got {moved!r}"

        page.keyboard.press("[")
        page.wait_for_function("() => STAGE.sym === 'MU'", timeout=5000, polling=100)

        page.keyboard.press("1")
        page.wait_for_function("() => STAGE.iv === '15m'", timeout=5000, polling=100)

        _open_dt_tab(page, "MU")
        page.evaluate("STAGE.iv = '4H'")   # a baseline distinct from '15m'
        page.click("#dtl-note")
        page.keyboard.type("1")
        note_val = page.evaluate("document.getElementById('dtl-note').value")
        assert "1" in note_val, note_val
        iv_after = page.evaluate("STAGE.iv")
        assert iv_after == "4H", f"typing '1' inside an input must not change STAGE.iv, got {iv_after!r}"

        assert errs == [], errs
        assert cerrs == [], cerrs
    finally:
        page.close()


# =============================================================================
# 8. Layout — no sideways scroll with the new sections present
# =============================================================================

@pytest.mark.parametrize("width,height", WIDTHS)
def test_day_trade_sections_no_sideways_scroll(browser, server, width, height):
    pin_ms = ct_ms(2026, 9, 23, 9, 30)
    page, errs, cerrs = _dt_page(
        browser, server, bars_payload=build_bars_payload(), poll_fixtures={MU_TV: mu_row()},
        gappers=_gappers_provider(GAPPERS_GOOD), pin_ms=pin_ms, viewport={"width": width, "height": height})
    try:
        _open_dt_tab(page, "MU")
        page.wait_for_function(
            "() => document.getElementById('s-day') && document.getElementById('s-gap')",
            timeout=5000, polling=100)
        page.wait_for_function(
            "() => document.querySelectorAll('#gap tr.rw[data-sym]').length>0",
            timeout=8000, polling=100)
        page.wait_for_timeout(300)

        overflow = page.evaluate(
            "document.documentElement.scrollWidth - document.documentElement.clientWidth")
        assert overflow <= 0, f"sideways scroll at {width}px: {overflow}px"
        assert errs == [], f"{width}px threw: {errs}"
        assert cerrs == [], f"{width}px console errors: {cerrs}"
    finally:
        page.close()


# =============================================================================
# 9. No explanation text in the new sections
# =============================================================================

def test_no_long_explanation_data_tips_in_new_sections(browser, server):
    pin_ms = ct_ms(2026, 9, 23, 9, 30)
    page, errs, cerrs = _dt_page(
        browser, server, bars_payload=build_bars_payload(), poll_fixtures={MU_TV: mu_row()},
        gappers=_gappers_provider(GAPPERS_GOOD), pin_ms=pin_ms)
    try:
        _open_dt_tab(page, "MU")
        page.wait_for_function(
            "() => document.getElementById('s-day') && document.getElementById('s-gap')",
            timeout=5000, polling=100)
        page.wait_for_function(
            "() => document.querySelectorAll('#gap tr.rw[data-sym]').length>0",
            timeout=8000, polling=100)

        long_tips = page.evaluate(
            "(function(){"
            " var out=[];"
            " ['#dtwrap','#s-day','#s-gap'].forEach(function(sel){"
            "   var root=document.querySelector(sel); if(!root) return;"
            "   root.querySelectorAll('[data-tip]').forEach(function(el){"
            "     var t=el.getAttribute('data-tip')||'';"
            "     if(t.length>60) out.push({sel:sel, tag:el.tagName, tip:t});"
            "   });"
            " });"
            " return out;"
            "})()")
        assert long_tips == [], f"explanation-length data-tip attributes found: {long_tips}"
        assert errs == [], errs
        assert cerrs == [], cerrs
    finally:
        page.close()


# =============================================================================
# 10. Review findings (2026-09-23 adversarial code review) — each fix pinned
# =============================================================================

def test_void_never_refunds_the_caps(browser, server):
    """A voided row still counts: its trade toward the trade cap and its loss
    (never its gain) toward the loss cap. log -> void -> log used to run four
    trades and -$1,349 against a $500 / 3-trade cap while the panel read OPEN."""
    page, errs = _pure_page(browser, server)
    try:
        now = now_js(2026, 9, 23, 7, 0)
        assert page.evaluate("dayCapsSet({loss:500, trades:3}, %s)" % now)["ok"] is True
        a = page.evaluate("dtJournalAdd({sym:'MU', side:'long', shares:10, entry:100, exit:55, plan:false, note:''}, %s)" % now)
        assert page.evaluate("dtJournalVoid(%r, %s)" % (a["id"], now))["ok"] is True
        st = page.evaluate("dayState(%s)" % now)
        assert st["budgetLeft"] == pytest.approx(50), st
        assert st["n"] == 1 and st["nVoid"] == 1, st
        # A voided WIN never counts toward the budget.
        b = page.evaluate("dtJournalAdd({sym:'MU', side:'long', shares:10, entry:100, exit:110, plan:false, note:''}, %s)" % now)
        page.evaluate("dtJournalVoid(%r, %s)" % (b["id"], now))
        st2 = page.evaluate("dayState(%s)" % now)
        assert st2["pnl"] == pytest.approx(-450), st2
        assert st2["n"] == 2, st2
        # The stats drop voided rows entirely.
        stats = page.evaluate("dtJournalStats()")
        assert stats["n"] == 0, stats
        assert errs == [], errs
    finally:
        page.close()


def test_void_window_closes_after_ten_minutes(browser, server):
    page, errs = _pure_page(browser, server)
    try:
        a = page.evaluate("dtJournalAdd({sym:'MU', side:'long', shares:1, entry:100, exit:101, plan:false, note:''}, %s)"
                          % now_js(2026, 9, 23, 7, 0))
        late = page.evaluate("dtJournalVoid(%r, %s)" % (a["id"], now_js(2026, 9, 23, 7, 11)))
        assert late["ok"] is False and "final" in late["err"], late
        assert errs == [], errs
    finally:
        page.close()


def test_dt_size_caps_at_the_account_cash(browser, server):
    """A tight stop sized 500 shares ($548K) on a $25K account; the size stops
    at what the account can pay for and says so."""
    page, errs = _pure_page(browser, server)
    try:
        r = page.evaluate("dtSize({acct:25000, riskPct:1, side:'long', entry:1096, stop:1095.5})")
        assert r["ok"] is True, r
        assert r["capped"] is True and r["shares"] == 22 and r["riskShares"] == 500, r
        assert r["pos"] <= 25000, r
        un = page.evaluate("dtSize({acct:10000, riskPct:1, side:'long', entry:100, stop:98})")
        assert un["capped"] is False and un["shares"] == 50, un
        assert errs == [], errs
    finally:
        page.close()


@pytest.mark.parametrize("t5_hhmm,final", [((14, 45), False), ((14, 55), True)])
def test_levels_after_close_lag_never_calls_a_running_price_the_close(browser, server, t5_hhmm, final):
    """For ~16 minutes after the close the delayed feed still prints the
    session's last minutes; its `close` is a running price until the feed's
    last 5-minute bar reaches the bell."""
    fx = mu_row(**{"time|5": ct_s(2026, 9, 23, *t5_hhmm)})
    page, errs = _boot_levels_page(browser, server, build_bars_payload(), fx)
    try:
        lv = page.evaluate("dtLevels('MU', %s)" % now_js(2026, 9, 23, 15, 5))
        assert lv["phase"] == "plan", lv
        rows = {r["k"]: r for r in lv["rows"]}
        if final:
            assert rows["close"]["label"].endswith("close"), rows["close"]
            assert not lv.get("closePending"), lv
        else:
            assert "last" in rows["close"]["label"] and "close" not in rows["close"]["label"], rows["close"]
            assert "so far" in rows["hi"]["label"], rows["hi"]
            assert lv.get("closePending") is True, lv
        assert errs == [], errs
    finally:
        page.close()


def test_gap_backoff_holds_after_a_failed_first_scan(browser, server):
    """GAP.key moves only on success, so gating on it refetched every tick
    after a failed first scan (40 requests in 10 minutes against an HTTP 500)."""
    page, errs, cerrs = _dt_page(browser, server, bars_payload=build_bars_payload(),
                                  poll_fixtures={MU_TV: mu_row()},
                                  gappers=lambda n, body: None, pin_ms=ct_ms(2026, 9, 23, 9, 30))
    try:
        page.wait_for_function("() => GAP.fails >= 1 && !GAP.inflight", timeout=8000, polling=100)
        refired = page.evaluate("(function(){ gapTick(GAP.lastAttempt + 20000); return !!GAP.inflight; })()")
        assert refired is False, "a failed scan must back off, not refetch on the next tick"
        refired2 = page.evaluate("(function(){ gapTick(GAP.lastAttempt + 31000); return !!GAP.inflight; })()")
        assert refired2 is True, "after the backoff window the scan should retry"
        assert errs == [], errs
    finally:
        page.close()


def test_gap_price_floor_reads_the_price_the_column_shows(browser, server):
    page, errs = _pure_page(browser, server)
    try:
        def floor_col(mode, hh):
            return page.evaluate(
                "(function(){ var b = gapScanBodies(%r, {dir:'up', px:5, stk:true}, %s)[0];"
                " return b.filter.filter(function(f){ return f.operation==='egreater' && f.right===5; }).map(function(f){ return f.left; }); })()"
                % (mode, now_js(2026, 9, 23, hh, 0)))
        assert floor_col("pre", 7) == ["premarket_close"]
        assert floor_col("post", 16) == ["postmarket_close"]
        assert floor_col("open", 10) == ["close"]
        assert errs == [], errs
    finally:
        page.close()


def test_entry_does_not_move_while_the_reader_edits_it(browser, server):
    page, errs, cerrs = _dt_page(browser, server, bars_payload=build_bars_payload(),
                                  poll_fixtures={MU_TV: mu_row()}, pin_ms=ct_ms(2026, 9, 23, 9, 30))
    try:
        page.wait_for_function("() => !!liveBySym('MU')", timeout=8000, polling=100)
        _open_dt_tab(page)
        page.focus("#dtentry")
        before = page.evaluate("DT.entry")
        page.evaluate("liveBySym('MU').px = 999.99; dtTabUpdate();")
        assert page.evaluate("DT.entry") == before, "the entry changed under a focused field"
        assert errs == [], errs
    finally:
        page.close()


def test_d_hotkey_from_the_heatmap_switches_to_the_chart(browser, server):
    page, errs, cerrs = _dt_page(browser, server, bars_payload=build_bars_payload(),
                                  poll_fixtures={MU_TV: mu_row()}, pin_ms=ct_ms(2026, 9, 23, 9, 30))
    try:
        page.evaluate("stageShow('MU'); stageSetView('heat');")
        page.evaluate("document.activeElement && document.activeElement.blur()")
        page.keyboard.press("d")
        st = page.evaluate("({view: STAGE.view, tab: STAGE.tab, wrap: !!document.getElementById('dtwrap')})")
        assert st == {"view": "chart", "tab": "dt", "wrap": True}, st
        assert errs == [], errs
    finally:
        page.close()


def test_bars_file_current_rule(browser, server):
    """bars.json built before today (on a trading day) lacks yesterday's bar;
    it is not today's fetch and is re-checked on a timer."""
    page, errs = _pure_page(browser, server)
    try:
        assert page.evaluate("barsFileCurrent({built:'2026-09-22'}, %s)" % now_js(2026, 9, 23, 10, 0)) is False
        assert page.evaluate("barsFileCurrent({built:'2026-09-23'}, %s)" % now_js(2026, 9, 23, 10, 0)) is True
        assert page.evaluate("barsFileCurrent({built:'2026-09-25'}, %s)" % now_js(2026, 9, 26, 10, 0)) is True
        assert errs == [], errs
    finally:
        page.close()


def test_pinned_clock_lands_on_the_ct_time(browser, server):
    """Guards the harness itself: every DOM test above names a CT session, and
    a mis-scaled pin silently ran them all on a closed day in the year 58698."""
    page, errs, cerrs = _dt_page(browser, server, bars_payload=build_bars_payload(),
                                  poll_fixtures={MU_TV: mu_row()}, pin_ms=ct_ms(2026, 9, 23, 9, 30))
    try:
        st = page.evaluate("({key: ctDateKey(new Date()), min: ctMinutesOfDay(new Date()), sess: priceSessionNow()})")
        assert st == {"key": "2026-09-23", "min": 9*60 + 30, "sess": "open"}, st
        assert errs == [], errs
    finally:
        page.close()


def test_click_inside_the_day_trade_tab_does_not_rechart(browser, server):
    """#dtwrap once carried data-sym, so the page-wide row delegate re-charted
    the symbol (zoom reset, focus lost) on a click at any plain text in it."""
    page, errs, cerrs = _dt_page(browser, server, bars_payload=build_bars_payload(),
                                  poll_fixtures={MU_TV: mu_row()}, pin_ms=ct_ms(2026, 9, 23, 9, 30))
    try:
        # start() charts its boot symbol once data.json lands; wait for that
        # first, so the count below sees only what the clicks cause.
        page.wait_for_function("() => !!liveBySym('MU') && !!STATE.data && STAGE.sym", timeout=8000, polling=100)
        page.wait_for_timeout(300)
        _open_dt_tab(page)
        page.evaluate("window.__shows = 0; var _ss = stageShow; stageShow = function(){ window.__shows++; return _ss.apply(this, arguments); }; 0;")
        page.click("#dtcalc h3")
        page.click("#dthead")
        assert page.evaluate("window.__shows") == 0, "a click inside the Day trade tab re-charted the symbol"
        assert page.locator("#dtwrap[data-sym]").count() == 0, "#dtwrap must not carry data-sym"
        assert errs == [], errs
    finally:
        page.close()


def test_restore_rejects_a_bad_time_and_a_stored_one_cannot_stop_the_boot(browser, server):
    page, errs = _pure_page(browser, server)
    try:
        bad = json.dumps({"journal": [{"id": "r9", "day": "2026-09-23", "t": 9e15, "sym": "MU", "side": "long",
                                       "shares": 1, "entry": 1, "exit": 2}]})
        r = page.evaluate("(t) => dayRestore(t, %s)" % now_js(2026, 9, 23, 7, 0), bad)
        assert r["ok"] is True and r["added"] == 0 and r["skipped"] == 1, r
        assert errs == [], errs
    finally:
        page.close()
    # A bad row already in storage (from before the validation) must not stop start().
    page = browser.new_page()
    errs2 = []
    page.on("pageerror", lambda e: errs2.append(str(e)))
    page.add_init_script("try{ localStorage.setItem('desk.day.journal', JSON.stringify([{id:'x', day:'2026-09-23', t:9e15, sym:'MU', side:'long', shares:1, entry:1, exit:2}])); }catch(e){}")
    page.route("**/*", make_route(server, data_payload=DT_DATA))
    try:
        page.goto(f"{server}/index.html", wait_until="load")
        page.wait_for_function("() => !!STATE.data", timeout=8000, polling=100)
        assert errs2 == [], errs2
    finally:
        page.close()


def test_settings_stick_when_storage_throws(browser, server):
    page = browser.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.add_init_script("Storage.prototype.setItem = function(){ throw new Error('blocked'); };"
                         "Storage.prototype.getItem = function(){ throw new Error('blocked'); };")
    page.route("**/*", make_route(server, data_payload=DT_DATA, bars_payload=build_bars_payload(),
                                  scan_handler=make_scan_handler(poll_fixtures={MU_TV: mu_row()},
                                                                 gappers=_gappers_provider(GAPPERS_GOOD))))
    try:
        page.goto(f"{server}/index.html", wait_until="load")
        page.wait_for_function("() => !!document.querySelector('#gapfilters button[data-gdir=\"up\"]')", timeout=8000, polling=100)
        page.click('#gapfilters button[data-gdir="up"]')
        assert page.evaluate("gapFilters().dir") == "up"
        assert page.get_attribute('#gapfilters button[data-gdir="up"]', "aria-pressed") == "true"
        page.evaluate("dtStoreSetting('desk.dt.acct', '25000')")
        assert page.evaluate("dtReadAcct()") == 25000
        assert errs == [], errs
    finally:
        page.close()


def test_opening_gappers_with_the_keyboard_scans(browser, server):
    page = browser.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.add_init_script("try{ localStorage.setItem('desk.s-gap', '1'); }catch(e){}")
    page.route("**/*", make_route(server, data_payload=DT_DATA, bars_payload=build_bars_payload(),
                                  scan_handler=make_scan_handler(poll_fixtures={MU_TV: mu_row()},
                                                                 gappers=_gappers_provider(GAPPERS_GOOD))))
    try:
        page.goto(f"{server}/index.html", wait_until="load")
        page.wait_for_function("() => document.getElementById('s-gap').classList.contains('closed')", timeout=8000, polling=100)
        assert page.evaluate("GAP.lastAttempt") == 0, "a closed section must not scan"
        page.focus("#s-gap .sh")
        page.keyboard.press("Enter")
        page.wait_for_function("() => GAP.lastAttempt > 0", timeout=8000, polling=100)
        page.wait_for_function("() => document.querySelectorAll('#gap tr.rw[data-sym]').length > 0", timeout=8000, polling=100)
        assert errs == [], errs
    finally:
        page.close()
