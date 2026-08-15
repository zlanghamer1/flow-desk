"""Flow Desk — one options-flow snapshot build cycle.

Free-data only, Python stdlib only (urllib/json/datetime/zoneinfo/math/os).
Every fetched field is type-checked before use; every step is fail-soft —
one bad name (a CBOE 404, a malformed TV row) is skipped and logged, it
never aborts the run. See /home/user/flow-desk/DATA_CONTRACT.md for the
authoritative output schema this module must produce.

────────────────────────────────────────────────────────────────────────────
PIPELINE (letters match the build spec)
────────────────────────────────────────────────────────────────────────────
(a) NO market-wide screen (dropped 2026-07-17 — it dumped dozens of
    correlated movers onto the boards on rotation days). The universe is a
    FIXED, curated list: PINNED = WATCHLIST (Zach's canonical picks + the
    semiconductor/memory names off his TradingView watchlist) + the 11 SPDR
    sector-index ETFs. See the PINNED definition below.
(b) Resolve every pinned name to a live TV quote via a SELF-HEALING exchange
    probe (try NASDAQ:, then NYSE:, then AMEX:, then CBOE: batch quote calls)
    rather than a hand-maintained ticker->exchange dict — a live check found
    COHR on NYSE (not NASDAQ) and the memory/semi ETFs DRAM/RAM on Cboe
    BZX, so trusting one static dict would silently drop pinned names.
(c) No pre-score cut — every resolved pinned name gets a CBOE chain pulled,
    in PINNED order (the point of the curated list is to show Zach's names).
(d) Fetch CBOE delayed chain per candidate (0.3s sleep, skip HTTP errors of
    any kind fail-soft — 403/404 both observed live for bad/optionless
    symbols). Parse OCC symbols (root+YYMMDD+C/P+strike*1000, 15 fixed-width
    chars from the end) into two DTE buckets:
      0-7 DTE  -> net_flow, cp_ratio, aggregate vol/OI, popular_contract,
                  conviction score (see WEIGHTS_CONVICTION below).
      14-183d  -> cp_skew, suggested_contract (0.30<=|delta|<=0.60, highest
                  premium), entry/stop/target/rr, earnings-in-window.
(e) Swing metrics pulled from history.json: persist (n/5 same-direction
    sessions), flow_5d, oi_build, trend (spot vs SMA20/SMA50), iv_rank
    (percentile once >=20 iv30 sessions collected).
(f) Swing score (see WEIGHTS_SWING below).
(g) Board membership: conviction = usable 0-7DTE bucket, score desc.
    swing = usable suggested_contract, swing-score desc. BOARD_CAP (50) is
    above the pinned-universe size so no curated name is truncated.
(h) Alert memory: first_board_conviction/first_board_swing {time, spot} set
    once per ticker per day, read back from history.json.
(i) Header stats across the union of both boards, deduped by ticker.
(j) Write data.json + history.json (60 sessions / 60 iv values kept, older
    pruned).

────────────────────────────────────────────────────────────────────────────
FORCED OFF-HOURS CYCLES (added 2026-07-18)
────────────────────────────────────────────────────────────────────────────
When market_state == "closed" (weekend, or outside the 08:00-15:20 CT halo)
the cycle STILL writes data.json so a forced test refreshes the live site,
but it does NOT mutate history.json: no today_sessions row, no iv_history
append, no first_board stamping, no save_history. This keeps forced off-hours
tests from polluting the day-over-day memory. (A Saturday 2026-07-18 session
row already exists on the data branch from a forced test taken before this
guard — do NOT try to repair the data branch as part of this change.)

────────────────────────────────────────────────────────────────────────────
CONVICTION SCORE (0-100 int) — weights sum to 100
────────────────────────────────────────────────────────────────────────────
  RVOL              25 pts  min(rvol / 3.0, 1.0) * 25            (3x rvol caps)
  Momentum          20 pts  min(|change_pct| / 5.0, 1.0) * 15
                            + 5 bonus if sign(change_pct) == sign(change_from_open)
                              (move is continuing through the day, not fading)
  Flow magnitude    25 pts  min(log10(|net_flow|+1) / 7.0, 1.0) * 20
                              (7 decades ~= $10M 0-7DTE premium caps the scale)
                            + 5 bonus if sign(net_flow) == sign(change_pct)
                              (options flow agrees with the stock's own move)
  C/P extremity     15 pts  min(|ln(cp_ratio)| / 2.0, 1.0) * 15
                              (symmetric around cp_ratio==1.0; 0 if no put vol)
  Vol/OI (0-7DTE)   10 pts  min((sum_vol/sum_oi) / 3.0, 1.0) * 10
  Contract concen.   5 pts  min(popular_contract premium / total 0-7 premium, 1.0) * 5

firing = score >= 80 OR net_flow accelerated vs the prior cycle: a name's
previous cycle's net_flow is cached in fetcher/.prev_cycle.json (fail-soft,
absent on first run); acceleration = same-sign net_flow with
|net_flow| >= |prev| * ACCEL_MULT (1.5x).

────────────────────────────────────────────────────────────────────────────
AGGRESSOR TILT (added 2026-07-18, Zach-approved; see vault
market-data/flow-desk/DIRECTIONAL_FLOW_DECISION.md)
────────────────────────────────────────────────────────────────────────────
Free chains can't see buy vs sell side, but each snapshot carries bid/ask/last
per contract. Between cycles we take each contract's VOLUME DELTA (cumulative
volume now minus previous cycle, same session only — volume resets overnight,
a negative delta means new session and is skipped) and classify the contract's
last trade against the current quote:
  pos = (last - bid) / (ask - bid), requiring ask > bid >= 0 and last > 0
  pos >= 0.60 -> traded at/near ask  (aggressive BUY)
  pos <= 0.40 -> traded at/near bid  (aggressive SELL)
  else        -> mid/unclassifiable  (excluded)
Premium of the delta (dv * last * 100) is bucketed:
  bullish = calls bought + puts sold;  bearish = calls sold + puts bought
and ACCUMULATED PER NAME PER DAY in history.json (tilt_bull_prem /
tilt_bear_prem on today's row — survives workflow re-dispatch). Per-contract
volume baselines live in .prev_cycle.json (job-local; after a restart the
first cycle just contributes nothing — fail-soft undercount, never a wrong
count). tilt = (bull - bear) / (bull + bear), -1..+1, null until anything
classifies. HONEST LIMIT (tooltipped in the UI): this samples only each
contract's LAST trade once per ~7-min cycle — a sampled proxy of aggressor
direction, not the full tape.
Scoring: conviction score gets a bounded post-adjustment, +5 if the tilt
agrees with the card's direction (|tilt| >= 0.30 and classified premium >=
$100k), -5 if it opposes at the same thresholds; clamped 0-100.

────────────────────────────────────────────────────────────────────────────
OI-CONFIRM (added 2026-07-18, same approval)
────────────────────────────────────────────────────────────────────────────
Did yesterday's flow OPEN new positions or just churn/close? Compare today's
open interest against yesterday's, normalized by yesterday's volume, on the
SWING bucket (14-183d — the 0-7DTE bucket is polluted by weekly expirations),
on the side (calls/puts) of YESTERDAY'S direction:
  frac = (oi_today_side - oi_yesterday_side) / yesterday_vol_side
  frac >= +0.25 -> "OPENING"   (yesterday's volume became held positions)
  frac <= -0.25 -> "CLOSING"   (positions unwound into the flow)
  else          -> "CHURN"     (day-traded / rolled)
  null when <2 sessions of side data or yesterday's side volume < 500
Scoring: swing score post-adjustment +5 OPENING / -10 CLOSING, applied ONLY
when yesterday's direction matches today's (a confirm of the opposite side
says nothing about today's thesis); clamped 0-100.

────────────────────────────────────────────────────────────────────────────
SEMI ETF FLOWS CONTEXT CARD (added 2026-07-19)
────────────────────────────────────────────────────────────────────────────
Who's moving actual fund money in semis — the closest free proxy to
household/mutual-fund positioning. One TV batch scan per cycle pulls
shares_outstanding / nav / aum / fund_flows.1M for ETF_FLOW_FUNDS
(SMH, SOXX, SOXL, SOXS, DRAM). Daily flow = ΔSO between sessions x NAV
(ETFs create/destroy shares as money enters/leaves the wrapper). SO
snapshots live in history.json under "etf_so" (60 sessions kept, never
written on closed days — same phantom-weekend rule as the rest of history).
CONTEXT ONLY: rendered as a header card, never touches any score. SOXX is
fetched for this card alone and stays out of the PINNED options universe.

────────────────────────────────────────────────────────────────────────────
SWING SCORE (0-100 int) — weights sum to 100, persist dominates
────────────────────────────────────────────────────────────────────────────
  Persist           35 pts  persist / persist_max * 35   (heaviest — a flow
                              that repeats session after session is the
                              highest-conviction swing signal free data can
                              offer; single-day flow is noisy)
  Flow_5d magnitude 20 pts  min(log10(|flow_5d|+1) / 7.5, 1.0) * 20
  OI build          15 pts  min(oi_build / 20000, 1.0) * 15 if oi_build > 0
                              else 0 (only reward OI actually building; a
                              shrinking or unknown OI trend earns nothing)
  Trend alignment   15 pts  15 if trend matches direction (UP+BULL/DOWN+BEAR)
                            7  if trend == MIXED
                            0  if trend opposes direction
  IV rank           10 pts  10 * (1 - iv_rank/100) once available;
                              5 (neutral) while iv_collecting
                              (INVERTED: cheap vol scores higher — when you
                              buy weeks of premium, low IV rank is the edge)
  C/P skew          5 pts   min(|ln(cp_skew)| / 2.0, 1.0) * 5

All fields are documented in DATA_CONTRACT.md; this module must match it.
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import context  # sibling module: vault brief/catalysts/news/facts + bars.json

TZ_CT = ZoneInfo("America/Chicago")

ROOT = Path(__file__).resolve().parent            # flow-desk/fetcher/
DEFAULT_OUT_DIR = ROOT.parent / "data"

PREV_CYCLE_FILE = ROOT / ".prev_cycle.json"

UA = "Mozilla/5.0 (flow-desk)"
TIMEOUT = 20
CBOE_SLEEP_SEC = 0.3

TV_SCAN_URL = "https://scanner.tradingview.com/america/scan"
CBOE_URL = "https://cdn.cboe.com/api/global/delayed_quotes/options/{sym}.json"

# Curated universe (see PINNED below) — every pinned name that has a usable
# CBOE chain becomes a candidate; the board cap is set high enough that no
# curated name is ever truncated off a board.
BOARD_CAP = 50
MAX_HISTORY_SESSIONS = 60
MAX_IV_HISTORY = 60

ACCEL_MULT = 1.5             # net_flow acceleration threshold for "firing"
MONEYNESS_BAND = 0.20        # +/-20% of spot for 0-7DTE popular_contract
SWING_DELTA_LO, SWING_DELTA_HI = 0.30, 0.60
DTE_SHORT_LO, DTE_SHORT_HI = 0, 7
DTE_SWING_LO, DTE_SWING_HI = 14, 183

STOP_MULT = 0.70
TARGET_MULT = 2.05
FIXED_RR = 3.5

# Aggressor tilt (see header): classification band + score-adjust thresholds.
TILT_BUY_POS = 0.60          # (last-bid)/(ask-bid) >= this -> aggressive buy
TILT_SELL_POS = 0.40         # <= this -> aggressive sell
TILT_MIN_ABS = 0.30          # |tilt| needed before it can move the score
TILT_MIN_PREM = 100_000.0    # classified $ premium needed before it can move the score
TILT_SCORE_ADJ = 5           # +/- points on the conviction score

# OI-confirm (see header): swing-bucket open-vs-close thresholds.
OI_CONFIRM_FRAC = 0.25       # |OI delta| / yesterday volume beyond this = OPENING/CLOSING
OI_CONFIRM_MIN_VOL = 500     # yesterday side volume below this -> null (can't judge)
OI_CONFIRM_OPEN_ADJ = 5      # swing score bonus on OPENING (directions matching)
OI_CONFIRM_CLOSE_ADJ = -10   # swing score penalty on CLOSING (directions matching)

# ── Biggest-orders board (added 2026-07-31) ─────────────────────────────────
# A cross-ticker leaderboard of the single options contracts with the most
# DOLLARS traded today, the way commercial "big flow" feeds present one.
#
# WHAT IT IS NOT: a single order. Those feeds rank individual blocks/sweeps off
# a trade-level tape, which is paid. The free CBOE feed publishes per-contract
# session aggregates, so a row here is one contract's WHOLE DAY (volume x last
# x 100) — the closest honest thing free data supports. Never label it as an
# order, and never present a row as evidence of who initiated: premium changing
# hands has no buy/sell side on this data (same caveat as net_flow).
#
# NEAR-MONEY ONLY, for exactly the reason FLOW % is (see analyze_ticker):
# premium is intrinsic + extrinsic, so a deep-ITM strike costs nearly what it
# is already worth. A handful of those carry enormous dollars while betting on
# nothing and would permanently own the top of the board — unfiltered, seven
# ~35%-ITM strikes were 79% of LLY's call premium on 2026-07-27. Don't widen
# MONEYNESS_BAND here to "show more names".
BIG_ORDERS_CAP = 12             # rows published, and the per-ticker shortlist size.
                                # Equal on purpose: a ticker can supply at most
                                # CAP rows to a CAP-row board, so shortlisting
                                # per ticker cannot change the ranking the cap
                                # below is applied to.
# Rows one ticker may occupy (Zach's call, 2026-07-31, after the first live
# cycle put 0-DTE QQQ calls in 5 of 12 rows at adjacent strikes — $683/$684/
# $685/$686/$687, same expiry). That ranking was honest but it crowded five
# other names off the board to say one thing five times.
#
# THE CAP IS DISCLOSED, NEVER SILENT — this is the whole condition he attached
# to it, and it is also the house rule (see the flows-accuracy work: a bounded
# board that doesn't say what it dropped reads as "covered everything"). The
# builder publishes big_orders_capped alongside the board: for each ticker, how
# many of the top BIG_ORDERS_CAP rows by dollars it actually earned versus how
# many are shown. The site renders that as a line under the board, so "QQQ owned
# 5 of the top 12" stays visible even though only 3 rows do.
BIG_ORDERS_PER_TICKER = 3       # one number to retune; 3 matches the reference
                                # format (its NVDA appeared 3 times)
BIG_ORDERS_MIN_PREMIUM = 100_000.0   # $ floor; a quiet session publishes a short
                                     # board rather than padding it with noise
BIG_ORDERS_DTE_HI = 183         # 0..183 inclusive — the UNION of the two scoring
                                # buckets (0-7 and 14-183), so this board does not
                                # inherit their 8-13 day blind spot
MAX_BIG_ORDERS_SESSIONS = 60    # history cap, same horizon as sessions/iv_history

# ── Semi ETF share-flow context card (added 2026-07-19) ─────────────────────
# Daily fund flows estimated from day-over-day shares-outstanding deltas:
# ETFs create/destroy shares as money enters/leaves, so ΔSO x NAV ≈ net $
# flow into the fund wrapper. TV's scanner exposes shares_outstanding, nav,
# aum and a ready-made trailing fund_flows.1M for ETFs, all key-free
# (verified live 2026-07-19 for all five funds below). This is a CONTEXT
# signal only — it never touches the conviction/swing scores.
# SOXX is fetched for this card only; it is NOT part of the PINNED options
# universe (the card tracks the biggest semi ETF even though Zach's options
# watchlist uses SMH/SOXL/SOXS).
ETF_FLOW_FUNDS = ["SMH", "SOXX", "SOXL", "SOXS", "DRAM"]
ETF_FLOW_COLUMNS = ["name", "shares_outstanding", "nav", "aum", "fund_flows.1M"]
MAX_ETF_SO_SESSIONS = 60     # history cap, same horizon as sessions/iv_history


# ── Curated universe (Zach's ruling 2026-07-17) ────────────────────────────
# Flow Desk no longer screens the whole market for movers — that dumped dozens
# of correlated names onto the boards on any rotation day. The universe is now
# a fixed, deliberate watch: Zach's watchlist (his canonical picks + the
# semiconductor/memory names off his TradingView watchlist) plus the 11 SPDR
# sector-index ETFs. Every name below was verified to have a usable US CBOE
# options chain on 2026-07-17; TV symbol/exchange still self-heals via
# _resolve_core_tv() (NASDAQ -> NYSE -> AMEX -> CBOE).
#
# Deliberately NOT included (verified 2026-07-17, don't silently re-add):
#   BESIY / IFNNY  — foreign ADRs (BE Semi, Infineon), no US CBOE chain (403)
#   NRGU           — 3x oil ETN, no listed options (403)
#   WTI            — CBOE root resolves to W&T Offshore (micro-cap oil E&P),
#                    NOT crude oil; almost certainly not the intended line
#   SPX / VIX      — index roots, not the equity/ETF chain this pipeline reads
#   SPMO           — broad-market momentum ETF, left off to keep the board lean
#   (QQQ was added back 2026-07-17 at Zach's request — it's below.)
WATCHLIST = [
    # Zach's canonical picks (vault, 2026-06-10)
    "MU", "CRWD", "COHR", "LLY", "V", "XOM",
    # Photonics subset plays alongside COHR (Zach's call, 2026-08-08). Both
    # verified to have usable CBOE chains that day: AXTI 1,540 contracts /
    # 65,320 volume; TSEM 1,598 contracts / 7,696 volume.
    "AXTI",                       # AXT — indium phosphide substrates
    "TSEM",                       # Tower Semiconductor — SiPh foundry
    # Semiconductor / memory cluster off his TradingView watchlist
    "SMH", "SOXL", "SOXS",        # semi ETFs (broad + 3x bull/bear)
    "MUU",                        # Direxion 2x Long MU
    # SK Hynix: the sponsored ADR, NOT the 2x ETF. Swapped 2026-07-25 —
    # SKHX (Leverage Shares 2x Long SK Hynix) carried 352 contracts / 195
    # total volume on the Cboe chain versus SKHY's 2,600 / 167k, so the
    # leveraged wrapper was scoring noise while the liquid SK Hynix options
    # venue sat off the board.
    "SKHY",                       # SK hynix Inc. sponsored ADR (NASDAQ)
    "SNDK",                       # Sandisk
    "DRAM",                       # Roundhill Memory ETF
    "RAM",                        # Roundhill T-REX 2x Long DRAM ETF
    "AVGO", "NVDA", "MRVL", "LITE", "CAMT", "ONTO",  # semis / semi-cap
    "GOOGL", "MSFT",              # megacap AI-demand names off his list
    # Added 2026-07-31 (Zach's call) so the biggest-orders board covers the
    # names that actually dominate the mega-cap options tape. AMZN and MSFT
    # calls owned the top of that leaderboard on the day it was built, and
    # neither AMZN nor META nor AMD was on the desk at all. AAPL / TSLA / NFLX
    # were considered in the same conversation and deliberately left off — he
    # picked these three.
    "AMZN", "META", "AMD",
    "CVX",                        # Chevron ("CHEV" on his TradingView list)
    "QQQ",                        # Nasdaq-100 (broad index, Zach's add 2026-07-17)
]

# 11 SPDR sector-index ETFs ("sector indexes like xle, xlc, xlp etc.")
SECTOR_ETFS = [
    "XLE", "XLC", "XLP", "XLF", "XLK",
    "XLV", "XLI", "XLY", "XLB", "XLU", "XLRE",
]

# The full pinned universe — deduped, order-preserving.
PINNED = list(dict.fromkeys(WATCHLIST + SECTOR_ETFS))

TV_COLUMNS = [
    "name", "close", "change", "change_from_open",
    "relative_volume_10d_calc", "market_cap_basic", "SMA20", "SMA50",
    "earnings_release_next_date",
    # Context-layer facts (added 2026-08, see fetcher/context.py /
    # DATA_CONTRACT.md's `facts`) — all five verified live to resolve for the
    # whole pinned universe. Short interest was ALSO probed live (
    # short_percent_float / short_interest_percent / short_interest /
    # shares_short / short_percent_of_float / shares_short_prior_month /
    # days_to_cover_short) and every candidate came back null for every
    # ticker — the free scanner does not carry it at all, so facts.short_pct
    # stays permanently None rather than adding a column here for it.
    "price_52_week_high", "price_52_week_low", "beta_1_year",
    "average_volume_10d_calc", "RSI",
]
# index positions into the "d" row, named for readability
_COL = {name: i for i, name in enumerate(TV_COLUMNS)}


class DataError(Exception):
    pass


def log(msg: str) -> None:
    print(f"[build_snapshot] {msg}")


# ── HTTP helpers ─────────────────────────────────────────────────────────────

def _post_json(url: str, body: dict) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "text/plain", "User-Agent": UA},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read())


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read())


def _is_clean_ticker(sym: str) -> bool:
    """Symbol hygiene: skip preferred shares / warrants / units."""
    return isinstance(sym, str) and sym and not any(c in sym for c in "/.-")


def _row_to_quote(sym_field: str, d: list) -> dict | None:
    """Validate one TV response row -> quote dict, or None on bad shape."""
    if not isinstance(d, list) or len(d) < len(TV_COLUMNS):
        return None
    if not isinstance(sym_field, str) or ":" not in sym_field:
        return None
    exch, ticker = sym_field.split(":", 1)
    if not _is_clean_ticker(ticker):
        return None

    def _num(i):
        v = d[i]
        return float(v) if isinstance(v, (int, float)) else None

    close = _num(_COL["close"])
    change = _num(_COL["change"])
    rvol = _num(_COL["relative_volume_10d_calc"])
    # A pinned name only needs a live price to be usable — the curated model
    # doesn't pre-score, so a missing rvol/change (common on thinly-traded new
    # leveraged ETFs like MUU/RAM) must not drop the name. Both are None-tolerant
    # downstream (rvol/change default to 0.0; SMA-less trend falls to MIXED).
    if close is None:
        return None
    earnings_raw = d[_COL["earnings_release_next_date"]]
    earnings_ts = int(earnings_raw) if isinstance(earnings_raw, (int, float)) else None
    return {
        "ticker": ticker,
        "tv_symbol": f"{exch}:{ticker}",
        "close": close,
        "change_pct": change,
        "change_from_open": _num(_COL["change_from_open"]),
        "rvol": rvol,
        "market_cap": _num(_COL["market_cap_basic"]),
        "sma20": _num(_COL["SMA20"]),
        "sma50": _num(_COL["SMA50"]),
        "earnings_ts": earnings_ts,
        # Context-layer facts (added 2026-08) — see TV_COLUMNS above and
        # fetcher/context.py:fetch_earnings_days, which turns these into
        # data.json's `facts` map. Numeric-or-None, same as every other
        # scanner field on this quote.
        "hi52": _num(_COL["price_52_week_high"]),
        "lo52": _num(_COL["price_52_week_low"]),
        "beta": _num(_COL["beta_1_year"]),
        "avol": _num(_COL["average_volume_10d_calc"]),
        "rsi": _num(_COL["RSI"]),
    }


def _resolve_core_tv(missing: list[str]) -> dict[str, dict]:
    """Self-healing exchange probe for pinned tickers.

    Tries NASDAQ -> NYSE -> AMEX -> CBOE batch quote calls; a ticker only
    needs one successful match. CBOE covers the memory/semi ETFs (DRAM, RAM)
    that list on Cboe BZX. Fail-soft per exchange call.
    """
    resolved: dict[str, dict] = {}
    remaining = list(missing)
    for exch in ("NASDAQ", "NYSE", "AMEX", "CBOE"):
        if not remaining:
            break
        tickers = [f"{exch}:{t}" for t in remaining]
        body = {"symbols": {"tickers": tickers}, "columns": TV_COLUMNS}
        try:
            raw = _post_json(TV_SCAN_URL, body)
        except Exception as e:
            log(f"WARN core resolve on {exch} failed: {e}")
            continue
        rows = raw.get("data")
        if not isinstance(rows, list):
            continue
        for item in rows:
            if not isinstance(item, dict):
                continue
            q = _row_to_quote(item.get("s"), item.get("d"))
            if q and q["ticker"] not in resolved:
                resolved[q["ticker"]] = q
        remaining = [t for t in remaining if t not in resolved]
    if remaining:
        log(f"WARN could not resolve TV symbol for: {remaining}")
    return resolved


def build_universe(dry_run: bool = False) -> tuple[dict[str, dict], int]:
    """Resolve the fixed PINNED universe -> {ticker: quote}, watched count.

    No market-wide screening: the universe is exactly the curated PINNED list
    (watchlist + sector ETFs). Every name is resolved to a live TV quote via
    the self-healing exchange probe. The second return value is the number of
    names we set out to watch (len PINNED) — there is no "screened" market
    count any more, so callers report it as the watched-list size.
    """
    names = list(PINNED)
    if dry_run:
        # Keep it small & fast: canonical picks + a couple sector ETFs.
        names = ["MU", "CRWD", "COHR", "LLY", "V", "XOM", "SMH", "XLE", "XLK"]
    quotes = _resolve_core_tv(names)
    return quotes, len(names)


def select_candidates(quotes: dict[str, dict]) -> list[str]:
    """Every resolved pinned name is a candidate, in PINNED order.

    The whole point of the curated universe is to show Zach's names, so there
    is no pre-score cut — anything that resolved gets a CBOE chain pulled.
    """
    return [t for t in PINNED if t in quotes]


# ── CBOE chain fetch + OCC parsing ──────────────────────────────────────────

def fetch_chain(ticker: str) -> dict | None:
    """Fetch + minimally validate a CBOE delayed chain. None on any failure."""
    url = CBOE_URL.format(sym=ticker)
    try:
        raw = _get_json(url)
    except Exception as e:
        log(f"skip {ticker}: chain fetch failed ({e})")
        return None
    data = raw.get("data") if isinstance(raw, dict) else None
    if not isinstance(data, dict):
        log(f"skip {ticker}: unexpected chain shape")
        return None
    options = data.get("options")
    if not isinstance(options, list):
        log(f"skip {ticker}: no options list")
        return None
    spot = data.get("current_price")
    if not isinstance(spot, (int, float)) or spot <= 0:
        spot = data.get("close") if isinstance(data.get("close"), (int, float)) else None
    iv30 = data.get("iv30")
    # CBOE's top-level iv30 is a PERCENTAGE (98.469 == 98.469%, verified live
    # 2026-07-16 against MU/ASTS/AAPL) — divide by 100 for the contract's
    # decimal convention (0.98 == 98%). Per-contract "iv" is already decimal.
    iv30_decimal = (float(iv30) / 100.0) if isinstance(iv30, (int, float)) else None
    return {
        "spot": float(spot) if isinstance(spot, (int, float)) else None,
        "iv30": iv30_decimal,
        "options": options,
    }


def parse_occ(occ: str) -> tuple[str, str, str, float] | None:
    """OCC symbol -> (root, yymmdd, 'C'|'P', strike). None if malformed."""
    if not isinstance(occ, str) or len(occ) < 15:
        return None
    tail = occ[-15:]
    root = occ[:-15]
    yymmdd, cp, strike_str = tail[0:6], tail[6], tail[7:15]
    if cp not in ("C", "P") or not yymmdd.isdigit() or not strike_str.isdigit():
        return None
    try:
        strike = int(strike_str) / 1000.0
    except ValueError:
        return None
    return root, yymmdd, cp, strike


def _expiry_date(yymmdd: str) -> date | None:
    try:
        yy, mm, dd = int(yymmdd[0:2]), int(yymmdd[2:4]), int(yymmdd[4:6])
        return date(2000 + yy, mm, dd)
    except ValueError:
        return None


def _num(v) -> float | None:
    return float(v) if isinstance(v, (int, float)) else None


def analyze_ticker(ticker: str, chain: dict, session_date: date,
                   prev_vols: dict | None = None) -> dict:
    """Bucket a chain's contracts into 0-7DTE and 14-183d groups + metrics.

    prev_vols: {occ: cumulative volume at the previous cycle}, SAME session
    only (caller enforces) — enables the aggressor-tilt classification of
    each contract's volume delta. None -> no baseline, tilt contributes 0
    this cycle (fail-soft undercount).
    """
    spot = chain["spot"]
    short_calls_vol = short_puts_vol = 0.0
    short_calls_prem = short_puts_prem = 0.0
    # Near-money-only premium, the basis for FLOW % (see the flow_pct block
    # below). Deliberately separate from short_*_prem so net_flow — which IS a
    # scoring input — keeps its existing whole-bucket definition.
    short_calls_prem_nm = short_puts_prem_nm = 0.0
    short_calls_oi = short_puts_oi = 0.0
    popular = None       # (premium, contract_dict)
    big_candidates: list[tuple[float, dict]] = []    # (premium, row) biggest-orders board
    swing_candidates: list[tuple[float, dict]] = []  # (premium, contract) 0.30<=|delta|<=0.60
    swing_call_prem = swing_put_prem = 0.0
    swing_calls_vol = swing_puts_vol = 0.0
    swing_calls_oi = swing_puts_oi = 0.0
    tilt_bull = tilt_bear = 0.0          # this cycle's classified premium
    contract_vols: dict[str, float] = {}  # occ -> cumulative vol (next cycle's baseline)

    for opt in chain["options"]:
        if not isinstance(opt, dict):
            continue
        occ = opt.get("option")
        parsed = parse_occ(occ) if isinstance(occ, str) else None
        if not parsed:
            continue
        root, yymmdd, cp, strike = parsed
        expiry = _expiry_date(yymmdd)
        if expiry is None:
            continue
        dte = (expiry - session_date).days
        if dte < 0:
            continue

        vol = _num(opt.get("volume")) or 0.0
        oi = _num(opt.get("open_interest")) or 0.0
        last = _num(opt.get("last_trade_price")) or 0.0
        delta = _num(opt.get("delta"))
        iv = _num(opt.get("iv"))
        premium = vol * last * 100.0

        in_short = DTE_SHORT_LO <= dte <= DTE_SHORT_HI
        in_swing = DTE_SWING_LO <= dte <= DTE_SWING_HI
        # Near-money gate, shared by FLOW %'s premium sums, the popular
        # contract and the biggest-orders board. Fails CLOSED without a spot:
        # with no reference price a stock-replacement strike is
        # indistinguishable from a bet, so the contract is simply not counted.
        near_money = bool(spot and spot > 0
                          and abs(strike / spot - 1) <= MONEYNESS_BAND)

        # ── biggest-orders board (added 2026-07-31) ─────────────────────
        # Spans the union of both DTE buckets (0..BIG_ORDERS_DTE_HI) so the
        # 8-13 day gap between them cannot hide a loud contract. Shortlisted
        # per ticker here; run_cycle merges and re-ranks across the universe.
        if (near_money and 0 <= dte <= BIG_ORDERS_DTE_HI
                and premium >= BIG_ORDERS_MIN_PREMIUM):
            big_candidates.append((premium, {
                "ticker": ticker,
                "side": "CALL" if cp == "C" else "PUT",
                "strike": strike,
                "expiry": expiry.isoformat(),
                "dte": dte,
                "last": last,
                "volume": int(vol),
                "open_interest": int(oi),
                "delta": delta,
                "iv": iv,
                "premium": premium,
                "occ": occ,
            }))

        # ── aggressor tilt (both DTE buckets) ──────────────────────────
        # Cumulative volumes feed the next cycle's baseline; with a same-
        # session baseline, classify this cycle's volume delta against the
        # current quote. A contract absent from the baseline simply traded
        # its first volume this cycle (delta = full volume).
        if (in_short or in_swing) and vol > 0:
            contract_vols[occ] = vol
            if prev_vols is not None and last > 0:
                prev_v = prev_vols.get(occ, 0.0)
                dv = vol - (prev_v if isinstance(prev_v, (int, float)) else 0.0)
                bid = _num(opt.get("bid"))
                ask = _num(opt.get("ask"))
                if dv > 0 and bid is not None and ask is not None and ask > bid >= 0:
                    pos = (last - bid) / (ask - bid)
                    prem_d = dv * last * 100.0
                    if pos >= TILT_BUY_POS:       # bought at/near the ask
                        if cp == "C":
                            tilt_bull += prem_d
                        else:
                            tilt_bear += prem_d
                    elif pos <= TILT_SELL_POS:    # sold at/near the bid
                        if cp == "C":
                            tilt_bear += prem_d
                        else:
                            tilt_bull += prem_d
                    # mid-band trades stay unclassified (excluded)

        if in_short:
            if cp == "C":
                short_calls_vol += vol
                short_calls_prem += premium
                short_calls_oi += oi
            else:
                short_puts_vol += vol
                short_puts_prem += premium
                short_puts_oi += oi

            if near_money:
                if cp == "C":
                    short_calls_prem_nm += premium
                else:
                    short_puts_prem_nm += premium
                if popular is None or premium > popular[0]:
                    popular = (premium, {
                        "side": "CALL" if cp == "C" else "PUT",
                        "strike": strike,
                        "expiry": expiry.isoformat(),
                        "dte": dte,
                        "last": last,
                        "delta": delta,
                        "iv": iv,
                        "volume": int(vol),
                        "open_interest": int(oi),
                        "occ": occ,
                    })

        if in_swing:
            if cp == "C":
                swing_call_prem += premium
                swing_calls_vol += vol
                swing_calls_oi += oi
            else:
                swing_put_prem += premium
                swing_puts_vol += vol
                swing_puts_oi += oi
            if delta is not None and SWING_DELTA_LO <= abs(delta) <= SWING_DELTA_HI:
                swing_candidates.append((premium, {
                    "side": "CALL" if cp == "C" else "PUT",
                    "strike": strike,
                    "expiry": expiry.isoformat(),
                    "dte": dte,
                    "delta": delta,
                    "iv": iv,
                    "volume": int(vol),
                    "open_interest": int(oi),
                    "occ": occ,
                    "entry": last,
                }))

    net_flow = short_calls_prem - short_puts_prem
    cp_ratio = (short_calls_vol / short_puts_vol) if short_puts_vol > 0 else None

    # Premium-weighted flow share (added 2026-07-25). cp_ratio counts CONTRACTS;
    # this counts DOLLARS, and the two can disagree sharply — MU on 2026-07-24
    # printed a near-1.0 contract ratio while the put side carried far more
    # premium, because near-money puts on a $920 stock at ~100% IV cost many
    # times what the calls did. Reported the way InsiderFinance shows it:
    # whichever side holds the larger share of premium, as a percentage.
    # Display only — it is NOT a scoring input (weights unchanged).
    #
    # NEAR-MONEY ONLY since 2026-07-28 (Zach flagged LLY printing C/P 4.06
    # put-heavy against 84% CALL in dollars). Premium is intrinsic + extrinsic
    # value; on a deep-ITM contract it is almost all intrinsic, so weighting
    # the whole bucket by dollars measures how far in the money somebody's
    # stock-replacement paper sits, not conviction. On LLY's 2026-07-27 chain
    # (spot ~$1,205) seven Jul-31 call strikes at $780-$910 — ~35% below spot,
    # ~330 contracts at ~$400 each, ~101% of price intrinsic — were 79% of all
    # call premium. Restricting to MONEYNESS_BAND gives 60.1% CALL; the
    # independent "drop anything >=90% intrinsic" filter gives 60.4%. Two
    # unrelated filters within 0.3pp is the evidence.
    #
    # Subtracting intrinsic value instead was measured and REJECTED: last is
    # the trade-time price while spot is now, so the subtraction mixes clocks
    # and drove computed intrinsic to 101-106% OF THE TRADED PRICE on a dozen
    # LLY contracts (extrinsic clamped to 0, deleting real premium). Across
    # this 30-name universe it flipped side on 11-12 names, 4 of them merely
    # by reading mid instead of last. The band flipped 2 and is immune — a 1%
    # spot move cannot reclassify a 35%-ITM strike.
    _prem_total = short_calls_prem_nm + short_puts_prem_nm
    if _prem_total > 0:
        _put_share = short_puts_prem_nm / _prem_total
        flow_side = "PUT" if _put_share >= 0.5 else "CALL"
        flow_pct = round((_put_share if _put_share >= 0.5 else 1 - _put_share) * 100, 1)
    else:
        flow_side, flow_pct = None, None
    sum_vol_0_7 = short_calls_vol + short_puts_vol
    sum_oi_0_7_total = short_calls_oi + short_puts_oi
    direction = "BULL" if net_flow >= 0 else "BEAR"
    # OI tracked "in the flow direction" — the side matching today's direction
    sum_oi_directional = short_calls_oi if direction == "BULL" else short_puts_oi

    cp_skew = (swing_call_prem / swing_put_prem) if swing_put_prem > 0 else None
    suggested = None
    if swing_candidates:
        swing_candidates.sort(key=lambda x: x[0], reverse=True)
        # The suggested contract must express the card's thesis: a BULL card
        # suggests a CALL, a BEAR card suggests a PUT. Pick the highest-premium
        # candidate on the matching side; only if that side has none do we fall
        # back to the highest-premium candidate overall.
        want_side = "CALL" if direction == "BULL" else "PUT"
        matching = [t for t in swing_candidates if t[1]["side"] == want_side]
        prem, c = (matching[0] if matching else swing_candidates[0])
        entry = c.pop("entry")
        c["entry"] = entry
        c["stop"] = round(entry * STOP_MULT, 2) if entry else None
        c["target"] = round(entry * TARGET_MULT, 2) if entry else None
        c["rr"] = FIXED_RR
        suggested = c

    # Biggest-orders shortlist: highest premium first, capped at the published
    # row count (see BIG_ORDERS_CAP — the cap cannot alter the merged ranking).
    big_candidates.sort(key=lambda x: x[0], reverse=True)
    big_orders = [row for _, row in big_candidates[:BIG_ORDERS_CAP]]

    return {
        "spot": spot,
        "iv30": chain["iv30"],
        "direction": direction,
        "net_flow": net_flow,
        "cp_ratio": cp_ratio,
        "flow_pct": flow_pct,
        "flow_side": flow_side,
        # The two inputs behind flow_pct, exposed so history can archive them
        # (flow_pct alone is not reconstructible or re-weightable after the fact)
        "nm_call_prem_0_7": short_calls_prem_nm,
        "nm_put_prem_0_7": short_puts_prem_nm,
        "sum_vol_0_7": sum_vol_0_7,
        "sum_oi_0_7_total": sum_oi_0_7_total,
        "sum_oi_0_7_directional": sum_oi_directional,
        "popular_contract": popular[1] if popular else None,
        "popular_premium": popular[0] if popular else 0.0,
        "big_orders": big_orders,
        "total_premium_0_7": short_calls_prem + short_puts_prem,
        "has_short_bucket": sum_vol_0_7 > 0,
        "cp_skew": cp_skew,
        "suggested_contract": suggested,
        # swing-bucket per-side totals (OI-confirm inputs, stored in history)
        "swing_calls_vol": swing_calls_vol,
        "swing_puts_vol": swing_puts_vol,
        "swing_calls_oi": swing_calls_oi,
        "swing_puts_oi": swing_puts_oi,
        # this cycle's classified aggressor premium + next cycle's baseline
        "tilt_bull_cycle": tilt_bull,
        "tilt_bear_cycle": tilt_bear,
        "contract_vols": contract_vols,
    }


# ── Semi ETF share flows (context card) ──────────────────────────────────────

def fetch_etf_fund_rows() -> dict[str, dict]:
    """Batch TV scan for the semi-ETF flow funds -> {ticker: fund row}.

    Same self-healing exchange probe as _resolve_core_tv (SMH/SOXX list on
    NASDAQ, SOXL/SOXS on AMEX, DRAM on Cboe BZX — but don't trust a static
    map). Fail-soft per exchange call; a fund with no row anywhere is simply
    absent from the result.
    """
    resolved: dict[str, dict] = {}
    remaining = list(ETF_FLOW_FUNDS)
    for exch in ("NASDAQ", "NYSE", "AMEX", "CBOE"):
        if not remaining:
            break
        body = {"symbols": {"tickers": [f"{exch}:{t}" for t in remaining]},
                "columns": ETF_FLOW_COLUMNS}
        try:
            raw = _post_json(TV_SCAN_URL, body)
        except Exception as e:
            log(f"WARN etf-flows resolve on {exch} failed: {e}")
            continue
        rows = raw.get("data") if isinstance(raw, dict) else None
        if not isinstance(rows, list):
            continue
        for item in rows:
            if not isinstance(item, dict):
                continue
            d = item.get("d")
            if not isinstance(d, list) or len(d) < len(ETF_FLOW_COLUMNS):
                continue
            name = d[0]
            if not isinstance(name, str) or name in resolved:
                continue
            resolved[name] = {
                "so": _num(d[1]),
                "nav": _num(d[2]),
                "aum": _num(d[3]),
                "flow_1m": _num(d[4]),
            }
        remaining = [t for t in remaining if t not in resolved]
    if remaining:
        log(f"WARN etf-flows: no TV row for {remaining}")
    return resolved



# ── Split detection for the SO-based flow maths ──────────────────────────────
# flow_1d = ΔSO x NAV is only "money in or out" while the share count changes
# for creation/redemption reasons. A split also changes it, by a lot: SOXS and
# SOXL are leveraged funds that reverse-split routinely, and a 1-for-10 reverse
# split divides SO by 10 overnight. Read naively that prints an outflow of ~90%
# of the fund's AUM on a day when nobody moved a dollar — the same fabricated
# headline as the CRWD 4-for-1 that produced a fake -74.9% in the Jul 1 2026
# morning brief. A split moves SO and NAV by reciprocal factors, so the product
# of the two ratios stays ~1 while each is far from 1.
_SPLIT_RATIOS = (2, 3, 4, 5, 6, 8, 10, 20)
_SPLIT_TOL = 0.08            # same 8% band the brief's price reconciler uses


def _ratio_near_split(ratio: float) -> bool:
    for r in _SPLIT_RATIOS:
        for cand in (float(r), 1.0 / r):
            if abs(ratio / cand - 1.0) <= _SPLIT_TOL:
                return True
    return False


def _so_delta_is_split(so0, so1, nav0, nav1) -> bool:
    """True when an SO jump is a split rather than creations/redemptions.

    Needs both NAVs to confirm. When a NAV is missing we cannot confirm, so an
    SO ratio sitting on a split factor is treated as a SUSPECTED split and the
    flow is withheld — for a display-only card, a dash beats a fabricated
    multi-billion number.
    """
    if not (isinstance(so0, (int, float)) and isinstance(so1, (int, float))
            and so0 > 0 and so1 > 0):
        return False
    so_ratio = so1 / so0
    if not _ratio_near_split(so_ratio):
        return False
    if (isinstance(nav0, (int, float)) and isinstance(nav1, (int, float))
            and nav0 > 0 and nav1 > 0):
        return abs(so_ratio * (nav1 / nav0) - 1.0) <= _SPLIT_TOL
    return True          # unconfirmable but split-shaped -> withhold


def build_etf_flows(history: dict, session_str: str,
                    write_history: bool) -> dict | None:
    """Fetch fund rows, update SO history, compute daily flows -> etf_flows.

    flow_1d = (SO this session - SO previous session) x NAV — one reading per
    session. streak = consecutive stored sessions (incl. latest) whose SO
    delta had the same sign. Both null until 2 sessions of SO history exist.
    Closed-day forced runs compute from live SO + stored history but do NOT
    write new SO rows (same phantom-weekend-session rule as the rest of
    history). Returns None when there is nothing to show at all.
    """
    live = fetch_etf_fund_rows()
    etf_so = history.setdefault("etf_so", {})
    funds = []
    for ticker in ETF_FLOW_FUNDS:
        row = live.get(ticker) or {}
        so_now = row.get("so")
        nav = row.get("nav")
        fund_hist = etf_so.get(ticker)
        if not isinstance(fund_hist, dict):
            fund_hist = {}
        if write_history and so_now is not None:
            etf_so[ticker] = fund_hist
            fund_hist[session_str] = {"so": so_now, "nav": nav}

        # SO series, oldest->newest; live value stands in for today's row so
        # a closed-day run still sees the freshest reading without storing it.
        # NAV rides along per session so splits can be detected (see
        # _so_delta_is_split) — a split is not a flow.
        series = [(d, v["so"], v.get("nav")) for d, v in sorted(fund_hist.items())
                  if isinstance(v, dict) and isinstance(v.get("so"), (int, float))
                  and d != session_str]
        if so_now is not None:
            series.append((session_str, so_now, nav))
        elif isinstance(fund_hist.get(session_str), dict):
            stored = fund_hist[session_str]
            if isinstance(stored.get("so"), (int, float)):
                so_now = stored["so"]
                if nav is None and isinstance(stored.get("nav"), (int, float)):
                    nav = stored["nav"]
                series.append((session_str, so_now, nav))

        flow_1d = None
        baseline_session = None
        streak = None
        split_suppressed = False
        if len(series) >= 2 and nav is not None:
            deltas = []
            for a, b in zip(series, series[1:]):
                if _so_delta_is_split(a[1], b[1], a[2], b[2]):
                    deltas.append(0.0)      # split: no money moved
                else:
                    deltas.append(b[1] - a[1])
            split_suppressed = _so_delta_is_split(
                series[-2][1], series[-1][1], series[-2][2], series[-1][2])
            if split_suppressed:
                # Don't print 0 either — that asserts a flat day we didn't
                # observe. The card shows a dash and the reason.
                flow_1d = None
            else:
                flow_1d = deltas[-1] * nav
            baseline_session = series[-2][0]
            streak = 0
            last_sign = (deltas[-1] > 0) - (deltas[-1] < 0)
            if last_sign != 0:
                for dlt in reversed(deltas):
                    if ((dlt > 0) - (dlt < 0)) == last_sign:
                        streak += 1
                    else:
                        break

        if so_now is None and row.get("flow_1m") is None:
            continue   # nothing at all to show for this fund this cycle
        funds.append({
            "ticker": ticker,
            "flow_1d": flow_1d,
            "baseline_session": baseline_session,
            "streak": streak,
            "flow_1m": row.get("flow_1m"),
            "aum": row.get("aum"),
            "so": so_now,
            "nav": nav,
            "split_suppressed": split_suppressed,
            "flow_session": baseline_session,
        })
    if not funds:
        return None
    # ONE-SESSION PUBLICATION LAG (measured 2026-07-28). The vendor's shares/NAV
    # record read during session S carries the OFFICIAL figures struck at the
    # close of S-1 — NAV is computed after the close and published next morning.
    # Verified on this repo's own etf_so history: pairing the stamped NAV with
    # the PRIOR session's close gives a 0.052% median error versus 2.187%
    # against the same session's close (30 pairs, 5 funds; SOXL/SOXS matched to
    # 0.01-0.05%). The flow ARITHMETIC is unaffected — both inputs carry the
    # same lag, so consecutive captures still difference to a true one-session
    # share change priced at that session's NAV. Only the LABEL was wrong:
    # `as_of_session` was the capture date, which claimed a day of freshness the
    # number does not have. `flow_session` per fund is the session the flow
    # actually belongs to; the site labels off that.
    sessions = [f["flow_session"] for f in funds if f.get("flow_session")]
    return {
        "as_of_session": session_str,          # capture session (kept, unchanged)
        "flow_session": max(sessions) if sessions else None,
        "funds": funds,
    }


# ── History (persistence across cycles) ─────────────────────────────────────

def load_history(out_dir: Path) -> dict:
    path = out_dir / "history.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("not a dict")
        raw.setdefault("sessions", {})
        raw.setdefault("iv_history", {})
        raw.setdefault("etf_so", {})
        raw.setdefault("big_orders", {})
        return raw
    except Exception:
        return {"sessions": {}, "iv_history": {}, "etf_so": {}, "big_orders": {}}


def save_history(out_dir: Path, history: dict) -> None:
    sessions = history.get("sessions", {})
    if len(sessions) > MAX_HISTORY_SESSIONS:
        for k in sorted(sessions.keys())[:-MAX_HISTORY_SESSIONS]:
            del sessions[k]
    for t, vals in history.get("iv_history", {}).items():
        if isinstance(vals, list) and len(vals) > MAX_IV_HISTORY:
            history["iv_history"][t] = vals[-MAX_IV_HISTORY:]
    for t, rows in history.get("etf_so", {}).items():
        if isinstance(rows, dict) and len(rows) > MAX_ETF_SO_SESSIONS:
            for k in sorted(rows.keys())[:-MAX_ETF_SO_SESSIONS]:
                del rows[k]
    big_hist = history.get("big_orders", {})
    if isinstance(big_hist, dict) and len(big_hist) > MAX_BIG_ORDERS_SESSIONS:
        for k in sorted(big_hist.keys())[:-MAX_BIG_ORDERS_SESSIONS]:
            del big_hist[k]
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "history.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(history, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_prev_cycle() -> dict:
    """Load the prior cycle's cache: {"session", "flows", "vols"}.

    Legacy shape (flat {ticker: net_flow}) is accepted as flows-only with an
    unknown session — accel still works, tilt just has no baseline yet.
    """
    empty = {"session": None, "flows": {}, "vols": {}}
    try:
        raw = json.loads(PREV_CYCLE_FILE.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return empty
        if "flows" in raw:
            return {
                "session": raw.get("session") if isinstance(raw.get("session"), str) else None,
                "flows": raw.get("flows") if isinstance(raw.get("flows"), dict) else {},
                "vols": raw.get("vols") if isinstance(raw.get("vols"), dict) else {},
            }
        # legacy flat shape
        flows = {k: v for k, v in raw.items() if isinstance(v, (int, float))}
        return {"session": None, "flows": flows, "vols": {}}
    except Exception:
        return empty


def save_prev_cycle(data: dict) -> None:
    try:
        PREV_CYCLE_FILE.write_text(json.dumps(data), encoding="utf-8")
    except Exception as e:
        log(f"WARN could not write prev-cycle cache: {e}")


# ── Scoring ──────────────────────────────────────────────────────────────────

def conviction_score(analysis: dict, quote: dict) -> int:
    rvol = quote["rvol"] or 0.0
    change_pct = quote["change_pct"] or 0.0
    change_from_open = quote["change_from_open"]
    net_flow = analysis["net_flow"]
    cp_ratio = analysis["cp_ratio"]
    sum_vol = analysis["sum_vol_0_7"]
    sum_oi = analysis["sum_oi_0_7_total"]
    total_prem = analysis["total_premium_0_7"]
    popular_prem = analysis["popular_premium"]

    pts = 0.0
    pts += min(rvol / 3.0, 1.0) * 25

    mom = min(abs(change_pct) / 5.0, 1.0) * 15
    if change_from_open is not None and change_pct != 0 and (
            (change_pct > 0) == (change_from_open > 0)):
        mom += 5
    pts += mom

    flow = min(math.log10(abs(net_flow) + 1) / 7.0, 1.0) * 20
    if net_flow != 0 and change_pct != 0 and ((net_flow > 0) == (change_pct > 0)):
        flow += 5
    pts += flow

    if cp_ratio and cp_ratio > 0:
        dist = min(abs(math.log(cp_ratio)) / 2.0, 1.0)
        pts += dist * 15

    if sum_oi > 0:
        pts += min((sum_vol / sum_oi) / 3.0, 1.0) * 10

    if total_prem > 0:
        pts += min(popular_prem / total_prem, 1.0) * 5

    return max(0, min(100, round(pts)))


def swing_score(persist: int, persist_max: int, flow_5d: float,
                oi_build: float | None, trend: str, direction: str,
                iv_rank: float | None, cp_skew: float | None) -> int:
    pts = 0.0
    if persist_max > 0:
        pts += (persist / persist_max) * 35

    pts += min(math.log10(abs(flow_5d) + 1) / 7.5, 1.0) * 20

    if oi_build is not None and oi_build > 0:
        pts += min(oi_build / 20000.0, 1.0) * 15

    if (trend == "UP" and direction == "BULL") or (trend == "DOWN" and direction == "BEAR"):
        pts += 15
    elif trend == "MIXED":
        pts += 7

    if iv_rank is None:
        pts += 5
    else:
        pts += max(0.0, 10 * (1 - iv_rank / 100))

    if cp_skew and cp_skew > 0:
        pts += min(abs(math.log(cp_skew)) / 2.0, 1.0) * 5

    return max(0, min(100, round(pts)))


# ── Main cycle ───────────────────────────────────────────────────────────────

def run_cycle(out_dir: Path, dry_run: bool = False) -> dict:
    now_utc = datetime.now(tz=timezone.utc)
    now_ct = now_utc.astimezone(TZ_CT)
    session_date = now_ct.date()
    session_str = session_date.isoformat()

    if now_ct.weekday() >= 5:
        market_state = "closed"
    else:
        open_min = 8 * 60 + 30
        close_min = 15 * 60
        cur_min = now_ct.hour * 60 + now_ct.minute
        pre_min = 8 * 60
        post_min = 15 * 60 + 20
        if open_min <= cur_min <= close_min:
            market_state = "open"
        elif pre_min <= cur_min < open_min:
            market_state = "premarket"
        elif close_min < cur_min <= post_min:
            market_state = "afterhours"
        else:
            market_state = "closed"
    # Forced off-hours cycles refresh data.json but must not touch history.
    write_history = market_state != "closed"

    log(f"cycle start {now_ct.strftime('%Y-%m-%d %H:%M CT')}")

    quotes, screened = build_universe(dry_run=dry_run)
    log(f"watched={screened} resolved={len(quotes)}")

    candidates = select_candidates(quotes)
    log(f"candidates={len(candidates)}")

    history = load_history(out_dir)
    today_sessions = history["sessions"].setdefault(session_str, {})
    iv_history = history["iv_history"]
    prev_cycle = load_prev_cycle()
    same_session = prev_cycle["session"] == session_str
    new_prev_cycle: dict = {"session": session_str, "flows": {}, "vols": {}}

    conviction_cards = []
    swing_cards = []
    big_orders_pool: list[dict] = []   # every ticker's shortlist, merged below
    with_options = 0

    for i, ticker in enumerate(candidates):
        if i > 0:
            time.sleep(CBOE_SLEEP_SEC)
        chain = fetch_chain(ticker)
        if chain is None:
            continue
        with_options += 1
        quote = quotes.get(ticker)
        if quote is None:
            continue

        prev_vols = prev_cycle["vols"].get(ticker) if same_session else None
        if not isinstance(prev_vols, dict):
            prev_vols = None
        analysis = analyze_ticker(ticker, chain, session_date, prev_vols=prev_vols)
        direction = analysis["direction"]
        net_flow = analysis["net_flow"]
        new_prev_cycle["flows"][ticker] = net_flow
        new_prev_cycle["vols"][ticker] = analysis["contract_vols"]

        # Biggest-orders board: collect for EVERY candidate, not just the ones
        # that make a scoring board — it is a universe-wide leaderboard, and a
        # name can have the loudest contract of the day without scoring well.
        for row in analysis["big_orders"]:
            big_orders_pool.append({**row, "tv_symbol": quote["tv_symbol"]})

        # iv30 history
        if write_history and analysis["iv30"] is not None:
            iv_history.setdefault(ticker, []).append(analysis["iv30"])

        # Today's session row (persisted regardless of board membership).
        # first_board_* fields, if already set earlier this same day (e.g. a
        # prior cycle), must survive this reassignment — carried forward
        # explicitly since first_board_* is stamped in a later pass below.
        prior_today = today_sessions.get(ticker)
        # Aggressor tilt accumulates ACROSS cycles within the day: prior
        # cycles' classified premium (persisted in history.json, so it
        # survives a workflow re-dispatch) plus this cycle's increment.
        tilt_bull_day = analysis["tilt_bull_cycle"]
        tilt_bear_day = analysis["tilt_bear_cycle"]
        if isinstance(prior_today, dict):
            if isinstance(prior_today.get("tilt_bull_prem"), (int, float)):
                tilt_bull_day += prior_today["tilt_bull_prem"]
            if isinstance(prior_today.get("tilt_bear_prem"), (int, float)):
                tilt_bear_day += prior_today["tilt_bear_prem"]
        if write_history:
            today_sessions[ticker] = {
                "net_flow_0_7": net_flow,
                "sum_oi_0_7": analysis["sum_oi_0_7_directional"],
                "gross_prem_0_7": analysis["total_premium_0_7"],   # calls+puts prem (for flow_5d %)
                # Near-money per-side premium — the two numbers FLOW % is built
                # from. Stored 2026-07-28 to close an archival gap the accuracy
                # backtest ran into: history kept only net_flow and gross
                # premium, so NOT ONE DAY of historical FLOW % could be
                # reconstructed and its predictive value was untestable. With
                # these, a determination becomes possible after ~30 sessions
                # (see market-data/results/flow_accuracy_2026-07.md).
                "nm_call_prem_0_7": analysis["nm_call_prem_0_7"],
                "nm_put_prem_0_7": analysis["nm_put_prem_0_7"],
                "iv30": analysis["iv30"],
                "direction": direction,
                "tilt_bull_prem": tilt_bull_day,
                "tilt_bear_prem": tilt_bear_day,
                # swing-bucket per-side totals — tomorrow's OI-confirm inputs
                "swing_vol_c": analysis["swing_calls_vol"],
                "swing_vol_p": analysis["swing_puts_vol"],
                "swing_oi_c": analysis["swing_calls_oi"],
                "swing_oi_p": analysis["swing_puts_oi"],
            }
            if isinstance(prior_today, dict):
                for k in ("first_board_conviction", "first_board_swing"):
                    if k in prior_today and prior_today[k]:
                        today_sessions[ticker][k] = prior_today[k]

        # tilt for display/scoring: bounded -1..+1, null until anything classifies
        tilt_prem_total = tilt_bull_day + tilt_bear_day
        tilt = ((tilt_bull_day - tilt_bear_day) / tilt_prem_total) if tilt_prem_total > 0 else None

        # ── swing metrics from history ──────────────────────────────────
        # persist: n/5 -- fixed 5-session denominator (contract's PERSIST_MAX);
        # missing prior sessions simply don't count as hits (not penalized
        # beyond the fraction they represent).
        prior_dates = sorted(d for d in history["sessions"].keys() if d < session_str)
        last5_dates = prior_dates[-5:]
        persist = 0
        for d in last5_dates:
            row = history["sessions"][d].get(ticker)
            if isinstance(row, dict) and row.get("direction") == direction:
                persist += 1
        persist_max = 5

        # flow_5d = today's net_flow + up to 4 prior sessions' net_flow (5 total).
        # flow_5d_pct re-expresses that net dollar flow as a percentage of gross
        # premium (calls+puts) over the SAME sessions -- i.e. how one-sided the
        # 5-day flow is (bounded -100..+100). net and gross are summed only over
        # sessions that carry gross data (today always does; history rows written
        # before gross_prem_0_7 existed are skipped for the %, so it stays bounded
        # and self-corrects as gross history fills in).
        flow_5d = net_flow
        net_for_pct = net_flow
        gross_for_pct = analysis["total_premium_0_7"] or 0.0
        for d in (last5_dates[-4:] if len(last5_dates) > 4 else last5_dates):
            row = history["sessions"][d].get(ticker)
            if not isinstance(row, dict):
                continue
            if isinstance(row.get("net_flow_0_7"), (int, float)):
                flow_5d += row["net_flow_0_7"]
                if isinstance(row.get("gross_prem_0_7"), (int, float)):
                    net_for_pct += row["net_flow_0_7"]
                    gross_for_pct += row["gross_prem_0_7"]
        flow_5d_pct = (net_for_pct / gross_for_pct * 100.0) if gross_for_pct > 0 else None

        # oi_build: today's directional sum_oi minus yesterday's
        oi_build = None
        if prior_dates:
            y_row = history["sessions"][prior_dates[-1]].get(ticker)
            if isinstance(y_row, dict) and isinstance(y_row.get("sum_oi_0_7"), (int, float)):
                oi_build = analysis["sum_oi_0_7_directional"] - y_row["sum_oi_0_7"]

        # OI-confirm: did yesterday's swing-bucket volume OPEN new positions
        # (OI grew by a meaningful fraction of it), CLOSE positions, or churn?
        # Computed on the side of YESTERDAY'S direction; see module header.
        oi_confirm = None
        oi_confirm_frac = None
        oi_confirm_side = None
        oi_confirm_dir_match = False
        if prior_dates:
            y_row = history["sessions"][prior_dates[-1]].get(ticker)
            if isinstance(y_row, dict) and isinstance(y_row.get("direction"), str):
                y_side = "c" if y_row["direction"] == "BULL" else "p"
                y_vol = y_row.get(f"swing_vol_{y_side}")
                y_oi = y_row.get(f"swing_oi_{y_side}")
                t_oi = analysis["swing_calls_oi"] if y_side == "c" else analysis["swing_puts_oi"]
                if (isinstance(y_vol, (int, float)) and isinstance(y_oi, (int, float))
                        and y_vol >= OI_CONFIRM_MIN_VOL):
                    frac = (t_oi - y_oi) / y_vol
                    oi_confirm_frac = round(frac, 3)
                    oi_confirm_side = "CALL" if y_side == "c" else "PUT"
                    oi_confirm_dir_match = (y_row["direction"] == direction)
                    if frac >= OI_CONFIRM_FRAC:
                        oi_confirm = "OPENING"
                    elif frac <= -OI_CONFIRM_FRAC:
                        oi_confirm = "CLOSING"
                    else:
                        oi_confirm = "CHURN"

        # trend: spot vs SMA20/SMA50
        spot = analysis["spot"]
        sma20, sma50 = quote.get("sma20"), quote.get("sma50")
        if spot and sma20 and sma50:
            if spot > sma20 and spot > sma50:
                trend = "UP"
            elif spot < sma20 and spot < sma50:
                trend = "DOWN"
            else:
                trend = "MIXED"
        else:
            trend = "MIXED"

        # iv_rank: percentile within iv_history (including today's just-appended value)
        ivs = iv_history.get(ticker, [])
        iv_rank = None
        iv_collecting = True
        if len(ivs) >= 20 and analysis["iv30"] is not None:
            iv_collecting = False
            sorted_ivs = sorted(ivs)
            rank_pos = sum(1 for v in sorted_ivs if v <= analysis["iv30"])
            iv_rank = round(100 * rank_pos / len(sorted_ivs))

        # earnings in window (needs suggested_contract expiry)
        suggested = analysis["suggested_contract"]
        earnings_ts = quote.get("earnings_ts")
        # earnings_days is only populated when earnings_in_window is true —
        # "null if none/out of window" per DATA_CONTRACT.md.
        earnings_in_window = False
        earnings_days = None
        if earnings_ts is not None and suggested is not None:
            try:
                edt = datetime.fromtimestamp(earnings_ts, tz=timezone.utc).date()
                expiry_d = date.fromisoformat(suggested["expiry"])
                if session_date <= edt <= expiry_d:
                    earnings_in_window = True
                    earnings_days = (edt - session_date).days
            except Exception:
                pass

        # Score + assemble candidate cards. spot_at_alert/first_board_* are
        # NOT stamped here — alert memory means "first time this ticker
        # actually appeared on the (capped, sorted) board", not merely "had
        # a usable bucket". Board membership is only decided after every
        # candidate's score is known and the list is sorted+capped below, so
        # stamping happens in a second pass over the surviving cards.
        conv_score = conviction_score(analysis, quote)
        # Aggressor-tilt post-adjustment (bounded, see module header): the
        # sampled buy/sell tilt confirming or contradicting the premium-proxy
        # direction moves the score +/-5 once enough premium has classified.
        if tilt is not None and tilt_prem_total >= TILT_MIN_PREM and abs(tilt) >= TILT_MIN_ABS:
            agrees = (tilt > 0) == (direction == "BULL")
            conv_score = max(0, min(100, conv_score + (TILT_SCORE_ADJ if agrees else -TILT_SCORE_ADJ)))
        accel = False
        prev_flow = prev_cycle["flows"].get(ticker)
        if isinstance(prev_flow, (int, float)) and prev_flow != 0 and net_flow != 0:
            if (net_flow > 0) == (prev_flow > 0) and abs(net_flow) >= abs(prev_flow) * ACCEL_MULT:
                accel = True
        firing = conv_score >= 80 or accel

        has_short_bucket = analysis["has_short_bucket"] or analysis["popular_contract"] is not None
        if has_short_bucket:
            conviction_cards.append({
                "ticker": ticker,
                "tv_symbol": quote["tv_symbol"],
                "direction": direction,
                "firing": firing,
                "score": conv_score,
                "spot": spot,
                "net_flow": net_flow,
                "cp_ratio": analysis["cp_ratio"],
                "flow_pct": analysis["flow_pct"],
                "flow_side": analysis["flow_side"],
                "rvol": quote["rvol"],
                "change_pct": quote["change_pct"],
                "tilt": round(tilt, 3) if tilt is not None else None,
                "tilt_prem": tilt_prem_total,
                "popular_contract": analysis["popular_contract"],
            })

        if suggested is not None:
            sw_score = swing_score(persist, persist_max, flow_5d, oi_build,
                                    trend, direction, iv_rank, analysis["cp_skew"])
            # OI-confirm post-adjustment (bounded, see module header) — only
            # when yesterday's direction matches today's card.
            if oi_confirm_dir_match:
                if oi_confirm == "OPENING":
                    sw_score = max(0, min(100, sw_score + OI_CONFIRM_OPEN_ADJ))
                elif oi_confirm == "CLOSING":
                    sw_score = max(0, min(100, sw_score + OI_CONFIRM_CLOSE_ADJ))
            swing_cards.append({
                "ticker": ticker,
                "tv_symbol": quote["tv_symbol"],
                "direction": direction,
                "score": sw_score,
                "spot": spot,
                "persist": persist,
                "persist_max": persist_max,
                "flow_5d": flow_5d,
                "flow_5d_pct": flow_5d_pct,
                "oi_build": oi_build,
                "oi_confirm": oi_confirm,
                "oi_confirm_frac": oi_confirm_frac,
                "oi_confirm_side": oi_confirm_side,
                "trend": trend,
                "iv_rank": iv_rank,
                "iv30": analysis["iv30"],
                "iv_collecting": iv_collecting,
                "cp_skew": analysis["cp_skew"],
                "earnings_in_window": earnings_in_window,
                "earnings_days": earnings_days,
                "suggested_contract": suggested,
            })

    conviction_cards.sort(key=lambda c: c["score"], reverse=True)
    swing_cards.sort(key=lambda c: c["score"], reverse=True)
    conviction_cards = conviction_cards[:BOARD_CAP]
    swing_cards = swing_cards[:BOARD_CAP]

    # ── alert memory: stamp first_board_* only for names that actually made
    # the capped board this cycle, and only once per ticker per day ────────
    if write_history:
        now_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        for board_cards, key in ((conviction_cards, "first_board_conviction"),
                                  (swing_cards, "first_board_swing")):
            for c in board_cards:
                ticker = c["ticker"]
                row = today_sessions.setdefault(ticker, {})
                if key not in row or not row[key]:
                    row[key] = {"time": now_iso, "spot": c["spot"]}
                fb = row[key]
                c["spot_at_alert"] = fb.get("spot") if isinstance(fb, dict) else None
    else:
        # Closed-day cycle: no history mutation, but spot_at_alert must still
        # be present on every card (DATA_CONTRACT field shape) — the frontend
        # already treats a missing/null value as "new this cycle" (no gain chip).
        for board_cards in (conviction_cards, swing_cards):
            for c in board_cards:
                c["spot_at_alert"] = None

    # ── stats tiles (union of both boards, deduped) ─────────────────────────
    by_ticker: dict[str, dict] = {}
    for c in conviction_cards:
        by_ticker[c["ticker"]] = {"direction": c["direction"], "firing": c["firing"],
                                   "score_conv": c["score"]}
    for c in swing_cards:
        e = by_ticker.setdefault(c["ticker"], {"direction": c["direction"], "firing": False,
                                                "score_conv": None})
        e.setdefault("direction", c["direction"])

    # ── biggest-orders board: merge every ticker's shortlist, re-rank, cap ───
    big_orders_pool.sort(key=lambda r: r["premium"], reverse=True)
    # The uncapped board is computed FIRST and is what the disclosure is measured
    # against: "earned" means a row ranked inside the top BIG_ORDERS_CAP on
    # dollars alone. Counting a ticker's whole shortlist instead would overstate
    # what the cap held back (a 13th-place row was never going to show anyway).
    uncapped = big_orders_pool[:BIG_ORDERS_CAP]
    earned: dict[str, int] = {}
    for row in uncapped:
        earned[row["ticker"]] = earned.get(row["ticker"], 0) + 1
    # Greedy fill in premium order, skipping a ticker once it hits its quota, so
    # the rows a crowded name gives up go to the next-loudest OTHER contracts
    # rather than shortening the board.
    big_orders = []
    shown: dict[str, int] = {}
    for row in big_orders_pool:
        if len(big_orders) >= BIG_ORDERS_CAP:
            break
        t = row["ticker"]
        if shown.get(t, 0) >= BIG_ORDERS_PER_TICKER:
            continue
        big_orders.append(row)
        shown[t] = shown.get(t, 0) + 1
    big_orders_capped = [
        {"ticker": t, "shown": min(n, BIG_ORDERS_PER_TICKER), "earned": n}
        for t, n in sorted(earned.items(), key=lambda kv: -kv[1])
        if n > BIG_ORDERS_PER_TICKER
    ]
    if big_orders_capped:
        log("big-orders per-ticker cap applied: "
            + ", ".join(f"{c['ticker']} {c['shown']}/{c['earned']}" for c in big_orders_capped))
    # Archived so the board is testable later. FLOW % shipped display-only with
    # only aggregates stored, and when its accuracy was questioned not one
    # historical day could be reconstructed — don't repeat that. Same weekend
    # guard as the rest of history: a forced closed-market cycle refreshes
    # data.json but must never create a session that did not happen.
    if write_history:
        big_hist = history.setdefault("big_orders", {})
        # Later cycles overwrite today's row: volume is cumulative, so the
        # last cycle of the session is the complete one.
        big_hist[session_str] = {
            "rows": [{k: v for k, v in row.items() if k != "tv_symbol"} for row in big_orders],
            "capped": big_orders_capped,
        }

    # ── semi ETF flows context card (fail-soft: null on any failure) ────────
    etf_flows = None
    try:
        etf_flows = build_etf_flows(history, session_str, write_history)
    except Exception as e:
        log(f"WARN etf-flows build failed: {e}")

    # ── context layer: vault brief/catalysts/news/facts + daily bars ────────
    # (added 2026-08, fetcher/context.py). Hourly-gated internally (vault/
    # econ/news) and daily-gated (bars) via fetcher/.context_cache.json — see
    # that module's docstring. Wrapped defensively here the same way
    # etf_flows is just above: every individual fetch inside context.py is
    # already fail-soft, this is belt-and-suspenders so a bug there can never
    # take down the rest of the cycle.
    context_fields: dict = {}
    bars_payload = None
    try:
        context_fields, bars_payload = context.build_context(quotes, PINNED, session_date, now_utc)
    except Exception as e:
        log(f"WARN context build failed: {e}")

    bullish_flow = sum(1 for v in by_ticker.values() if v["direction"] == "BULL")
    bearish_flow = sum(1 for v in by_ticker.values() if v["direction"] == "BEAR")
    firing_count = sum(1 for v in by_ticker.values() if v.get("firing"))
    high_conviction = sum(1 for v in by_ticker.values()
                          if v.get("score_conv") is not None and v["score_conv"] >= 60)

    data = {
        "generated_at": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_at_ct": now_ct.strftime("%Y-%m-%d %H:%M CT"),
        "session_date": session_str,
        "market_state": market_state,
        "universe": {
            "watched": screened,          # size of the curated pinned list
            "candidates": len(candidates),  # of those, how many resolved a quote
            "with_options": with_options,   # of those, how many had a usable chain
            "pinned": len(PINNED),
        },
        "stats": {
            "bullish_flow": bullish_flow,
            "bearish_flow": bearish_flow,
            "firing": firing_count,
            "high_conviction": high_conviction,
        },
        "etf_flows": etf_flows,
        "big_orders": big_orders,
        "big_orders_capped": big_orders_capped,
        "conviction": conviction_cards,
        "swing": swing_cards,
        "notes": {
            "flow_proxy": ("Net flow = call premium traded minus put premium traded "
                           "(volume x last x 100). Free data can't see buy/sell side "
                           "— this is premium changing hands, not directional order flow."),
            "delay": ("Options data is 15-minute delayed (CBOE free feed). Stock prices "
                      "update live every 30s (TradingView Cboe One)."),
            "tilt": ("Aggressor tilt classifies each contract's last trade against its "
                     "bid/ask each refresh (near ask = bought, near bid = sold) and "
                     "accumulates the day's classified premium: calls bought + puts sold "
                     "= bullish, calls sold + puts bought = bearish. It samples one trade "
                     "per contract per ~7-min cycle — a sampled proxy, not the full tape."),
            "flow_pct": ("Flow % is the premium-weighted put/call split for 0-7 DTE: "
                         "whichever side holds the larger share of the dollars traded, "
                         "shown as a percentage. C/P counts contracts, Flow % counts "
                         "dollars — they disagree when one side's options are far more "
                         "expensive, which is how a put-heavy day can hide behind a "
                         "balanced contract ratio. Display only, not a scoring input."),
            "oi_confirm": ("OI-confirm checks whether yesterday's 2wk-6mo flow became "
                           "held positions: open interest up >=25% of yesterday's volume "
                           "= OPENING, down >=25% = CLOSING, else CHURN."),
            "etf_flows": ("Semi ETF flows = day-over-day change in each fund's shares "
                          "outstanding x NAV — real money entering or leaving the fund "
                          "wrapper (ETFs create/destroy shares as money moves), one "
                          "reading per session. Mixes retail and institutional money; "
                          "context only, never a scoring input. 1M flow comes straight "
                          "from TradingView."),
            "big_orders": ("Biggest orders = the options contracts with the most dollars "
                           "traded today across the whole watch list (volume x last x 100), "
                           "strikes within 20% of the stock price, expiring inside 6 months. "
                           "Each row is one contract's WHOLE SESSION, not a single order — "
                           "free data publishes per-contract daily totals, not a trade-by-"
                           "trade tape, so an individual block or sweep can't be seen here. "
                           "As with net flow there is no buy/sell side: a big put row can be "
                           "a hedge, a bearish bet, or someone selling puts. At most "
                           f"{BIG_ORDERS_PER_TICKER} rows per ticker, so one busy name can't "
                           "say the same thing five times; any name that earned more rows "
                           "than it got is listed under the board. Display only."),
        },
        # Context-layer keys (brief/catalysts/news/facts/desk_private/
        # context_updated_at) — each OMITTED entirely when its own build had
        # nothing to show this cycle, never present as null (see
        # DATA_CONTRACT.md). context_fields is {} when context.build_context
        # raised (caught above), so this is a no-op in that case.
        **context_fields,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    data_path = out_dir / "data.json"
    tmp = data_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(data_path)

    # bars.json sidecar (added 2026-08) — only written on cycles that actually
    # rebuilt it (see context.build_context's daily gate); loop.py's `git add
    # -A` over OUT_DIR already covers any new file here, so this needed no
    # loop.py change to start publishing.
    if bars_payload is not None:
        bars_path = out_dir / "bars.json"
        bars_tmp = bars_path.with_suffix(".json.tmp")
        bars_tmp.write_text(json.dumps(bars_payload, indent=2), encoding="utf-8")
        bars_tmp.replace(bars_path)
        log(f"wrote {bars_path} ({bars_path.stat().st_size} bytes)")

    if write_history:
        save_history(out_dir, history)
    save_prev_cycle(new_prev_cycle)

    log(f"wrote {data_path} ({data_path.stat().st_size} bytes)")
    return data


def _print_summary(data: dict) -> None:
    u = data["universe"]
    print(f"\nwatched={u['watched']}  candidates={u['candidates']}  "
          f"with_options={u['with_options']}  pinned={u['pinned']}")
    print(f"stats: {data['stats']}")
    print("\nTop 5 conviction:")
    for c in data["conviction"][:5]:
        print(f"  {c['ticker']:<6} score={c['score']:<3} dir={c['direction']:<4} "
              f"net_flow={c['net_flow']:,.0f} firing={c['firing']}")
    print("\nTop 5 swing:")
    for c in data["swing"][:5]:
        print(f"  {c['ticker']:<6} score={c['score']:<3} dir={c['direction']:<4} "
              f"persist={c['persist']}/{c['persist_max']} flow_5d={c['flow_5d']:,.0f}")


def main() -> int:
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    out_dir_env = os.environ.get("OUT_DIR")
    out_dir = Path(out_dir_env) if out_dir_env else DEFAULT_OUT_DIR
    try:
        data = run_cycle(out_dir, dry_run=dry_run)
    except Exception as e:
        import traceback
        print(f"[build_snapshot] FATAL: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1
    _print_summary(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
