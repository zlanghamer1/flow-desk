"""Flow Desk verdicts — the one decision layer.

Design record: docs/superpowers/specs/2026-09-11-desk-verdicts-design.md
Payload shape: DATA_CONTRACT.md -> "Verdicts (added 2026-09-11)"

A weighted composite of nine readings the desk already publishes, computed
once per cycle and read -- never re-derived -- by the page. `conviction_score`
and `swing_score` are UNCHANGED and are two of the nine inputs (standing ban
10: a display-only field never feeds a board score; this composite is a
separate, additive layer that reads display-only fields and never writes
back into either board score).

Evidence class: UNVALIDATED. Every constant below is set by judgment and
pre-registered in the design doc and the vault's
`portfolio-thesis/decisions-log.md`. Changing one needs a dated amendment
there first.

Run: python3 -m pytest fetcher/test_verdict.py -q
"""
from __future__ import annotations

import json
import math
from pathlib import Path

# ── Inputs, in render order (also the page's VERDICT_INPUT_LABELS key set,
# pinned equal by fetcher/test_sync_constants.py) ───────────────────────────
# `market` (the brief score) left the composite 2026-09-11 (attempt #3
# amendment): one number a day, identical for every name, so it could never
# re-rank -- it only moved the call count, and its measured forward sign was
# the wrong way. The brief verdict prints as a chip on the board instead.
VERDICT_INPUT_ORDER = ("trend", "rs63", "framework", "analyst_rating",
                        "target_upside", "flow_today", "flow_persist",
                        "valuation")

# Weights, 2026-09-11 (backtest attempt #3, decisions-log OUTCOME entry).
# Two classes:
#   * the four tested legs carry 82 of 100 in EQUAL proportions -- attempt
#     #3 judged regime-conditional and refit candidates walk-forward and
#     none was distinguishable from flat equal (desk paired t 0.68) or
#     cleared the S&P guard, so C0 stands. 82 does not divide by four; the
#     registration puts the two spare points on trend and rs63 (rounding,
#     not a ranking).
#   * the four untestable legs are JUDGMENT, registered before the run:
#     flow 5 + 5 (one shared direction bit, FAILED 2026-07-28 direction
#     test, 39 further sessions leaning the other way; at 10 it can never
#     cross +-35 alone, even at the 50-point coverage floor), analysts 5 + 3
#     (consensus LEVEL reads near-null at one month; target upside is a
#     contrarian price proxy, -0.68 with rs63).
# Any change needs a dated decisions-log amendment first.
VERDICT_WEIGHTS = {
    "trend": 21, "rs63": 21, "framework": 20, "analyst_rating": 5,
    "target_upside": 3, "flow_today": 5, "flow_persist": 5,
    "valuation": 20,
}

# The horizon a call is a read on: the backtests' primary forward window.
VERDICT_HORIZON_DAYS = 21

# Call thresholds and coverage/earnings gates. First pass, pre-registered,
# unvalidated.
VERDICT_BUY_MIN = 35
VERDICT_SELL_MAX = -35
VERDICT_MIN_WEIGHT = 50
VERDICT_MIN_INPUTS = 3
VERDICT_EARNINGS_GATE_DAYS = 3

# trend: same 50d/200d + dead zone the chart-page quick read already uses,
# so the two verdicts about the same fact can never disagree. First pass,
# pre-registered, unvalidated.
VERDICT_TREND_DEAD_ZONE = 0.003
VERDICT_SMA_SHORT = 50
VERDICT_SMA_LONG = 200

# rs63: relative strength over ~1 quarter of trading. First pass,
# pre-registered, unvalidated.
VERDICT_RS_SESSIONS = 63
VERDICT_RS_SPAN = 0.20

# framework: 5-metric tier -> signed value. First pass, pre-registered,
# unvalidated.
VERDICT_FRAMEWORK_TIER = {
    "BUY_5": 1.0, "BUY_4": 0.75, "ADD": 0.4, "HOLD": 0.0, "AVOID": -1.0,
}

# analyst_rating / target_upside: CENTERED ON THE DESK'S OWN CROSS-SECTION
# each cycle (2026-09-11, attempt #3 amendment) -- the median over pinned
# names with >= VERDICT_MIN_ANALYSTS analysts, so the two legs rank names
# against each other instead of against a fixed market snapshot. Under the
# fixed 2026-09-10 market-probe centers below (median recommendation_mark
# 1.43, median 12-month target upside +20%, 2,731 US stocks) the pair read
# +0.45 and +0.56 mean value on the live desk -- a +6-point push on every
# covered name -- with target upside pinned at +1.0 on 15 of 38 names. The
# probe centers stay as the FALLBACK when fewer than
# VERDICT_ANALYST_CENTER_MIN_NAMES names carry a reading. Spans unchanged.
VERDICT_MIN_ANALYSTS = 5
VERDICT_ANALYST_CENTER_MIN_NAMES = 8
VERDICT_REC_MARK_CENTER = 1.43      # fallback center (market probe 2026-09-10)
VERDICT_REC_MARK_SPAN = 0.45
VERDICT_TARGET_CENTER = 0.20        # fallback center (market probe 2026-09-10)
VERDICT_TARGET_SPAN = 0.30
ANALYST_FALLBACK_SOURCE = "market probe 2026-09-10"

# valuation. First pass, pre-registered, unvalidated. The prior-EPS floor
# (2026-09-11, attempt #3 amendment) is the Financials tab's own
# DERIVED_PEG_MIN_PRIOR_EPS rule: a PEG whose growth denominator is a
# prior-year EPS base under $0.05 is a near-zero-denominator artifact, not
# a valuation (BE's P/E 352 / PEG on a $0.0047 base, live 2026-08-22). The
# base is implied from the vendor's own P/E and PEG: eps_ttm = spot / pe,
# growth = pe / (100 * peg), prior = eps_ttm / (1 + growth).
VERDICT_PEG_CENTER = 1.5
VERDICT_PE_MAX = 150.0
VERDICT_PEG_MIN_PRIOR_EPS = 0.05

# Market regime (2026-09-11, attempt #3): SPY vs its own 200-session average,
# the SAME series construction trend_input uses (settled closes + the cycle
# spot). Published and printed as a dynamic disclosure. NO weight is
# conditioned on it: attempt #3 found momentum flips sign in bear markets
# on both universes (desk rs63 +0.045 bull / -0.042 bear, t 2.6; S&P
# -0.095 bear, t 3.2) but no regime-conditional weight set was
# distinguishable from flat equal (desk paired t 0.68), so the regime is
# disclosed, not acted on. A bear-regime gate is registered as an attempt #4
# candidate, never shipped on this data.
REGIME_BASIS = "SPY vs its 200-day average"

_MINUS = "−"   # U+2212 MINUS SIGN — every note printing a negative
                    # number uses this, never ASCII hyphen-minus.
_MIDDOT = "·"  # U+00B7 MIDDLE DOT — coverage-gate note separator.


def clamp(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _signed(x: float, decimals: int = 1) -> str:
    """Format a signed number with U+2212, guarding signed zero.

    r = round(x, decimals), using the same round-half-away-from-zero
    convention `_round_half_away_from_zero` uses for the composite score
    (so _signed(0.5, 0) prints "+1", not the "0" Python's banker's-rounding
    round() would give). eps is half the smallest unit this precision can
    print; any r whose magnitude falls under it — a real negative number
    that rounds to zero, e.g. _signed(-0.04, 1) — prints as unsigned zero,
    never "+0" and never a false "-0" (F1, 2026-09-11: the old version had
    no zero guard at all and printed "−0", "−0.0" and even "+-0.0").
    """
    factor = 10 ** decimals
    r = _round_half_away_from_zero(x * factor) / factor
    eps = 0.5 * 10 ** (-decimals)
    if abs(r) < eps:
        return f"{0.0:.{decimals}f}"
    if r < 0:
        return f"{_MINUS}{abs(r):.{decimals}f}"
    return f"+{r:.{decimals}f}"


def _round_half_away_from_zero(x: float) -> int:
    """int(round(x)), but half-way values always round AWAY from zero —
    Python's own round() is banker's rounding and would send -34.5 to -34
    (toward even), one point short of the SELL threshold. Pinned at exactly
    .5 by test_verdict.py."""
    if x >= 0:
        return int(math.floor(x + 0.5))
    return int(-math.floor(-x + 0.5))


# ── bars.json reader ────────────────────────────────────────────────────────

def closes_of(bars_payload: dict | None, ticker: str) -> list[float]:
    """Daily closing prices for `ticker`, oldest first, from a bars.json
    payload of any published shape:
      v1 -- bare close numbers: [86.85, 87.10, ...]
      v2 -- [open, high, low, close] quads
      v3/v4 -- [open, high, low, close, volume] quints (v4 adds sessions/
               bar_dates alongside, which this reader ignores)
    A row that is neither a number nor a list with a numeric index-3 close is
    skipped rather than raising, matching every other fail-soft reader in
    this codebase.
    """
    if not isinstance(bars_payload, dict):
        return []
    bars = bars_payload.get("bars")
    if not isinstance(bars, dict):
        return []
    rows = bars.get(ticker)
    if not isinstance(rows, list):
        return []
    out: list[float] = []
    for row in rows:
        if isinstance(row, (int, float)) and not isinstance(row, bool):
            out.append(float(row))
        elif isinstance(row, list) and len(row) >= 4:
            c = row[3]
            if isinstance(c, (int, float)) and not isinstance(c, bool):
                out.append(float(c))
    return out


def dates_of(bars_payload: dict | None, ticker: str, n_rows: int) -> list[str] | None:
    """The calendar date for each of `ticker`'s trailing `n_rows` closes
    (oldest first, same order and length `closes_of` would return for that
    row count), or None when the payload carries no calendar at all
    (bars.json v1-v3, no "sessions" key) -- the fallback signal rs63_input
    uses to go positional (F5, 2026-09-11).

    `bar_dates` overrides `sessions` for the handful of tickers whose own
    tail differs from the equity calendar (VIX, CRUDE, DXY carry their own
    date lists, one-to-one with their own bars). Every other ticker's rows
    line up with the tail of "sessions" -- many tickers (recent IPOs,
    younger leveraged ETFs) have FEWER rows than "sessions" has entries, so
    this slices to the trailing `n_rows` rather than assuming equal length.
    """
    if not isinstance(bars_payload, dict):
        return None
    bar_dates = bars_payload.get("bar_dates")
    if isinstance(bar_dates, dict) and ticker in bar_dates:
        d = bar_dates[ticker]
        return d if isinstance(d, list) else None
    sessions = bars_payload.get("sessions")
    if not isinstance(sessions, list):
        return None
    if n_rows <= 0:
        return []
    if n_rows > len(sessions):
        # More rows than the calendar has entries for -- this ticker's own
        # dates cannot be recovered by slicing "sessions" (F-2026-09-11: the
        # old code returned the full, too-short sessions list here, which is
        # LENGTH-MISALIGNED with the caller's `n_rows` closes). None signals
        # "no usable calendar", the same as bars.json carrying no "sessions"
        # key at all, so rs63_input takes its disclosed positional fallback
        # instead of pairing mismatched-length lists.
        return None
    return sessions[-n_rows:]


def load_bars_from_disk(out_dir) -> dict | None:
    """bars.json from OUT_DIR, fail-soft: missing file or bad JSON -> None,
    never raises. Used when this cycle did not rebuild bars.json itself (the
    daily-gated rebuild in fetcher/context.py), so the copy already on disk
    (the data-branch checkout) is what verdicts reads instead."""
    try:
        path = Path(out_dir) / "bars.json"
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


# ── per-input mappings: each returns (v, note) -- v in -1..+1 or None ───────

def _trailing_smas(series: list[float]) -> tuple[float, float]:
    """(SMA50, SMA200) over the trailing legs of `series`. Pure arithmetic,
    no null-handling: `series` must already be the caller's full window
    (trend_input's `closes + [spot]`) and at least VERDICT_SMA_LONG long."""
    sma50 = sum(series[-VERDICT_SMA_SHORT:]) / VERDICT_SMA_SHORT
    sma200 = sum(series[-VERDICT_SMA_LONG:]) / VERDICT_SMA_LONG
    return sma50, sma200


def trend_input(spot: float | None, closes: list[float]) -> tuple[float | None, str]:
    """Price vs its own 50-day and 200-day averages -- mirroring the page's
    own quick read under the chart bit for bit (index.html's seriesFull(),
    F4 2026-09-11 fix). bars.json's newest row is the PRIOR settled session
    (the daily build drops the in-progress bar); the page's seriesFull()
    appends the live/cycle price as the newest bar before averaging, so
    `series` here is exactly that: settled closes with the cycle spot
    appended as the newest bar. Averaging `closes` alone -- this function's
    behavior before the fix -- is one bar short of what the chart draws,
    and read a different trend word for the same name on the same day (QQQ,
    CLSK, XLF, 2026-09-11 review). 199 settled closes plus the spot now
    suffice; 200 settled closes did before the fix.
    """
    if spot is None or spot <= 0:
        return None, "no spot"
    series = closes + [spot]
    if len(series) < VERDICT_SMA_LONG:
        return None, "fewer than 200 sessions of history"
    sma50, sma200 = _trailing_smas(series)

    def leg(m: float) -> tuple[float, str]:
        r = spot / m - 1
        if abs(r) < VERDICT_TREND_DEAD_ZONE:
            return 0.0, "on"
        return (1.0, "above") if r > 0 else (-1.0, "below")

    v50, w50 = leg(sma50)
    v200, w200 = leg(sma200)
    v = 0.5 * v50 + 0.5 * v200
    note = f"{w50} 50d {_MIDDOT} {w200} 200d"
    return v, note


def rs63_input(ticker: str, closes: list[float], spy_closes: list[float],
                dates: list[str] | None, spy_dates: list[str] | None
                ) -> tuple[float | None, str]:
    """Relative strength over the last VERDICT_RS_SESSIONS (63) SPY sessions.

    Anchored on SPY's OWN calendar (F5, 2026-09-11 fix): the anchor date is
    the session VERDICT_RS_SESSIONS before SPY's newest, and the name's
    return is measured from ITS close on that same calendar date, found by
    date lookup in `dates` rather than by counting back `n` positions in
    `closes` -- positional indexing silently pairs mismatched calendars for
    any ticker whose own history has gaps or starts later than SPY's.
    `dates` / `spy_dates` come from `dates_of()`: bars.json v4's "bar_dates"
    override for a name whose tail differs from the equity calendar, else
    "sessions". Falls back to plain positional indexing, disclosed in the
    note, only when the payload carries no calendar at all (bars.json
    v1-v3 -- `dates_of` returns None then).

    The benchmark measured against itself is a tautology: SPY, or any
    ticker whose `closes` list literally IS the `spy_closes` list, reads
    null rather than a guaranteed +0pp.
    """
    if ticker == "SPY" or closes is spy_closes:
        return None, "benchmark"

    n = VERDICT_RS_SESSIONS + 1

    if dates is None or spy_dates is None:
        if len(closes) < n or len(spy_closes) < n:
            return None, "fewer than 64 daily closes"
        name_ret = closes[-1] / closes[-n] - 1
        spy_ret = spy_closes[-1] / spy_closes[-n] - 1
        diff = name_ret - spy_ret
        v = clamp(diff / VERDICT_RS_SPAN)
        note = (f"{_signed(diff * 100)}pp vs SPY, {VERDICT_RS_SESSIONS} sessions "
                "(positional; no calendar in bars)")
        return v, note

    if len(spy_dates) < n or len(spy_closes) < n or not closes or not dates:
        return None, "fewer than 64 daily closes"

    anchor_date = spy_dates[-n]

    # A name with fewer than 64 closes, or whose own history starts after
    # the anchor date, can never carry that date -- that is a SHORT HISTORY,
    # not a hole in an otherwise-long-enough history. Checking this before
    # the index lookup keeps the two failure modes from being conflated: a
    # bug fixed 2026-09-11 had RAM/SKHY/SKHX/STLL (all well under 64 rows)
    # raise ValueError out of dates.index() and print "calendar gap in the
    # 63-session window" -- true only for a name whose dates SPAN the
    # anchor but skip that one session.
    if len(closes) < n or dates[0] > anchor_date:
        return None, "fewer than 64 daily closes"

    try:
        name_idx = dates.index(anchor_date)
    except ValueError:
        return None, "calendar gap in the 63-session window"

    name_ret = closes[-1] / closes[name_idx] - 1
    spy_ret = spy_closes[-1] / spy_closes[-n] - 1
    diff = name_ret - spy_ret
    v = clamp(diff / VERDICT_RS_SPAN)
    note = f"{_signed(diff * 100)}pp vs SPY, {VERDICT_RS_SESSIONS} sessions"
    return v, note


def framework_input(facts_entry: dict | None) -> tuple[float | None, str]:
    f = facts_entry or {}
    fw = f.get("framework")
    verdict = fw.get("verdict") if isinstance(fw, dict) else None
    if not verdict:
        return None, "no framework score"
    if verdict == "BUILDING":
        return None, "building"
    if verdict == "NOT_APPLICABLE":
        return None, "fund"
    capped = verdict.endswith("_CAPPED")
    tier = verdict.replace("_BUILDING", "").replace("_CAPPED", "")
    v = VERDICT_FRAMEWORK_TIER.get(tier)
    if v is None:
        return None, "unrecognized framework verdict"
    # F2 (2026-09-11 fix): the note is the rendered TIER, never the raw
    # enum -- CLAUDE.md's framework rule is "a tier carries no '(building)'
    # suffix at render; '(capped)' does print". This is the one function
    # every surface reads the note from, so the Overview strip and the
    # framework panel can no longer print two different words for the same
    # fact ("ADD_BUILDING" one block above the panel's own plain "ADD").
    note = tier + (" (capped)" if capped else "")
    return v, note


def _covered(f: dict) -> bool:
    rt = f.get("rec_total")
    return isinstance(rt, (int, float)) and not isinstance(rt, bool) and rt >= VERDICT_MIN_ANALYSTS


def _median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else 0.5 * (s[mid - 1] + s[mid])


def analyst_centers(facts: dict | None, spot_of) -> dict:
    """The cycle's own analyst centers: median recommendation mark and median
    target upside over pinned names with >= VERDICT_MIN_ANALYSTS analysts.
    `spot_of(ticker)` returns the cycle spot or None. Falls back to the
    2026-09-10 market-probe constants, and says so, when fewer than
    VERDICT_ANALYST_CENTER_MIN_NAMES names carry the reading."""
    marks: list[float] = []
    ups: list[float] = []
    for ticker, f in (facts or {}).items():
        if not isinstance(f, dict) or not _covered(f):
            continue
        rm = f.get("rec_mark")
        if isinstance(rm, (int, float)) and not isinstance(rm, bool):
            marks.append(float(rm))
        tg = f.get("target")
        sp = spot_of(ticker)
        if (isinstance(tg, (int, float)) and not isinstance(tg, bool) and tg > 0
                and isinstance(sp, (int, float)) and not isinstance(sp, bool) and sp > 0):
            ups.append(float(tg) / float(sp) - 1.0)
    out = {"rec_mark": VERDICT_REC_MARK_CENTER, "target_upside": VERDICT_TARGET_CENTER,
           "n_rec_mark": len(marks), "n_target_upside": len(ups),
           "source": ANALYST_FALLBACK_SOURCE}
    if len(marks) >= VERDICT_ANALYST_CENTER_MIN_NAMES:
        out["rec_mark"] = round(_median(marks), 4)
        out["source"] = "desk"
    if len(ups) >= VERDICT_ANALYST_CENTER_MIN_NAMES:
        out["target_upside"] = round(_median(ups), 4)
        out["source"] = "desk" if len(marks) >= VERDICT_ANALYST_CENTER_MIN_NAMES else "mixed"
    return out


def analyst_rating_input(facts_entry: dict | None, center: float | None = None
                          ) -> tuple[float | None, str]:
    """`center` is the cycle's desk median mark (analyst_centers); None means
    the fixed fallback center."""
    f = facts_entry or {}
    rm = f.get("rec_mark")
    rt = f.get("rec_total")
    if rm is None:
        return None, "no analyst rating"
    if rt is None or rt < VERDICT_MIN_ANALYSTS:
        return None, "fewer than 5 analysts"
    c = VERDICT_REC_MARK_CENTER if center is None else center
    v = clamp((c - rm) / VERDICT_REC_MARK_SPAN)
    note = f"{rm:.2f} of 3 {_MIDDOT} {int(rt)} analysts"
    return v, note


def target_upside_input(facts_entry: dict | None, spot: float | None,
                        center: float | None = None) -> tuple[float | None, str]:
    """`center` is the cycle's desk median target upside (analyst_centers);
    None means the fixed fallback center."""
    f = facts_entry or {}
    target = f.get("target")
    rt = f.get("rec_total")
    if target is None or spot is None or spot <= 0:
        return None, "no price target"
    if rt is None or rt < VERDICT_MIN_ANALYSTS:
        return None, "fewer than 5 analysts"
    upside = target / spot - 1
    c = VERDICT_TARGET_CENTER if center is None else center
    v = clamp((upside - c) / VERDICT_TARGET_SPAN)
    note = f"{_signed(upside * 100, 0)}% to the average target"
    return v, note


def _flow_input(card: dict | None, board_name: str, no_card_note: str) -> tuple[float | None, str]:
    if not card:
        return None, no_card_note
    direction = card.get("direction")
    score = card.get("score")
    if direction not in ("BULL", "BEAR") or score is None:
        return None, no_card_note
    # build_snapshot reads `net_flow >= 0` as BULL, so a chain with exactly
    # zero net premium would lend its whole score to the bull side. A zero
    # is no direction (2026-09-11 review). A missing net_flow key (older
    # cards, trimmed fixtures) is not a zero and passes through.
    nf = card.get("net_flow")
    if isinstance(nf, (int, float)) and not isinstance(nf, bool) and nf == 0:
        return None, "no net flow"
    sign = 1.0 if direction == "BULL" else -1.0
    v = clamp(sign * score / 100.0)
    note = f"{direction} {int(score)} on {board_name}"
    return v, note


def flow_today_input(conv_card: dict | None) -> tuple[float | None, str]:
    return _flow_input(conv_card, "Conviction", "no conviction card")


def flow_persist_input(swing_card: dict | None) -> tuple[float | None, str]:
    return _flow_input(swing_card, "Swing", "no swing card")


def implied_prior_eps(spot: float | None, pe: float, peg: float) -> float | None:
    """The prior-year TTM EPS base the vendor's PEG rests on, implied from its
    own P/E and PEG: eps_ttm = spot / pe; growth = pe / (100 * peg); prior =
    eps_ttm / (1 + growth). None when there is no spot to anchor it."""
    if spot is None or spot <= 0 or pe <= 0 or peg <= 0:
        return None
    eps_ttm = spot / pe
    growth = pe / (100.0 * peg)
    return eps_ttm / (1.0 + growth)


def valuation_input(facts_entry: dict | None, spot: float | None = None) -> tuple[float | None, str]:
    """F3 (2026-09-11 fix): each null branch names the fact it actually is,
    not a guessed cause. A null PEG with a healthy positive P/E (CRWD pe
    5850, SNDK 23, MRVL 75 and seven more the day this was found) used to
    print "no PEG (loss-making)" -- a real vendor gap misdiagnosed as an
    unprofitable company. A missing `pe` printed the unrelated "P/E out of
    range". Seven distinct facts now get seven distinct sentences; the
    seventh (2026-09-11, attempt #3 amendment) is the prior-EPS floor the
    Financials tab already applies to the same vendor PEG."""
    f = facts_entry or {}
    if f.get("sec_type") == "fund":
        return None, "fund"
    peg = f.get("peg")
    if peg is None:
        return None, "no PEG reading"
    if peg <= 0:
        return None, f"PEG {_signed(peg, 2)}"
    pe = f.get("pe")
    if pe is None:
        return None, "no P/E reading"
    if pe <= 0:
        return None, f"P/E {_signed(pe, 1)}"
    if pe > VERDICT_PE_MAX:
        return None, f"P/E {pe:.0f}, above {VERDICT_PE_MAX:.0f}"
    prior = implied_prior_eps(spot, pe, peg)
    if prior is not None and prior < VERDICT_PEG_MIN_PRIOR_EPS:
        return None, f"PEG {peg:.2f} on a ${prior:.3f} prior-year EPS base"
    v = clamp((VERDICT_PEG_CENTER - peg) / VERDICT_PEG_CENTER)
    note = f"PEG {peg:.2f}"
    return v, note


def compute_regime(spy_closes: list[float], spy_spot: float | None) -> dict:
    """The market regime this cycle, from SPY's settled closes plus its cycle
    spot (the same `closes + [spot]` series trend_input reads): `bear` when
    SPY sits below its own 200-session average, `bull` otherwise, null with
    the reason when it cannot be read. `spy_vs_200d` is the signed distance
    (spot / SMA200 - 1). Disclosure only; no weight reads it."""
    if spy_spot is None or spy_spot <= 0:
        return {"name": None, "spy_vs_200d": None, "basis": REGIME_BASIS, "note": "no SPY spot"}
    series = list(spy_closes) + [float(spy_spot)]
    if len(series) < VERDICT_SMA_LONG:
        return {"name": None, "spy_vs_200d": None, "basis": REGIME_BASIS,
                "note": "fewer than 200 SPY sessions of history"}
    sma200 = sum(series[-VERDICT_SMA_LONG:]) / VERDICT_SMA_LONG
    dist = float(spy_spot) / sma200 - 1.0
    name = "bear" if dist < 0 else "bull"
    return {"name": name, "spy_vs_200d": round(dist, 4), "basis": REGIME_BASIS,
            "note": f"SPY {_signed(dist * 100)}% vs its 200-day"}


# ── per-ticker and whole-payload assembly ───────────────────────────────────

def compute_verdict(ticker: str, *, spot: float | None, closes: list[float],
                     spy_closes: list[float], facts_entry: dict | None,
                     conv_card: dict | None, swing_card: dict | None,
                     brief: dict | None = None, dates: list[str] | None = None,
                     spy_dates: list[str] | None = None,
                     centers: dict | None = None) -> dict:
    """`brief` is accepted for call-site compatibility and unused: the brief
    score left the composite 2026-09-11. `centers` is analyst_centers()'s
    dict for this cycle; None means the fixed fallback centers."""
    c = centers or {}
    raw = {
        "trend": trend_input(spot, closes),
        "rs63": rs63_input(ticker, closes, spy_closes, dates, spy_dates),
        "framework": framework_input(facts_entry),
        "analyst_rating": analyst_rating_input(facts_entry, c.get("rec_mark")),
        "target_upside": target_upside_input(facts_entry, spot, c.get("target_upside")),
        "flow_today": flow_today_input(conv_card),
        "flow_persist": flow_persist_input(swing_card),
        "valuation": valuation_input(facts_entry, spot),
    }

    inputs_out: dict[str, dict] = {}
    weight = 0
    wsum = 0.0
    n = 0
    for key in VERDICT_INPUT_ORDER:
        v, note = raw[key]
        inputs_out[key] = {"v": v, "note": note}
        if v is not None:
            weight += VERDICT_WEIGHTS[key]
            wsum += VERDICT_WEIGHTS[key] * v
            n += 1

    n_total = len(VERDICT_INPUT_ORDER)

    if weight >= VERDICT_MIN_WEIGHT and n >= VERDICT_MIN_INPUTS:
        score = _round_half_away_from_zero(100.0 * wsum / weight)
        if score >= VERDICT_BUY_MIN:
            call = "BUY"
        elif score <= VERDICT_SELL_MAX:
            call = "SELL"
        else:
            call = "HOLD"
        note = None
    else:
        score = None
        call = None
        note = f"{n} of {n_total} inputs {_MIDDOT} weight {weight} of 100"

    earn_days = (facts_entry or {}).get("earn_days")
    if (call in ("BUY", "SELL")
            and isinstance(earn_days, (int, float))
            and not isinstance(earn_days, bool)
            and 0 <= earn_days <= VERDICT_EARNINGS_GATE_DAYS):
        call = "HOLD"
        note = f"earnings in {int(earn_days)}d"

    return {
        "score": score,
        "call": call,
        "note": note,
        "n": n,
        "n_total": n_total,
        "weight": weight,
        "inputs": inputs_out,
    }


def compute_verdicts(conviction_cards, swing_cards, facts: dict | None,
                      spot_by_ticker: dict | None, quotes: dict | None,
                      bars_payload: dict | None, brief: dict | None) -> dict | None:
    """The whole `verdicts` payload block, or None when `facts` is empty/None
    (nothing to compute a verdict about -- the caller omits the key
    entirely, per the optional-key convention)."""
    if not facts:
        return None

    conv_by_ticker = {c["ticker"]: c for c in (conviction_cards or [])}
    swing_by_ticker = {c["ticker"]: c for c in (swing_cards or [])}
    spy_closes = closes_of(bars_payload, "SPY")
    spy_dates = dates_of(bars_payload, "SPY", len(spy_closes))

    def spot_of(ticker: str) -> float | None:
        sp = (spot_by_ticker or {}).get(ticker)
        if isinstance(sp, (int, float)) and not isinstance(sp, bool) and sp > 0:
            return float(sp)
        qc = ((quotes or {}).get(ticker) or {}).get("close")
        if isinstance(qc, (int, float)) and not isinstance(qc, bool) and qc > 0:
            return float(qc)
        return None

    centers = analyst_centers(facts, spot_of)
    regime = compute_regime(spy_closes, spot_of("SPY"))

    by_ticker: dict[str, dict] = {}
    counts = {"buy": 0, "sell": 0, "hold": 0, "none": 0}
    n_total = len(VERDICT_INPUT_ORDER)
    failed = 0

    for ticker in sorted(facts.keys()):
        facts_entry = facts.get(ticker) or {}
        spot = spot_of(ticker)
        closes = closes_of(bars_payload, ticker)
        dates = dates_of(bars_payload, ticker, len(closes))

        # One name's bad data must never take the whole block down: the
        # caller wraps compute_verdicts in a single try (build_snapshot), so
        # an exception here used to drop every verdict (2026-09-11 review).
        # The failed name publishes a null entry naming the failure class.
        try:
            entry = compute_verdict(
                ticker, spot=spot, closes=closes, spy_closes=spy_closes,
                dates=dates, spy_dates=spy_dates,
                facts_entry=facts_entry, conv_card=conv_by_ticker.get(ticker),
                swing_card=swing_by_ticker.get(ticker), brief=brief, centers=centers,
            )
        except Exception as e:  # noqa: BLE001 -- fail-soft per name, by design
            failed += 1
            entry = {
                "score": None, "call": None,
                "note": f"not computed ({type(e).__name__})",
                "n": 0, "n_total": n_total, "weight": 0,
                "inputs": {k: {"v": None, "note": "not computed"} for k in VERDICT_INPUT_ORDER},
            }
        by_ticker[ticker] = entry

        call = entry["call"]
        if call == "BUY":
            counts["buy"] += 1
        elif call == "SELL":
            counts["sell"] += 1
        elif call == "HOLD":
            counts["hold"] += 1
        else:
            counts["none"] += 1

    return {
        "v": 2,   # 2026-09-11: eight inputs (market removed), regime,
                  # analyst_centers, horizon_days, failed
        "thresholds": {"buy": VERDICT_BUY_MIN, "sell": VERDICT_SELL_MAX},
        "min_weight": VERDICT_MIN_WEIGHT,
        "min_inputs": VERDICT_MIN_INPUTS,
        "earnings_gate_days": VERDICT_EARNINGS_GATE_DAYS,
        "horizon_days": VERDICT_HORIZON_DAYS,
        "order": list(VERDICT_INPUT_ORDER),
        "weights": dict(VERDICT_WEIGHTS),
        # the regime this cycle (disclosure; no weight reads it) and the
        # analyst centers the two analyst legs were measured against
        "regime": regime,
        "analyst_centers": centers,
        "failed": failed,
        # F10 (2026-09-11): the vintage of bars.json this cycle's trend/rs63
        # legs were computed from -- null when bars_payload wasn't a dict at
        # all (load_bars_from_disk found nothing), string otherwise.
        "bars_built": bars_payload.get("built") if isinstance(bars_payload, dict) else None,
        "counts": counts,
        "by_ticker": by_ticker,
    }
