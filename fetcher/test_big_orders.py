"""Biggest-orders board — the cross-ticker $-traded leaderboard.

Run: python3 -m pytest fetcher/test_big_orders.py

What these tests defend, in order of how badly each would mislead Zach if it
broke:

1. The board must NOT be dominated by deep-ITM stock-replacement paper. It is
   ranked on premium, and premium is intrinsic + extrinsic, so a handful of
   strikes 35% in the money carry enormous dollars while betting on nothing.
   That is the same trap FLOW % fell into (LLY 2026-07-27: seven ~35%-ITM
   strikes were 79% of all call premium). The near-money band is the fix and
   these tests pin it.
2. The cross-ticker ranking must be exact. Per-ticker shortlists exist to keep
   memory bounded, and BIG_ORDERS_CAP is deliberately the same number as the
   published row count so shortlisting cannot silently drop a row that belongs
   on the board. If someone "optimises" the shortlist smaller, a loud name
   would get an invisible quota — test_one_loud_name_can_take_several_rows.
3. It must fail closed without a spot, and it must not inherit the 8-13 DTE
   blind spot between the two scoring boards.
4. It must never move a score.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_snapshot import (  # noqa: E402
    analyze_ticker, BIG_ORDERS_CAP, BIG_ORDERS_DTE_HI,
    BIG_ORDERS_MIN_PREMIUM, MONEYNESS_BAND,
    BIG_ORDERS_BASELINE_SESSIONS, big_orders_normal_premium, rank_big_orders)

SESSION = date(2026, 7, 27)


def _occ(root: str, expiry: str, cp: str, strike: float) -> str:
    return f"{root}{expiry}{cp}{int(round(strike * 1000)):08d}"


def _opt(root, expiry, cp, strike, vol, last, oi=100):
    return {
        "option": _occ(root, expiry, cp, strike),
        "volume": vol, "last_trade_price": last, "open_interest": oi,
        "bid": max(0.0, last - 0.05), "ask": last + 0.05,
        "delta": 0.5, "iv": 0.4,
    }


def _chain(spot, options, iv30=0.4):
    return {"spot": spot, "iv30": iv30, "options": options}


EXP = "260729"          # 2 days out — inside every bucket


def _big(a):
    return a["big_orders"]


# ── 1. the deep-ITM trap ─────────────────────────────────────────────────────

def test_deep_itm_paper_is_excluded_even_when_it_is_the_biggest_dollars():
    """The whole point of the band. The ITM call here trades the MOST dollars
    of anything on the chain; it must still not appear, because it is a way of
    holding the stock, not a bet on it."""
    spot = 1200.0
    options = [
        _opt("LLY", EXP, "C", 790.0, 640, 409.0),    # $26.2M, ~34% ITM
        _opt("LLY", EXP, "C", 1200.0, 200, 18.0),    # $0.36M, at the money
    ]
    rows = _big(analyze_ticker("LLY", _chain(spot, options), SESSION))
    assert [r["strike"] for r in rows] == [1200.0]
    assert rows[0]["premium"] == pytest.approx(200 * 18.0 * 100)


def test_deep_otm_lottery_tickets_are_excluded_too():
    """Symmetry — the band cuts both ways, so a wall of 2-cent far-OTM churn
    can't buy its way onto the board on contract count."""
    spot = 100.0
    far = spot * (1 + MONEYNESS_BAND) + 1.0
    options = [
        _opt("T", EXP, "C", far, 5_000_000, 0.02),   # $10M of pennies
        _opt("T", EXP, "P", 100.0, 2_000, 1.0),      # $0.2M, real
    ]
    rows = _big(analyze_ticker("T", _chain(spot, options), SESSION))
    assert [r["strike"] for r in rows] == [100.0]


def test_strike_exactly_on_the_band_edge_is_included():
    spot = 100.0
    options = [_opt("T", EXP, "C", spot * (1 + MONEYNESS_BAND), 20_000, 1.0)]
    rows = _big(analyze_ticker("T", _chain(spot, options), SESSION))
    assert len(rows) == 1


# ── 2. ranking and caps ──────────────────────────────────────────────────────

def test_rows_are_sorted_by_dollars_descending():
    spot = 100.0
    options = [
        _opt("T", EXP, "C", 100.0, 1_000, 2.0),      # $0.2M
        _opt("T", EXP, "P", 95.0, 5_000, 3.0),       # $1.5M
        _opt("T", EXP, "C", 105.0, 2_000, 4.0),      # $0.8M
    ]
    rows = _big(analyze_ticker("T", _chain(spot, options), SESSION))
    prems = [r["premium"] for r in rows]
    assert prems == sorted(prems, reverse=True)
    assert rows[0]["strike"] == 95.0 and rows[0]["side"] == "PUT"


def test_one_loud_name_can_take_several_rows():
    """No hidden per-ticker quota: the shortlist is BIG_ORDERS_CAP deep, which
    is the published row count, so a name that genuinely owns the tape owns the
    board. AMZN did exactly this on 2026-07-31 (5 of the top 8)."""
    spot = 100.0
    options = [
        _opt("AMZN", EXP, "C", 100.0 + i, 10_000, 5.0 + i)
        for i in range(BIG_ORDERS_CAP + 6)
    ]
    rows = _big(analyze_ticker("AMZN", _chain(spot, options), SESSION))
    assert len(rows) == BIG_ORDERS_CAP


def test_premium_floor_keeps_a_quiet_session_honest():
    """Below the floor publishes a SHORT board, not a padded one."""
    spot = 100.0
    tiny = (BIG_ORDERS_MIN_PREMIUM / 100.0) - 1.0   # contracts x price, just under
    options = [
        _opt("T", EXP, "C", 100.0, 1, tiny),                  # under the floor
        _opt("T", EXP, "P", 100.0, 1, tiny + 2.0),            # over it
    ]
    rows = _big(analyze_ticker("T", _chain(spot, options), SESSION))
    assert [r["side"] for r in rows] == ["PUT"]
    assert rows[0]["premium"] >= BIG_ORDERS_MIN_PREMIUM


# ── 3. DTE coverage and failing closed ───────────────────────────────────────

def test_the_8_to_13_day_gap_between_the_scoring_boards_is_covered():
    """0-7 DTE and 14-183 DTE leave 8-13 uncovered on the scored boards. This
    board must NOT inherit that hole — a loud 10-day contract is still loud."""
    spot = 100.0
    ten_days = "260806"                     # SESSION + 10
    options = [_opt("T", ten_days, "C", 100.0, 20_000, 3.0)]
    a = analyze_ticker("T", _chain(spot, options), SESSION)
    rows = _big(a)
    assert len(rows) == 1 and rows[0]["dte"] == 10
    # and it is genuinely in neither scoring bucket
    assert a["popular_contract"] is None
    assert a["suggested_contract"] is None


def test_expiry_beyond_the_horizon_is_dropped():
    spot = 100.0
    options = [
        _opt("T", "270729", "C", 100.0, 50_000, 20.0),   # ~2 years out
        _opt("T", EXP, "C", 100.0, 2_000, 2.0),
    ]
    rows = _big(analyze_ticker("T", _chain(spot, options), SESSION))
    assert len(rows) == 1
    assert rows[0]["dte"] <= BIG_ORDERS_DTE_HI


def test_no_spot_fails_closed():
    """Without a reference price a stock-replacement strike is
    indistinguishable from a bet, so nothing is published — the same rule
    FLOW % follows. An empty board is honest; a wrong ranking is not."""
    options = [_opt("T", EXP, "C", 100.0, 50_000, 20.0)]
    a = analyze_ticker("T", {"spot": None, "iv30": 0.4, "options": options}, SESSION)
    assert _big(a) == []
    assert a["flow_pct"] is None          # same failure mode, same reason


def test_expired_contracts_are_not_on_the_board():
    spot = 100.0
    options = [_opt("T", "260726", "C", 100.0, 50_000, 20.0)]   # yesterday
    assert _big(analyze_ticker("T", _chain(spot, options), SESSION)) == []


# ── 4. shape, and staying out of the scoring ─────────────────────────────────

def test_row_carries_every_field_the_contract_promises():
    spot = 100.0
    options = [_opt("T", EXP, "C", 105.0, 4_000, 3.5, oi=1234)]
    row = _big(analyze_ticker("T", _chain(spot, options), SESSION))[0]
    assert row["ticker"] == "T"
    assert row["side"] == "CALL"
    assert row["strike"] == 105.0
    assert row["expiry"] == "2026-07-29"
    assert row["dte"] == 2
    assert row["last"] == 3.5
    assert row["volume"] == 4000
    assert row["open_interest"] == 1234
    assert row["premium"] == pytest.approx(4_000 * 3.5 * 100)
    assert row["occ"] == "T260729C00105000"
    # tv_symbol is stamped by run_cycle, not here
    assert "tv_symbol" not in row


def test_board_does_not_disturb_the_scoring_inputs():
    """Display only. net_flow keeps its whole-bucket definition (deep-ITM
    included) even though this board excludes that paper."""
    spot = 1200.0
    options = [
        _opt("LLY", EXP, "C", 790.0, 640, 409.0),    # excluded from the board
        _opt("LLY", EXP, "P", 1190.0, 500, 20.0),
    ]
    a = analyze_ticker("LLY", _chain(spot, options), SESSION)
    assert [r["strike"] for r in _big(a)] == [1190.0]
    assert a["net_flow"] == pytest.approx((640 * 409.0 - 500 * 20.0) * 100)
    assert a["direction"] == "BULL"


# ── 5. the per-ticker cap and its disclosure (Zach's call, 2026-07-31) ────────
# These live in run_cycle, so they are exercised through the same merge logic a
# real cycle uses: build a pool of rows, apply the cap, check both the board and
# the disclosure. The cap is only acceptable BECAUSE it is disclosed — a test
# that checked the cap without checking the disclosure would bless half of it.

def _merge(pool_rows, normal_by_ticker=None):
    """Mirror of run_cycle's merge/cap/disclose block. The ORDER comes from the
    real rank_big_orders (vs_normal desc, then raw premium); with no baselines
    supplied every row has vs_normal=None and the walk runs on raw premium,
    which is what the cap/disclosure tests below exercise."""
    from build_snapshot import BIG_ORDERS_CAP as CAP, BIG_ORDERS_PER_TICKER as PER
    pool = rank_big_orders([dict(r) for r in pool_rows], normal_by_ticker or {})
    board, shown = [], {}
    for r in pool:
        if len(board) >= CAP:
            break
        if shown.get(r["ticker"], 0) >= PER:
            continue
        board.append(r)
        shown[r["ticker"]] = shown.get(r["ticker"], 0) + 1
    # earned counts a ticker's rows across the WHOLE pool, not a naive top-CAP
    # slice by raw premium — the walk above backfills PAST that slice, so a
    # ticker with zero rows in the naive top-12 can still earn (and lose) a
    # seat further down (2026-08-21 review, flow boards finding #2). The
    # disclosure gate requires the ticker to have hit its OWN per-ticker
    # quota (shown==PER) as well as earned>shown — a single quiet row that
    # never ranked onto the board at all (shown=0, earned=1) is an ordinary
    # miss on dollars, not a per-ticker cap to confess.
    earned = {}
    for r in pool:
        earned[r["ticker"]] = earned.get(r["ticker"], 0) + 1
    capped = [{"ticker": t, "shown": shown.get(t, 0), "earned": n}
              for t, n in sorted(earned.items(), key=lambda kv: -kv[1])
              if shown.get(t, 0) >= PER and n > shown.get(t, 0)]
    return board, capped


def _row(ticker, premium, strike=100.0):
    return {"ticker": ticker, "premium": premium, "strike": strike, "side": "CALL"}


def test_the_qqq_case_shows_three_rows_and_says_it_earned_five():
    """The exact shape that prompted the cap: 0-DTE QQQ calls at adjacent
    strikes holding 5 of the top 12 by dollars."""
    pool = [_row("QQQ", 76e6 - i * 1e6, 683.0 + i) for i in range(5)]
    pool += [_row(f"OTHER{i}", 20e6 - i * 1e5) for i in range(20)]
    board, capped = _merge(pool)
    assert sum(1 for r in board if r["ticker"] == "QQQ") == 3
    assert capped == [{"ticker": "QQQ", "shown": 3, "earned": 5}]


def test_the_cap_does_not_shorten_the_board():
    """Rows a crowded name gives up go to the next-loudest OTHER contracts —
    the board must still be full, or the cap would cost coverage."""
    from build_snapshot import BIG_ORDERS_CAP
    pool = [_row("QQQ", 90e6 - i, 683.0 + i) for i in range(9)]
    pool += [_row(f"N{i}", 5e6 - i) for i in range(30)]
    board, _ = _merge(pool)
    assert len(board) == BIG_ORDERS_CAP
    assert len({r["ticker"] for r in board}) >= 4     # breadth, which was the point


def test_no_disclosure_when_the_cap_binds_nothing():
    """Silence here is honest: nothing was held back, so there is nothing to
    confess. An always-on note would train him to ignore it."""
    pool = [_row(f"N{i}", 9e6 - i) for i in range(20)]
    board, capped = _merge(pool)
    assert capped == []
    assert len(board) == 12


def test_disclosure_counts_a_tickers_whole_pool_not_the_naive_top_cap_slice():
    """A ticker whose qualifying rows sit ENTIRELY below the naive top-12 by
    raw premium can still earn — and lose — rows via the greedy walk's
    backfill, once enough higher-ranked tickers ahead of it get capped at 3
    each. The old disclosure measured 'earned' from pool[:BIG_ORDERS_CAP]
    alone, so a ticker like Z below never appeared in earned{} at all and
    silently vanished from the disclosure despite genuinely losing a row to
    the per-ticker cap (2026-08-21 review, flow boards finding #2)."""
    # QQQ, AMZN and MSFT each contribute 5 rows ranked ahead of Z's — 15 raw
    # rows, 9 of them kept (3 each), 6 skipped for hitting the per-ticker cap.
    pool = [_row("QQQ", 90e6 - i, 683.0 + i) for i in range(5)]
    pool += [_row("AMZN", 80e6 - i, 250.0 + i) for i in range(5)]
    pool += [_row("MSFT", 70e6 - i, 410.0 + i) for i in range(5)]
    # Z's 4 rows rank 16th-19th overall — entirely outside pool[:12] — but
    # the board still has 3 slots open (9 kept so far, cap is 12), so the
    # walk reaches past rank 12 and gives Z 3 of its 4 rows before the board
    # fills.
    pool += [_row("Z", 5e6 - i, 50.0 + i) for i in range(4)]
    pool += [_row(f"N{i}", 1e6 - i) for i in range(20)]   # filler, ranked last
    board, capped = _merge(pool)
    assert sum(1 for r in board if r["ticker"] == "Z") == 3
    by_ticker = {c["ticker"]: c for c in capped}
    assert by_ticker["Z"] == {"ticker": "Z", "shown": 3, "earned": 4}
    assert by_ticker["QQQ"] == {"ticker": "QQQ", "shown": 3, "earned": 5}


def test_two_crowded_names_are_both_disclosed_worst_first():
    pool = [_row("QQQ", 90e6 - i, 683.0 + i) for i in range(5)]
    pool += [_row("AMZN", 80e6 - i, 250.0 + i) for i in range(4)]
    pool += [_row(f"N{i}", 1e6 - i) for i in range(10)]
    _, capped = _merge(pool)
    assert [c["ticker"] for c in capped] == ["QQQ", "AMZN"]
    assert capped[0]["earned"] == 5 and capped[1]["earned"] == 4


# ── 6. ranked relative to each name's normal (Zach, 2026-09-03) ──────────────
# "Biggest options dollars today in the desk should be relative to its normal.
# Right now, only Nvidia, SPY, QQQ, and one other are shown." On raw dollars
# the index ETFs own the board by size alone; these pin the ratio ranking, the
# baseline's own-history-only rule, and the no-baseline fallback.

def _sessions(session_str, ticker_days):
    """history['sessions'] shaped map: {date: {ticker: {nm_call, nm_put}}}."""
    out = {}
    for t, days in ticker_days.items():
        for i, (c, p) in enumerate(days):
            d = f"2026-06-{i+1:02d}"
            out.setdefault(d, {})[t] = {"nm_call_prem_0_7": c, "nm_put_prem_0_7": p}
    out.setdefault(session_str, {})
    return out


def test_normal_premium_averages_prior_near_money_dollars():
    sess = _sessions("2026-07-27", {"MU": [(600_000.0, 400_000.0)] * BIG_ORDERS_BASELINE_SESSIONS})
    normal, n = big_orders_normal_premium(sess, "2026-07-27", "MU")
    assert normal == pytest.approx(1_000_000.0)
    assert n == BIG_ORDERS_BASELINE_SESSIONS


def test_normal_premium_excludes_today_and_needs_minimum_history():
    """Today's own row must never sit in its own baseline (a loud day would
    dilute the ratio it is measured by), and short history reads None."""
    days = [(1.0, 1.0)] * (BIG_ORDERS_BASELINE_SESSIONS - 1)
    sess = _sessions("2026-07-27", {"MU": days})
    sess["2026-07-27"]["MU"] = {"nm_call_prem_0_7": 9e9, "nm_put_prem_0_7": 9e9}
    normal, n = big_orders_normal_premium(sess, "2026-07-27", "MU")
    assert normal is None and n == BIG_ORDERS_BASELINE_SESSIONS - 1
    # rows predating the near-money fields (2026-07-28) don't count either
    sess["2026-06-30"] = {"MU": {"net_flow_0_7": 1.0}}
    assert big_orders_normal_premium(sess, "2026-07-27", "MU")[0] is None


def test_a_quiet_name_having_a_loud_day_outranks_spy_on_raw_dollars():
    """The whole point: SPY's $20M contract is an ordinary hour for SPY; AEHR's
    $400K contract is four normal days of AEHR's entire options business."""
    pool = [_row("SPY", 20e6), _row("AEHR", 400e3), _row("MU", 3e6)]
    normals = {"SPY": (200e6, 20), "AEHR": (100e3, 20), "MU": (2e6, 20)}
    board, _ = _merge(pool, normals)
    assert [r["ticker"] for r in board] == ["AEHR", "MU", "SPY"]
    assert board[0]["vs_normal"] == pytest.approx(4.0)
    assert board[0]["normal_prem"] == pytest.approx(100e3)
    assert board[0]["normal_sessions"] == 20
    assert board[2]["vs_normal"] == pytest.approx(0.1)


def test_no_baseline_rows_sort_after_every_ranked_row_on_raw_dollars():
    """A missing baseline is disclosed (vs_normal null), never guessed as 0x
    or as infinity — and it never displaces a ranked row."""
    pool = [_row("NEW", 50e6), _row("NEW2", 60e6), _row("MU", 1e6)]
    normals = {"MU": (2e6, 20), "NEW": (None, 3), "NEW2": (None, 0)}
    board, _ = _merge(pool, normals)
    assert [r["ticker"] for r in board] == ["MU", "NEW2", "NEW"]
    assert board[1]["vs_normal"] is None and board[1]["normal_prem"] is None
    assert board[2]["normal_sessions"] == 3


def test_ratio_ranking_keeps_a_tickers_own_rows_in_premium_order():
    """One normal per ticker, so within a name the order is still by dollars —
    which is why analyze_ticker's per-ticker premium shortlist stays exact."""
    pool = [_row("MU", 1e6, 100.0), _row("MU", 3e6, 101.0), _row("MU", 2e6, 102.0)]
    board, _ = _merge(pool, {"MU": (2e6, 20)})
    assert [r["strike"] for r in board] == [101.0, 102.0, 100.0]


def test_per_ticker_cap_and_disclosure_still_apply_under_ratio_ranking():
    pool = [_row("QQQ", 90e6 - i, 683.0 + i) for i in range(5)]
    pool += [_row(f"N{i}", 1e6 - i) for i in range(20)]
    normals = {"QQQ": (10e6, 20)}
    for i in range(20):
        normals[f"N{i}"] = (1e6, 20)
    board, capped = _merge(pool, normals)
    assert sum(1 for r in board if r["ticker"] == "QQQ") == 3
    assert capped == [{"ticker": "QQQ", "shown": 3, "earned": 5}]
