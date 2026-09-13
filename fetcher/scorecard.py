"""Call scorecard — how the desk's own verdicts did (added 2026-09-12).

Payload shape: DATA_CONTRACT.md -> "Scorecard (added 2026-09-12)" and
"verdict_history.json".

Every cycle records the calls fetcher/verdict.py published (BUY / HOLD /
SELL, with the score and the cycle spot) into `verdict_history.json` on the
`data` branch, one row per (session, ticker). Once bars.json carries
VERDICT_HORIZON_DAYS (21) settled sessions after a call's session, the call
is graded against the close on that 21st session: a BUY is right when the
name closed higher than the spot it was called at, a SELL when it closed
lower. HOLD rows resolve too (the move prints) but are never right or wrong.
SPY's move over the same window is recorded beside every graded row.

The page reads `data.json.scorecard` and never re-derives a grade
(standing ban 10's "computed in the fetcher, read by the page" posture).
Nothing here feeds a board score or a verdict; it only reports what past
verdicts did. The horizon is the verdict layer's own pre-registered
VERDICT_HORIZON_DAYS, read from that module so the two can never drift.

Run: python3 -m pytest fetcher/test_scorecard.py -q
"""
from __future__ import annotations

import json
from bisect import bisect_right
from pathlib import Path

from verdict import VERDICT_HORIZON_DAYS, closes_of, cycle_spot, dates_of

# Sessions kept in verdict_history.json, oldest pruned first on save. Same
# horizon class as gamma_history (~ a year of sessions).
MAX_VERDICT_HISTORY_SESSIONS = 250

# Resolved rows published newest first, capped so data.json stays small; the
# summary counts still cover every resolved row in the history.
SCORECARD_MAX_ROWS = 60

GRADED_CALLS = ("BUY", "SELL")
LOGGED_CALLS = ("BUY", "SELL", "HOLD")


# ── verdict_history.json persistence (same pattern as gamma_history) ────────

def load_verdict_history(out_dir) -> dict:
    """verdict_history.json from OUT_DIR, fail-soft: a missing, corrupt or
    non-dict file reads as an empty history, never raises."""
    path = Path(out_dir) / "verdict_history.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("not a dict")
        if not isinstance(raw.get("sessions"), dict):
            raw["sessions"] = {}
        return raw
    except Exception:
        return {"v": 1, "sessions": {}}


def save_verdict_history(out_dir, verdict_history: dict) -> None:
    sessions = verdict_history.get("sessions", {})
    if isinstance(sessions, dict) and len(sessions) > MAX_VERDICT_HISTORY_SESSIONS:
        for k in sorted(sessions.keys())[:-MAX_VERDICT_HISTORY_SESSIONS]:
            del sessions[k]
    verdict_history["v"] = 1
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "verdict_history.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(verdict_history, indent=2), encoding="utf-8")
    tmp.replace(path)


# ── per-cycle recording ──────────────────────────────────────────────────────

def record_calls(verdict_history: dict, verdicts: dict | None,
                 spot_by_ticker: dict | None, quotes: dict | None,
                 session_str: str, write_history: bool) -> int:
    """Fold this cycle's published calls into verdict_history in place.
    Returns the number of calls recorded this cycle.

    Same write_history gate as every other history writer: a forced
    closed-day cycle never fabricates a session. Only a ticker with a real
    call (BUY / HOLD / SELL) AND a positive cycle spot is logged -- a call
    with no entry price can never be graded, so it is skipped rather than
    stored unevaluable (the gamma_history null-spot rule). A same-day re-run
    OVERWRITES the session's rows: the last cycle of the day is the one
    closest to the close, which is the entry price a 21-session read should
    be measured from. A ticker absent from this cycle keeps any earlier
    same-session row.
    """
    if not write_history or not isinstance(verdicts, dict):
        return 0
    by_ticker = verdicts.get("by_ticker")
    if not isinstance(by_ticker, dict):
        return 0
    sessions = verdict_history.setdefault("sessions", {})
    row = sessions.setdefault(session_str, {})
    calls = row.setdefault("calls", {})
    spy_spot = cycle_spot("SPY", spot_by_ticker, quotes)
    if spy_spot is not None:
        row["spy_spot"] = spy_spot
    n = 0
    for ticker, entry in by_ticker.items():
        if not isinstance(entry, dict):
            continue
        call = entry.get("call")
        if call not in LOGGED_CALLS:
            continue
        spot = cycle_spot(ticker, spot_by_ticker, quotes)
        if spot is None:
            continue
        score = entry.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            score = None
        calls[ticker] = {"call": call, "score": score, "spot": spot}
        n += 1
    if n == 0 and not calls and "spy_spot" not in row:
        # nothing usable this cycle and nothing from an earlier one: do not
        # leave an empty phantom session behind
        del sessions[session_str]
    return n


# ── grading ──────────────────────────────────────────────────────────────────

def _target_index(sessions: list[str], call_date: str, horizon: int) -> int:
    """Index in `sessions` of the `horizon`-th settled session AFTER
    `call_date`. bisect_right counts the sessions on or before the call
    date, so the first session after it sits at that count and the
    horizon-th at count + horizon - 1. A call date missing from the calendar
    (bars built before that day, or a holiday key) lands on the same
    arithmetic: the sessions strictly before it are the count."""
    return bisect_right(sessions, call_date) + horizon - 1


def _close_on(bars_payload: dict, ticker: str, date: str) -> float | None:
    closes = closes_of(bars_payload, ticker)
    dates = dates_of(bars_payload, ticker, len(closes))
    if not closes or dates is None:
        return None
    try:
        i = dates.index(date)
    except ValueError:
        return None
    return closes[i]


def _mean(xs: list[float]) -> float | None:
    return round(sum(xs) / len(xs), 4) if xs else None


def compute_scorecard(verdict_history: dict, bars_payload: dict | None,
                      horizon: int = VERDICT_HORIZON_DAYS) -> dict | None:
    """The whole `scorecard` payload, or None when no session has ever been
    logged (the caller omits the key entirely, per the optional-key
    convention -- the page then keeps the slot with a one-line reason).

    Grading needs bars.json's session calendar. Without one (no payload, or
    a pre-v4 payload with no "sessions" list) every call stays open and
    `bars_built` reads null, so the page can say why nothing has resolved.
    """
    sessions_hist = verdict_history.get("sessions") if isinstance(verdict_history, dict) else None
    if not isinstance(sessions_hist, dict) or not sessions_hist:
        return None

    calendar: list[str] = []
    if isinstance(bars_payload, dict) and isinstance(bars_payload.get("sessions"), list):
        calendar = [d for d in bars_payload["sessions"] if isinstance(d, str)]
    bars_built = bars_payload.get("built") if isinstance(bars_payload, dict) else None

    open_counts = {"buy": 0, "sell": 0, "hold": 0}
    unresolvable = 0
    resolved_rows: list[dict] = []
    calls_logged = 0
    earliest_open: dict | None = None

    for call_date in sorted(sessions_hist.keys()):
        srow = sessions_hist[call_date]
        calls = srow.get("calls") if isinstance(srow, dict) else None
        if not isinstance(calls, dict):
            continue
        spy_spot = srow.get("spy_spot") if isinstance(srow, dict) else None
        if isinstance(spy_spot, bool) or not isinstance(spy_spot, (int, float)) or spy_spot <= 0:
            spy_spot = None

        target_i = _target_index(calendar, call_date, horizon) if calendar else None
        reached = target_i is not None and target_i < len(calendar)
        target_date = calendar[target_i] if reached else None
        spy_close = _close_on(bars_payload, "SPY", target_date) if reached else None
        elapsed = (len(calendar) - bisect_right(calendar, call_date)) if calendar else 0

        for ticker in sorted(calls.keys()):
            c = calls[ticker]
            if not isinstance(c, dict):
                continue
            call = c.get("call")
            spot = c.get("spot")
            if call not in LOGGED_CALLS or isinstance(spot, bool) \
                    or not isinstance(spot, (int, float)) or spot <= 0:
                continue
            calls_logged += 1
            close = _close_on(bars_payload, ticker, target_date) if reached else None
            if close is None:
                if reached:
                    # the calendar reached the horizon but this name has no
                    # close on that date (short history, a calendar gap):
                    # never guessed, counted separately
                    unresolvable += 1
                else:
                    open_counts[call.lower()] += 1
                    if earliest_open is None:
                        earliest_open = {
                            "date": call_date,
                            "sessions_elapsed": elapsed,
                            "sessions_left": max(0, horizon - elapsed),
                        }
                continue
            move = close / spot - 1.0
            spy_move = (spy_close / spy_spot - 1.0) if (spy_close and spy_spot) else None
            hit = None
            if call == "BUY":
                hit = move > 0
            elif call == "SELL":
                hit = move < 0
            resolved_rows.append({
                "date": call_date,
                "ticker": ticker,
                "call": call,
                "score": c.get("score"),
                "spot": spot,
                "close": close,
                "close_date": target_date,
                "move": round(move, 4),
                "spy_move": round(spy_move, 4) if spy_move is not None else None,
                "hit": hit,
            })

    def _summary(call: str) -> dict:
        rows = [r for r in resolved_rows if r["call"] == call]
        out = {
            "n": len(rows),
            "avg_move": _mean([r["move"] for r in rows]),
            "avg_vs_spy": _mean([r["move"] - r["spy_move"] for r in rows if r["spy_move"] is not None]),
            "n_vs_spy": sum(1 for r in rows if r["spy_move"] is not None),
        }
        if call in GRADED_CALLS:
            out["hits"] = sum(1 for r in rows if r["hit"])
            out["misses"] = sum(1 for r in rows if r["hit"] is False)
        return out

    resolved_rows.sort(key=lambda r: (r["date"], r["ticker"]), reverse=True)
    return {
        "v": 1,
        "horizon_days": horizon,
        "since": min(sessions_hist.keys()),
        "sessions_logged": len(sessions_hist),
        "calls_logged": calls_logged,
        "bars_built": bars_built,
        "open": open_counts,
        "unresolvable": unresolvable,
        "earliest_open": earliest_open,
        "resolved": {"buy": _summary("BUY"), "sell": _summary("SELL"), "hold": _summary("HOLD")},
        "rows_total": len(resolved_rows),
        "rows": resolved_rows[:SCORECARD_MAX_ROWS],
    }
