"""Flow Desk context layer — fetcher/context.py.

Run: python3 -m pytest fetcher/test_context.py -q

Every test injects a fake `_get(url, headers) -> bytes` at the same seam
context.py's real code uses, so nothing in this file ever touches the
network — a fake that receives an unexpected URL raises AssertionError
immediately rather than silently returning something plausible, so a test
that should skip the network (no token, fresh hourly gate) actually proves
it via an assertion failure if the implementation regresses.

What these tests defend, roughly in order of how badly each would mislead
Zach or leak a secret if it broke:

1. A missing VAULT_READ_TOKEN must never attempt a vault request (a
   misconfigured/absent secret should degrade silently, not throw, and
   definitely not accidentally probe a private repo unauthenticated).
2. The csv-mirror-wins precedence: Zach's hand-kept econ_calendar.csv is the
   verified source and must beat the raw TV scrape on a same-day conflict.
3. Anchors (next FOMC, next CPI, each pinned name's next earnings) survive
   past the 28-day display window — that's the whole point of calling them
   anchors instead of just letting the window drop them.
4. facts fields are None, never 0, when TradingView doesn't have them — a
   silent 0 for e.g. beta would misrepresent a real (if unknown) number.
5. The OpEx calendar's third-Friday math is right across a month boundary
   and correctly relabels quarter-end months (quadruple witching).
6. The two independent gates (hourly context fetch, daily bars build) each
   skip their own network work when fresh, and each still lets the OTHER
   one run when only it is stale.
7. (wave 3, 2026-08-15) The news per-ticker cap guarantees other tagged
   names room on the board without silently dropping items below the total
   cap, and never reorders the final list out of newest-first.
8. (wave 3) bars.json v3's volume never gets zero-filled when unknown, the
   2y history bump never widens avg_move's own basis, and a bars_sig
   mismatch forces a same-day rebuild instead of serving a stale-shape cache.
9. (wave 3) A Yahoo earnings row's missing revenue is backfilled from the
   same symbol's stockanalysis.com quarterly series ONLY — never a guessed
   or zero-filled number, and rev_est/rev_surprise_pct are never touched.
"""
from __future__ import annotations

import json
import sys
import urllib.error
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import context  # noqa: E402


def _boom(url, headers):
    raise AssertionError(f"should not have called the network: {url}")


def _econ_row(d, title, importance, time_ct="00:00", source="tv_calendar", ticker=None):
    return {
        "date": d, "time_ct": time_ct, "title": title, "importance": importance,
        "kind": "econ", "ticker": ticker, "session": None,
        "forecast": None, "prior": None, "actual": None,
        "anchor": False, "source": source,
    }


def _yahoo_json(closes, opens=None, highs=None, lows=None, volumes=None):
    """Build a v8 chart API response. By default open=high=low=close (fine
    for tests that only care about the close-derived arithmetic); pass
    opens/highs/lows explicitly to test real OHLC divergence. `volumes` is
    OMITTED entirely by default (no "volume" key at all) — matching a real
    malformed/short response and exercising _extract_yahoo_ohlcv's fail-soft
    "no volume array -> every row's v is None" path; pass it explicitly to
    test real volume values (including None entries mid-array)."""
    quote = {
        "open": opens if opens is not None else list(closes),
        "high": highs if highs is not None else list(closes),
        "low": lows if lows is not None else list(closes),
        "close": closes,
    }
    if volumes is not None:
        quote["volume"] = volumes
    return json.dumps({"chart": {"result": [{"indicators": {"quote": [quote]}}]}}).encode()


def _news_json(items):
    return json.dumps({"items": items}).encode()


def _sa_skip_data_json():
    """A stockanalysis.com __data.json response whose last node is "skip"
    (unchanged) — makes _fetch_sa_page return None cleanly. Used by tests
    that don't care about the fund-sidecar builder's specifics but need
    SOME response for its (now unconditional, on the bars-rebuild gate)
    stockanalysis.com requests."""
    return json.dumps({"nodes": [{"type": "skip"}, {"type": "skip"}, {"type": "skip"}]}).encode()


def _yahoo_crumb_and_empty_quotesummary(url):
    """Routes the Yahoo crumb dance + a quoteSummary call to an empty-but-
    valid response, for tests that don't care about fund-sidecar specifics."""
    if "fc.yahoo.com" in url:
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
    if "getcrumb" in url:
        return b"testcrumb"
    if "quoteSummary" in url:
        return json.dumps({"quoteSummary": {"result": [{}]}}).encode()
    return None


# ── 1. token-absent -> every vault fetch skips the network ─────────────────

def test_token_absent_all_vault_fetches_skip_network():
    assert context.fetch_vault_file("some/path.json", None, _get=_boom) is None
    assert context.fetch_brief(None, date(2026, 8, 15), _get=_boom) is None
    assert context.fetch_desk_private(None, _get=_boom) is None
    assert context.fetch_memory_events(None, _get=_boom) == []
    assert context.fetch_econ_calendar_csv(None, _get=_boom) == []


def test_empty_string_token_also_skips_network():
    assert context.fetch_vault_file("x", "", _get=_boom) is None


def test_token_present_but_request_fails_is_fail_soft():
    def fake_get(url, headers):
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
    assert context.fetch_vault_file("missing.json", "tok", _get=fake_get) is None
    assert context.fetch_memory_events("tok", _get=fake_get) == []


def test_fetch_vault_file_success_decodes_text_and_sends_bearer_header():
    seen = {}
    def fake_get(url, headers):
        seen["url"] = url
        seen["headers"] = headers
        return "hello vault".encode("utf-8")
    out = context.fetch_vault_file("market-data/data/brief_summary.json", "tok123", _get=fake_get)
    assert out == "hello vault"
    assert seen["url"] == context.VAULT_RAW_BASE + "market-data/data/brief_summary.json"
    assert seen["headers"]["Authorization"] == "Bearer tok123"


# ── fetch_brief: stale flag ──────────────────────────────────────────────────

def test_brief_stale_true_when_older_than_session_date():
    def fake_get(url, headers):
        return json.dumps({"date": "2026-08-13", "posture": "ok"}).encode()
    out = context.fetch_brief("tok", date(2026, 8, 15), _get=fake_get)
    assert out["stale"] is True


def test_brief_stale_false_when_same_as_session_date():
    def fake_get(url, headers):
        return json.dumps({"date": "2026-08-15"}).encode()
    out = context.fetch_brief("tok", date(2026, 8, 15), _get=fake_get)
    assert out["stale"] is False


def test_brief_stale_true_when_date_missing_or_malformed():
    def fake_get_missing(url, headers):
        return json.dumps({"posture": "ok"}).encode()
    def fake_get_bad(url, headers):
        return json.dumps({"date": "not-a-date"}).encode()
    assert context.fetch_brief("tok", date(2026, 8, 15), _get=fake_get_missing)["stale"] is True
    assert context.fetch_brief("tok", date(2026, 8, 15), _get=fake_get_bad)["stale"] is True


def test_brief_invalid_json_returns_none():
    def fake_get(url, headers):
        return b"not json{"
    assert context.fetch_brief("tok", date(2026, 8, 15), _get=fake_get) is None


# ── fetch_desk_private: opaque passthrough ──────────────────────────────────

def test_desk_private_passes_through_verbatim():
    payload = {"v": 1, "iv": "abc", "ct": "def"}
    def fake_get(url, headers):
        return json.dumps(payload).encode()
    assert context.fetch_desk_private("tok", _get=fake_get) == payload


def test_desk_private_invalid_json_returns_none():
    def fake_get(url, headers):
        return b"{not valid"
    assert context.fetch_desk_private("tok", _get=fake_get) is None


# ── fetch_memory_events: parsing + ticker heuristic ─────────────────────────

def test_looks_like_us_ticker_heuristic():
    assert context._looks_like_us_ticker("MU") is True
    assert context._looks_like_us_ticker("ALL") is False       # this CSV's own sentinel
    assert context._looks_like_us_ticker("005930") is False     # KRX numeric code
    assert context._looks_like_us_ticker("000660") is False
    assert context._looks_like_us_ticker("285A") is False       # TSE code, has a digit
    assert context._looks_like_us_ticker("") is False


def test_fetch_memory_events_parses_rows_and_maps_ticker():
    csv_text = (
        "date,scope,kind,event,importance,confidence,source\n"
        "2026-09-29,MU,earnings,Micron fiscal Q4 results,HIGH,estimated,thesis file\n"
        "2026-08-31,ALL,contract,DRAM contract prices settle,MEDIUM,estimated,TrendForce\n"
        "2026-10-08,005930,earnings,Samsung prelim results,MEDIUM,estimated,usual schedule\n"
    )
    def fake_get(url, headers):
        return csv_text.encode()
    rows = context.fetch_memory_events("tok", _get=fake_get)
    assert len(rows) == 3
    by_date = {r["date"]: r for r in rows}
    assert by_date["2026-09-29"]["ticker"] == "MU"
    assert by_date["2026-09-29"]["kind"] == "memory"
    assert by_date["2026-09-29"]["source"] == "memory_events"
    assert by_date["2026-08-31"]["ticker"] is None   # "ALL" sentinel
    assert by_date["2026-10-08"]["ticker"] is None   # KRX numeric code


def test_fetch_memory_events_drops_rows_with_bad_dates():
    csv_text = (
        "date,scope,kind,event,importance,confidence,source\n"
        "not-a-date,MU,earnings,bad row,HIGH,estimated,x\n"
        "2026-09-29,MU,earnings,good row,HIGH,estimated,x\n"
    )
    def fake_get(url, headers):
        return csv_text.encode()
    rows = context.fetch_memory_events("tok", _get=fake_get)
    assert len(rows) == 1
    assert rows[0]["title"] == "good row"


# ── fetch_econ_calendar_csv ──────────────────────────────────────────────────

def test_fetch_econ_calendar_csv_parses_rows():
    csv_text = (
        "date,time_ct,event,importance\n"
        "2026-09-16,13:00,FOMC Rate Decision + Summary of Economic Projections (dot plot),HIGH\n"
    )
    def fake_get(url, headers):
        return csv_text.encode()
    rows = context.fetch_econ_calendar_csv("tok", _get=fake_get)
    assert len(rows) == 1
    r = rows[0]
    assert r["date"] == "2026-09-16" and r["time_ct"] == "13:00"
    assert r["kind"] == "econ" and r["source"] == "econ_calendar"
    assert r["importance"] == "HIGH"


# ── fetch_econ_tv: importance mapping + CT conversion ───────────────────────

def test_econ_importance_mapping_and_ct_conversion():
    body = {
        "status": "ok",
        "result": [
            {"title": "Housing Starts", "date": "2026-08-18T12:30:00.000Z", "importance": 1,
             "forecast": 1.35, "previous": 1.427, "actual": None},
            {"title": "6-Month Bill Auction", "date": "2026-08-17T15:30:00.000Z", "importance": -1,
             "forecast": None, "previous": 3.83, "actual": None},
            {"title": "NY Empire State Manufacturing Index", "date": "2026-08-17T12:30:00.000Z",
             "importance": 0, "forecast": 10.2, "previous": 15.6, "actual": None},
        ],
    }
    def fake_get(url, headers):
        assert "economic-calendar.tradingview.com" in url
        assert headers.get("Origin") == "https://www.tradingview.com"
        assert headers.get("Referer")
        return json.dumps(body).encode()

    rows = context.fetch_econ_tv(days=28, _get=fake_get)
    by_title = {r["title"]: r for r in rows}
    assert by_title["Housing Starts"]["importance"] == "HIGH"
    # LOW rows are dropped at fetch since the 2026-08-15 importance floor —
    # see test_fetch_econ_tv_drops_low_importance for the rule itself.
    assert "6-Month Bill Auction" not in by_title
    assert by_title["NY Empire State Manufacturing Index"]["importance"] == "MEDIUM"

    hs = by_title["Housing Starts"]
    # 2026-08-18T12:30:00Z -> America/Chicago is CDT (UTC-5) in August -> 07:30 CT
    assert hs["date"] == "2026-08-18"
    assert hs["time_ct"] == "07:30"
    assert hs["forecast"] == pytest.approx(1.35)
    assert hs["prior"] == pytest.approx(1.427)
    assert hs["actual"] is None
    assert hs["kind"] == "econ" and hs["source"] == "tv_calendar"


def test_econ_tv_malformed_rows_are_skipped_not_fatal():
    body = {"result": [
        {"title": None, "date": "2026-08-18T12:30:00.000Z", "importance": 1},   # bad title
        {"title": "OK Row", "date": "not-a-date", "importance": 1},            # bad date
        "not even a dict",
        {"title": "Good Row", "date": "2026-08-18T12:30:00.000Z", "importance": 1},
    ]}
    def fake_get(url, headers):
        return json.dumps(body).encode()
    rows = context.fetch_econ_tv(_get=fake_get)
    assert [r["title"] for r in rows] == ["Good Row"]


def test_econ_tv_network_failure_returns_empty_list():
    def fake_get(url, headers):
        raise urllib.error.URLError("no route")
    assert context.fetch_econ_tv(_get=fake_get) == []


# ── csv-mirror-wins merge precedence ─────────────────────────────────────────

def test_csv_mirror_wins_same_day_similar_title_conflict():
    tv_rows = [_econ_row("2026-09-16", "FOMC Rate Decision", "HIGH", time_ct="08:00")]
    csv_rows = [_econ_row(
        "2026-09-16", "FOMC Rate Decision + Summary of Economic Projections (dot plot)",
        "HIGH", time_ct="13:00", source="econ_calendar",
    )]
    merged = context._dedup_econ(tv_rows, csv_rows)
    assert len(merged) == 1
    assert merged[0]["source"] == "econ_calendar"
    assert merged[0]["time_ct"] == "13:00"


def test_csv_and_tv_rows_on_different_days_both_survive():
    tv_rows = [_econ_row("2026-08-20", "Retail Sales", "HIGH")]
    csv_rows = [_econ_row("2026-08-21", "PPI", "HIGH", source="econ_calendar")]
    merged = context._dedup_econ(tv_rows, csv_rows)
    assert len(merged) == 2


def test_build_catalysts_applies_csv_precedence_end_to_end():
    session_date = date(2026, 8, 15)
    econ_rows = [_econ_row("2026-08-17", "CPI", "MEDIUM")]
    csv_mirror = [_econ_row("2026-08-17", "CPI (July)", "HIGH", source="econ_calendar")]
    cats = context.build_catalysts(econ_rows, [], {}, csv_mirror, session_date)
    cpi_rows = [c for c in cats if "cpi" in c["title"].lower()]
    assert len(cpi_rows) == 1
    assert cpi_rows[0]["source"] == "econ_calendar"
    assert cpi_rows[0]["importance"] == "HIGH"


# ── anchors past the horizon ─────────────────────────────────────────────────

def test_fomc_and_cpi_anchors_included_past_the_28_day_window():
    session_date = date(2026, 8, 15)   # window ends 2026-09-12
    csv_mirror = [
        _econ_row("2026-09-16", "FOMC Rate Decision + Summary of Economic Projections (dot plot)",
                  "HIGH", source="econ_calendar"),
        _econ_row("2026-09-20", "CPI (August)", "HIGH", source="econ_calendar"),
    ]
    cats = context.build_catalysts([], [], {}, csv_mirror, session_date)
    fomc = [c for c in cats if "fomc rate decision" in c["title"].lower()]
    cpi = [c for c in cats if c["title"].lower().startswith("cpi")]
    assert len(fomc) == 1 and fomc[0]["anchor"] is True and fomc[0]["date"] == "2026-09-16"
    assert len(cpi) == 1 and cpi[0]["anchor"] is True and cpi[0]["date"] == "2026-09-20"
    # neither row is duplicated
    assert len(cats) == len([c for c in cats if c["kind"] == "market"]) + 2


def test_fomc_anchor_promotes_existing_in_window_row_instead_of_duplicating():
    session_date = date(2026, 8, 15)
    csv_mirror = [_econ_row("2026-08-20", "FOMC Rate Decision", "HIGH", source="econ_calendar")]
    cats = context.build_catalysts([], [], {}, csv_mirror, session_date)
    fomc_rows = [c for c in cats if "fomc rate decision" in c["title"].lower()]
    assert len(fomc_rows) == 1
    assert fomc_rows[0]["anchor"] is True


def test_earnings_catalyst_always_anchor_true_in_or_out_of_window():
    session_date = date(2026, 8, 15)
    ts_near = int(datetime(2026, 8, 25, 20, 0, tzinfo=timezone.utc).timestamp())
    ts_far = int(datetime(2026, 10, 14, 20, 0, tzinfo=timezone.utc).timestamp())
    earn_map = {
        "MU": {"ts": ts_near, "days": 10},
        "CRWD": {"ts": ts_far, "days": 60},
    }
    cats = context.build_catalysts([], [], earn_map, [], session_date)
    by_ticker = {c["ticker"]: c for c in cats if c["kind"] == "earnings"}
    assert by_ticker["MU"]["anchor"] is True
    assert by_ticker["CRWD"]["anchor"] is True
    assert by_ticker["CRWD"]["date"] == "2026-10-14"
    assert by_ticker["MU"]["source"] == "tv_earnings"


def test_earnings_catalyst_skipped_when_days_is_none():
    earn_map = {"MU": {"ts": 123456, "days": None}}
    cats = context.build_catalysts([], [], earn_map, [], date(2026, 8, 15))
    assert not any(c["kind"] == "earnings" for c in cats)


# ── OpEx: third-Friday math + month boundary + quarter-end ──────────────────

def test_opex_third_friday_across_a_month_boundary():
    # Independently computed oracle (plain calendar arithmetic, not this
    # module): July 2026's third Friday is 2026-07-17; August 2026's is
    # 2026-08-21.
    rows = context._build_opex_rows(date(2026, 7, 1), days=55)
    by_date = {r["date"]: r for r in rows}
    assert by_date["2026-07-17"]["title"] == "Monthly options expiration"
    assert by_date["2026-07-17"]["importance"] == "MEDIUM"
    assert by_date["2026-08-21"]["title"] == "Monthly options expiration"
    assert by_date["2026-08-21"]["importance"] == "MEDIUM"
    # neighboring Fridays in each month stay weekly
    assert by_date["2026-07-10"]["title"] == "Weekly options expiration"
    assert by_date["2026-07-10"]["importance"] == "LOW"
    assert by_date["2026-08-14"]["title"] == "Weekly options expiration"
    for r in by_date.values():
        assert r["kind"] == "market" and r["source"] == "market_calendar"


def test_opex_quarter_end_month_gets_quadruple_witching_title():
    # September 2026's third Friday is 2026-09-18 (independently computed).
    rows = context._build_opex_rows(date(2026, 9, 1), days=28)
    by_date = {r["date"]: r for r in rows}
    assert by_date["2026-09-18"]["title"] == "Quarterly options expiration (quadruple witching)"
    assert by_date["2026-09-18"]["importance"] == "MEDIUM"


def test_opex_non_quarter_end_third_friday_is_plain_monthly():
    # August is not a quarter-end month.
    rows = context._build_opex_rows(date(2026, 8, 1), days=28)
    by_date = {r["date"]: r for r in rows}
    assert by_date["2026-08-21"]["title"] == "Monthly options expiration"


# ── catalysts sorted ─────────────────────────────────────────────────────────

def test_catalysts_are_sorted_by_date_then_time():
    session_date = date(2026, 8, 15)
    econ_rows = [
        _econ_row("2026-08-20", "Retail Sales", "HIGH", time_ct="07:30"),
        _econ_row("2026-08-16", "Some Note", "LOW", time_ct="09:00"),
    ]
    memory_rows = [{
        "date": "2026-08-18", "time_ct": None, "title": "Contract settle",
        "importance": "MEDIUM", "kind": "memory", "ticker": None, "session": None,
        "forecast": None, "prior": None, "actual": None, "anchor": False,
        "source": "memory_events",
    }]
    cats = context.build_catalysts(econ_rows, memory_rows, {}, [], session_date, days=28)
    ordering = [(c["date"], c.get("time_ct") or "") for c in cats]
    assert ordering == sorted(ordering)


# ── forward-fetch backfill (2026-08-22, round 9 finding #1) ─────────────────

def test_econ_tv_looks_back_26_hours_so_todays_release_can_carry_actual():
    """fetch_econ_tv's own from=now-only window meant a released row's
    `actual` could never be received at all -- TV only sets `actual` on a
    row whose time has already passed, and from=now excludes anything in
    the past by definition. Assert the request now looks back."""
    seen = {}
    def fake_get(url, headers):
        seen["url"] = url
        return json.dumps({"result": []}).encode()
    context.fetch_econ_tv(_get=fake_get)
    from urllib.parse import urlparse, parse_qs
    q = parse_qs(urlparse(seen["url"]).query)
    frm = datetime.fromisoformat(q["from"][0].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    assert frm < now - timedelta(hours=20)   # well before now -- a real lookback, not a rounding artifact
    assert frm > now - timedelta(hours=30)   # and bounded, not an unbounded backward window


def test_catalyst_still_fresh_econ_row_within_6h_grace():
    row = {"date": "2026-08-22", "time_ct": "07:30"}
    now_ct = datetime(2026, 8, 22, 12, 0, tzinfo=context.TZ_CT)     # 4.5h after release
    assert context._catalyst_still_fresh(row, now_ct)
    now_ct_late = datetime(2026, 8, 22, 14, 0, tzinfo=context.TZ_CT)  # 6.5h after release
    assert not context._catalyst_still_fresh(row, now_ct_late)


def test_catalyst_still_fresh_no_time_row_clears_at_end_of_day():
    row = {"date": "2026-08-22", "time_ct": None}
    assert context._catalyst_still_fresh(row, datetime(2026, 8, 22, 23, 0, tzinfo=context.TZ_CT))
    assert not context._catalyst_still_fresh(row, datetime(2026, 8, 23, 0, 30, tzinfo=context.TZ_CT))


def test_merge_catalysts_forward_backfills_released_row_the_fresh_fetch_dropped():
    """The exact bug: a from=now-only refetch no longer returns a HIGH row
    that released an hour ago, so build_catalysts alone would silently drop
    it. _merge_catalysts_forward must bring it back from the previous
    cycle's cache while it's still inside its own grace period."""
    prev = [_econ_row("2026-08-22", "Non Farm Payrolls", "HIGH", time_ct="07:30")]
    fresh = []   # this cycle's from=now fetch no longer includes it
    now_ct = datetime(2026, 8, 22, 9, 0, tzinfo=context.TZ_CT)   # 1.5h after release
    merged = context._merge_catalysts_forward(fresh, prev, now_ct)
    assert any(r["title"] == "Non Farm Payrolls" for r in merged)


def test_merge_catalysts_forward_drops_stale_previous_row_past_grace():
    prev = [_econ_row("2026-08-22", "Non Farm Payrolls", "HIGH", time_ct="07:30")]
    fresh = []
    now_ct = datetime(2026, 8, 22, 14, 0, tzinfo=context.TZ_CT)   # 6.5h after release
    merged = context._merge_catalysts_forward(fresh, prev, now_ct)
    assert not any(r["title"] == "Non Farm Payrolls" for r in merged)


def test_merge_catalysts_forward_never_duplicates_a_row_still_in_the_fresh_fetch():
    row = _econ_row("2026-08-22", "CPI", "HIGH", time_ct="07:30")
    now_ct = datetime(2026, 8, 22, 8, 0, tzinfo=context.TZ_CT)
    merged = context._merge_catalysts_forward([row], [dict(row)], now_ct)
    assert len([r for r in merged if r["title"] == "CPI"]) == 1


def test_memory_rows_are_not_bounded_by_the_display_window():
    """memory_events.csv rows show regardless of how far out they are — the
    source is small and hand-curated, unlike the noisy TV econ feed."""
    session_date = date(2026, 8, 15)
    far_memory = [{
        "date": "2027-06-30", "time_ct": None, "title": "far-future contract note",
        "importance": "MEDIUM", "kind": "memory", "ticker": None, "session": None,
        "forecast": None, "prior": None, "actual": None, "anchor": False,
        "source": "memory_events",
    }]
    cats = context.build_catalysts([], far_memory, {}, [], session_date, days=28)
    assert any(c["title"] == "far-future contract note" for c in cats)


# ── facts: None-vs-0, earn_days ──────────────────────────────────────────────

def test_facts_missing_field_stays_none_not_zero():
    quotes = {
        "MU": {"hi52": 1255.0, "lo52": 113.46, "market_cap": 1.0e12, "beta": None,
               "avol": None, "rsi": 56.3, "earnings_ts": None},
    }
    facts = context.fetch_earnings_days(quotes, date(2026, 8, 15))
    assert facts["MU"]["beta"] is None
    assert facts["MU"]["avol"] is None
    assert facts["MU"]["short_pct"] is None
    assert facts["MU"]["earn_days"] is None
    assert facts["MU"]["hi52"] == 1255.0
    assert facts["MU"]["beta"] != 0
    assert facts["MU"]["avol"] != 0
    assert facts["MU"]["avg_move"] is None   # set later by build_context, not here


def test_earn_days_none_when_earnings_is_in_the_past_and_correct_when_future():
    session_date = date(2026, 8, 15)
    past_ts = int(datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc).timestamp())
    future_ts = int(datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc).timestamp())
    quotes = {"PAST": {"earnings_ts": past_ts}, "FUT": {"earnings_ts": future_ts}}
    facts = context.fetch_earnings_days(quotes, session_date)
    assert facts["PAST"]["earn_days"] is None
    assert facts["FUT"]["earn_days"] == 45


def test_short_pct_is_always_none_regardless_of_input():
    quotes = {"MU": {}}
    facts = context.fetch_earnings_days(quotes, date(2026, 8, 15))
    assert facts["MU"]["short_pct"] is None


# ── news: cap, ordering, rotation banner ─────────────────────────────────────

def test_news_cap_is_20_total_and_newest_first():
    def fake_get(url, headers):
        if "symbol:NASDAQ:MU" in url:
            items = [{"title": f"MU headline {i}", "published": 1000 + i,
                      "storyPath": f"/news/mu{i}/"} for i in range(15)]
        elif "symbol:NASDAQ:CRWD" in url:
            items = [{"title": f"CRWD headline {i}", "published": 2000 + i,
                      "storyPath": f"/news/crwd{i}/"} for i in range(15)]
        else:
            raise AssertionError(url)
        return _news_json(items)
    result = context.fetch_news(["NASDAQ:MU", "NASDAQ:CRWD"], _get=fake_get)
    assert result is not None
    assert len(result["items"]) == 20
    tss = [it["ts"] for it in result["items"]]
    assert tss == sorted(tss, reverse=True)
    assert result["items"][0]["ticker"] == "CRWD"   # highest published ts overall


def test_news_one_symbol_failing_does_not_block_the_others():
    def fake_get(url, headers):
        if "symbol:NASDAQ:BAD" in url:
            raise urllib.error.URLError("boom")
        return _news_json([{"title": "Good headline", "published": 500, "storyPath": "/n/1/"}])
    result = context.fetch_news(["NASDAQ:BAD", "NASDAQ:MU"], _get=fake_get)
    assert result is not None
    assert result["items"][0]["title"] == "Good headline"


def test_news_none_when_nothing_comes_back_at_all():
    def fake_get(url, headers):
        raise urllib.error.URLError("boom")
    assert context.fetch_news(["NASDAQ:MU"], _get=fake_get) is None


def test_rotation_banner_threshold_is_two_hits():
    def make(titles):
        items = [{"title": t, "published": 1000 - i, "storyPath": f"/n/{i}/"}
                  for i, t in enumerate(titles)]
        return _news_json(items)
    one_hit = context.fetch_news(
        ["NASDAQ:MU"],
        _get=lambda u, h: make(["Tech rotation hits chipmakers", "Quiet day for MU", "MU up 2%"]),
    )
    assert one_hit["rotation_banner"] is False
    two_hits = context.fetch_news(
        ["NASDAQ:MU"],
        _get=lambda u, h: make(["Tech rotation hits chipmakers", "Analysts warn of a pullback", "MU up 2%"]),
    )
    assert two_hits["rotation_banner"] is True


def test_news_url_falls_back_to_story_path_when_link_absent():
    def fake_get(url, headers):
        return _news_json([{"title": "T", "published": 1, "storyPath": "/news/x/"}])
    result = context.fetch_news(["NASDAQ:MU"], _get=fake_get)
    assert result["items"][0]["url"] == "https://www.tradingview.com/news/x/"


# ── news: per-ticker breadth cap (added 2026-08-15, wave 3, Task A) ─────────

def _cap_item(ticker, ts):
    return {"ticker": ticker, "title": f"{ticker} {ts}", "ts": str(ts), "url": None, "_sort": ts}


def test_apply_news_ticker_cap_guarantees_breadth_when_pool_has_enough_tickers():
    """6 tickers x 5 items, evenly interleaved by recency. 6*3 (cap) == 18 <=
    total_cap 20, so every ticker is GUARANTEED its 3 with room to spare —
    the core promise of ruling #1 ("want to see other names mentioned too")."""
    pooled = []
    ts = 30
    tickers = ["A", "B", "C", "D", "E", "F"]
    for _ in range(5):
        for t in tickers:
            pooled.append(_cap_item(t, ts))
            ts -= 1
    assert len(pooled) == 30
    result = context._apply_news_ticker_cap(pooled, total_cap=20, per_ticker_cap=3)
    assert len(result) == 20
    counts: dict[str, int] = {}
    for it in result:
        counts[it["ticker"]] = counts.get(it["ticker"], 0) + 1
    for t in tickers:
        assert counts[t] >= 3, f"{t} did not get its guaranteed 3 slots: {counts}"
    assert sum(counts.values()) == 20
    sorts = [it["_sort"] for it in result]
    assert sorts == sorted(sorts, reverse=True)   # newest-first overall, even after backfill


def test_apply_news_ticker_cap_backfills_from_dominant_ticker_on_a_narrow_pool():
    """Only 2 tickers in the pool: the cap alone can't reach total_cap, so
    backfill fills the rest from the capped-out ticker — a mega-cap can still
    dominate the COUNT (this is not a parity rule), but a smaller name that
    DOES have news no longer gets crowded out of the board entirely."""
    pooled = ([_cap_item("NVDA", 100 - i) for i in range(15)]
              + [_cap_item("MU", 50 - i) for i in range(2)])
    result = context._apply_news_ticker_cap(pooled, total_cap=10, per_ticker_cap=3)
    counts: dict[str, int] = {}
    for it in result:
        counts[it["ticker"]] = counts.get(it["ticker"], 0) + 1
    assert len(result) == 10
    assert counts["MU"] == 2     # MU's whole (small) supply survives
    assert counts["NVDA"] == 8    # backfilled to fill out the rest of total_cap


def test_apply_news_ticker_cap_under_total_pool_size_returns_everything():
    pooled = [_cap_item("A", 3), _cap_item("B", 2), _cap_item("A", 1)]
    result = context._apply_news_ticker_cap(pooled, total_cap=20, per_ticker_cap=3)
    assert len(result) == 3


def test_fetch_news_per_ticker_cap_lets_other_names_through_with_mega_caps_still_dominant():
    """Reproduces the exact live numbers NEWS_PER_TICKER_CAP was built to fix
    (Zach, 2026-08-15): a 20-item board where NVDA/AMZN/GOOGL alone held 14
    of 20 slots. After the cap: the big names keep the SAME counts here
    (mega-caps can still dominate — this cap does not force parity), but
    MU/LLY/COHR are now guaranteed a seat instead of being crowded out."""
    feeds = {
        "NASDAQ:NVDA": [1006, 1005, 1004, 1003, 1002, 1001],
        "NASDAQ:AMZN": [905, 904, 903, 902, 901],
        "NASDAQ:GOOGL": [803, 802, 801],
        "NASDAQ:MU": [704, 703, 702, 701],
        "NYSE:LLY": [600],
        "NASDAQ:COHR": [501, 500],
    }
    def fake_get(url, headers):
        for tv_symbol, ts_list in feeds.items():
            if f"symbol:{tv_symbol}" in url:
                items = [{"title": f"{tv_symbol} headline {ts}", "published": ts,
                          "storyPath": f"/news/{tv_symbol}/{ts}/"} for ts in ts_list]
                return _news_json(items)
        raise AssertionError(url)

    result = context.fetch_news(list(feeds.keys()), _get=fake_get)
    assert result is not None
    tickers = [it["ticker"] for it in result["items"]]
    assert len(tickers) == 20
    hist: dict[str, int] = {}
    for t in tickers:
        hist[t] = hist.get(t, 0) + 1
    assert hist["NVDA"] == 6
    assert hist["AMZN"] == 5
    assert hist["GOOGL"] == 3
    assert hist["MU"] == 3     # guaranteed room — would have been crowded out uncapped
    assert hist["LLY"] == 1
    assert hist["COHR"] == 2
    tss = [it["ts"] for it in result["items"]]
    assert tss == sorted(tss, reverse=True)


def test_fetch_news_no_ticker_exceeds_per_ticker_cap_unless_backfilled():
    """A single ticker with a flood of items never exceeds NEWS_PER_TICKER_CAP
    UNLESS backfill needed its excess to reach NEWS_CAP (here it does — MU is
    the only ticker in the pool, so its excess fills the whole 20)."""
    def fake_get(url, headers):
        items = [{"title": f"MU headline {i}", "published": 1000 + i,
                  "storyPath": f"/news/mu{i}/"} for i in range(30)]
        return _news_json(items)
    result = context.fetch_news(["NASDAQ:MU"], _get=fake_get)
    assert len(result["items"]) == context.NEWS_CAP == 20
    assert all(it["ticker"] == "MU" for it in result["items"])


# ── bars: avg_move arithmetic, window, fail-soft ────────────────────────────

def test_avg_move_known_series():
    # 100 -> 110 (+10%), 110 -> 99 (-10%): mean(10, 10) = 10.0
    assert context._avg_move([100.0, 110.0, 99.0]) == pytest.approx(10.0)


def test_avg_move_window_is_last_20_closes_only():
    noise = [5.0] * 10   # would blow the average up if it ever leaked into the window
    tail = []
    for _ in range(10):
        tail += [100.0, 110.0]
    closes = noise + tail   # 30 total; last 20 == tail exactly
    mv = context._avg_move(closes)
    expected_changes = [abs((b - a) / a) * 100.0 for a, b in zip(tail, tail[1:])]
    expected = round(sum(expected_changes) / len(expected_changes), 2)
    assert mv == pytest.approx(expected)
    assert mv < 20.0   # sanity bound: the noise (5 -> 100) would be a ~1900% move


def test_avg_move_none_when_fewer_than_two_closes():
    assert context._avg_move([]) is None
    assert context._avg_move([100.0]) is None


def test_build_bars_end_to_end_and_fail_soft_skip():
    def fake_get(url, headers):
        assert "query1.finance.yahoo.com" in url
        assert "range=2y" in url and "interval=1d" in url   # 2026-08-15 wave 3: 1y -> 2y
        if "/GOOD" in url:
            return _yahoo_json([100.0 + i for i in range(25)])
        raise urllib.error.URLError("boom")
    payload, avg_move = context.build_bars(["GOOD", "BAD"], date(2026, 8, 15), _get=fake_get)
    assert payload["built"] == "2026-08-15"
    assert payload["v"] == 4
    assert "GOOD" in payload["bars"] and "BAD" not in payload["bars"]
    # No "volume" array in this fixture at all -> v is None (never 0) for every row.
    assert payload["bars"]["GOOD"][0] == [100.0, 100.0, 100.0, 100.0, None]
    assert payload["bars"]["GOOD"][-1] == [124.0, 124.0, 124.0, 124.0, None]
    assert "GOOD" in avg_move and avg_move["GOOD"] > 0
    assert "BAD" not in avg_move


def test_build_bars_caps_at_504_and_drops_nulls():
    closes = [None] * 5 + [float(i) for i in range(600)]
    def fake_get(url, headers):
        return _yahoo_json(closes)
    payload, _ = context.build_bars(["MU"], date(2026, 8, 15), _get=fake_get)
    assert len(payload["bars"]["MU"]) == context.BARS_MAX == 504
    # OHLC legs are never None (the row would have been dropped); volume MAY
    # legitimately be None (no volume array in this fixture) — checked separately.
    assert all(v is not None for row in payload["bars"]["MU"] for v in row[:4])
    assert all(row[4] is None for row in payload["bars"]["MU"])


# ── gates: hourly (context) and daily (bars) ────────────────────────────────

def test_hourly_gate_fresh_timestamp_skips_network_and_carries_cache_forward(tmp_path, monkeypatch):
    monkeypatch.setattr(context, "CONTEXT_CACHE_FILE", tmp_path / ".context_cache.json")
    monkeypatch.setattr(context, "INTRA_SLEEP_SEC", 0)
    now = datetime(2026, 8, 15, 14, 0, 0, tzinfo=timezone.utc)
    cache = {
        "context_fetched_at": "2026-08-15T13:30:00Z",   # 30 min ago -> fresh (<55min)
        "bars_built_date": "2026-08-15",                  # today -> bars also fresh
        "bars_sig": context.BARS_BUILD_SIG,               # AND matches -> no rebuild
        "fund_sig": context.FUND_BUILD_SIG,               # fund shape current too
        "avg_move": {"MU": 4.2},
        "brief": {"date": "2026-08-15", "stale": False},
        "catalysts": [_econ_row("2026-08-16", "cached row", "LOW")],
        "news": {"items": [], "rotation_banner": False},
        "desk_private": {"v": 1},
    }
    context.save_context_cache(cache)

    quotes = {"MU": {"tv_symbol": "NASDAQ:MU", "earnings_ts": None, "hi52": None,
                     "lo52": None, "market_cap": None, "beta": None, "avol": None, "rsi": None}}
    fields, bars_payload, fund_payload, _intra, _cons = context.build_context(quotes, ["MU"], date(2026, 8, 15), now, _get=_boom)
    assert bars_payload is None
    assert fund_payload is None   # same gate as bars — both fresh, neither rebuilds
    assert fields["brief"] == {"date": "2026-08-15", "stale": False}
    assert fields["catalysts"] == cache["catalysts"]
    assert fields["desk_private"] == {"v": 1}
    assert fields["facts"]["MU"]["avg_move"] == 4.2
    assert fields["context_updated_at"] == "2026-08-15T13:30:00Z"


def test_stale_context_triggers_full_refetch_and_updates_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(context, "CONTEXT_CACHE_FILE", tmp_path / ".context_cache.json")
    monkeypatch.setattr(context, "INTRA_SLEEP_SEC", 0)
    monkeypatch.setenv("VAULT_READ_TOKEN", "tok123")
    now = datetime(2026, 8, 15, 14, 0, 0, tzinfo=timezone.utc)
    # no cache file at all yet -> first cycle of the process -> definitely stale

    def fake_get(url, headers):
        if "raw.githubusercontent.com" in url:
            if "brief_summary" in url:
                return json.dumps({"date": "2026-08-15", "posture": "ok"}).encode()
            if "desk_private" in url:
                return json.dumps({"v": 1, "blob": "abc"}).encode()
            if "memory_events" in url:
                return b"date,scope,kind,event,importance,confidence,source\n"
            if "econ_calendar" in url:
                return b"date,time_ct,event,importance\n"
            raise AssertionError(url)
        if "economic-calendar.tradingview.com" in url:
            return json.dumps({"status": "ok", "result": []}).encode()
        if "news-mediator.tradingview.com" in url:
            return json.dumps({"items": []}).encode()
        if "stockanalysis.com" in url:
            return _sa_skip_data_json()
        yahoo_fund = _yahoo_crumb_and_empty_quotesummary(url)
        if yahoo_fund is not None:
            return yahoo_fund
        if "query1.finance.yahoo.com" in url:
            return _yahoo_json([1.0, 2.0])
        raise AssertionError(f"unexpected URL: {url}")

    quotes = {"MU": {"tv_symbol": "NASDAQ:MU", "earnings_ts": None, "hi52": 1.0, "lo52": 1.0,
                     "market_cap": 1.0, "beta": 1.0, "avol": 1.0, "rsi": 50.0}}
    fields, bars_payload, fund_payload, _intra, _cons = context.build_context(quotes, ["MU"], date(2026, 8, 15), now, _get=fake_get)
    assert fields["brief"]["date"] == "2026-08-15" and fields["brief"]["stale"] is False
    assert fields["desk_private"] == {"v": 1, "blob": "abc"}
    assert fields["context_updated_at"] == "2026-08-15T14:00:00Z"
    assert bars_payload is not None
    assert bars_payload["v"] == 4
    assert fund_payload is not None and "MU" in fund_payload   # same gate as bars — both rebuilt

    saved = context.load_context_cache()
    assert saved["context_fetched_at"] == "2026-08-15T14:00:00Z"
    assert saved["bars_built_date"] == "2026-08-15"
    assert saved["bars_sig"] == context.BARS_BUILD_SIG


def test_build_context_without_token_still_gets_tv_and_opex_but_not_vault(tmp_path, monkeypatch):
    monkeypatch.setattr(context, "CONTEXT_CACHE_FILE", tmp_path / ".context_cache.json")
    monkeypatch.setattr(context, "INTRA_SLEEP_SEC", 0)
    monkeypatch.delenv("VAULT_READ_TOKEN", raising=False)
    now = datetime(2026, 8, 15, 14, 0, 0, tzinfo=timezone.utc)

    def fake_get(url, headers):
        assert "raw.githubusercontent.com" not in url, "vault must never be called with no token"
        if "economic-calendar.tradingview.com" in url:
            return json.dumps({"status": "ok", "result": []}).encode()
        if "news-mediator.tradingview.com" in url:
            return json.dumps({"items": []}).encode()
        if "stockanalysis.com" in url:
            return _sa_skip_data_json()
        yahoo_fund = _yahoo_crumb_and_empty_quotesummary(url)
        if yahoo_fund is not None:
            return yahoo_fund
        if "query1.finance.yahoo.com" in url:
            return _yahoo_json([1.0, 2.0])
        raise AssertionError(f"unexpected URL: {url}")

    quotes = {"MU": {"tv_symbol": "NASDAQ:MU", "earnings_ts": None}}
    fields, _, fund_payload, _intra, _cons = context.build_context(quotes, ["MU"], date(2026, 8, 15), now, _get=fake_get)
    assert "brief" not in fields
    assert "desk_private" not in fields
    assert "catalysts" in fields
    assert any(c["kind"] == "market" for c in fields["catalysts"])   # OpEx needs no vault/TV data
    assert fund_payload is not None and "MU" in fund_payload   # no vault token needed for this leg either


def test_bars_only_gate_rebuilds_bars_without_refetching_context(tmp_path, monkeypatch):
    monkeypatch.setattr(context, "CONTEXT_CACHE_FILE", tmp_path / ".context_cache.json")
    monkeypatch.setattr(context, "INTRA_SLEEP_SEC", 0)
    now = datetime(2026, 8, 15, 14, 0, 0, tzinfo=timezone.utc)
    cache = {
        "context_fetched_at": "2026-08-15T13:50:00Z",   # 10 min ago -> fresh, no refetch
        "bars_built_date": "2026-08-14",                  # yesterday -> bars ARE stale
        "bars_sig": context.BARS_BUILD_SIG,               # sig matches; DATE is what's stale here
        "avg_move": {"MU": 9.99},
        "brief": {"date": "2026-08-15", "stale": False},
        "catalysts": [],
        "news": {"items": [], "rotation_banner": False},
        "desk_private": None,
    }
    context.save_context_cache(cache)

    def fake_get(url, headers):
        if "stockanalysis.com" in url:
            return _sa_skip_data_json()
        yahoo_fund = _yahoo_crumb_and_empty_quotesummary(url)
        if yahoo_fund is not None:
            return yahoo_fund
        assert "query1.finance.yahoo.com" in url, f"unexpected fetch: {url}"
        return _yahoo_json([100.0 + i for i in range(25)])

    quotes = {"MU": {"tv_symbol": "NASDAQ:MU", "earnings_ts": None, "hi52": None, "lo52": None,
                     "market_cap": None, "beta": None, "avol": None, "rsi": None}}
    fields, bars_payload, fund_payload, _intra, _cons = context.build_context(quotes, ["MU"], date(2026, 8, 15), now, _get=fake_get)
    assert bars_payload is not None and bars_payload["built"] == "2026-08-15"
    assert bars_payload["v"] == 4
    assert fields["brief"] == {"date": "2026-08-15", "stale": False}   # carried from cache
    assert fields["facts"]["MU"]["avg_move"] is not None
    assert fields["facts"]["MU"]["avg_move"] != 9.99   # replaced by the fresh rebuild
    assert fund_payload is not None and "MU" in fund_payload   # same gate as bars — both rebuilt

    saved = context.load_context_cache()
    assert saved["bars_built_date"] == "2026-08-15" and saved["bars_sig"] == context.BARS_BUILD_SIG


def test_bars_gate_same_day_same_sig_is_cached_no_rebuild(tmp_path, monkeypatch):
    """Both halves of the gate agree today's cache is current -> no rebuild,
    no network at all (the _boom getter would raise on any attempted call)."""
    monkeypatch.setattr(context, "CONTEXT_CACHE_FILE", tmp_path / ".context_cache.json")
    monkeypatch.setattr(context, "INTRA_SLEEP_SEC", 0)
    now = datetime(2026, 8, 15, 14, 0, 0, tzinfo=timezone.utc)
    cache = {
        "context_fetched_at": "2026-08-15T13:50:00Z",   # fresh -> no context refetch either
        "bars_built_date": "2026-08-15",                  # today...
        "bars_sig": context.BARS_BUILD_SIG,               # ...AND matching signature -> cached
        "fund_sig": context.FUND_BUILD_SIG,               # fund shape current too
        "avg_move": {"MU": 4.2},
        "brief": None, "catalysts": [], "news": None, "desk_private": None,
    }
    context.save_context_cache(cache)

    quotes = {"MU": {"tv_symbol": "NASDAQ:MU", "earnings_ts": None, "hi52": None, "lo52": None,
                     "market_cap": None, "beta": None, "avol": None, "rsi": None}}
    fields, bars_payload, fund_payload, _intra, _cons = context.build_context(quotes, ["MU"], date(2026, 8, 15), now, _get=_boom)
    assert bars_payload is None
    assert fund_payload is None


def test_bars_gate_same_day_different_sig_forces_rebuild(tmp_path, monkeypatch):
    """The exact bug BARS_BUILD_SIG exists to prevent: bars_built_date already
    says today (written by an earlier cycle running the OLD code, before a
    same-day deploy that changed build_bars's output shape), but the stored
    signature is stale — the date match ALONE must not be enough to skip the
    rebuild, or this cycle would keep serving the old shape until midnight."""
    monkeypatch.setattr(context, "CONTEXT_CACHE_FILE", tmp_path / ".context_cache.json")
    monkeypatch.setattr(context, "INTRA_SLEEP_SEC", 0)
    now = datetime(2026, 8, 15, 14, 0, 0, tzinfo=timezone.utc)
    cache = {
        "context_fetched_at": "2026-08-15T13:50:00Z",   # fresh -> context leg still skips
        "bars_built_date": "2026-08-15",                  # today...
        "bars_sig": "v2-quads",                            # ...but an OLDER build signature
        "avg_move": {"MU": 4.2},
        "brief": None, "catalysts": [], "news": None, "desk_private": None,
    }
    context.save_context_cache(cache)

    def fake_get(url, headers):
        if "stockanalysis.com" in url:
            return _sa_skip_data_json()
        yahoo_fund = _yahoo_crumb_and_empty_quotesummary(url)
        if yahoo_fund is not None:
            return yahoo_fund
        assert "query1.finance.yahoo.com" in url, f"unexpected fetch: {url}"
        return _yahoo_json([100.0 + i for i in range(25)])

    quotes = {"MU": {"tv_symbol": "NASDAQ:MU", "earnings_ts": None, "hi52": None, "lo52": None,
                     "market_cap": None, "beta": None, "avol": None, "rsi": None}}
    fields, bars_payload, fund_payload, _intra, _cons = context.build_context(quotes, ["MU"], date(2026, 8, 15), now, _get=fake_get)
    assert bars_payload is not None and bars_payload["v"] == context.BARS_VERSION
    assert fund_payload is not None and "MU" in fund_payload

    saved = context.load_context_cache()
    assert saved["bars_built_date"] == "2026-08-15"
    assert saved["bars_sig"] == context.BARS_BUILD_SIG   # stale sig replaced with the current one


def test_is_context_stale_missing_or_old_timestamp():
    now = datetime(2026, 8, 15, 14, 0, 0, tzinfo=timezone.utc)
    assert context._is_context_stale({"context_fetched_at": None}, now) is True
    fresh = {"context_fetched_at": (now - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")}
    stale = {"context_fetched_at": (now - timedelta(minutes=56)).strftime("%Y-%m-%dT%H:%M:%SZ")}
    assert context._is_context_stale(fresh, now) is False
    assert context._is_context_stale(stale, now) is True


def test_load_context_cache_missing_file_returns_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(context, "CONTEXT_CACHE_FILE", tmp_path / "does_not_exist.json")
    cache = context.load_context_cache()
    assert cache["context_fetched_at"] is None
    assert cache["bars_built_date"] is None
    assert cache["bars_sig"] is None
    assert cache["avg_move"] == {}
    assert cache["brief"] is None
    assert cache["catalysts"] == []


def test_load_context_cache_corrupt_file_is_fail_soft(tmp_path, monkeypatch):
    f = tmp_path / ".context_cache.json"
    f.write_text("not json{{{", encoding="utf-8")
    monkeypatch.setattr(context, "CONTEXT_CACHE_FILE", f)
    cache = context.load_context_cache()
    assert cache["context_fetched_at"] is None


# ── title-conflict helper (used by _dedup_econ) ─────────────────────────────

def test_titles_conflict_substring_and_parenthetical_normalization():
    assert context._titles_conflict("CPI", "CPI (July)") is True
    assert context._titles_conflict("FOMC Rate Decision",
                                     "FOMC Rate Decision + Summary of Economic Projections (dot plot)") is True
    assert context._titles_conflict("Jobs Report", "PPI") is False
    assert context._titles_conflict("", "CPI") is False


def test_fetch_econ_tv_drops_low_importance():
    """Fable 2026-08-15: the desk's econ floor is MEDIUM — raw TV LOW rows
    (auctions, minor releases; 299 rows/~129KB in the live probe) never
    publish. LOW survives only via market_calendar / the CSV mirror."""
    payload = json.dumps({"result": [
        {"title": "3-Month Bill Auction", "date": "2026-08-20T15:30:00Z", "importance": -1},
        {"title": "FOMC Minutes", "date": "2026-08-19T18:00:00Z", "importance": 0},
        {"title": "CPI", "date": "2026-09-11T12:30:00Z", "importance": 1},
    ]}).encode()
    rows = context.fetch_econ_tv(days=28, _get=lambda url, headers=None: payload)
    titles = [r["title"] for r in rows]
    assert "3-Month Bill Auction" not in titles
    assert "FOMC Minutes" in titles and "CPI" in titles
    assert all(r["importance"] in ("HIGH", "MEDIUM") for r in rows)


def test_build_bars_v3_quints_and_facts_fundamentals_passthrough():
    """2026-08-15 wave 3: bars.json v3 rows are [o,h,l,c,v] quints; rows with
    a missing OHLC leg are dropped (volume plays no part in that decision —
    the dropped row's own volume reading is irrelevant); avg_move still
    computes from closes. And the facts map must pass the scanner
    fundamentals through (None stays None, never 0)."""
    payload = {"chart": {"result": [{"indicators": {"quote": [{
        "open": [10.0, 11.0, None, 12.0], "high": [10.5, 11.5, 12.0, 12.5],
        "low": [9.5, 10.5, 11.0, 11.5], "close": [10.2, 11.2, 11.8, 12.2],
        "volume": [1000, 2000, 3000, 4000]}]}}]}}
    bars, avg = context.build_bars(["ZZZ"], date(2026, 8, 15),
                                    _get=lambda url, headers=None: json.dumps(payload).encode())
    assert bars["v"] == 4
    assert bars["bars"]["ZZZ"] == [[10.0, 10.5, 9.5, 10.2, 1000], [11.0, 11.5, 10.5, 11.2, 2000],
                                    [12.0, 12.5, 11.5, 12.2, 4000]]
    assert "ZZZ" in avg and avg["ZZZ"] > 0
    quotes = {"ZZZ": {"tv_symbol": "NASDAQ:ZZZ", "hi52": 20.0, "lo52": 5.0, "market_cap": 1e9,
              "beta": 1.1, "avol": 1e6, "rsi": 55.0, "earnings_ts": None,
              "pe": 12.5, "peg": None, "net_margin": 22.0, "gross_margin": None, "op_margin": 18.0,
              "fcf_margin": None, "debt_eq": 0.4, "roe": None, "ps": 3.1, "pb": None,
              "ev_ebitda": 9.9, "yld": None, "target": 25.0, "rec_mark": 2.1}}
    facts = context.fetch_earnings_days(quotes, date(2026, 8, 15))
    f = facts["ZZZ"]
    assert f["pe"] == 12.5 and f["peg"] is None and f["debt_eq"] == 0.4
    assert f["rec_mark"] == 2.1 and f["gross_margin"] is None
    assert f["net_margin"] == 22.0 and f["op_margin"] == 18.0 and f["ps"] == 3.1
    assert f["ev_ebitda"] == 9.9 and f["target"] == 25.0
    for k in ("peg", "gross_margin", "fcf_margin", "roe", "pb", "yld"):
        assert f[k] is None and f[k] != 0


def test_build_bars_ohlc_round_trips_with_null_volume_when_no_volume_array():
    """A bar with every OHLC leg present survives; values are rounded 2dp. No
    "volume" array in the response at all -> v is None (never 0) for the
    row, same None != 0 rule as every other missing reading in this file."""
    payload = {"chart": {"result": [{"indicators": {"quote": [{
        "open": [10.001], "high": [10.999], "low": [9.994], "close": [10.501]}]}}]}}
    bars, _ = context.build_bars(["ZZZ"], date(2026, 8, 15),
                                  _get=lambda url, headers=None: json.dumps(payload).encode())
    assert bars["bars"]["ZZZ"] == [[10.0, 11.0, 9.99, 10.5, None]]


def test_extract_yahoo_ohlcv_null_volume_on_valid_bar_stays_none_not_zero():
    """A day with perfectly good OHLC but a null volume reading mid-array
    keeps the bar (OHLC alone decides whether a row survives) with v: None —
    never 0, which would misrepresent "unknown" as "no shares traded"."""
    payload = {"chart": {"result": [{"indicators": {"quote": [{
        "open": [10.0, 11.0], "high": [10.5, 11.5], "low": [9.5, 10.5], "close": [10.2, 11.2],
        "volume": [1500, None]}]}}]}}
    rows = context._extract_yahoo_ohlcv(payload)
    assert rows == [[10.0, 10.5, 9.5, 10.2, 1500, None], [11.0, 11.5, 10.5, 11.2, None, None]]


def test_extract_yahoo_ohlcv_float_volume_cast_to_int_and_missing_index_is_none():
    payload = {"chart": {"result": [{"indicators": {"quote": [{
        "open": [10.0, 11.0], "high": [10.5, 11.5], "low": [9.5, 10.5], "close": [10.2, 11.2],
        "volume": [1234.0]}]}}]}}   # short volume array: only 1 entry for 2 bars
    rows = context._extract_yahoo_ohlcv(payload)
    assert rows[0][4] == 1234 and isinstance(rows[0][4], int)   # cast, not left as float
    assert rows[1][4] is None   # index out of range on the volume array -> None, not 0


def test_build_bars_avg_move_unaffected_by_2y_of_extra_older_history():
    """2026-08-15 wave 3: BARS_MAX doubled (252 -> 504) for a 2-year chart
    range, but avg_move must still read exactly like the pre-2y behavior —
    only the last 20 closes, regardless of how much MORE history now sits in
    front of them. 504 rows total: the oldest 484 are a wild, easily
    distinguishable swing; the last 20 are the SAME known alternating series
    the plain `_avg_move` unit test above already pins the expected value
    for — proving BARS_MAX's widening never leaks into this arithmetic."""
    noise = [5.0, 5000.0] * 242   # 484 rows of extreme, easy-to-spot noise
    tail = []
    for _ in range(10):
        tail += [100.0, 110.0]     # 20 rows: known +10%/-9.09% alternation
    closes = noise + tail           # 504 total
    assert len(closes) == 504
    def fake_get(url, headers):
        return _yahoo_json(closes)
    payload, avg_move = context.build_bars(["MU"], date(2026, 8, 15), _get=fake_get)
    assert len(payload["bars"]["MU"]) == 504   # all kept (== BARS_MAX, nothing trimmed)
    expected_changes = [abs((b - a) / a) * 100.0 for a, b in zip(tail, tail[1:])]
    expected = round(sum(expected_changes) / len(expected_changes), 2)
    assert avg_move["MU"] == pytest.approx(expected)
    assert avg_move["MU"] < 20.0   # sanity bound: the noise swings are ~1000x moves


def test_avg_move_basis_constant_is_decoupled_from_bars_max():
    assert context.BARS_MAX == 504
    assert context.AVG_MOVE_BASIS == 252
    assert context.AVG_MOVE_BASIS != context.BARS_MAX


def test_track_only_names_never_reach_chain_candidates():
    """Pin the 2026-07-25 SKHX ghost-liquidity ruling: TRACK_ONLY names are
    quoted/tracked (facts/bars/fund/rail) but deliberately never chain-fetched
    — select_candidates() is the enforcement point, so this exercises it
    directly rather than merely inspecting the set."""
    import build_snapshot as bs
    assert bs.TRACK_ONLY == {"SKHX", "NRGU", "OILU", "STLL", "AAOG"}
    for t in bs.TRACK_ONLY:
        assert t in bs.WATCHLIST, t + " must still be on the watchlist (tracked)"
        assert t in bs.PINNED, t + " must still be tracked"

    # Every pinned name "resolved" this cycle, TRACK_ONLY included.
    quotes = {t: {"ticker": t, "tv_symbol": f"NASDAQ:{t}"} for t in bs.PINNED}
    candidates = bs.select_candidates(quotes)
    assert "SKHX" not in candidates
    for t in bs.TRACK_ONLY:
        assert t not in candidates, t + " must never reach a CBOE chain fetch"
    # Everything else that resolved DOES become a candidate.
    for t in bs.PINNED:
        if t not in bs.TRACK_ONLY:
            assert t in candidates


def test_select_candidates_track_only_excluded_even_when_it_did_resolve():
    """The exclusion is a deliberate rule, not an accident of a missing quote:
    give SKHX a perfectly good resolved quote (as if its ghost chain looked
    fine) and it must still never become a candidate."""
    import build_snapshot as bs
    quotes = {"SKHX": {"ticker": "SKHX", "tv_symbol": "CBOE:SKHX", "close": 15.0}}
    assert bs.select_candidates(quotes) == []


# ── fund/{SYM}.json sidecars (added 2026-08-15, Task 4) ─────────────────────

def _sa_data_json(root):
    """A minimal stockanalysis.com __data.json fixture: a single "data" node
    whose array is just [root]. _devalue_resolve(data, 0) returns `root`
    almost verbatim since nothing in it needs a reference lookup — AS LONG
    AS every numeric leaf is a float, never a bare int (an int leaf would be
    misread as a devalue reference index into this 1-element array). Real
    stockanalysis.com payloads are properly flattened; this shortcut is only
    valid for these hand-built fixtures."""
    return json.dumps({"nodes": [{"type": "data", "data": [root]}]}).encode()


def _yahoo_qs(result):
    return json.dumps({"quoteSummary": {"result": [result]}}).encode()


def test_devalue_resolve_basic_reference_walk():
    # data[0] is the root: {"a": 1, "b": 2}; data[1] = "hello" (a's value);
    # data[2] = [3, -1] (b's value: a 2-element list whose first element
    # references data[3] = 1.5, and whose second element IS the reference
    # -1 itself — devalue's "undefined" sentinel -> None).
    data = [{"a": 1, "b": 2}, "hello", [3, -1], 1.5]
    out = context._devalue_resolve(data, 0)
    assert out == {"a": "hello", "b": [1.5, None]}


def test_fetch_sa_page_skip_node_and_network_failure_are_none():
    assert context._fetch_sa_page("ZZZ", context.SA_STATISTICS_PATH,
                                   _get=lambda u, h: _sa_skip_data_json()) is None
    def fake_fail(u, h):
        raise urllib.error.URLError("boom")
    assert context._fetch_sa_page("ZZZ", context.SA_STATISTICS_PATH, _get=fake_fail) is None


def test_fetch_sa_statistics_parses_short_float_pe_forward_and_amc_session():
    root = {
        "shortSelling": {"data": [
            {"id": "shortInterest", "value": "292.67M"},
            {"id": "shortFloat", "title": "Short % of Float", "value": "1.26%", "hover": "1.259%"},
        ]},
        "ratios": {"data": [
            {"id": "pe", "value": "34.48", "hover": "34.483"},
            {"id": "peForward", "value": "22.59", "hover": "22.589"},
        ]},
        "dates": {
            "text": "The next confirmed earnings date is Wednesday, August 26, 2026, after market close.",
            "data": [{"id": "earningsdate", "value": "Aug 26, 2026"}],
        },
    }
    def fake_get(url, headers):
        assert url == "https://stockanalysis.com/stocks/nvda/statistics/__data.json"
        return _sa_data_json(root)
    out = context.fetch_sa_statistics("NVDA", _get=fake_get)
    assert out["short_pct_float"] == pytest.approx(1.259)
    assert out["pe_forward"] == pytest.approx(22.589)
    assert out["next_earnings_date"] == "2026-08-26"
    assert out["next_earnings_session"] == "AMC"


def test_fetch_sa_statistics_before_market_open_session():
    root = {"shortSelling": {"data": []}, "ratios": {"data": []},
            "dates": {"text": "The next confirmed earnings date is Tuesday, before market open.",
                      "data": [{"id": "earningsdate", "value": "Sep 1, 2026"}]}}
    out = context.fetch_sa_statistics("ZZZ", _get=lambda u, h: _sa_data_json(root))
    assert out["next_earnings_session"] == "BMO"
    assert out["next_earnings_date"] == "2026-09-01"


def test_fetch_sa_statistics_missing_rows_and_page_failure_are_all_none():
    empty = {"short_pct_float": None, "pe_forward": None,
              "next_earnings_date": None, "next_earnings_session": None}
    root = {"shortSelling": {"data": []}, "ratios": {"data": []}, "dates": {"data": [], "text": ""}}
    assert context.fetch_sa_statistics("ZZZ", _get=lambda u, h: _sa_data_json(root)) == empty

    def fake_fail(u, h):
        raise urllib.error.URLError("boom")
    assert context.fetch_sa_statistics("ZZZ", _get=fake_fail) == empty


def test_fetch_sa_quarterly_drops_ttm_and_keeps_newest_first():
    financial_data = {
        "datekey": ["TTM", "2026-04-26", "2026-01-25", "2025-10-26", "2025-07-27"],
        "fiscalYear": ["2027", "2026", "2026", "2026", "2026"],
        "fiscalQuarter": ["Q1", "Q4", "Q3", "Q2", "Q1"],
        "revenue": [253491000000.0, 68127000000.0, 57006000000.0, 46743000000.0, 44062000000.0],
        "epsdil": [6.52965, 1.87, 1.62, 1.3, 1.05],
    }
    root = {"financialData": financial_data}
    rows = context.fetch_sa_quarterly("NVDA", _get=lambda u, h: _sa_data_json(root))
    assert rows is not None
    assert len(rows) == 4   # TTM dropped
    assert all(r["date"] != "TTM" for r in rows)
    assert rows[0]["fiscal_quarter"] == "Q4" and rows[0]["fiscal_year"] == "2026"   # newest first, as returned
    assert rows[-1]["fiscal_quarter"] == "Q1" and rows[-1]["revenue"] == pytest.approx(44062000000.0)


def test_fetch_sa_quarterly_bad_shape_or_network_failure_is_none():
    assert context.fetch_sa_quarterly("ZZZ", _get=lambda u, h: _sa_data_json({"financialData": None})) is None
    assert context.fetch_sa_quarterly("ZZZ", _get=lambda u, h: _sa_data_json({})) is None
    def fake_fail(u, h):
        raise urllib.error.URLError("boom")
    assert context.fetch_sa_quarterly("ZZZ", _get=fake_fail) is None


def test_build_quarterly_series_oldest_first_and_capped():
    # 20 newest-first synthetic rows: index 0 = newest (value 0), index 19 = oldest (value 19).
    rows = [{"fiscal_year": "2020", "fiscal_quarter": "Q1", "revenue": float(i), "eps": float(i)}
            for i in range(20)]
    series = context._build_quarterly_series(rows)
    assert len(series["periods"]) == context.FUND_MAX_QUARTERLY == 12
    # capped to the 12 NEWEST (values 0..11), then reversed to oldest-first.
    assert series["revenue"][0] == 11.0 and series["revenue"][-1] == 0.0
    assert series["periods"][0] == "Q1 20"


def test_build_annual_series_sums_complete_fiscal_years_only():
    rows = [
        {"fiscal_year": "2026", "fiscal_quarter": "Q4", "revenue": 68127000000.0, "eps": 1.87},
        {"fiscal_year": "2026", "fiscal_quarter": "Q3", "revenue": 57006000000.0, "eps": 1.62},
        {"fiscal_year": "2026", "fiscal_quarter": "Q2", "revenue": 46743000000.0, "eps": 1.3},
        {"fiscal_year": "2026", "fiscal_quarter": "Q1", "revenue": 44062000000.0, "eps": 1.05},
        {"fiscal_year": "2027", "fiscal_quarter": "Q1", "revenue": 81615000000.0, "eps": 1.87},  # partial FY27
    ]
    annual = context._build_annual_series(rows)
    assert annual["periods"] == ["FY26"]   # FY27 excluded: only 1 of 4 quarters present
    assert annual["revenue"][0] == pytest.approx(215938000000.0)
    assert annual["eps"][0] == pytest.approx(5.84)


def test_build_annual_series_caps_at_max_years():
    rows = []
    for y in range(2015, 2028):   # 13 candidate years, all complete
        yy = str(y)
        for q in ("Q1", "Q2", "Q3", "Q4"):
            rows.append({"fiscal_year": yy, "fiscal_quarter": q, "revenue": 1.0, "eps": 1.0})
    annual = context._build_annual_series(rows)
    assert len(annual["periods"]) == context.FUND_MAX_ANNUAL == 6
    assert annual["periods"][-1] == "FY27"   # most recent complete year kept


# ── quarterly net income + free cash flow (added 2026-08-19) ────────────────

def test_fetch_sa_quarterly_carries_net_income_when_present():
    financial_data = {
        "datekey": ["TTM", "2026-05-28", "2026-02-26"],
        "fiscalYear": ["2026", "2026", "2026"],
        "fiscalQuarter": ["Q4", "Q3", "Q2"],
        "revenue": [90274000000.0, 37378000000.0, 28100000000.0],
        "epsdil": [44.17, 16.05, 12.01],
        "netinccmn": [50469000000.0, 18574000000.0, 13900000000.0],
    }
    rows = context.fetch_sa_quarterly("MU", _get=lambda u, h: _sa_data_json({"financialData": financial_data}))
    assert rows[0]["ni"] == pytest.approx(18574000000.0)   # TTM dropped, newest first
    assert rows[1]["ni"] == pytest.approx(13900000000.0)


def test_fetch_sa_quarterly_missing_net_income_array_degrades_to_none():
    """`netinccmn` is optional — a payload without it (or with a shorter
    array) yields per-row ni=None while revenue/eps parse normally, never a
    failed page and never a 0."""
    financial_data = {
        "datekey": ["2026-05-28", "2026-02-26"],
        "fiscalYear": ["2026", "2026"],
        "fiscalQuarter": ["Q3", "Q2"],
        "revenue": [37378000000.0, 28100000000.0],
        "epsdil": [16.05, 12.01],
    }
    rows = context.fetch_sa_quarterly("MU", _get=lambda u, h: _sa_data_json({"financialData": financial_data}))
    assert rows[0]["revenue"] == pytest.approx(37378000000.0)
    assert rows[0]["ni"] is None and rows[1]["ni"] is None


def test_fetch_sa_cashflow_q_maps_datekey_to_fcf_and_drops_ttm():
    financial_data = {
        "datekey": ["TTM", "2026-05-28", "2026-02-26"],
        "fiscalYear": ["2026", "2026", "2026"],
        "fiscalQuarter": ["Q4", "Q3", "Q2"],
        "fcf": [26172000000.0, 17562000000.0, 5516000000.0],
    }
    def fake_get(url, headers):
        assert url == "https://stockanalysis.com/stocks/mu/financials/cash-flow-statement/__data.json?p=quarterly"
        return _sa_data_json({"financialData": financial_data})
    out = context.fetch_sa_cashflow_q("MU", _get=fake_get)
    assert out == {"2026-05-28": pytest.approx(17562000000.0),
                   "2026-02-26": pytest.approx(5516000000.0)}   # TTM never a key


def test_fetch_sa_cashflow_q_bad_shape_or_failure_is_none():
    assert context.fetch_sa_cashflow_q("ZZZ", _get=lambda u, h: _sa_data_json({"financialData": None})) is None
    assert context.fetch_sa_cashflow_q("ZZZ", _get=lambda u, h: _sa_data_json({})) is None
    def fake_fail(u, h):
        raise urllib.error.URLError("boom")
    assert context.fetch_sa_cashflow_q("ZZZ", _get=fake_fail) is None


def test_merge_fcf_joins_by_date_never_by_position():
    """The two stockanalysis pages can cover different spans — the join is
    by datekey. A quarter the cash-flow page doesn't carry reads None, and a
    None/failed map leaves every row None."""
    rows = [{"date": "2026-05-28"}, {"date": "2026-02-26"}, {"date": None}]
    context._merge_fcf_into_rows(rows, {"2026-02-26": 5516000000.0, "2019-01-01": 1.0})
    assert rows[0]["fcf"] is None                          # income row absent from CF page
    assert rows[1]["fcf"] == pytest.approx(5516000000.0)   # joined by date, not position
    assert rows[2]["fcf"] is None                          # unlabeled row can't join

    rows2 = [{"date": "2026-05-28"}]
    context._merge_fcf_into_rows(rows2, None)              # whole CF leg failed
    assert rows2[0]["fcf"] is None


def test_quarterly_and_annual_series_carry_ni_and_fcf():
    rows = []
    for q, rev, eps, ni, fcf in (("Q4", 4.0, 0.4, 2.0, 1.0), ("Q3", 3.0, 0.3, 1.5, None),
                                 ("Q2", 2.0, 0.2, 1.0, 0.5), ("Q1", 1.0, 0.1, 0.5, 0.25)):
        rows.append({"fiscal_year": "2026", "fiscal_quarter": q, "date": f"2026-{q}",
                     "revenue": rev, "eps": eps, "ni": ni, "fcf": fcf})
    series = context._build_quarterly_series(rows)
    assert series["ni"] == [0.5, 1.0, 1.5, 2.0]            # oldest first, like revenue
    assert series["fcf"] == [0.25, 0.5, None, 1.0]         # a missing quarter stays None

    annual = context._build_annual_series(rows)
    assert annual["ni"] == [pytest.approx(5.0)]            # all 4 quarters present -> summed
    assert annual["fcf"] == [None]                         # one missing quarter -> no partial sum
    assert annual["revenue"] == [pytest.approx(10.0)]      # unaffected by the fcf gap


def test_build_fund_sidecar_fcf_leg_joins_and_fails_soft():
    """End-to-end: income + cash-flow pages both live -> quarterly.fcf joined
    by datekey; the fcf leg failing alone leaves revenue/eps/ni intact."""
    income = {"financialData": {
        "datekey": ["2026-05-28", "2026-02-26"],
        "fiscalYear": ["2026", "2026"], "fiscalQuarter": ["Q3", "Q2"],
        "revenue": [37378000000.0, 28100000000.0], "epsdil": [16.05, 12.01],
        "netinccmn": [18574000000.0, 13900000000.0],
    }}
    cashflow = {"financialData": {
        "datekey": ["2026-05-28"],   # shorter span than the income page
        "fiscalYear": ["2026"], "fiscalQuarter": ["Q3"],
        "fcf": [17562000000.0],
    }}
    def fake_get(url, headers):
        if "statistics" in url:
            return _sa_skip_data_json()
        if "financials/income-statement" in url:
            return _sa_data_json(income)
        if "financials/cash-flow-statement" in url:
            return _sa_data_json(cashflow)
        raise AssertionError(url)
    payload = context.build_fund_sidecar("MU", date(2026, 8, 19), None, None, _get=fake_get)
    assert payload["quarterly"]["ni"] == [pytest.approx(13900000000.0), pytest.approx(18574000000.0)]
    assert payload["quarterly"]["fcf"] == [None, pytest.approx(17562000000.0)]   # Q2 not on the CF page

    def fake_get_cf_down(url, headers):
        if "financials/cash-flow-statement" in url:
            raise urllib.error.URLError("boom")
        return fake_get(url, headers)
    payload2 = context.build_fund_sidecar("MU", date(2026, 8, 19), None, None, _get=fake_get_cf_down)
    assert payload2["quarterly"]["revenue"][-1] == pytest.approx(37378000000.0)   # income leg survives
    assert payload2["quarterly"]["fcf"] == [None, None]                            # never 0, never guessed


def test_fund_sig_mismatch_forces_same_day_rebuild(tmp_path, monkeypatch):
    """The exact bug FUND_BUILD_SIG exists to prevent: bars are current for
    today under the current BARS_BUILD_SIG, but the fund sidecar shape
    changed in a same-day deploy — the stale fund signature alone must force
    the shared rebuild (this same gate rebuilds bars too; that is idempotent)."""
    monkeypatch.setattr(context, "CONTEXT_CACHE_FILE", tmp_path / ".context_cache.json")
    monkeypatch.setattr(context, "INTRA_SLEEP_SEC", 0)
    monkeypatch.setattr(context, "FUND_SLEEP_SEC", 0)
    now = datetime(2026, 8, 19, 14, 0, 0, tzinfo=timezone.utc)
    cache = {
        "context_fetched_at": "2026-08-19T13:50:00Z",   # context fresh -> no refetch
        "bars_built_date": "2026-08-19",                  # bars current for today...
        "bars_sig": context.BARS_BUILD_SIG,               # ...under the current sig
        "fund_sig": "v1-pre-ni-fcf",                      # ...but the fund shape is stale
        "avg_move": {}, "brief": None, "catalysts": [], "news": None, "desk_private": None,
    }
    context.save_context_cache(cache)

    def fake_get(url, headers):
        raise urllib.error.URLError("offline")   # every leg fails soft; the gate is what's under test
    quotes = {"MU": {"tv_symbol": "NASDAQ:MU", "earnings_ts": None, "hi52": None, "lo52": None,
                     "market_cap": None, "beta": None, "avol": None, "rsi": None}}
    fields, bars_payload, fund_payload, _intra, _cons = context.build_context(
        quotes, ["MU"], date(2026, 8, 19), now, _get=fake_get)
    assert fund_payload is not None                       # rebuild ran
    assert "MU" in fund_payload
    saved = json.loads((tmp_path / ".context_cache.json").read_text())
    assert saved["fund_sig"] == context.FUND_BUILD_SIG    # sig recorded -> next cycle skips


def test_facts_carry_sector_and_industry_strings():
    quotes = {"MU": {"tv_symbol": "NASDAQ:MU", "earnings_ts": None, "hi52": None, "lo52": None,
                     "market_cap": None, "beta": None, "avol": None, "rsi": None,
                     "sector": "Electronic Technology", "industry": "Semiconductors"},
              "ZZZ": {"tv_symbol": "NYSE:ZZZ", "earnings_ts": None, "hi52": None, "lo52": None,
                      "market_cap": None, "beta": None, "avol": None, "rsi": None}}
    facts = context.fetch_earnings_days(quotes, date(2026, 8, 19))
    assert facts["MU"]["sector"] == "Electronic Technology"
    assert facts["MU"]["industry"] == "Semiconductors"
    assert facts["ZZZ"]["sector"] is None and facts["ZZZ"]["industry"] is None


def test_fetch_yahoo_crumb_tolerates_fc_yahoo_404_and_extracts_crumb():
    def fake_get(url, headers):
        if "fc.yahoo.com" in url:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        if "getcrumb" in url:
            return b"abc123crumb"
        raise AssertionError(url)
    assert context.fetch_yahoo_crumb(_get=fake_get) == "abc123crumb"


def test_fetch_yahoo_crumb_none_when_getcrumb_itself_fails():
    def fake_get(url, headers):
        if "fc.yahoo.com" in url:
            return b""
        raise urllib.error.URLError("boom")
    assert context.fetch_yahoo_crumb(_get=fake_get) is None


def test_fetch_yahoo_fundamentals_full_shape_matches_and_derives_session():
    period_end = int(datetime(2026, 4, 30, tzinfo=timezone.utc).timestamp())
    reported = int(datetime(2026, 5, 20, 20, 15, tzinfo=timezone.utc).timestamp())   # 16:15 ET -> afterhours
    next_earn = int(datetime(2026, 8, 27, tzinfo=timezone.utc).timestamp())
    result = {
        "defaultKeyStatistics": {
            "forwardPE": {"raw": 17.467222, "fmt": "17.47"},
            "shortPercentOfFloat": {"raw": 0.0126, "fmt": "1.26%"},
        },
        "earnings": {
            "earningsChart": {"quarterly": [{
                "date": "1Q2026", "fiscalQuarter": "1Q2027",
                "actual": {"raw": 1.87}, "estimate": {"raw": 1.77191},
                "surprisePct": "5.54",
                "periodEndDate": {"raw": period_end}, "reportedDate": {"raw": reported},
            }]},
            "financialsChart": {"quarterly": [{"date": "1Q2026", "revenue": {"raw": 81615000000}}]},
        },
        "calendarEvents": {"earnings": {
            "earningsDate": [{"raw": next_earn}],
            "earningsAverage": {"raw": 2.083},
            "revenueAverage": {"raw": 91846098240},
        }},
    }
    def fake_get(url, headers):
        assert "quoteSummary/NVDA" in url and "crumb=abc" in url
        return _yahoo_qs(result)
    out = context.fetch_yahoo_fundamentals("NVDA", "abc", _get=fake_get)
    assert out["pe_forward"] == pytest.approx(17.467222)
    assert out["short_pct_float"] == pytest.approx(1.26, abs=1e-6)
    assert len(out["earnings"]) == 1
    row = out["earnings"][0]
    assert row["period"] == "Q1 2027"
    assert row["date"] == "2026-04-30"
    assert row["report_date"] == "2026-05-20"   # announcement date — page anchors E-badges here
    assert row["session"] == "afterhours"
    assert row["eps"] == pytest.approx(1.87) and row["eps_est"] == pytest.approx(1.77191)
    assert row["eps_surprise_pct"] == pytest.approx(5.54)
    assert row["rev"] == pytest.approx(81615000000.0)
    assert row["rev_est"] is None and row["rev_surprise_pct"] is None   # never sourced, see module header
    assert out["next_earnings"] == {
        "date": "2026-08-27", "session": None,   # no intraday time in calendarEvents
        "eps_est": pytest.approx(2.083), "rev_est": pytest.approx(91846098240.0),
    }


def test_fetch_yahoo_fundamentals_revenue_unmatched_stays_none():
    period_end = int(datetime(2026, 4, 30, tzinfo=timezone.utc).timestamp())
    result = {
        "defaultKeyStatistics": {},
        "earnings": {
            "earningsChart": {"quarterly": [{
                "date": "1Q2026", "fiscalQuarter": "1Q2027",
                "actual": {"raw": 1.87}, "estimate": {"raw": 1.77},
                "surprisePct": "5.65", "periodEndDate": {"raw": period_end}, "reportedDate": None,
            }]},
            "financialsChart": {"quarterly": []},   # no matching revenue row at all
        },
        "calendarEvents": {},
    }
    out = context.fetch_yahoo_fundamentals("NVDA", "abc", _get=lambda u, h: _yahoo_qs(result))
    assert out["earnings"][0]["rev"] is None
    assert out["earnings"][0]["session"] is None   # no reportedDate -> can't classify
    assert out["next_earnings"] is None


def test_fetch_yahoo_fundamentals_fetch_failure_is_all_empty():
    def fake_fail(u, h):
        raise urllib.error.URLError("boom")
    out = context.fetch_yahoo_fundamentals("NVDA", "abc", _get=fake_fail)
    assert out == {"short_pct_float": None, "pe_forward": None, "earnings": [], "next_earnings": None,
                   "ratings": [], "currency": None}

    # A 200 with a shape quoteSummary doesn't recognize is equally fail-soft.
    out2 = context.fetch_yahoo_fundamentals("NVDA", "abc", _get=lambda u, h: json.dumps({"quoteSummary": {"result": []}}).encode())
    assert out2 == {"short_pct_float": None, "pe_forward": None, "earnings": [], "next_earnings": None,
                    "ratings": [], "currency": None}


# ── earnings-row revenue backfill (added 2026-08-15, wave 3, Task C) ────────

def test_backfill_earnings_revenue_matches_by_quarter_number_and_year_mod_100():
    earnings = [
        {"period": "Q1 2027", "rev": None},
        {"period": "Q4 2026", "rev": None},
        {"period": "Q2 2027", "rev": 555.0},   # already has rev -> must NOT be overwritten
        {"period": None, "rev": None},           # unparseable -> left alone
        {"period": "Q3 2099", "rev": None},      # no matching quarter anywhere -> stays None
    ]
    quarterly = {"periods": ["Q4 26", "Q1 27", "Q2 27"], "revenue": [111.0, 222.0, 999.0], "eps": [0, 0, 0]}
    context._backfill_earnings_revenue(earnings, quarterly)
    assert earnings[0]["rev"] == 222.0   # "Q1 2027" -> "Q1 27"
    assert earnings[1]["rev"] == 111.0   # "Q4 2026" -> "Q4 26"
    assert earnings[2]["rev"] == 555.0   # untouched — already had a real value
    assert earnings[3]["rev"] is None    # unparseable period, left alone, never guessed
    assert earnings[4]["rev"] is None    # no match found, left alone


def test_backfill_earnings_revenue_never_touches_rev_est_or_surprise_pct():
    earnings = [{"period": "Q1 2027", "rev": None, "rev_est": None, "rev_surprise_pct": None}]
    quarterly = {"periods": ["Q1 27"], "revenue": [222.0], "eps": [0]}
    context._backfill_earnings_revenue(earnings, quarterly)
    assert earnings[0]["rev"] == 222.0
    assert earnings[0]["rev_est"] is None            # never invented
    assert earnings[0]["rev_surprise_pct"] is None   # never invented


def test_backfill_earnings_revenue_no_quarterly_series_is_a_no_op():
    earnings = [{"period": "Q1 2027", "rev": None}]
    context._backfill_earnings_revenue(earnings, {"periods": [], "revenue": [], "eps": []})
    assert earnings[0]["rev"] is None
    context._backfill_earnings_revenue(earnings, {})   # malformed/empty quarterly dict entirely
    assert earnings[0]["rev"] is None
    context._backfill_earnings_revenue([], {"periods": ["Q1 27"], "revenue": [1.0], "eps": [0]})  # no rows at all


def test_build_fund_sidecar_backfills_missing_revenue_from_stockanalysis_quarterly():
    """AXTI-shaped scenario (2026-08-15, live): Yahoo's earnings row has no
    financialsChart match for its quarter (rev stays None straight out of
    fetch_yahoo_fundamentals — see
    test_fetch_yahoo_fundamentals_revenue_unmatched_stays_none), but the SAME
    symbol's already-fetched stockanalysis.com quarterly series has that
    exact quarter ("Q1 2027" <-> "Q1 27" — same quarter number, year mod
    100), so build_fund_sidecar backfills rev from there. rev_est/
    rev_surprise_pct must stay untouched (never invented)."""
    period_end = int(datetime(2026, 4, 30, tzinfo=timezone.utc).timestamp())
    yahoo_result = {
        "defaultKeyStatistics": {},
        "earnings": {
            "earningsChart": {"quarterly": [{
                "date": "1Q2026", "fiscalQuarter": "1Q2027",
                "actual": {"raw": 0.05}, "estimate": {"raw": 0.04},
                "surprisePct": "25.0", "periodEndDate": {"raw": period_end}, "reportedDate": None,
            }]},
            "financialsChart": {"quarterly": []},   # no matching revenue row at all -> rev None
        },
        "calendarEvents": {},
    }
    financial_data = {
        "datekey": ["TTM", "2026-04-30"],
        "fiscalYear": ["2028", "2027"],
        "fiscalQuarter": ["Q2", "Q1"],
        "revenue": [999.0, 45123456.0],
        "epsdil": [9.9, 0.05],
    }
    sa_root_quarterly = {"financialData": financial_data}

    def fake_get(url, headers):
        if "statistics" in url:
            return _sa_skip_data_json()
        if "financials/income-statement" in url:
            return _sa_data_json(sa_root_quarterly)
        if "quoteSummary" in url:
            return _yahoo_qs(yahoo_result)
        raise AssertionError(url)

    payload = context.build_fund_sidecar("AXTI", date(2026, 8, 15), "crumbtoken", None, _get=fake_get)
    assert "Q1 27" in payload["quarterly"]["periods"]   # sanity: the quarterly series really has it
    assert payload["earnings"][0]["period"] == "Q1 2027"
    assert payload["earnings"][0]["rev"] == pytest.approx(45123456.0)   # backfilled
    assert payload["earnings"][0]["rev_est"] is None                     # never invented
    assert payload["earnings"][0]["rev_surprise_pct"] is None            # never invented


def test_build_fund_sidecar_revenue_stays_null_when_no_quarterly_series_to_backfill_from():
    """Fail-soft: when stockanalysis.com's quarterly leg has nothing (fetch
    failed entirely here), a Yahoo earnings row with rev None stays None —
    never guessed, never zero-filled."""
    period_end = int(datetime(2026, 4, 30, tzinfo=timezone.utc).timestamp())
    yahoo_result = {
        "defaultKeyStatistics": {},
        "earnings": {
            "earningsChart": {"quarterly": [{
                "date": "1Q2026", "fiscalQuarter": "1Q2027",
                "actual": {"raw": 0.05}, "estimate": {"raw": 0.04},
                "surprisePct": "25.0", "periodEndDate": {"raw": period_end}, "reportedDate": None,
            }]},
            "financialsChart": {"quarterly": []},
        },
        "calendarEvents": {},
    }
    def fake_get(url, headers):
        if "statistics" in url:
            return _sa_skip_data_json()
        if "financials/income-statement" in url:
            raise urllib.error.URLError("boom")   # quarterly leg fails entirely
        if "quoteSummary" in url:
            return _yahoo_qs(yahoo_result)
        raise AssertionError(url)
    payload = context.build_fund_sidecar("AXTI", date(2026, 8, 15), "crumbtoken", None, _get=fake_get)
    assert payload["earnings"][0]["rev"] is None
    assert payload["quarterly"] == {"periods": [], "revenue": [], "eps": [], "ni": [], "fcf": [], "opinc": []}


def test_build_fund_sidecar_yahoo_next_earnings_session_falls_back_to_stockanalysis_text():
    """Yahoo's calendarEvents carries no intraday time, so next_earnings.session
    is None straight out of fetch_yahoo_fundamentals; build_fund_sidecar must
    fill it in — from a TV earnings_ts if one is available, else from
    stockanalysis.com's own before/after-market text."""
    sa_stats_root = {
        "shortSelling": {"data": [{"id": "shortFloat", "hover": "4.103%"}]},
        "ratios": {"data": [{"id": "peForward", "hover": "48.83"}]},
        "dates": {"text": "after market close", "data": [{"id": "earningsdate", "value": "Aug 27, 2026"}]},
    }
    next_earn_ts = int(datetime(2026, 8, 27, tzinfo=timezone.utc).timestamp())
    yahoo_result = {
        "defaultKeyStatistics": {},
        "earnings": {"earningsChart": {"quarterly": []}, "financialsChart": {"quarterly": []}},
        "calendarEvents": {"earnings": {
            "earningsDate": [{"raw": next_earn_ts}],
            "earningsAverage": {"raw": 2.01}, "revenueAverage": {"raw": 92100000000.0},
        }},
    }
    def fake_get(url, headers):
        if "statistics" in url:
            return _sa_data_json(sa_stats_root)
        if "financials/income-statement" in url:
            raise urllib.error.URLError("boom")   # quarterly leg fails independently
        if "quoteSummary" in url:
            return _yahoo_qs(yahoo_result)
        raise AssertionError(url)

    # No TV earnings_ts available -> falls back to stockanalysis.com's session text.
    payload = context.build_fund_sidecar("MRVL", date(2026, 8, 15), "crumbtoken", None, _get=fake_get)
    assert payload["sym"] == "MRVL" and payload["built"] == "2026-08-15"
    assert payload["short_pct_float"] == pytest.approx(4.103)
    assert payload["pe_forward"] == pytest.approx(48.83)
    assert payload["quarterly"] == {"periods": [], "revenue": [], "eps": [], "ni": [], "fcf": [], "opinc": []}   # that leg failed, stays scaffolded
    assert payload["next_earnings"] == {
        "date": "2026-08-27", "session": "AMC",   # from stockanalysis.com's text, not TV
        "eps_est": pytest.approx(2.01), "rev_est": pytest.approx(92100000000.0),
    }

    # A same-ticker TV earnings_ts, if available, takes priority over the
    # stockanalysis.com text (premarket here vs AMC from the text above).
    premarket_ts = datetime(2026, 8, 27, 11, 0, tzinfo=timezone.utc).timestamp()   # 07:00 ET -> premarket
    payload2 = context.build_fund_sidecar("MRVL", date(2026, 8, 15), "crumbtoken", premarket_ts, _get=fake_get)
    assert payload2["next_earnings"]["session"] == "premarket"


def test_build_fund_sidecar_yahoo_leg_skipped_entirely_when_crumb_is_none():
    sa_stats_root = {
        "shortSelling": {"data": [{"id": "shortFloat", "hover": "2.0%"}]},
        "ratios": {"data": [{"id": "peForward", "hover": "10.0"}]},
        "dates": {"text": "before market open", "data": [{"id": "earningsdate", "value": "Sep 1, 2026"}]},
    }
    def fake_get(url, headers):
        if "statistics" in url:
            return _sa_data_json(sa_stats_root)
        if "financials/income-statement" in url:
            raise urllib.error.URLError("boom")
        raise AssertionError(f"yahoo must not be called with no crumb: {url}")
    payload = context.build_fund_sidecar("XYZ", date(2026, 8, 15), None, None, _get=fake_get)
    assert payload["short_pct_float"] == pytest.approx(2.0)
    assert payload["pe_forward"] == pytest.approx(10.0)
    assert payload["earnings"] == []
    assert payload["next_earnings"] == {"date": "2026-09-01", "session": "BMO", "eps_est": None, "rev_est": None}
    assert payload["quarterly"] == {"periods": [], "revenue": [], "eps": [], "ni": [], "fcf": [], "opinc": []}


def test_build_fund_universe_fetches_crumb_exactly_once_across_symbols():
    calls = {"crumb": 0}
    def fake_get(url, headers):
        if "fc.yahoo.com" in url:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        if "getcrumb" in url:
            calls["crumb"] += 1
            return b"crumb"
        if "statistics" in url or "financials/income-statement" in url:
            return _sa_skip_data_json()
        if "quoteSummary" in url:
            return _yahoo_qs({})
        raise AssertionError(url)
    out = context.build_fund_universe(["A", "B", "C"], date(2026, 8, 15), _get=fake_get)
    assert set(out.keys()) == {"A", "B", "C"}
    assert calls["crumb"] == 1   # one crumb dance for the whole run, not per symbol


def test_build_fund_universe_no_crumb_still_builds_from_stockanalysis_only():
    def fake_get(url, headers):
        if "fc.yahoo.com" in url or "getcrumb" in url:
            raise urllib.error.URLError("boom")
        if "quoteSummary" in url:
            raise AssertionError("must not call yahoo quoteSummary with no crumb")
        if "statistics" in url or "financials/income-statement" in url:
            return _sa_skip_data_json()
        raise AssertionError(url)
    out = context.build_fund_universe(["A"], date(2026, 8, 15), _get=fake_get)
    assert "A" in out


def test_build_fund_universe_symbol_level_exception_is_fail_soft(monkeypatch):
    """One symbol's total, unexpected failure inside build_fund_sidecar must
    not lose the rest of the universe."""
    real_build = context.build_fund_sidecar
    def flaky(sym, session_date, crumb, earn_ts, _get=None):
        if sym == "BAD":
            raise RuntimeError("boom")
        return real_build(sym, session_date, crumb, earn_ts, _get=_get)
    monkeypatch.setattr(context, "build_fund_sidecar", flaky)

    def fake_get(url, headers):
        if "fc.yahoo.com" in url:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        if "getcrumb" in url:
            return b"crumb"
        if "statistics" in url or "financials/income-statement" in url:
            return _sa_skip_data_json()
        if "quoteSummary" in url:
            return _yahoo_qs({})
        raise AssertionError(url)

    out = context.build_fund_universe(["GOOD", "BAD"], date(2026, 8, 15), _get=fake_get)
    assert set(out.keys()) == {"GOOD"}


# ── tape bars + truncated-series retry (2026-08-17) ─────────────────────────

def test_tape_bars_fetch_under_yahoo_alias_but_key_by_desk_key():
    """TAPE_BARS symbols are FETCHED as their Yahoo ticker (^VIX, CL=F) and
    STORED under the desk key the page looks them up by (VIX, CRUDE). The
    URL-encoding matters: a bare "^" or "=" in the path is not a valid URL."""
    seen = []
    def fake_get(url, headers):
        seen.append(url)
        return _yahoo_json([float(100 + i) for i in range(300)])
    payload, _ = context.build_bars(["VIX", "CRUDE", "MU"], date(2026, 8, 15),
                                    _get=fake_get, aliases=context.TAPE_BARS)
    assert sorted(payload["bars"].keys()) == ["CRUDE", "MU", "VIX"]
    assert any("%5EVIX" in u for u in seen)      # ^VIX, percent-encoded
    assert any("CL%3DF" in u for u in seen)      # CL=F, percent-encoded
    assert any("/MU?" in u for u in seen)        # no alias -> fetched as itself
    assert not any("/VIX?" in u for u in seen)   # never fetched under the desk key


def test_crude_bars_key_is_not_wti():
    """W&T Offshore (the oil-producer equity) owns the ticker "WTI" in the
    rail. Crude must never be stored under it or the rail row and the tape
    tile would chart the same key at two completely different prices."""
    assert "WTI" not in context.TAPE_BARS
    assert context.TAPE_BARS["CRUDE"] == "CL=F"


def test_truncated_series_is_refetched_and_longest_response_wins():
    """Yahoo intermittently answers with a well-formed but truncated series
    (measured live on ^TNX: 17 rows instead of ~502, on roughly half of
    identical back-to-back requests). The short response must be refetched,
    not charted — 17 bars silently draw a chart with no 50/200-day averages."""
    responses = [_yahoo_json([1.0] * 16),                              # truncated
                 _yahoo_json([1.0] * 16),                              # truncated again
                 _yahoo_json([float(i) for i in range(1, 401)])]       # good
    calls = {"n": 0}
    def fake_get(url, headers):
        r = responses[min(calls["n"], len(responses) - 1)]
        calls["n"] += 1
        return r
    payload, _ = context.build_bars(["US10Y"], date(2026, 8, 15), _get=fake_get)
    assert calls["n"] == 3                       # initial + 2 retries
    assert len(payload["bars"]["US10Y"]) == 400  # the good series, not the 16-row one


def test_short_series_retry_stops_once_a_full_series_arrives():
    """A healthy symbol costs exactly one request — the retry must be driven
    by the short series, never run unconditionally."""
    calls = {"n": 0}
    def fake_get(url, headers):
        calls["n"] += 1
        return _yahoo_json([float(i) for i in range(1, 301)])
    context.build_bars(["SPY"], date(2026, 8, 15), _get=fake_get)
    assert calls["n"] == 1


def test_genuinely_short_listing_survives_retries_and_is_kept():
    """A young listing (SKHY, DRAM) really does have few bars. It gets
    retried, then KEPT — never dropped — so the rail doesn't lose the name."""
    calls = {"n": 0}
    def fake_get(url, headers):
        calls["n"] += 1
        return _yahoo_json([float(i) for i in range(1, 41)])
    payload, avg = context.build_bars(["SKHY"], date(2026, 8, 15), _get=fake_get)
    assert calls["n"] == 1 + context.BARS_SHORT_RETRIES
    assert len(payload["bars"]["SKHY"]) == 40
    assert "SKHY" in avg


def test_first_attempt_error_still_skips_symbol_without_retrying():
    calls = {"n": 0}
    def fake_get(url, headers):
        calls["n"] += 1
        raise urllib.error.URLError("boom")
    payload, _ = context.build_bars(["BAD"], date(2026, 8, 15), _get=fake_get)
    assert payload["bars"] == {} and calls["n"] == 1


def test_retry_error_keeps_the_short_series_already_in_hand():
    """A failure on a RETRY must not throw away the (short but real) series
    the first attempt returned."""
    calls = {"n": 0}
    def fake_get(url, headers):
        calls["n"] += 1
        if calls["n"] == 1:
            return _yahoo_json([float(i) for i in range(1, 31)])
        raise urllib.error.URLError("boom")
    payload, _ = context.build_bars(["ZZZ"], date(2026, 8, 15), _get=fake_get)
    assert len(payload["bars"]["ZZZ"]) == 30


# ── catalyst units (2026-08-17) ─────────────────────────────────────────────

def _econ_payload(**over):
    row = {"title": "Housing Starts", "date": "2026-08-18T12:30:00.000Z",
           "importance": 1, "forecast": 1.35, "previous": 1.427, "actual": None,
           "unit": None, "scale": "M", "period": "Jul", "source": "Census Bureau"}
    row.update(over)
    return json.dumps({"result": [row]}).encode()


def test_econ_rows_carry_unit_scale_period_and_agency():
    """The feed's unit/scale/period/source were being dropped, which is why
    the desk rendered "fc 1.35 · prior 1.427" for a figure denominated in
    millions of homes. All four now ride along for the renderer."""
    rows = context.fetch_econ_tv(_get=lambda url, headers: _econ_payload())
    assert len(rows) == 1
    r = rows[0]
    assert r["scale"] == "M" and r["period"] == "Jul"
    assert r["agency"] == "Census Bureau"
    assert r["unit"] is None                 # this release carries no unit
    assert r["forecast"] == 1.35 and r["prior"] == 1.427   # already scaled, not rescaled


def test_econ_percent_unit_passes_through():
    rows = context.fetch_econ_tv(_get=lambda url, headers: _econ_payload(
        title="Unemployment Rate", unit="%", scale=None, previous=4.1))
    assert rows[0]["unit"] == "%" and rows[0]["scale"] is None


def test_econ_blank_labels_normalize_to_none_not_empty_string():
    """"" and None must both mean "no label" so the page tests one condition."""
    rows = context.fetch_econ_tv(_get=lambda url, headers: _econ_payload(
        unit="  ", scale="", period=None, source=""))
    r = rows[0]
    assert r["unit"] is None and r["scale"] is None
    assert r["period"] is None and r["agency"] is None


# ── 10. Fed-hike odds (Polymarket, added 2026-08-18) ─────────────────────────
# What these defend: the desk must never print a hike probability it cannot
# stand behind. A thin book, a book that does not sum to ~100%, a flipped
# Yes/No pair, or a dead endpoint all have to produce NO CARD rather than a
# confident-looking number — and the card, once shown, has to carry the DAILY
# change Zach asked for (2026-08-18), not just the weekly one.

def _poly_market(label, yes, token="tok", closed=False):
    """Gamma's real wire shape: outcomes / outcomePrices / clobTokenIds arrive
    as JSON-encoded STRINGS inside the JSON, not as arrays."""
    return {
        "groupItemTitle": label,
        "outcomes": json.dumps(["Yes", "No"]),
        "outcomePrices": json.dumps([f"{yes}", f"{1 - yes:.4f}"]),
        "clobTokenIds": json.dumps([token, token + "_no"]),
        "closed": closed,
    }


def _poly_sept(volume=36_569_390.0):
    return {
        "title": "Fed Decision in September?",
        "slug": "fed-decision-in-september-762",
        "endDate": "2026-09-16T00:00:00Z",
        "volume": volume, "liquidity": 3_828_616.38,
        "markets": [
            _poly_market("50+ bps decrease", 0.0035, "d50"),
            _poly_market("25 bps decrease", 0.0075, "d25"),
            _poly_market("No change", 0.715, "hold"),
            _poly_market("25 bps increase", 0.285, "u25"),
            _poly_market("50+ bps increase", 0.0035, "u50"),
        ],
    }


def _poly_dec():
    """Higher volume, LATER meeting — the shelf really does order December
    above September, so picking by volume order would read the wrong meeting."""
    e = _poly_sept(volume=99_000_000.0)
    e["title"] = "Fed Decision in December?"
    e["slug"] = "fed-decision-in-december-x"
    e["endDate"] = "2026-12-09T23:59:00Z"
    return e


def _poly_year(yes=0.485):
    return {"title": "Fed rate hike in 2026?", "slug": "fed-rate-hike-in-2026",
            "endDate": "2026-12-09T00:00:00Z", "volume": 7_614_865.0,
            "markets": [_poly_market("", yes, "yr")]}


def _poly_get(events, history=None, fail_history=False):
    hist = history or []

    def fake_get(url, headers):
        if url.startswith(context.POLY_EVENTS_URL):
            return json.dumps(events).encode()
        if url.startswith(context.POLY_HISTORY_URL):
            if fail_history:
                raise urllib.error.URLError("down")
            return json.dumps({"history": hist}).encode()
        raise AssertionError(f"unexpected URL {url}")
    return fake_get


def _poly_hist(points):
    """CLOB history wire shape: [{"t": unix, "p": price}]. A fixture of bare
    tuples parses to an EMPTY history and makes delta assertions vacuous."""
    return [{"t": t, "p": p} for t, p in points]


SESSION = date(2026, 8, 18)


def test_fed_odds_happy_path_normalises_the_book_to_100():
    out = context.fetch_fed_odds(SESSION, _get=_poly_get([_poly_sept(), _poly_year()]))
    assert out["hike_pct"] == pytest.approx(28.4, abs=0.1)
    assert out["hold_pct"] == pytest.approx(70.5, abs=0.1)
    assert (out["hike_pct"] + out["hold_pct"] + out["cut_pct"]) == pytest.approx(100.0, abs=0.2)
    assert out["hike_pct_raw"] == pytest.approx(28.85)
    assert out["meeting_date"] == "2026-09-16"
    assert out["days_to_meeting"] == 29
    assert out["year_hike_pct"] == pytest.approx(48.5)
    assert out["url"] == "https://polymarket.com/event/fed-decision-in-september-762"
    assert out["grade"] == "HOSTILE"        # 28% clears FED_HIKE_HOSTILE_PCT
    assert out["alarm"] is False           # but not the 40% alarm line


def test_fed_odds_sums_every_increase_leg_not_just_the_headline_one():
    """"Does the Fed raise" is satisfied by ANY increase, 25bp or 50bp."""
    out = context.fetch_fed_odds(SESSION, _get=_poly_get([_poly_sept()]))
    assert out["hike_pct_raw"] == pytest.approx(28.5 + 0.35)


def test_fed_odds_picks_the_nearest_meeting_not_the_biggest_market():
    out = context.fetch_fed_odds(SESSION, _get=_poly_get([_poly_dec(), _poly_sept()]))
    assert out["meeting_date"] == "2026-09-16"


def test_fed_odds_reads_yes_by_label_not_by_position():
    """A flipped outcomes pair must not turn a 28% hike into a 72% one."""
    e = _poly_sept()
    e["markets"][3]["outcomes"] = json.dumps(["No", "Yes"])
    e["markets"][3]["outcomePrices"] = json.dumps(["0.715", "0.285"])
    out = context.fetch_fed_odds(SESSION, _get=_poly_get([e]))
    assert out["hike_pct_raw"] == pytest.approx(28.85)


def test_fed_odds_carries_the_daily_change_alongside_the_weekly():
    """Zach, 2026-08-18: "I want the daily update, not just weekly." Each
    window takes the last print at or before its cutoff; both hike legs read
    the same fixture history here, so every figure doubles."""
    import time
    now = int(time.time())
    hist = _poly_hist([(now - 40 * 86400, 0.10), (now - 8 * 86400, 0.20),
                       (now - 2 * 86400, 0.30), (now - 60, 0.40)])
    out = context.fetch_fed_odds(SESSION, _get=_poly_get([_poly_sept()], hist))
    assert out["chg_1d_pp"] == pytest.approx(28.85 - 60.0, abs=0.1)
    assert out["chg_1w_pp"] == pytest.approx(28.85 - 40.0, abs=0.1)
    assert out["chg_1m_pp"] == pytest.approx(28.85 - 20.0, abs=0.1)


def test_fed_odds_reports_no_delta_rather_than_a_partial_one():
    """History that does not reach back a week must print nothing for the week,
    never the oldest available number relabelled."""
    import time
    now = int(time.time())
    hist = _poly_hist([(now - 3600, 0.28)])
    out = context.fetch_fed_odds(SESSION, _get=_poly_get([_poly_sept()], hist))
    assert out["chg_1d_pp"] is None
    assert out["chg_1w_pp"] is None


def test_fed_odds_survives_a_dead_history_endpoint():
    """The probability comes from gamma; history is a nice-to-have."""
    out = context.fetch_fed_odds(SESSION,
                                 _get=_poly_get([_poly_sept()], fail_history=True))
    assert out["hike_pct"] == pytest.approx(28.4, abs=0.1)
    assert out["chg_1d_pp"] is None


def test_fed_odds_a_hard_one_day_jump_grades_hostile_and_alarms():
    import time
    now = int(time.time())
    e = _poly_sept()
    # 12% hike now, 1% a day ago -> +11pp in a day, well past FED_HIKE_JUMP_PP
    e["markets"][3] = _poly_market("25 bps increase", 0.12, "u25")
    e["markets"][2] = _poly_market("No change", 0.875, "hold")
    hist = _poly_hist([(now - 3 * 86400, 0.005), (now - 60, 0.06)])
    out = context.fetch_fed_odds(SESSION, _get=_poly_get([e], hist))
    assert out["chg_1d_pp"] >= context.FED_HIKE_JUMP_PP
    assert out["grade"] == "HOSTILE"
    assert out["alarm"] is True


def test_fed_odds_an_expected_cut_grades_supportive():
    e = _poly_sept()
    e["markets"] = [_poly_market("25 bps decrease", 0.79, "d25"),
                    _poly_market("No change", 0.20, "hold"),
                    _poly_market("25 bps increase", 0.01, "u25")]
    out = context.fetch_fed_odds(SESSION, _get=_poly_get([e]))
    assert out["grade"] == "SUPPORTIVE"
    assert out["alarm"] is False


def test_fed_odds_thin_book_returns_none_not_a_number():
    assert context.fetch_fed_odds(
        SESSION, _get=_poly_get([_poly_sept(volume=1_000.0)])) is None


def test_fed_odds_book_that_does_not_sum_to_about_100_returns_none():
    e = _poly_sept()
    e["markets"] = [_poly_market("25 bps increase", 0.285, "u25"),
                    _poly_market("No change", 0.30, "hold")]
    assert context.fetch_fed_odds(SESSION, _get=_poly_get([e])) is None


def test_fed_odds_past_meeting_is_not_used():
    assert context.fetch_fed_odds(
        date(2026, 10, 1), _get=_poly_get([_poly_sept()])) is None


def test_fed_odds_no_increase_leg_returns_none():
    e = _poly_sept()
    e["markets"] = [_poly_market("No change", 1.0, "hold")]
    assert context.fetch_fed_odds(SESSION, _get=_poly_get([e])) is None


def test_fed_odds_dead_endpoint_and_garbage_are_fail_soft():
    def boom(url, headers):
        raise urllib.error.URLError("network down")
    assert context.fetch_fed_odds(SESSION, _get=boom) is None
    for junk in (b"not json", b'{"not":"a list"}', b"[]", b'[{"title":null}]'):
        assert context.fetch_fed_odds(SESSION, _get=lambda u, h, j=junk: j) is None


def test_fed_odds_ignores_unrelated_events_on_the_fed_shelf():
    noise = {"title": "Jerome Powell out of Fed Board by…?",
             "endDate": "2026-12-31T00:00:00Z", "volume": 5_000_000.0,
             "markets": [_poly_market("", 0.1)]}
    assert context.fetch_fed_odds(SESSION, _get=_poly_get([noise])) is None


# ── build_context wiring + cache survival ───────────────────────────────────

def test_fed_odds_land_in_the_data_json_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(context, "CONTEXT_CACHE_FILE", tmp_path / ".context_cache.json")
    now = datetime(2026, 8, 18, 14, 0, 0, tzinfo=timezone.utc)
    cache = {"context_fetched_at": None,            # stale -> the gate runs
             "bars_built_date": "2026-08-18",       # bars fresh -> no bars work
             "bars_sig": context.BARS_BUILD_SIG, "avg_move": {},
             "brief": None, "catalysts": [], "news": None, "desk_private": None}
    context.save_context_cache(cache)

    poly = _poly_get([_poly_sept(), _poly_year()])

    def fake_get(url, headers):
        if url.startswith(context.POLY_EVENTS_URL) or url.startswith(context.POLY_HISTORY_URL):
            return poly(url, headers)
        return b"{}"          # every other leg fails soft on its own

    quotes = {"MU": {"tv_symbol": "NASDAQ:MU", "earnings_ts": None, "hi52": None,
                     "lo52": None, "market_cap": None, "beta": None,
                     "avol": None, "rsi": None}}
    fields, _, _, _, _cons = context.build_context(quotes, ["MU"], SESSION, now, _get=fake_get)
    assert fields["fed_odds"]["hike_pct"] == pytest.approx(28.4, abs=0.1)


def test_fed_odds_survive_the_cache_round_trip_between_hourly_refreshes(tmp_path, monkeypatch):
    """load_context_cache rebuilds a FIXED dict, so an unlisted key is dropped
    on reload — that would blink the desk's Fed card out on every cycle between
    the hourly fetches."""
    monkeypatch.setattr(context, "CONTEXT_CACHE_FILE", tmp_path / ".context_cache.json")
    now = datetime(2026, 8, 18, 14, 0, 0, tzinfo=timezone.utc)
    context.save_context_cache({
        "context_fetched_at": "2026-08-18T13:30:00Z",     # 30 min ago -> fresh
        "bars_built_date": "2026-08-18", "bars_sig": context.BARS_BUILD_SIG,
        "avg_move": {}, "brief": None, "catalysts": [], "news": None,
        "desk_private": None,
        "fed_odds": {"hike_pct": 28.4, "grade": "HOSTILE"},
    })
    quotes = {"MU": {"tv_symbol": "NASDAQ:MU", "earnings_ts": None, "hi52": None,
                     "lo52": None, "market_cap": None, "beta": None,
                     "avol": None, "rsi": None}}
    fields, _, _, _, _cons = context.build_context(quotes, ["MU"], SESSION, now, _get=_boom)
    assert fields["fed_odds"] == {"hike_pct": 28.4, "grade": "HOSTILE"}


def test_absent_fed_odds_omit_the_key_entirely(tmp_path, monkeypatch):
    """No key at all, so the page hides the card. Never a 0% hike."""
    monkeypatch.setattr(context, "CONTEXT_CACHE_FILE", tmp_path / ".context_cache.json")
    now = datetime(2026, 8, 18, 14, 0, 0, tzinfo=timezone.utc)
    context.save_context_cache({
        "context_fetched_at": "2026-08-18T13:30:00Z", "bars_built_date": "2026-08-18",
        "bars_sig": context.BARS_BUILD_SIG, "avg_move": {}, "brief": None,
        "catalysts": [], "news": None, "desk_private": None, "fed_odds": None})
    quotes = {"MU": {"tv_symbol": "NASDAQ:MU", "earnings_ts": None, "hi52": None,
                     "lo52": None, "market_cap": None, "beta": None,
                     "avol": None, "rsi": None}}
    fields, _, _, _, _cons = context.build_context(quotes, ["MU"], SESSION, now, _get=_boom)
    assert "fed_odds" not in fields

def test_intraday_gate_fresh_timestamp_skips_rebuild(tmp_path, monkeypatch):
    """intraday_built_at newer than INTRA_STALE_SEC -> build_intraday_bars is
    not called at all; stale/absent -> it is. The gate is independent of the
    once-daily bars gate."""
    from datetime import date, datetime, timezone
    monkeypatch.setattr(context, "CONTEXT_CACHE_FILE", tmp_path / ".context_cache.json")
    monkeypatch.setattr(context, "INTRA_SLEEP_SEC", 0)
    now = datetime(2026, 8, 18, 14, 0, tzinfo=timezone.utc)
    calls = []
    monkeypatch.setattr(context, "build_intraday_bars",
                        lambda *a, **k: calls.append(1) or {"built": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "v": 1, "i15": {}, "i60": {}})
    def _boom(*a, **k):
        raise AssertionError("network")
    quotes = {"MU": {"tv_symbol": "NASDAQ:MU", "earnings_ts": None, "hi52": None, "lo52": None,
                     "market_cap": None, "beta": None, "avol": None, "rsi": None}}
    # 1st build: no timestamp in cache -> rebuild fires
    context.build_context(quotes, ["MU"], date(2026, 8, 18), now, _get=_boom)
    assert len(calls) == 1
    # 2nd build 5 minutes later: fresh -> no rebuild
    now2 = datetime(2026, 8, 18, 14, 5, tzinfo=timezone.utc)
    context.build_context(quotes, ["MU"], date(2026, 8, 18), now2, _get=_boom)
    assert len(calls) == 1
    # 3rd build 30 minutes later: stale -> rebuild fires again
    now3 = datetime(2026, 8, 18, 14, 35, tzinfo=timezone.utc)
    context.build_context(quotes, ["MU"], date(2026, 8, 18), now3, _get=_boom)
    assert len(calls) == 2


def test_extract_yahoo_ohlcv_ts_drops_rows_without_timestamps():
    obj = {"chart": {"result": [{
        "timestamp": [100, None, 300],
        "indicators": {"quote": [{
            "open": [1.0, 2.0, 3.0], "high": [1.5, 2.5, 3.5],
            "low": [0.5, 1.5, 2.5], "close": [1.2, 2.2, 3.2],
            "volume": [10, 20, None]}]}}]}}
    rows = context._extract_yahoo_ohlcv_ts(obj)
    assert [r[0] for r in rows] == [100, 300]          # ts-less row dropped
    assert rows[0][1:] == [1.0, 1.5, 0.5, 1.2, 10]
    assert rows[1][5] is None                          # missing volume kept as None


# ── analyst rating changes (added 2026-08-19) ───────────────────────────────

def _rating_row(ts, action, firm="Firm A", frm="Neutral", to="Buy", pt=0.0, prior=0.0):
    return {"epochGradeDate": ts, "firm": firm, "toGrade": to, "fromGrade": frm,
            "action": action, "priceTargetAction": "Raises",
            "currentPriceTarget": pt, "priorPriceTarget": prior}


def test_parse_ratings_keeps_only_real_upgrades_and_downgrades():
    """init / reit / main are 60-78% of a real history and are NOT rating
    changes — classifying on the price target instead would paint the chart
    with false markers."""
    today = date(2026, 8, 19)
    base = int(datetime(2026, 6, 1, 14, 30, tzinfo=timezone.utc).timestamp())
    hist = [
        _rating_row(base, "up", firm="B of A", frm="Neutral", to="Buy", pt=300.0, prior=250.0),
        _rating_row(base - 86400, "down", firm="New Street", frm="Buy", to="Neutral"),
        _rating_row(base - 2 * 86400, "main", firm="Citi"),      # price target moved, rating held
        _rating_row(base - 3 * 86400, "init", firm="Wolfe", frm=""),
        _rating_row(base - 4 * 86400, "reit", firm="UBS"),
    ]
    rows = context._parse_ratings({"history": hist}, today=today)
    assert [r["dir"] for r in rows] == ["up", "down"]
    assert rows[0]["firm"] == "B of A" and rows[0]["to"] == "Buy" and rows[0]["from"] == "Neutral"
    assert rows[0]["pt"] == pytest.approx(300.0) and rows[0]["pt_prior"] == pytest.approx(250.0)
    assert rows[1]["pt"] is None and rows[1]["pt_prior"] is None   # Yahoo writes 0.0 for absent, never a $0 target


def test_parse_ratings_uses_eastern_calendar_date():
    """A row stamped after 8pm ET belongs on THAT trading day, not the next
    one — the same class of off-by-one the snapshot session-date guard fixed."""
    ts = int(datetime(2026, 6, 2, 1, 30, tzinfo=timezone.utc).timestamp())   # 9:30pm ET on 06-01
    rows = context._parse_ratings({"history": [_rating_row(ts, "up")]}, today=date(2026, 8, 19))
    assert rows[0]["date"] == "2026-06-01"
    assert rows[0]["ts"] == ts        # raw epoch kept so same-day rows still order


def test_parse_ratings_drops_stale_rows_caps_and_dedupes():
    today = date(2026, 8, 19)
    old_ts = int(datetime(2020, 1, 2, 15, 0, tzinfo=timezone.utc).timestamp())
    fresh = int(datetime(2026, 7, 1, 15, 0, tzinfo=timezone.utc).timestamp())
    hist = [_rating_row(old_ts, "up")]                                  # older than RATINGS_MAX_AGE_DAYS
    hist += [_rating_row(fresh, "up", firm="Dup"), _rating_row(fresh + 60, "up", firm="Dup")]  # same day+firm+dir
    hist += [_rating_row(fresh - i * 86400, "down", firm="F%d" % i) for i in range(1, 60)]
    rows = context._parse_ratings({"history": hist}, today=today)
    assert len(rows) == context.RATINGS_MAX
    assert all(r["date"] >= "2023" for r in rows)
    dups = [r for r in rows if r["firm"] == "Dup"]
    assert len(dups) == 1


def test_parse_ratings_missing_or_broken_module_is_empty_never_raises():
    """ETFs omit the module entirely; a garbage payload must not kill the
    sidecar build."""
    for bad in (None, {}, {"history": None}, {"history": [None, 5, "x"]},
                {"history": [{"action": "up"}]},                     # no timestamp
                {"history": [_rating_row("nope", "up")]}):
        assert context._parse_ratings(bad, today=date(2026, 8, 19)) == []


def test_fund_sidecar_carries_ratings_and_survives_their_absence():
    period_end = int(datetime(2026, 4, 30, tzinfo=timezone.utc).timestamp())
    ts = int(datetime(2026, 5, 12, 15, 0, tzinfo=timezone.utc).timestamp())
    yahoo_result = {
        "defaultKeyStatistics": {}, "calendarEvents": {},
        "earnings": {"earningsChart": {"quarterly": []}, "financialsChart": {"quarterly": []}},
        "upgradeDowngradeHistory": {"history": [
            _rating_row(ts, "down", firm="Barclays", frm="Overweight", to="Equal Weight"),
            _rating_row(ts - 86400, "main", firm="Citi"),
        ]},
    }
    def fake_get(url, headers):
        if "statistics" in url or "financials" in url:
            return _sa_skip_data_json()
        if "quoteSummary" in url:
            assert "upgradeDowngradeHistory" in url    # rides the SAME request, no extra call
            return _yahoo_qs(yahoo_result)
        raise AssertionError(url)
    payload = context.build_fund_sidecar("MU", date(2026, 8, 19), "crumbtoken", period_end, _get=fake_get)
    assert [r["dir"] for r in payload["ratings"]] == ["down"]
    assert payload["ratings"][0]["firm"] == "Barclays"

    yahoo_result.pop("upgradeDowngradeHistory")        # ETF-shaped response
    payload2 = context.build_fund_sidecar("SPY", date(2026, 8, 19), "crumbtoken", None, _get=fake_get)
    assert payload2["ratings"] == []


def test_yahoo_fundamentals_carries_reporting_currency():
    """A US-listed ADR reports in its home currency; the page must be able to
    say so instead of labeling trillions of won "dollars"."""
    body = json.dumps({"quoteSummary": {"result": [{
        "defaultKeyStatistics": {},
        "financialData": {"financialCurrency": "KRW"},
    }]}}).encode()
    out = context.fetch_yahoo_fundamentals("SKHY", "abc", _get=lambda u, h: body)
    assert out["currency"] == "KRW"


def test_yahoo_fundamentals_currency_rejects_junk():
    for junk in ("", "US DOLLAR", "US$", "u", None, 7):
        body = json.dumps({"quoteSummary": {"result": [{
            "defaultKeyStatistics": {},
            "financialData": {"financialCurrency": junk},
        }]}}).encode()
        out = context.fetch_yahoo_fundamentals("X", "abc", _get=lambda u, h: body)
        assert out["currency"] is None, junk


def test_yahoo_fundamentals_currency_absent_module_is_none():
    body = json.dumps({"quoteSummary": {"result": [{"defaultKeyStatistics": {}}]}}).encode()
    out = context.fetch_yahoo_fundamentals("SPY", "abc", _get=lambda u, h: body)
    assert out["currency"] is None


def test_quotesummary_request_asks_for_financial_data():
    """The currency rides the existing call — no second request may appear."""
    seen = []

    def spy(url, headers):
        seen.append(url)
        return json.dumps({"quoteSummary": {"result": [{"defaultKeyStatistics": {}}]}}).encode()

    context.fetch_yahoo_fundamentals("MU", "abc", _get=spy)
    assert len(seen) == 1
    assert "financialData" in seen[0]


def test_fund_build_sig_forces_a_rebuild_for_currency():
    assert context.FUND_BUILD_SIG == "v4-ni-fcf-ratings-currency"


# ── quote-wick repair (added 2026-08-19) ────────────────────────────────────

def _wick_rows(extra=None):
    """Twelve calm bars plus whatever `extra` adds. Calm = 0.1% wicks."""
    rows = []
    for i in range(12):
        base = 100.0 + i
        rows.append([1700000000 + i * 900, base, base * 1.001, base * 0.999, base + 0.5, 1000])
    if extra:
        rows.extend(extra)
    return rows


def test_repair_quote_wicks_clamps_a_zero_volume_artifact():
    """The MU case: a zero-volume bar whose wick is 28% from its own body."""
    bad = [1700020000, 110.0, 141.0, 79.0, 110.1, 0]
    rows = _wick_rows([bad])
    n = context._repair_quote_wicks(rows, "MU", "15m")
    assert n == 1
    assert rows[-1][2] == 110.1      # high clamped to the body top
    assert rows[-1][3] == 110.0      # low clamped to the body bottom
    assert rows[-1][1] == 110.0 and rows[-1][4] == 110.1   # open/close untouched


def test_repair_quote_wicks_never_touches_a_bar_that_traded():
    """Volume means the wick is real, however large."""
    traded = [1700020000, 110.0, 141.0, 79.0, 110.1, 5_000_000]
    rows = _wick_rows([traded])
    assert context._repair_quote_wicks(rows, "MU", "15m") == 0
    assert rows[-1][2] == 141.0 and rows[-1][3] == 79.0


def test_repair_quote_wicks_leaves_ordinary_zero_volume_bars_alone():
    """Most zero-volume bars are extended-hours bars with sane wicks."""
    calm = [1700020000, 110.0, 110.2, 109.8, 110.1, 0]
    rows = _wick_rows([calm])
    assert context._repair_quote_wicks(rows, "MU", "15m") == 0
    assert rows[-1][2] == 110.2


def test_repair_quote_wicks_threshold_scales_with_the_symbol():
    """A jumpy instrument keeps a wick a calm one would lose."""
    jumpy = []
    for i in range(12):
        base = 10.0 + i * 0.1
        jumpy.append([1700000000 + i * 900, base, base * 1.05, base * 0.95, base + 0.02, 1000])
    # median wick 5% -> threshold 50%, so a 30% zero-volume wick survives here
    jumpy.append([1700020000, 11.0, 14.3, 11.0, 11.02, 0])
    assert context._repair_quote_wicks(jumpy, "SOXL", "15m") == 0
    # the same bar against the calm series (median 0.1% -> 4% floor) is clamped
    calm = _wick_rows([[1700020000, 11.0, 14.3, 11.0, 11.02, 0]])
    assert context._repair_quote_wicks(calm, "MU", "15m") == 1


def test_repair_quote_wicks_survives_malformed_rows():
    rows = _wick_rows([[1700020000, None, None, None, None, 0], "junk", [1]])
    assert context._repair_quote_wicks(rows, "X", "15m") == 0


def test_repair_quote_wicks_empty_series_is_zero():
    assert context._repair_quote_wicks([], "X", "15m") == 0

def _yahoo_json_with_ts(closes, stamps):
    """Yahoo v8 chart payload with explicit epoch timestamps, one per bar."""
    n = len(closes)
    return json.dumps({"chart": {"result": [{
        "timestamp": stamps,
        "indicators": {"quote": [{"open": list(closes), "high": list(closes),
                                  "low": list(closes), "close": list(closes),
                                  "volume": [1000] * n}]}}]}}).encode()


def _ct_noon_epoch(y, m, d):
    return int(datetime(y, m, d, 17, 0, tzinfo=timezone.utc).timestamp())


def test_build_bars_publishes_the_real_session_calendar_not_a_weekday_count():
    """v4: bars.json carries the sessions its rows actually came from.

    The page used to reconstruct dates by walking back one weekday per bar,
    which ignores market holidays — the drift reached ~20 sessions at the left
    edge of a 2-year series and put every earnings badge and rating arrow on
    the wrong candle. Here Labor Day (2026-09-07) is missing from the feed, so
    a weekday count would label the oldest bar Sep 1 when it is really Aug 31.
    """
    stamps = [_ct_noon_epoch(2026, 8, 31), _ct_noon_epoch(2026, 9, 1),
              _ct_noon_epoch(2026, 9, 2), _ct_noon_epoch(2026, 9, 3),
              _ct_noon_epoch(2026, 9, 4),   # 9/7 is Labor Day: no bar
              _ct_noon_epoch(2026, 9, 8)]
    payload, _ = context.build_bars(
        ["AAA"], date(2026, 9, 9),
        _get=lambda url, headers=None: _yahoo_json_with_ts([10.0 + i for i in range(6)], stamps))
    assert payload["v"] == 4
    assert payload["sessions"] == ["2026-08-31", "2026-09-01", "2026-09-02",
                                    "2026-09-03", "2026-09-04", "2026-09-08"]
    assert "bar_dates" not in payload
    assert len(payload["bars"]["AAA"]) == len(payload["sessions"])


def test_build_bars_names_the_tickers_whose_dates_are_not_the_calendar_tail():
    """A young listing shares the calendar's tail and needs no entry; a ticker
    that missed a session in the middle carries its own date array."""
    full = [_ct_noon_epoch(2026, 9, d) for d in (1, 2, 3, 4, 8)]
    young = full[-2:]                      # listed late: a clean tail
    gappy = [full[0], full[1], full[3], full[4]]   # halted on 9/3
    series = {"FULL": (5, full), "YOUNG": (2, young), "GAPPY": (4, gappy)}
    def fake_get(url, headers=None):
        for sym, (n, st) in series.items():
            if f"/{sym}?" in url or f"/{sym}" in url:
                return _yahoo_json_with_ts([10.0 + i for i in range(n)], st)
        raise AssertionError("unexpected url " + url)
    payload, _ = context.build_bars(["FULL", "YOUNG", "GAPPY"], date(2026, 9, 9), _get=fake_get)
    assert payload["sessions"] == ["2026-09-01", "2026-09-02", "2026-09-03",
                                    "2026-09-04", "2026-09-08"]
    assert "FULL" not in payload.get("bar_dates", {})
    assert "YOUNG" not in payload.get("bar_dates", {})
    assert payload["bar_dates"]["GAPPY"] == ["2026-09-01", "2026-09-02",
                                              "2026-09-04", "2026-09-08"]


def test_build_bars_calendar_is_the_equity_list_not_a_union_with_the_tape():
    """The tape rides in the same payload and crude trades on days the NYSE is
    shut. If `sessions` were the union, every equity's labels would shift by
    the extra futures days; the calendar is the most common equity list and the
    odd symbol out carries its own array."""
    eq = [_ct_noon_epoch(2026, 9, d) for d in (1, 2, 3, 4)]
    fut = [_ct_noon_epoch(2026, 9, d) for d in (1, 2, 3, 4, 5)]   # trades Saturday too
    series = {"AAA": (4, eq), "BBB": (4, eq), "CRUDE": (5, fut)}
    def fake_get(url, headers=None):
        for sym, (n, st) in series.items():
            if f"/{sym}?" in url or f"/{sym}" in url:
                return _yahoo_json_with_ts([10.0 + i for i in range(n)], st)
        raise AssertionError("unexpected url " + url)
    payload, _ = context.build_bars(["AAA", "BBB", "CRUDE"], date(2026, 9, 9), _get=fake_get)
    assert payload["sessions"] == ["2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04"]
    assert "AAA" not in payload.get("bar_dates", {})
    assert "BBB" not in payload.get("bar_dates", {})
    assert payload["bar_dates"]["CRUDE"][-1] == "2026-09-05"


def test_build_bars_omits_the_calendar_when_the_feed_sends_no_timestamps():
    """No timestamp array means no dates to publish. The payload says nothing
    rather than guessing, and the page falls back to its own reconstruction
    with the approximation stated on screen."""
    payload, _ = context.build_bars(
        ["NOTS"], date(2026, 8, 15),
        _get=lambda url, headers=None: _yahoo_json([10.0, 11.0, 12.0]))
    assert "sessions" not in payload
    assert payload["bars"]["NOTS"]
