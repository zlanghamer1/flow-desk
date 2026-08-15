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


def _yahoo_json(closes):
    return json.dumps({"chart": {"result": [{"indicators": {"quote": [{"close": closes}]}}]}}).encode()


def _news_json(items):
    return json.dumps({"items": items}).encode()


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
        if "/GOOD" in url:
            return _yahoo_json([100.0 + i for i in range(25)])
        raise urllib.error.URLError("boom")
    payload, avg_move = context.build_bars(["GOOD", "BAD"], date(2026, 8, 15), _get=fake_get)
    assert payload["built"] == "2026-08-15"
    assert "GOOD" in payload["bars"] and "BAD" not in payload["bars"]
    assert payload["bars"]["GOOD"][0] == 100.0
    assert payload["bars"]["GOOD"][-1] == 124.0
    assert "GOOD" in avg_move and avg_move["GOOD"] > 0
    assert "BAD" not in avg_move


def test_build_bars_caps_at_252_and_drops_nulls():
    closes = [None] * 5 + [float(i) for i in range(300)]
    def fake_get(url, headers):
        return _yahoo_json(closes)
    payload, _ = context.build_bars(["MU"], date(2026, 8, 15), _get=fake_get)
    assert len(payload["bars"]["MU"]) == 252
    assert None not in payload["bars"]["MU"]


# ── gates: hourly (context) and daily (bars) ────────────────────────────────

def test_hourly_gate_fresh_timestamp_skips_network_and_carries_cache_forward(tmp_path, monkeypatch):
    monkeypatch.setattr(context, "CONTEXT_CACHE_FILE", tmp_path / ".context_cache.json")
    now = datetime(2026, 8, 15, 14, 0, 0, tzinfo=timezone.utc)
    cache = {
        "context_fetched_at": "2026-08-15T13:30:00Z",   # 30 min ago -> fresh (<55min)
        "bars_built_date": "2026-08-15",                  # today -> bars also fresh
        "avg_move": {"MU": 4.2},
        "brief": {"date": "2026-08-15", "stale": False},
        "catalysts": [_econ_row("2026-08-16", "cached row", "LOW")],
        "news": {"items": [], "rotation_banner": False},
        "desk_private": {"v": 1},
    }
    context.save_context_cache(cache)

    quotes = {"MU": {"tv_symbol": "NASDAQ:MU", "earnings_ts": None, "hi52": None,
                     "lo52": None, "market_cap": None, "beta": None, "avol": None, "rsi": None}}
    fields, bars_payload = context.build_context(quotes, ["MU"], date(2026, 8, 15), now, _get=_boom)
    assert bars_payload is None
    assert fields["brief"] == {"date": "2026-08-15", "stale": False}
    assert fields["catalysts"] == cache["catalysts"]
    assert fields["desk_private"] == {"v": 1}
    assert fields["facts"]["MU"]["avg_move"] == 4.2
    assert fields["context_updated_at"] == "2026-08-15T13:30:00Z"


def test_stale_context_triggers_full_refetch_and_updates_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(context, "CONTEXT_CACHE_FILE", tmp_path / ".context_cache.json")
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
        if "query1.finance.yahoo.com" in url:
            return _yahoo_json([1.0, 2.0])
        raise AssertionError(f"unexpected URL: {url}")

    quotes = {"MU": {"tv_symbol": "NASDAQ:MU", "earnings_ts": None, "hi52": 1.0, "lo52": 1.0,
                     "market_cap": 1.0, "beta": 1.0, "avol": 1.0, "rsi": 50.0}}
    fields, bars_payload = context.build_context(quotes, ["MU"], date(2026, 8, 15), now, _get=fake_get)
    assert fields["brief"]["date"] == "2026-08-15" and fields["brief"]["stale"] is False
    assert fields["desk_private"] == {"v": 1, "blob": "abc"}
    assert fields["context_updated_at"] == "2026-08-15T14:00:00Z"
    assert bars_payload is not None

    saved = context.load_context_cache()
    assert saved["context_fetched_at"] == "2026-08-15T14:00:00Z"
    assert saved["bars_built_date"] == "2026-08-15"


def test_build_context_without_token_still_gets_tv_and_opex_but_not_vault(tmp_path, monkeypatch):
    monkeypatch.setattr(context, "CONTEXT_CACHE_FILE", tmp_path / ".context_cache.json")
    monkeypatch.delenv("VAULT_READ_TOKEN", raising=False)
    now = datetime(2026, 8, 15, 14, 0, 0, tzinfo=timezone.utc)

    def fake_get(url, headers):
        assert "raw.githubusercontent.com" not in url, "vault must never be called with no token"
        if "economic-calendar.tradingview.com" in url:
            return json.dumps({"status": "ok", "result": []}).encode()
        if "news-mediator.tradingview.com" in url:
            return json.dumps({"items": []}).encode()
        if "query1.finance.yahoo.com" in url:
            return _yahoo_json([1.0, 2.0])
        raise AssertionError(f"unexpected URL: {url}")

    quotes = {"MU": {"tv_symbol": "NASDAQ:MU", "earnings_ts": None}}
    fields, _ = context.build_context(quotes, ["MU"], date(2026, 8, 15), now, _get=fake_get)
    assert "brief" not in fields
    assert "desk_private" not in fields
    assert "catalysts" in fields
    assert any(c["kind"] == "market" for c in fields["catalysts"])   # OpEx needs no vault/TV data


def test_bars_only_gate_rebuilds_bars_without_refetching_context(tmp_path, monkeypatch):
    monkeypatch.setattr(context, "CONTEXT_CACHE_FILE", tmp_path / ".context_cache.json")
    now = datetime(2026, 8, 15, 14, 0, 0, tzinfo=timezone.utc)
    cache = {
        "context_fetched_at": "2026-08-15T13:50:00Z",   # 10 min ago -> fresh, no refetch
        "bars_built_date": "2026-08-14",                  # yesterday -> bars ARE stale
        "avg_move": {"MU": 9.99},
        "brief": {"date": "2026-08-15", "stale": False},
        "catalysts": [],
        "news": {"items": [], "rotation_banner": False},
        "desk_private": None,
    }
    context.save_context_cache(cache)

    def fake_get(url, headers):
        assert "query1.finance.yahoo.com" in url, f"unexpected fetch: {url}"
        return _yahoo_json([100.0 + i for i in range(25)])

    quotes = {"MU": {"tv_symbol": "NASDAQ:MU", "earnings_ts": None, "hi52": None, "lo52": None,
                     "market_cap": None, "beta": None, "avol": None, "rsi": None}}
    fields, bars_payload = context.build_context(quotes, ["MU"], date(2026, 8, 15), now, _get=fake_get)
    assert bars_payload is not None and bars_payload["built"] == "2026-08-15"
    assert fields["brief"] == {"date": "2026-08-15", "stale": False}   # carried from cache
    assert fields["facts"]["MU"]["avg_move"] is not None
    assert fields["facts"]["MU"]["avg_move"] != 9.99   # replaced by the fresh rebuild


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
