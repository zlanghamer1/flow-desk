"""Flow Desk verdicts composite — fetcher/verdict.py.

Run: python3 -m pytest fetcher/test_verdict.py -q

Every value asserted here is PREDICTED before the test runs (written into the
test as a comment or inline arithmetic) and then compared against
`verdict`'s real functions — never the other way around. Design record:
docs/superpowers/specs/2026-09-11-desk-verdicts-design.md.
"""
from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verdict  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


# ── payload-level shape ─────────────────────────────────────────────────────

def test_weights_sum_to_100():
    assert sum(verdict.VERDICT_WEIGHTS.values()) == 100


def test_order_and_weights_keys_match():
    assert set(verdict.VERDICT_INPUT_ORDER) == set(verdict.VERDICT_WEIGHTS.keys())
    assert len(verdict.VERDICT_INPUT_ORDER) == len(set(verdict.VERDICT_INPUT_ORDER)) == 9


# ── _signed: signed-zero guard (F1, 2026-09-11) ───────────────────────────
# _signed used to have no zero guard at all: _signed(-0.4, 0) printed "−0",
# _signed(-0.04, 1) printed "−0.0", and _signed(-0.0, 1) printed the ASCII-
# hyphen, both-signed "+-0.0". Every case below is predicted from the fixed
# rule (round half away from zero, then guard anything whose rounded
# magnitude falls under half the smallest printed unit) before it is run.

def test_signed_negative_rounds_to_unsigned_zero_zero_decimals():
    assert verdict._signed(-0.4, 0) == "0"


def test_signed_negative_rounds_to_unsigned_zero_one_decimal():
    assert verdict._signed(-0.04, 1) == "0.0"


def test_signed_negative_zero_is_unsigned_zero():
    assert verdict._signed(-0.0, 1) == "0.0"


def test_signed_negative_six_rounds_to_minus_one():
    assert verdict._signed(-0.6, 0) == f"{verdict._MINUS}1"


def test_signed_half_rounds_away_from_zero_not_bankers_rounding():
    # Python's own round(0.5) is banker's rounding and gives 0 (round half to
    # EVEN); _signed instead uses _round_half_away_from_zero, the same
    # convention the composite score itself rounds with, so a tie always
    # moves off zero and away from it: "+1", never "0".
    assert verdict._signed(0.5, 0) == "+1"


def test_signed_never_prints_ascii_hyphen():
    for x in (-0.4, -0.04, -0.0, -0.6, -34.5, -1234.5):
        s = verdict._signed(x, 1)
        assert "-" not in s, f"_signed({x!r}, 1) == {s!r} used ASCII hyphen-minus"


def test_target_upside_at_boundary_prints_unsigned_zero_not_minus_zero():
    # target 0.4% below spot: upside*100 == -0.4, which _signed(-0.4, 0)
    # rounds to unsigned zero -- "0%", never "−0%" or "+0%".
    v, note = verdict.target_upside_input(
        {"target": 99.6, "rec_total": 20}, spot=100.0)
    assert note == "0% to the average target"
    assert "−0%" not in note and "+0%" not in note


def test_rs63_signed_note_guards_tiny_negative_gap():
    # a −0.02 percentage-point gap rounds to 0.0pp, not "−0.0pp".
    closes = _rs_closes(-0.0002)
    spy = _rs_closes(0.0)
    dates = _rs_dates()
    v, note = verdict.rs63_input("T9", closes, spy, dates, dates)
    assert note == "0.0pp vs SPY, 63 sessions"


# ── trend ────────────────────────────────────────────────────────────────

def _closes_for_smas(sma50: float, sma200: float, spot: float = 100.0,
                      n: int = 200) -> list[float]:
    """(n-1) closes such that trend_input's `series = closes + [spot]` (F4,
    2026-09-11: the series trend_input actually averages, mirroring the
    page's seriesFull()) has a trailing-50 average of exactly sma50 and a
    trailing-n average of exactly sma200. The series' last 50 elements are
    the closes' last 49 plus the appended spot; its full n elements are
    every close plus the appended spot. Solving both constraints for the
    two constants (a leading block of n-50-1, then 49 elements) pins the
    exact averages regardless of which spot is later passed in."""
    last49_sum = sma50 * 50 - spot
    last49 = last49_sum / 49
    first_count = (n - 1) - 49
    first_val = (sma200 * n - last49_sum - spot) / first_count
    return [first_val] * first_count + [last49] * 49


def test_trend_above_50d_dead_zone_200d_is_half():
    # spot 1.5% above SMA50 (above; outside 0.3% dead zone) and 0.1% above
    # SMA200 (inside the dead zone -> "on") -> v = 0.5*1 + 0.5*0 = 0.5
    sma50 = 100.0
    spot = sma50 * 1.015
    sma200 = spot / 1.001
    closes = _closes_for_smas(sma50, sma200, spot)
    v, note = verdict.trend_input(spot, closes)
    assert v == pytest.approx(0.5)
    assert note == "above 50d · on 200d"


def test_trend_below_both():
    sma50 = 100.0
    spot = sma50 * 0.95
    sma200 = spot / 0.95  # spot 5% below SMA200 too
    closes = _closes_for_smas(sma50, sma200, spot)
    v, note = verdict.trend_input(spot, closes)
    assert v == pytest.approx(-1.0)
    assert note == "below 50d · below 200d"


def test_trend_null_fewer_than_200_closes():
    # F4: the series trend_input averages is closes + [spot], so 198 closes
    # (+ the spot = 199 total) is one short of VERDICT_SMA_LONG (200). The
    # note reads "sessions of history", not "daily closes" -- 199 CLOSES
    # plus the spot suffice, so calling the null threshold "200 daily
    # closes" was itself off by one (fixed 2026-09-11).
    v, note = verdict.trend_input(100.0, [100.0] * 198)
    assert v is None
    assert note == "fewer than 200 sessions of history"


def test_trend_null_no_spot():
    v, note = verdict.trend_input(None, [100.0] * 200)
    assert v is None
    assert note == "no spot"
    v2, _ = verdict.trend_input(0.0, [100.0] * 200)
    assert v2 is None
    v3, _ = verdict.trend_input(-5.0, [100.0] * 200)
    assert v3 is None


def test_trend_dead_zone_boundary():
    # clearly outside the 0.3% dead zone (0.5%) reads as a real move; clearly
    # inside it (0.1%) reads as "on". (An exact-0.3% case is not asserted:
    # binary floats can't represent 100.3/100-1 as precisely 0.003, so a
    # boundary test there would pin float noise, not the dead-zone rule.)
    closes = [100.0] * 199
    v, note = verdict.trend_input(100.0 * 1.005, closes)
    assert note == "above 50d · above 200d"
    assert v == pytest.approx(1.0)
    v2, note2 = verdict.trend_input(100.0 * 1.001, closes)
    assert note2 == "on 50d · on 200d"
    assert v2 == 0.0


# ── trend: series includes the cycle spot as the newest bar (F4, 2026-09-11) ─
# bars.json's newest row is the PRIOR settled session; the page's own
# seriesFull() (index.html) appends the live/cycle price as the newest bar
# before computing rollMA(50)/rollMA(200). Averaging `closes` alone -- this
# function's behavior before the fix -- is one bar short of what the chart
# draws, and read a different trend word for the same name on the same day
# (QQQ, CLSK, XLF, 2026-09-11 review).

def test_trailing_smas_sma200_exact_with_199_closes_plus_spot():
    closes = [100.0] * 199
    spot = 120.0
    series = closes + [spot]
    sma50, sma200 = verdict._trailing_smas(series)
    assert sma200 == pytest.approx((199 * 100.0 + 120.0) / 200)
    # sanity: the exact fraction actually used, spelled out
    assert sma200 == pytest.approx(100.1)


def test_trend_199_closes_plus_spot_is_sufficient():
    # 199 settled closes used to read null ("fewer than 200 sessions of
    # history"); with the spot correctly appended as the 200th bar, it now
    # resolves.
    v, note = verdict.trend_input(120.0, [100.0] * 199)
    assert v is not None
    assert note == "above 50d · above 200d"


def test_trend_spot_inclusion_flips_leg_qqq_style():
    # 200 settled closes: one high outlier as the OLDEST row, everything
    # else flat at 100. The buggy (closes-only) computation would average
    # all 200 of them, including that oldest outlier, and read the spot as
    # BELOW its 200-day average. The fixed computation appends the spot as
    # the newest bar and takes the trailing 200 of the 201-long series,
    # which drops that same oldest outlier -- the two disagree on the same
    # input, which is exactly the QQQ/CLSK/XLF bug this fix closes.
    closes = [200.0] + [100.0] * 199
    spot = 100.0
    # buggy closes-only SMA200 = mean(closes) = (200 + 199*100) / 200 = 100.5
    buggy_sma200 = (200.0 + 199 * 100.0) / 200.0
    assert spot / buggy_sma200 - 1 < -verdict.VERDICT_TREND_DEAD_ZONE  # buggy reads "below"
    # fixed SMA200 = mean(closes[1:] + [spot]) = mean([100.0]*200) = 100.0
    v, note = verdict.trend_input(spot, closes)
    assert "on 200d" in note
    assert "below 200d" not in note


# ── rs63 ─────────────────────────────────────────────────────────────────
# F5 (2026-09-11 fix): the lookback is anchored on SPY's own calendar, not
# a shared position in two lists that may not share a calendar at all.
# rs63_input now takes (ticker, closes, spy_closes, dates, spy_dates).

def _rs_closes(ret: float, n: int = 64) -> list[float]:
    """n closes where closes[-1]/closes[-n] - 1 == ret exactly."""
    base = 100.0
    return [base] * (n - 1) + [base * (1 + ret)]


def _rs_dates(n: int = 64, start: str = "2026-01-01") -> list[str]:
    """n sequential ISO date strings, oldest first -- a stand-in calendar for
    the calendar-anchored rs63 tests. rs63_input only ever compares these for
    equality/lookup, never parses them, so they need not be real trading
    sessions."""
    d0 = datetime.date.fromisoformat(start)
    return [(d0 + datetime.timedelta(days=i)).isoformat() for i in range(n)]


def test_rs63_plus_20pp_is_1():
    closes = _rs_closes(0.20)
    spy = _rs_closes(0.0)
    dates = _rs_dates()
    v, note = verdict.rs63_input("T1", closes, spy, dates, dates)
    assert v == pytest.approx(1.0)
    assert note == "+20.0pp vs SPY, 63 sessions"


def test_rs63_plus_30pp_clamps_to_1():
    closes = _rs_closes(0.30)
    spy = _rs_closes(0.0)
    dates = _rs_dates()
    v, _ = verdict.rs63_input("T1", closes, spy, dates, dates)
    assert v == pytest.approx(1.0)


def test_rs63_negative_uses_minus_sign():
    closes = _rs_closes(-0.10)
    spy = _rs_closes(0.0)
    dates = _rs_dates()
    v, note = verdict.rs63_input("T1", closes, spy, dates, dates)
    assert v == pytest.approx(-0.5)
    assert note == "−10.0pp vs SPY, 63 sessions"
    assert "-10.0pp" not in note  # ASCII hyphen-minus must never appear


def test_rs63_null_fewer_than_64_closes_positional_fallback():
    # no calendar at all -> straight positional length check, both ways.
    v, note = verdict.rs63_input("T1", [100.0] * 63, [100.0] * 64, None, None)
    assert v is None
    assert note == "fewer than 64 daily closes"
    v2, _ = verdict.rs63_input("T1", [100.0] * 64, [100.0] * 63, None, None)
    assert v2 is None


def test_rs63_null_spy_fewer_than_64_sessions_on_calendar_path():
    # SPY's own anchor lookup (spy_closes[-n] / spy_dates[-n]) always needs
    # >= 64 sessions, calendar or not -- the name's own row count alone does
    # NOT gate the calendar path (that is the point of F5: the name is
    # looked up by date, not by a required position), so this specifically
    # starves SPY rather than the name.
    dates64 = _rs_dates(64)
    dates63 = _rs_dates(63)
    v, note = verdict.rs63_input("T1", [100.0] * 64, [100.0] * 63, dates64, dates63)
    assert v is None
    assert note == "fewer than 64 daily closes"


def test_rs63_benchmark_null_when_ticker_is_spy():
    closes = _rs_closes(0.10)
    dates = _rs_dates()
    v, note = verdict.rs63_input("SPY", closes, closes, dates, dates)
    assert v is None
    assert note == "benchmark"


def test_rs63_benchmark_null_when_closes_list_is_the_spy_list():
    # the tautology guard is on object identity, not the ticker string --
    # any caller that hands rs63_input the SAME list for both legs (a bug
    # elsewhere, or literally the benchmark under another name) gets null.
    closes = _rs_closes(0.10)
    dates = _rs_dates()
    v, note = verdict.rs63_input("NOT_SPY", closes, closes, dates, dates)
    assert v is None
    assert note == "benchmark"


def test_rs63_positional_fallback_when_no_calendar():
    # bars.json v1-v3 carries no "sessions"/"bar_dates" -> dates_of returns
    # None -> rs63_input falls back to positional indexing and discloses it.
    closes = _rs_closes(0.20)
    spy = _rs_closes(0.0)
    v, note = verdict.rs63_input("T1", closes, spy, None, None)
    assert v == pytest.approx(1.0)
    assert note == "+20.0pp vs SPY, 63 sessions (positional; no calendar in bars)"


def test_rs63_aligned_tails_positional_equals_calendar():
    # when the name's calendar lines up with SPY's own tail 1:1 (the common
    # case: same trading history, no gaps), the calendar-anchored read and
    # the plain positional read must agree exactly -- the F5 regression
    # guard for the common path.
    closes = _rs_closes(0.20)
    spy = _rs_closes(0.0)
    dates = _rs_dates()
    v_cal, note_cal = verdict.rs63_input("T1", closes, spy, dates, dates)
    v_pos, note_pos = verdict.rs63_input("T1", closes, spy, None, None)
    assert v_cal == pytest.approx(v_pos)
    assert note_cal == note_pos.replace(" (positional; no calendar in bars)", "")


def test_rs63_calendar_gap_is_null():
    # the name has 64 closes but its OWN calendar never carries SPY's anchor
    # date (its history starts on a different run of dates entirely) --
    # this is a real calendar mismatch, distinct from "too few closes".
    spy = _rs_closes(0.0)
    spy_dates = _rs_dates()
    name_closes = _rs_closes(0.0)
    name_dates = _rs_dates(start="2020-01-01")  # nowhere near spy_dates
    v, note = verdict.rs63_input("T1", name_closes, spy, name_dates, spy_dates)
    assert v is None
    assert note == "calendar gap in the 63-session window"


# ── F1 (2026-09-11 fix): short-history names must never reach the calendar-
# gap branch. RAM, SKHY, SKHX, STLL (fetcher/testdata/verdict_sample_
# 2026-09-10.json) all have far fewer than 64 rows; dates_of's tail-
# alignment convention hands a short name a dates list that STARTS AFTER
# the anchor date, so dates.index(anchor_date) raised ValueError and the
# old code printed "calendar gap in the 63-session window" -- wrong: the
# real reason is a short history, not a hole in a long enough one.

def test_rs63_short_history_starting_after_anchor_reads_fewer_than_64_not_gap():
    spy = _rs_closes(0.0)
    spy_dates = _rs_dates()
    anchor_date = spy_dates[-64]
    # 40 closes/dates, all AFTER the anchor date -- the exact RAM/SKHY/SKHX/
    # STLL shape (a name pinned recently, with fewer bars on file than the
    # published sessions calendar has entries).
    later_start = (datetime.date.fromisoformat(anchor_date)
                   + datetime.timedelta(days=10)).isoformat()
    name_dates = _rs_dates(n=40, start=later_start)
    name_closes = [100.0] * 40
    v, note = verdict.rs63_input("T1", name_closes, spy, name_dates, spy_dates)
    assert v is None
    assert note == "fewer than 64 daily closes"
    assert note != "calendar gap in the 63-session window"


def test_rs63_calendar_gap_when_dates_span_anchor_but_skip_it():
    # The calendar-gap note is reserved for a name whose OWN date list truly
    # SPANS the anchor date (starts earlier, has >= 64 closes) but is
    # missing that one specific session -- a real hole, distinct from the
    # short-history case above, which must never reach this branch.
    spy = _rs_closes(0.0)
    spy_dates = _rs_dates()
    anchor_date = spy_dates[-64]
    d0 = datetime.date.fromisoformat(anchor_date) - datetime.timedelta(days=2)
    name_dates = [(d0 + datetime.timedelta(days=i)).isoformat() for i in range(65)]
    name_dates.remove(anchor_date)
    assert len(name_dates) == 64
    name_closes = [100.0] * 64
    v, note = verdict.rs63_input("T1", name_closes, spy, name_dates, spy_dates)
    assert v is None
    assert note == "calendar gap in the 63-session window"


# ── framework ────────────────────────────────────────────────────────────
# F2 (2026-09-11 fix): the note is the rendered TIER ("ADD"), never the raw
# enum ("ADD_BUILDING") -- 19 of 63 names on the day this was found rendered
# the raw enum on the Overview strip one block above the framework panel's
# own plain tier word. "_BUILDING" never survives to the note; "_CAPPED"
# survives as the disclosed "(capped)" suffix, per CLAUDE.md's framework
# rule ("a tier verdict carries no '(building)' suffix at render... '(capped)'
# does print, because there the ceiling is the honest thing to name").

@pytest.mark.parametrize("raw_verdict,expected_v,expected_note", [
    ("BUY_5", 1.0, "BUY_5"),
    ("BUY_4", 0.75, "BUY_4"),
    ("ADD", 0.4, "ADD"),
    ("HOLD", 0.0, "HOLD"),
    ("AVOID", -1.0, "AVOID"),
    ("ADD_BUILDING", 0.4, "ADD"),
    ("HOLD_CAPPED", 0.0, "HOLD (capped)"),
    ("BUY_4_CAPPED", 0.75, "BUY_4 (capped)"),
])
def test_framework_tiers(raw_verdict, expected_v, expected_note):
    facts_entry = {"framework": {"verdict": raw_verdict}}
    v, note = verdict.framework_input(facts_entry)
    assert v == pytest.approx(expected_v)
    assert note == expected_note


def test_framework_building_is_null():
    v, note = verdict.framework_input({"framework": {"verdict": "BUILDING"}})
    assert v is None
    assert note == "building"


def test_framework_not_applicable_is_null():
    v, note = verdict.framework_input({"framework": {"verdict": "NOT_APPLICABLE"}})
    assert v is None
    assert note == "fund"


def test_framework_absent_is_null():
    v, note = verdict.framework_input({})
    assert v is None
    assert note == "no framework score"
    v2, note2 = verdict.framework_input(None)
    assert v2 is None
    assert note2 == "no framework score"


# ── analyst_rating ───────────────────────────────────────────────────────

def test_analyst_rating_strong_buy():
    v, note = verdict.analyst_rating_input({"rec_mark": 1.0, "rec_total": 57})
    # (1.43 - 1.0) / 0.45 = 0.955555...
    assert round(v, 4) == 0.9556
    assert note == "1.00 of 3 · 57 analysts"


def test_analyst_rating_center_is_zero():
    v, _ = verdict.analyst_rating_input({"rec_mark": 1.43, "rec_total": 20})
    assert v == pytest.approx(0.0)


def test_analyst_rating_clamps_at_minus1():
    v, _ = verdict.analyst_rating_input({"rec_mark": 2.78, "rec_total": 20})
    assert v == pytest.approx(-1.0)


def test_analyst_rating_null_below_min_analysts():
    v, note = verdict.analyst_rating_input({"rec_mark": 1.2, "rec_total": 4})
    assert v is None
    assert note == "fewer than 5 analysts"


def test_analyst_rating_null_no_mark():
    v, note = verdict.analyst_rating_input({"rec_total": 57})
    assert v is None
    assert note == "no analyst rating"


# ── target_upside ────────────────────────────────────────────────────────

def test_target_upside_plus50_is_1():
    v, note = verdict.target_upside_input({"target": 150.0, "rec_total": 20}, spot=100.0)
    assert v == pytest.approx(1.0)
    assert note == "+50% to the average target"


def test_target_upside_plus20_is_0():
    v, _ = verdict.target_upside_input({"target": 120.0, "rec_total": 20}, spot=100.0)
    assert v == pytest.approx(0.0)


def test_target_upside_minus10_is_minus1():
    v, note = verdict.target_upside_input({"target": 90.0, "rec_total": 20}, spot=100.0)
    assert v == pytest.approx(-1.0)
    assert note == "−10% to the average target"


def test_target_upside_null_below_min_analysts():
    v, note = verdict.target_upside_input({"target": 150.0, "rec_total": 2}, spot=100.0)
    assert v is None
    assert note == "fewer than 5 analysts"


def test_target_upside_null_no_target():
    v, note = verdict.target_upside_input({"rec_total": 20}, spot=100.0)
    assert v is None
    assert note == "no price target"
    v2, _ = verdict.target_upside_input({"target": 150.0, "rec_total": 20}, spot=None)
    assert v2 is None


# ── flow_today / flow_persist ────────────────────────────────────────────

def test_flow_today_bear_62():
    v, note = verdict.flow_today_input({"direction": "BEAR", "score": 62})
    assert v == pytest.approx(-0.62)
    assert note == "BEAR 62 on Conviction"


def test_flow_today_bull_100():
    v, _ = verdict.flow_today_input({"direction": "BULL", "score": 100})
    assert v == pytest.approx(1.0)


def test_flow_today_null_no_card():
    v, note = verdict.flow_today_input(None)
    assert v is None
    assert note == "no conviction card"


def test_flow_persist_bear_40():
    v, note = verdict.flow_persist_input({"direction": "BEAR", "score": 40})
    assert v == pytest.approx(-0.40)
    assert note == "BEAR 40 on Swing"


def test_flow_persist_null_no_card():
    v, note = verdict.flow_persist_input(None)
    assert v is None
    assert note == "no swing card"


# ── valuation ────────────────────────────────────────────────────────────
# F3 (2026-09-11 fix): each null branch names the fact it actually is. A
# null PEG with a healthy positive P/E (CRWD pe 5850, SNDK 23, MRVL 75 and
# seven more the day this was found) used to print "no PEG (loss-making)" --
# a real vendor gap misdiagnosed as an unprofitable company. A missing `pe`
# used to print the unrelated "P/E out of range". One test per branch,
# asserting the exact string.

def test_valuation_peg_003():
    v, note = verdict.valuation_input({"peg": 0.03, "pe": 22.0})
    assert v == pytest.approx(0.98)
    assert note == "PEG 0.03"


def test_valuation_peg_3_is_minus1():
    v, _ = verdict.valuation_input({"peg": 3.0, "pe": 20.0})
    assert v == pytest.approx(-1.0)


def test_valuation_null_peg_absent_with_positive_pe():
    # the exact CRWD/SNDK/MRVL shape: peg missing, pe real and positive --
    # this is "no PEG reading", never "loss-making" (the company may well be
    # very profitable; the vendor simply didn't publish a PEG).
    v, note = verdict.valuation_input({"pe": 5850.0})
    assert v is None
    assert note == "no PEG reading"


def test_valuation_null_negative_peg_prints_signed_value():
    v, note = verdict.valuation_input({"peg": -4.9, "pe": 20.0})
    assert v is None
    assert note == f"PEG {verdict._MINUS}4.90"


def test_valuation_null_zero_peg_prints_unsigned_zero():
    v, note = verdict.valuation_input({"peg": 0.0, "pe": 20.0})
    assert v is None
    assert note == "PEG 0.00"


def test_valuation_null_pe_absent():
    v, note = verdict.valuation_input({"peg": 1.0})
    assert v is None
    assert note == "no P/E reading"


def test_valuation_null_negative_pe_prints_signed_value():
    v, note = verdict.valuation_input({"peg": 1.0, "pe": -5.0})
    assert v is None
    assert note == f"P/E {verdict._MINUS}5.0"


def test_valuation_null_pe_over_150():
    v, note = verdict.valuation_input({"peg": 1.0, "pe": 352.0})
    assert v is None
    assert note == "P/E 352, above 150"


def test_valuation_null_fund_regardless_of_peg():
    v, note = verdict.valuation_input({"peg": 0.03, "pe": 22.0, "sec_type": "fund"})
    assert v is None
    assert note == "fund"


# ── market ───────────────────────────────────────────────────────────────

def test_market_score_minus1():
    v, note = verdict.market_input({"score": -1, "verdict": "NEUTRAL", "stale": False})
    assert v == pytest.approx(-0.2)
    assert note == "brief NEUTRAL (−1)"


def test_market_null_stale():
    v, note = verdict.market_input({"score": -1, "verdict": "NEUTRAL", "stale": True})
    assert v is None
    assert note == "brief stale"


def test_market_null_absent():
    v, note = verdict.market_input(None)
    assert v is None
    assert note == "no brief"
    v2, note2 = verdict.market_input({})
    assert v2 is None
    assert note2 == "no brief"


def test_market_null_no_score():
    v, note = verdict.market_input({"stale": False})
    assert v is None
    assert note == "no market score"


# ── fund still gets trend/rs/flow ────────────────────────────────────────

def test_fund_keeps_trend_rs_and_flow_inputs():
    facts_entry = {"sec_type": "fund", "framework": {"verdict": "NOT_APPLICABLE"},
                   "peg": 0.5, "pe": 20.0}
    closes = _closes_for_smas(100.0, 100.0)
    spot = 105.0
    conv = {"direction": "BULL", "score": 50}
    # QQQ, not SPY: this is a fund (framework/valuation both null), but not
    # the rs63 benchmark itself (F5) -- spy_closes is a separate object with
    # the same content so rs63 still resolves rather than reading "benchmark".
    entry = verdict.compute_verdict(
        "QQQ", spot=spot, closes=closes, spy_closes=list(closes), facts_entry=facts_entry,
        conv_card=conv, swing_card=None, brief=None)
    assert entry["inputs"]["trend"]["v"] is not None
    assert entry["inputs"]["rs63"]["v"] is not None
    assert entry["inputs"]["flow_today"]["v"] is not None
    assert entry["inputs"]["framework"]["v"] is None
    assert entry["inputs"]["framework"]["note"] == "fund"
    assert entry["inputs"]["valuation"]["v"] is None
    assert entry["inputs"]["valuation"]["note"] == "fund"


def test_track_only_style_name_no_cards():
    closes = _closes_for_smas(100.0, 100.0)
    entry = verdict.compute_verdict(
        "WTI", spot=105.0, closes=closes, spy_closes=closes, facts_entry={},
        conv_card=None, swing_card=None, brief=None)
    assert entry["inputs"]["flow_today"] == {"v": None, "note": "no conviction card"}
    assert entry["inputs"]["flow_persist"] == {"v": None, "note": "no swing card"}


# ── compute_verdict: coverage gate, renormalization, thresholds ──────────

def test_renormalization_and_coverage_gate():
    # trend +1 (w14), rs63 -1 (w14), flow_persist +0.5 (w15) -> weight 43,
    # n=3: weight < 50 -> coverage gate fails even though n_inputs is enough.
    closes = _closes_for_smas(100.0, 100.0)
    spot = 105.0  # +5% above both SMAs -> trend v = +1.0
    spy = _rs_closes(0.20)   # spy up 20%, name flat -> diff -20pp -> v=-1.0
    name_closes = _rs_closes(0.0)
    # trend needs >=200 closes; rs63 needs >=64 and reads the SAME closes
    # list passed to compute_verdict, so build one list satisfying both.
    combined = _closes_for_smas(100.0, 100.0)  # 200 flat-ish closes, last 50 == 100
    # override so the last 64 give rs63 ret == 0 exactly (already flat there)
    swing = {"direction": "BULL", "score": 50}  # v = +0.5

    entry = verdict.compute_verdict(
        "T1", spot=spot, closes=combined, spy_closes=spy, facts_entry={},
        conv_card=None, swing_card=swing, brief=None)
    assert entry["inputs"]["trend"]["v"] == pytest.approx(1.0)
    assert entry["inputs"]["rs63"]["v"] == pytest.approx(-1.0)
    assert entry["inputs"]["flow_persist"]["v"] == pytest.approx(0.5)
    assert entry["weight"] == 43
    assert entry["n"] == 3
    assert entry["score"] is None
    assert entry["call"] is None
    assert entry["note"] == "3 of 9 inputs · weight 43 of 100"

    # add flow_today +1.0 (w10) -> weight 53, n=4. trend (14) and rs63 (-14)
    # now carry the SAME weight and opposite-unit values, so they cancel to
    # 0 regardless of magnitude -- the whole sum comes from flow_persist and
    # flow_today: score = round(100 * (14*1 + 14*-1 + 15*0.5 + 10*1) / 53)
    #                    = round(100 * 17.5 / 53) = round(33.019) = 33 -> HOLD
    # (below the registered set's arithmetic gave 50 -> BUY here; the new
    # equal weights on trend/rs63 no longer let one of them dominate).
    conv = {"direction": "BULL", "score": 100}  # v = +1.0
    entry2 = verdict.compute_verdict(
        "T1", spot=spot, closes=combined, spy_closes=spy, facts_entry={},
        conv_card=conv, swing_card=swing, brief=None)
    assert entry2["weight"] == 53
    assert entry2["n"] == 4
    assert entry2["score"] == 33
    assert entry2["call"] == "HOLD"
    assert entry2["note"] is None


def test_min_inputs_gate_two_inputs_weight_35():
    # trend (14) + flow_persist (15) = weight 29, n=2 -> no call. Note this
    # does NOT isolate VERDICT_MIN_INPUTS as an independent gate: weight
    # (29) is also short of VERDICT_MIN_WEIGHT (50) here, and F8 (below)
    # shows that under the CURRENT weight table no 2-input combination can
    # ever reach weight 50 in the first place, so an n<3 case whose weight
    # gate passes is not constructible today. (2026-09-11 reweight: this was
    # 35 under the registered trend=20 weight; the test name is now a loose
    # label, not the literal weight value.)
    closes = _closes_for_smas(100.0, 100.0)
    swing = {"direction": "BULL", "score": 50}
    entry = verdict.compute_verdict(
        "T2", spot=105.0, closes=closes, spy_closes=[], facts_entry={},
        conv_card=None, swing_card=swing, brief=None)
    assert entry["weight"] == 29
    assert entry["n"] == 2
    assert entry["score"] is None
    assert entry["call"] is None
    assert entry["note"] == "2 of 9 inputs · weight 29 of 100"


def test_min_inputs_gate_is_currently_unreachable_by_itself():
    # F8 (2026-09-11): VERDICT_MIN_INPUTS (3) is subsumed by the weight gate
    # under the current table -- the two largest weights (flow_persist 15 +
    # a 14-weight leg = 29, after the 2026-09-11 reweight put trend, rs63
    # and framework in a three-way tie at 14) already fall short of
    # VERDICT_MIN_WEIGHT (50), so no 2-input combination can ever pass the
    # weight leg, and the n>=3 check can never be the SOLE reason a call is
    # withheld. This guard fails the moment a future weight-table change
    # lets some pair of inputs alone clear 50 -- at that point
    # VERDICT_MIN_INPUTS starts doing real, independent work and deserves
    # its own passing test.
    top_two = sorted(verdict.VERDICT_WEIGHTS.values(), reverse=True)[:2]
    assert sum(top_two) < verdict.VERDICT_MIN_WEIGHT


def _weight50_entry(trend_v_sign: int, fw_verdict: str, conv_score: float, conv_dir: str):
    """trend (w14) + framework (w14) + target_upside (w7) + flow_today (w10)
    + market (w5) = weight 50. Framework is pinned HOLD (v=0.0), target is
    pinned exactly at the analyst-upside center (VERDICT_TARGET_CENTER,
    0.20 -> v=0.0) and the brief score is pinned at 0 (v=0.0), so three of
    the five legs are always-zero padding that brings the weight to exactly
    50 without touching the sum -- only trend and flow_today ever move the
    score. (2026-09-11 reweight: the registered table's trend+framework+
    flow_today alone summed to 50; the new table's 14+14+10=38 needed two
    more zero-valued legs to reach the same coverage-gate boundary.)"""
    closes = _closes_for_smas(100.0, 100.0)
    spot = 100.0 * (1.05 if trend_v_sign > 0 else 0.95)
    facts_entry = {
        "framework": {"verdict": fw_verdict},
        "target": spot * (1.0 + verdict.VERDICT_TARGET_CENTER),  # upside == center -> v=0
        "rec_total": 10,
    }
    conv = {"direction": conv_dir, "score": conv_score}
    brief = {"score": 0, "verdict": "NEUTRAL", "stale": False}  # market center -> v=0
    return verdict.compute_verdict(
        "T3", spot=spot, closes=closes, spy_closes=[], facts_entry=facts_entry,
        conv_card=conv, swing_card=None, brief=brief)


def test_threshold_exactly_35_is_buy():
    # trend +1 (14) + flow_today BULL 35 (10*0.35=3.5); framework, target_upside
    # and market all contribute 0 (see _weight50_entry).
    # wsum = 14 + 3.5 = 17.5; weight = 50; score = 100*17.5/50 = 35.0
    entry = _weight50_entry(+1, "HOLD", 35, "BULL")
    assert entry["weight"] == 50
    assert entry["score"] == 35
    assert entry["call"] == "BUY"


def test_threshold_34_is_hold():
    # wsum = 14 + 10*0.30 = 17.0; score = 100*17/50 = 34.0
    entry = _weight50_entry(+1, "HOLD", 30, "BULL")
    assert entry["score"] == 34
    assert entry["call"] == "HOLD"


def test_threshold_minus35_is_sell():
    # trend -1 (-14) + flow_today BEAR 35 (-3.5)
    # wsum = -14 - 3.5 = -17.5; score = 100*-17.5/50 = -35.0
    entry = _weight50_entry(-1, "HOLD", 35, "BEAR")
    assert entry["score"] == -35
    assert entry["call"] == "SELL"


def test_threshold_minus34_is_hold():
    # wsum = -14 - 3.0 = -17.0; score = -34.0
    entry = _weight50_entry(-1, "HOLD", 30, "BEAR")
    assert entry["score"] == -34
    assert entry["call"] == "HOLD"


# ── rounding at .5 (pinned rule: half rounds AWAY from zero) ─────────────

def test_round_half_away_from_zero_helper():
    assert verdict._round_half_away_from_zero(34.5) == 35
    assert verdict._round_half_away_from_zero(-34.5) == -35
    assert verdict._round_half_away_from_zero(0.5) == 1
    assert verdict._round_half_away_from_zero(-0.5) == -1
    assert verdict._round_half_away_from_zero(0.0) == 0
    assert verdict._round_half_away_from_zero(2.4) == 2
    assert verdict._round_half_away_from_zero(2.6) == 3


def test_score_rounds_half_away_from_zero_at_sell_threshold():
    # trend -1 (-14) + flow_today BEAR 32.5 (-3.25)
    # wsum = -17.25, weight = 50 -> ratio -34.5 -> rounds to -35 -> SELL,
    # NOT Python round()'s banker's-rounding -34 (which would stay HOLD).
    entry = _weight50_entry(-1, "HOLD", 32.5, "BEAR")
    assert entry["score"] == -35
    assert entry["call"] == "SELL"


def test_score_rounds_half_away_from_zero_at_buy_threshold():
    # trend +1 (14) + flow_today BULL 32.5 (+3.25); wsum = 17.25 -> 34.5 -> 35
    entry = _weight50_entry(+1, "HOLD", 32.5, "BULL")
    assert entry["score"] == 35
    assert entry["call"] == "BUY"


# ── earnings gate ─────────────────────────────────────────────────────────
# Same weight-50 padding as _weight50_entry (framework HOLD, target pinned at
# the analyst-upside center, market pinned at 0 -- all three v=0.0), so only
# trend and flow_today move the score. 2026-09-11 reweight: trend+framework+
# flow_today alone summed to the registered table's 50; the new table needs
# the same two extra zero-valued legs _weight50_entry added.

def _buy_entry(earn_days):
    closes = _closes_for_smas(100.0, 100.0)
    spot = 105.0
    facts_entry = {
        "framework": {"verdict": "HOLD"},
        "target": spot * (1.0 + verdict.VERDICT_TARGET_CENTER),  # upside == center -> v=0
        "rec_total": 10,
    }
    if earn_days is not None:
        facts_entry["earn_days"] = earn_days
    conv = {"direction": "BULL", "score": 35}  # v=+0.35 -> wsum 17.5, score 35 BUY
    brief = {"score": 0, "verdict": "NEUTRAL", "stale": False}  # market center -> v=0
    return verdict.compute_verdict(
        "T4", spot=spot, closes=closes, spy_closes=[], facts_entry=facts_entry,
        conv_card=conv, swing_card=None, brief=brief)


def _sell_entry(earn_days):
    closes = _closes_for_smas(100.0, 100.0)
    spot = 95.0
    facts_entry = {
        "framework": {"verdict": "HOLD"},
        "target": spot * (1.0 + verdict.VERDICT_TARGET_CENTER),
        "rec_total": 10,
    }
    if earn_days is not None:
        facts_entry["earn_days"] = earn_days
    conv = {"direction": "BEAR", "score": 35}  # mirrors to score -35 SELL
    brief = {"score": 0, "verdict": "NEUTRAL", "stale": False}
    return verdict.compute_verdict(
        "T5", spot=spot, closes=closes, spy_closes=[], facts_entry=facts_entry,
        conv_card=conv, swing_card=None, brief=brief)


@pytest.mark.parametrize("earn_days", [0, 1, 3])
def test_earnings_gate_holds_a_buy(earn_days):
    entry = _buy_entry(earn_days)
    assert entry["score"] == 35  # score is unchanged and still published
    assert entry["call"] == "HOLD"
    assert entry["note"] == f"earnings in {earn_days}d"


@pytest.mark.parametrize("earn_days", [4, -1, None])
def test_earnings_gate_does_not_fire(earn_days):
    entry = _buy_entry(earn_days)
    assert entry["score"] == 35
    assert entry["call"] == "BUY"
    assert entry["note"] is None


@pytest.mark.parametrize("earn_days", [0, 2, 3])
def test_earnings_gate_holds_a_sell_too(earn_days):
    entry = _sell_entry(earn_days)
    assert entry["score"] == -35
    assert entry["call"] == "HOLD"
    assert entry["note"] == f"earnings in {earn_days}d"


# ── payload shape / determinism ──────────────────────────────────────────

def test_compute_verdict_payload_shape():
    closes = _closes_for_smas(100.0, 100.0)
    entry = verdict.compute_verdict(
        "MU", spot=105.0, closes=closes, spy_closes=closes,
        facts_entry={"framework": {"verdict": "HOLD"}}, conv_card=None,
        swing_card=None, brief=None)
    for key in ("score", "call", "note", "n", "n_total", "weight", "inputs"):
        assert key in entry
    assert entry["n_total"] == 9
    assert set(entry["inputs"].keys()) == set(verdict.VERDICT_INPUT_ORDER)
    for k in verdict.VERDICT_INPUT_ORDER:
        assert set(entry["inputs"][k].keys()) == {"v", "note"}


def test_compute_verdict_is_deterministic():
    closes = _closes_for_smas(100.0, 100.0)
    kwargs = dict(spot=105.0, closes=closes, spy_closes=closes,
                  facts_entry={"framework": {"verdict": "ADD"}, "peg": 1.0, "pe": 20.0},
                  conv_card={"direction": "BULL", "score": 40},
                  swing_card={"direction": "BEAR", "score": 30}, brief={"score": 2})
    e1 = verdict.compute_verdict("MU", **kwargs)
    e2 = verdict.compute_verdict("MU", **kwargs)
    assert e1 == e2


def test_compute_verdicts_none_for_empty_facts():
    assert verdict.compute_verdicts([], [], {}, {}, {}, None, None) is None
    assert verdict.compute_verdicts([], [], None, {}, {}, None, None) is None


def test_compute_verdicts_shape_and_counts():
    facts = {
        "AAA": {"framework": {"verdict": "BUY_5"}},
        "BBB": {"framework": {"verdict": "AVOID"}},
    }
    conv = [{"ticker": "AAA", "direction": "BULL", "score": 90, "spot": 100.0},
            {"ticker": "BBB", "direction": "BEAR", "score": 90, "spot": 50.0}]
    out = verdict.compute_verdicts(conv, [], facts, {}, {}, None, None)
    assert out["v"] == 1
    assert out["order"] == list(verdict.VERDICT_INPUT_ORDER)
    assert out["weights"] == verdict.VERDICT_WEIGHTS
    assert out["thresholds"] == {"buy": 35, "sell": -35}
    assert out["bars_built"] is None
    assert set(out["by_ticker"].keys()) == {"AAA", "BBB"}
    total = sum(out["counts"].values())
    assert total == len(facts)


# ── bars_built (F10, 2026-09-11) ──────────────────────────────────────────

def test_compute_verdicts_publishes_bars_built():
    facts = {"AAA": {}}
    bars_payload = {"built": "2026-09-10", "bars": {}}
    out = verdict.compute_verdicts([], [], facts, {}, {}, bars_payload, None)
    assert out["bars_built"] == "2026-09-10"


def test_compute_verdicts_bars_built_null_when_no_bars_payload():
    facts = {"AAA": {}}
    out = verdict.compute_verdicts([], [], facts, {}, {}, None, None)
    assert out["bars_built"] is None


# ── rs63 positional fallback end-to-end on a v2 bars.json (F5) ────────────

def test_compute_verdicts_rs63_falls_back_to_positional_on_v2_bars():
    # a v2 bars.json (quads, no "sessions"/"bar_dates") -- dates_of returns
    # None for every ticker, so rs63's note discloses the positional
    # fallback all the way through compute_verdicts, not just rs63_input in
    # isolation.
    name_closes = _rs_closes(0.20)
    spy_closes = _rs_closes(0.0)
    bars_payload = {"v": 2, "bars": {
        "AAA": [[0, 0, 0, c] for c in name_closes],
        "SPY": [[0, 0, 0, c] for c in spy_closes],
    }}
    facts = {"AAA": {}}
    out = verdict.compute_verdicts([], [], facts, {"AAA": 100.0}, {}, bars_payload, None)
    note = out["by_ticker"]["AAA"]["inputs"]["rs63"]["note"]
    assert note == "+20.0pp vs SPY, 63 sessions (positional; no calendar in bars)"


# ── spot resolution: spot_by_ticker first, then quotes.close, else None ──

def test_compute_verdicts_spot_prefers_spot_by_ticker():
    # F9 (2026-09-11 fix): the old version passed no bars, so `closes` was
    # always [] and trend read null regardless of which spot fed it --
    # the test never actually exercised the preference it claimed to pin.
    # With real closes on file, spot_by_ticker (105, reads ABOVE both
    # averages) must win over quotes.close (95, reads BELOW) -- the trend
    # note is the observable proof of which one flowed through.
    facts = {"AAA": {}}
    bars_payload = {"bars": {"AAA": [100.0] * 200}}
    out = verdict.compute_verdicts(
        [], [], facts, {"AAA": 105.0}, {"AAA": {"close": 95.0}}, bars_payload, None)
    note = out["by_ticker"]["AAA"]["inputs"]["trend"]["note"]
    assert note == "above 50d · above 200d"


def test_compute_verdicts_spot_falls_back_to_quotes_close():
    facts = {"AAA": {}}
    out = verdict.compute_verdicts([], [], facts, {}, {"AAA": {"close": 99.0}}, None, None)
    assert "AAA" in out["by_ticker"]


def test_compute_verdicts_spot_none_when_neither_positive():
    facts = {"AAA": {}}
    out = verdict.compute_verdicts([], [], facts, {"AAA": -1.0}, {"AAA": {"close": 0}}, None, None)
    assert out["by_ticker"]["AAA"]["inputs"]["trend"]["note"] == "no spot"


# ── closes_of: v1/v2/v3/v4 shapes ─────────────────────────────────────────

def test_closes_of_v1_bare_numbers():
    payload = {"bars": {"MU": [100.0, 101.0, 102.5]}}
    assert verdict.closes_of(payload, "MU") == [100.0, 101.0, 102.5]


def test_closes_of_v2_quads():
    payload = {"v": 2, "bars": {"MU": [[100, 105, 99, 101.5], [101, 106, 100, 103.25]]}}
    assert verdict.closes_of(payload, "MU") == [101.5, 103.25]


def test_closes_of_v3_v4_quints():
    payload = {"v": 4, "sessions": ["2026-01-01"], "bars": {
        "MU": [[100, 105, 99, 101.5, 1000], [101, 106, 100, 103.25, 2000]]}}
    assert verdict.closes_of(payload, "MU") == [101.5, 103.25]


def test_closes_of_missing_ticker_or_bad_payload():
    assert verdict.closes_of({"bars": {}}, "MU") == []
    assert verdict.closes_of(None, "MU") == []
    assert verdict.closes_of({}, "MU") == []
    assert verdict.closes_of({"bars": {"MU": None}}, "MU") == []


# ── dates_of: bars.json calendar reader (F5, 2026-09-11) ─────────────────

def test_dates_of_none_for_v1_v3_payload_no_sessions():
    # bars.json v1-v3 carries no "sessions" key at all -- the signal
    # rs63_input reads as "fall back to positional".
    payload = {"v": 2, "bars": {"MU": [[100, 105, 99, 101.5]]}}
    assert verdict.dates_of(payload, "MU", 1) is None
    assert verdict.dates_of(None, "MU", 1) is None
    assert verdict.dates_of({}, "MU", 1) is None


def test_dates_of_uses_bar_dates_override_when_present():
    payload = {"bar_dates": {"VIX": ["2026-01-01", "2026-01-02"]},
               "sessions": ["2026-02-01", "2026-02-02"]}
    assert verdict.dates_of(payload, "VIX", 2) == ["2026-01-01", "2026-01-02"]


def test_dates_of_falls_back_to_sessions_for_other_tickers():
    payload = {"bar_dates": {"VIX": ["2026-01-01"]},
               "sessions": ["2026-02-01", "2026-02-02"]}
    assert verdict.dates_of(payload, "MU", 2) == ["2026-02-01", "2026-02-02"]


def test_dates_of_slices_sessions_to_match_a_shorter_history():
    # a recently-added ticker (SKHY, DRAM, ...) has fewer bars rows than
    # "sessions" has entries -- its dates are the TAIL of sessions, not the
    # head, and not the full list.
    payload = {"sessions": ["2026-01-01", "2026-01-02", "2026-01-03"]}
    assert verdict.dates_of(payload, "NEWCO", 2) == ["2026-01-02", "2026-01-03"]
    assert verdict.dates_of(payload, "NEWCO", 0) == []


def test_dates_of_none_when_more_rows_than_sessions_has_entries():
    # F5-follow-up (2026-09-11 fix): a ticker with MORE bars rows than
    # "sessions" has entries, and no bar_dates override, used to return the
    # full (too-short) sessions list -- length-MISALIGNED with the caller's
    # closes, since rs63_input indexes both lists assuming they line up.
    # None is the correct signal: no usable calendar, same as bars.json
    # carrying no "sessions" key at all, so rs63_input takes its disclosed
    # positional fallback instead of silently pairing mismatched lists.
    payload = {"sessions": ["2026-01-01", "2026-01-02"]}
    assert verdict.dates_of(payload, "OLDCO", 3) is None


def test_dates_of_none_feeds_rs63_positional_fallback_end_to_end():
    # dates_of's None (a 3-row ticker against a 2-entry sessions list) flows
    # straight into rs63_input's positional fallback, and a RESOLVED read
    # discloses it -- never a null note.
    bars_payload = {"sessions": ["2026-01-01", "2026-01-02"]}
    name_closes = _rs_closes(0.20)
    spy_closes = _rs_closes(0.0)
    dates = verdict.dates_of(bars_payload, "OLDCO", len(name_closes))
    assert dates is None
    v, note = verdict.rs63_input("OLDCO", name_closes, spy_closes, dates, dates)
    assert v == pytest.approx(1.0)
    assert note == "+20.0pp vs SPY, 63 sessions (positional; no calendar in bars)"


# ── load_bars_from_disk ───────────────────────────────────────────────────

def test_load_bars_from_disk_missing_file(tmp_path):
    assert verdict.load_bars_from_disk(tmp_path) is None


def test_load_bars_from_disk_corrupt_json(tmp_path):
    (tmp_path / "bars.json").write_text("{not json", encoding="utf-8")
    assert verdict.load_bars_from_disk(tmp_path) is None


def test_load_bars_from_disk_parses_v4(tmp_path):
    payload = {"built": "2026-09-10", "v": 4, "sessions": ["2026-09-10"],
               "bars": {"MU": [[1, 2, 0.5, 1.5, 100]]}}
    (tmp_path / "bars.json").write_text(json.dumps(payload), encoding="utf-8")
    loaded = verdict.load_bars_from_disk(tmp_path)
    assert loaded == payload


# ── build_snapshot wiring ─────────────────────────────────────────────────

def test_build_snapshot_imports_verdict():
    src = (ROOT / "fetcher" / "build_snapshot.py").read_text(encoding="utf-8")
    assert "import verdict" in src


def test_build_snapshot_has_verdicts_optional_spread():
    src = (ROOT / "fetcher" / "build_snapshot.py").read_text(encoding="utf-8")
    assert '**({"verdicts": verdicts} if verdicts else {})' in src


# ── integration against a real, trimmed sample payload (F7, 2026-09-11) ──
# The old version pointed at THIS SESSION's own /tmp scratchpad path, so the
# one test that ever ran against real desk data was skipped everywhere else.
# fetcher/testdata/verdict_sample_2026-09-10.json is a trimmed, checked-in
# copy of a real cycle's data.json + bars.json (see its own "note" field for
# exactly what was kept) -- this test always runs.

FIXTURE = ROOT / "fetcher" / "testdata" / "verdict_sample_2026-09-10.json"


def test_integration_against_fixture_payload():
    d = json.loads(FIXTURE.read_text(encoding="utf-8"))
    conv = d["conviction"]
    sw = d["swing"]
    spots = {c["ticker"]: c["spot"] for c in conv + sw if c.get("spot")}
    out = verdict.compute_verdicts(conv, sw, d["facts"], spots, {}, d["bars"], d["brief"])
    assert out is not None
    assert out["bars_built"] == d["bars"]["built"] == "2026-09-10"
    assert sum(out["counts"].values()) == len(d["facts"])

    # every counts bucket equals a fresh tally over by_ticker -- the two can
    # never silently drift apart.
    tally = {"buy": 0, "sell": 0, "hold": 0, "none": 0}
    for entry in out["by_ticker"].values():
        call = entry["call"]
        key = {"BUY": "buy", "SELL": "sell", "HOLD": "hold"}.get(call, "none")
        tally[key] += 1
    assert out["counts"] == tally

    for ticker, entry in out["by_ticker"].items():
        if entry["score"] is not None:
            assert -100 <= entry["score"] <= 100
        if entry["call"] == "BUY":
            assert entry["score"] >= verdict.VERDICT_BUY_MIN
        elif entry["call"] == "SELL":
            assert entry["score"] <= verdict.VERDICT_SELL_MAX
        # F2: a published framework note never leaks the raw "_BUILDING" /
        # "_CAPPED" enum -- only the rendered tier, plus "(capped)" when
        # earned.
        fw_note = entry["inputs"]["framework"]["note"]
        if fw_note is not None:
            assert "_BUILDING" not in fw_note
            assert "_CAPPED" not in fw_note

    # Pinned counts, re-derived AFTER the F1-F5 fixes on this exact fixture
    # (pre-F1-F5, registered-weight counts on the same fixture: buy 9, sell
    # 8, hold 39, none 7; with the F1-F5 fixes and the REGISTERED weights,
    # counts were buy 8, sell 8, hold 40, none 7, with exactly one ticker
    # moved by the fixes alone: XLF, BUY -> HOLD -- see the trend/rs63 notes
    # below, which are fix behavior and unaffected by the reweight).
    #
    # 2026-09-11 REWEIGHT (backtest attempt #2, equal weights over the four
    # testable legs -- decisions-log OUTCOME entry 2026-09-11): re-running
    # the same fixture at the new weights moves six more tickers relative to
    # the registered-weight counts above:
    #   MOD:  SELL -> HOLD   (-36 -> -29; lost weight off framework/trend)
    #   MSFT: HOLD -> BUY    (28 -> 35)
    #   MU:   HOLD -> BUY    (34 -> 35; trend+rs63+valuation gained weight)
    #   SPY:  HOLD -> no call (-10 -> null; resolved weight fell under 50 --
    #         SPY's rs63 is always null (benchmark) and it carries no
    #         framework/analyst/target/valuation, so losing 6 points of
    #         weight off trend+framework dropped its total from 54 to 44)
    #   WTI:  BUY -> no call  (58 -> null; no analyst/target/valuation/flow-
    #         today coverage, so its resolved weight fell from 50 to 48)
    #   XLRE: HOLD -> no call (3 -> null; same shape as WTI/SPY, 50 -> 48)
    # Every one of these three "-> no call" moves is the SAME mechanism:
    # trend and framework each dropped 6 points of weight (20 -> 14) while
    # only names that also carry rs63 and/or valuation picked up the
    # difference elsewhere: SPY/WTI/XLRE do not, so their resolved weight
    # crossed below VERDICT_MIN_WEIGHT (50) even though nothing about their
    # OWN inputs changed.
    assert out["counts"] == {"buy": 9, "sell": 7, "hold": 37, "none": 10}

    xlf = out["by_ticker"]["XLF"]
    assert xlf["call"] == "HOLD"
    assert xlf["inputs"]["trend"]["note"] == "below 50d · above 200d"
    assert xlf["inputs"]["trend"]["v"] == pytest.approx(0.0)

    for moved_ticker, expect_call in (
        ("MOD", "HOLD"), ("MSFT", "BUY"), ("MU", "BUY"),
        ("SPY", None), ("WTI", None), ("XLRE", None),
    ):
        assert out["by_ticker"][moved_ticker]["call"] == expect_call, moved_ticker

    mu = out["by_ticker"]["MU"]
    assert mu["call"] == "BUY"
    assert mu["score"] == 35
    assert mu["note"] is None
    assert mu["n"] == 8
    assert mu["n_total"] == 9
    assert mu["weight"] == 86
    mu_inputs = mu["inputs"]
    assert mu_inputs["trend"] == {"v": pytest.approx(1.0), "note": "above 50d · above 200d"}
    assert mu_inputs["rs63"]["note"] == "+6.4pp vs SPY, 63 sessions"
    assert mu_inputs["rs63"]["v"] == pytest.approx(0.31890031626220505)
    assert mu_inputs["framework"] == {"v": None, "note": "building"}
    assert mu_inputs["analyst_rating"]["note"] == "1.12 of 3 · 57 analysts"
    assert mu_inputs["analyst_rating"]["v"] == pytest.approx(0.6826511111111108)
    assert mu_inputs["target_upside"] == {"v": pytest.approx(1.0), "note": "+61% to the average target"}
    assert mu_inputs["flow_today"] == {"v": pytest.approx(-0.62), "note": "BEAR 62 on Conviction"}
    assert mu_inputs["flow_persist"] == {"v": pytest.approx(-0.4), "note": "BEAR 40 on Swing"}
    assert mu_inputs["valuation"]["note"] == "PEG 0.03"
    assert mu_inputs["valuation"]["v"] == pytest.approx(0.9777543567196417)
    assert mu_inputs["market"] == {"v": pytest.approx(-0.2), "note": "brief NEUTRAL (−1)"}
    # score = round(100 * (14*1.0 + 14*0.31890031626220505 + 8*0.6826511111111108
    #   + 7*1.0 + 10*-0.62 + 15*-0.4 + 13*0.9777543567196417 + 5*-0.2) / 86)
    #        = round(100 * 30.4366201537151 / 86) = round(35.391...) = 35 -> BUY

    # F1 (2026-09-11 fix): RAM, SKHY, SKHX and STLL all carry far fewer than
    # 64 rows in this fixture (54, 43, 41, 21) with no bar_dates override,
    # so dates_of hands each a dates list drawn from the TAIL of "sessions"
    # -- entirely AFTER SPY's anchor date. dates.index(anchor_date) used to
    # raise ValueError there and print "calendar gap in the 63-session
    # window", the wrong reason (that note is reserved for a name whose
    # dates genuinely span the anchor but skip that one session).
    for short_history_ticker in ("RAM", "SKHY", "SKHX", "STLL"):
        entry = out["by_ticker"][short_history_ticker]
        rs63 = entry["inputs"]["rs63"]
        assert rs63["v"] is None, (short_history_ticker, rs63)
        assert rs63["note"] == "fewer than 64 daily closes", (short_history_ticker, rs63)
