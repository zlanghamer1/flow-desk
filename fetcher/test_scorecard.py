"""Call scorecard (fetcher/scorecard.py, added 2026-09-12).

Pins: the write_history gate, the positive-spot rule, same-day overwrite,
the 21-session grading arithmetic against bars.json's calendar (a call date
on the calendar, a call date missing from it, a call too young to grade,
a name with no close on the target date), hit/miss per call type, the SPY
comparison, the row cap, the optional-key omission, and the disk layer.
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import scorecard  # noqa: E402
from scorecard import (  # noqa: E402
    MAX_VERDICT_HISTORY_SESSIONS,
    SCORECARD_MAX_ROWS,
    compute_scorecard,
    load_verdict_history,
    record_calls,
    save_verdict_history,
)
from verdict import VERDICT_HORIZON_DAYS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


# ── helpers ─────────────────────────────────────────────────────────────────

def _weekdays(start: str, n: int) -> list[str]:
    d = date.fromisoformat(start)
    out = []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _bars(sessions: list[str], closes: dict[str, list[float]], built: str | None = None) -> dict:
    """A bars.json v4 payload: every ticker's rows line up with the TAIL of
    `sessions` (shorter histories are allowed, like the real file)."""
    bars = {}
    for t, cl in closes.items():
        bars[t] = [[c, c, c, c, 1000] for c in cl]
    return {"v": 4, "built": built or sessions[-1], "sessions": sessions, "bars": bars, "bar_dates": {}}


def _verdicts(calls: dict[str, tuple[str | None, int | None]]) -> dict:
    return {"by_ticker": {t: {"call": c, "score": s} for t, (c, s) in calls.items()}}


# ── record_calls ────────────────────────────────────────────────────────────

def test_record_calls_logs_call_score_spot_and_spy_spot():
    vh = {"v": 1, "sessions": {}}
    n = record_calls(vh, _verdicts({"MU": ("BUY", 69), "LLY": ("HOLD", 12)}),
                     {"MU": 977.4, "SPY": 650.0}, {"LLY": {"close": 800.0}}, "2026-09-14", True)
    assert n == 2
    row = vh["sessions"]["2026-09-14"]
    assert row["spy_spot"] == pytest.approx(650.0)
    assert row["calls"]["MU"] == {"call": "BUY", "score": 69, "spot": 977.4}
    assert row["calls"]["LLY"] == {"call": "HOLD", "score": 12, "spot": 800.0}


def test_record_calls_skips_when_write_history_false():
    vh = {"v": 1, "sessions": {}}
    assert record_calls(vh, _verdicts({"MU": ("BUY", 69)}), {"MU": 1.0}, {}, "2026-09-14", False) == 0
    assert vh["sessions"] == {}


def test_record_calls_skips_no_call_and_no_spot():
    vh = {"v": 1, "sessions": {}}
    n = record_calls(vh, _verdicts({"SOXL": (None, None), "MU": ("BUY", 69), "CRWD": ("SELL", -40)}),
                     {"MU": 977.4, "CRWD": None}, {"CRWD": {"close": 0}}, "2026-09-14", True)
    assert n == 1
    assert set(vh["sessions"]["2026-09-14"]["calls"]) == {"MU"}


def test_record_calls_same_session_overwrites_and_keeps_absent_ticker():
    vh = {"v": 1, "sessions": {}}
    record_calls(vh, _verdicts({"MU": ("BUY", 60), "CRWD": ("SELL", -50)}),
                 {"MU": 100.0, "CRWD": 200.0}, {}, "2026-09-14", True)
    record_calls(vh, _verdicts({"MU": ("HOLD", 20)}), {"MU": 101.0}, {}, "2026-09-14", True)
    calls = vh["sessions"]["2026-09-14"]["calls"]
    assert calls["MU"] == {"call": "HOLD", "score": 20, "spot": 101.0}
    assert calls["CRWD"]["spot"] == 200.0


def test_record_calls_leaves_no_phantom_session_when_nothing_usable():
    vh = {"v": 1, "sessions": {}}
    assert record_calls(vh, _verdicts({"SOXL": (None, None)}), {}, {}, "2026-09-14", True) == 0
    assert vh["sessions"] == {}


def test_record_calls_tolerates_absent_verdicts():
    vh = {"v": 1, "sessions": {}}
    assert record_calls(vh, None, {}, {}, "2026-09-14", True) == 0
    assert vh["sessions"] == {}


# ── compute_scorecard: grading arithmetic ───────────────────────────────────

H = VERDICT_HORIZON_DAYS


def test_compute_scorecard_none_when_nothing_logged():
    assert compute_scorecard({"v": 1, "sessions": {}}, None) is None
    assert compute_scorecard({}, None) is None


def test_call_on_calendar_grades_against_the_21st_session_after_it():
    sessions = _weekdays("2026-01-05", 40)
    call_date = sessions[5]
    target = sessions[5 + H]
    mu = [100.0] * 40
    mu[5 + H] = 110.0          # close on the 21st session after the call
    mu[5 + H - 1] = 50.0       # the session before it must NOT be read
    spy = [500.0] * 40
    spy[5 + H] = 505.0
    bars = _bars(sessions, {"MU": mu, "SPY": spy})
    vh = {"sessions": {call_date: {"spy_spot": 500.0, "calls": {"MU": {"call": "BUY", "score": 60, "spot": 100.0}}}}}
    sc = compute_scorecard(vh, bars)
    assert sc["rows"][0]["close_date"] == target
    assert sc["rows"][0]["close"] == 110.0
    assert sc["rows"][0]["move"] == pytest.approx(0.10)
    assert sc["rows"][0]["spy_move"] == pytest.approx(0.01)
    assert sc["rows"][0]["hit"] is True
    assert sc["resolved"]["buy"] == {"n": 1, "hits": 1, "misses": 0, "avg_move": 0.1,
                                     "avg_vs_spy": pytest.approx(0.09), "n_vs_spy": 1}
    assert sc["open"] == {"buy": 0, "sell": 0, "hold": 0}
    assert sc["earliest_open"] is None
    assert sc["calls_logged"] == 1 and sc["rows_total"] == 1


def test_call_date_missing_from_calendar_uses_the_sessions_after_it():
    # a call logged on a day bars.json never carries (a half-day the daily
    # build skipped) still grades on the 21st session strictly after it
    sessions = _weekdays("2026-01-05", 40)
    call_date = "2026-01-10"   # a Saturday: not in the weekday calendar
    after = [s for s in sessions if s > call_date]
    target = after[H - 1]
    mu = [100.0] * 40
    mu[sessions.index(target)] = 90.0
    bars = _bars(sessions, {"MU": mu})
    vh = {"sessions": {call_date: {"calls": {"MU": {"call": "SELL", "score": -60, "spot": 100.0}}}}}
    sc = compute_scorecard(vh, bars)
    row = sc["rows"][0]
    assert row["close_date"] == target and row["hit"] is True and row["spy_move"] is None
    assert sc["resolved"]["sell"]["hits"] == 1
    assert sc["resolved"]["sell"]["n_vs_spy"] == 0 and sc["resolved"]["sell"]["avg_vs_spy"] is None


def test_call_too_young_stays_open_with_sessions_left():
    sessions = _weekdays("2026-01-05", 30)
    call_date = sessions[20]     # only 9 sessions have followed
    bars = _bars(sessions, {"MU": [100.0] * 30})
    vh = {"sessions": {call_date: {"calls": {
        "MU": {"call": "BUY", "score": 60, "spot": 100.0},
        "LLY": {"call": "HOLD", "score": 5, "spot": 100.0},
    }}}}
    sc = compute_scorecard(vh, bars)
    assert sc["rows"] == []
    assert sc["open"] == {"buy": 1, "sell": 0, "hold": 1}
    assert sc["earliest_open"] == {"date": call_date, "sessions_elapsed": 9, "sessions_left": H - 9}


def test_call_newer_than_the_calendar_reads_zero_elapsed():
    sessions = _weekdays("2026-01-05", 30)
    bars = _bars(sessions, {"MU": [100.0] * 30})
    vh = {"sessions": {"2026-03-02": {"calls": {"MU": {"call": "BUY", "score": 60, "spot": 100.0}}}}}
    sc = compute_scorecard(vh, bars)
    assert sc["earliest_open"] == {"date": "2026-03-02", "sessions_elapsed": 0, "sessions_left": H}


def test_no_calendar_keeps_every_call_open_and_bars_built_null():
    vh = {"sessions": {"2026-01-05": {"calls": {"MU": {"call": "BUY", "score": 60, "spot": 100.0}}}}}
    sc = compute_scorecard(vh, None)
    assert sc["bars_built"] is None
    assert sc["open"]["buy"] == 1 and sc["rows"] == []
    assert sc["earliest_open"]["sessions_elapsed"] == 0


def test_name_without_a_close_on_the_target_date_is_unresolvable_not_guessed():
    sessions = _weekdays("2026-01-05", 40)
    call_date = sessions[5]
    # SKHY listed late: only the last 10 sessions of history, none at the target
    bars = _bars(sessions, {"MU": [100.0] * 40, "SKHY": [50.0] * 10})
    vh = {"sessions": {call_date: {"calls": {
        "MU": {"call": "BUY", "score": 60, "spot": 100.0},
        "SKHY": {"call": "BUY", "score": 60, "spot": 50.0},
    }}}}
    sc = compute_scorecard(vh, bars)
    assert sc["unresolvable"] == 1
    assert [r["ticker"] for r in sc["rows"]] == ["MU"]
    assert sc["open"] == {"buy": 0, "sell": 0, "hold": 0}


def test_hit_rule_per_call_type_and_flat_is_a_miss():
    sessions = _weekdays("2026-01-05", 40)
    call_date = sessions[0]
    t = H  # target index for a call on sessions[0]
    def series(end):
        s = [100.0] * 40
        s[t] = end
        return s
    bars = _bars(sessions, {"UP": series(101.0), "DN": series(99.0), "FLAT": series(100.0),
                            "HB": series(101.0), "HS": series(99.0)})
    vh = {"sessions": {call_date: {"calls": {
        "UP": {"call": "BUY", "score": 50, "spot": 100.0},
        "DN": {"call": "BUY", "score": 50, "spot": 100.0},
        "FLAT": {"call": "BUY", "score": 50, "spot": 100.0},
        "HB": {"call": "SELL", "score": -50, "spot": 100.0},
        "HS": {"call": "SELL", "score": -50, "spot": 100.0},
        "H": {"call": "HOLD", "score": 0, "spot": 100.0},
    }}}}
    bars["bars"]["H"] = bars["bars"]["UP"]
    sc = compute_scorecard(vh, bars)
    hits = {r["ticker"]: r["hit"] for r in sc["rows"]}
    assert hits == {"UP": True, "DN": False, "FLAT": False, "HB": False, "HS": True, "H": None}
    assert sc["resolved"]["buy"] == {"n": 3, "hits": 1, "misses": 2, "avg_move": pytest.approx(0.0),
                                     "avg_vs_spy": None, "n_vs_spy": 0}
    assert sc["resolved"]["sell"]["hits"] == 1 and sc["resolved"]["sell"]["misses"] == 1
    assert sc["resolved"]["hold"] == {"n": 1, "avg_move": 0.01, "avg_vs_spy": None, "n_vs_spy": 0}
    assert "hits" not in sc["resolved"]["hold"]


def test_rows_newest_first_and_capped_while_counts_cover_everything():
    n_days = SCORECARD_MAX_ROWS + 10 + H + 1
    sessions = _weekdays("2025-01-06", n_days)
    bars = _bars(sessions, {"MU": [float(100 + i) for i in range(n_days)]})
    vh = {"sessions": {sessions[i]: {"calls": {"MU": {"call": "BUY", "score": 50, "spot": 100.0 + i}}}
                       for i in range(SCORECARD_MAX_ROWS + 10)}}
    sc = compute_scorecard(vh, bars)
    assert sc["rows_total"] == SCORECARD_MAX_ROWS + 10
    assert len(sc["rows"]) == SCORECARD_MAX_ROWS
    assert sc["rows"][0]["date"] > sc["rows"][-1]["date"]
    assert sc["resolved"]["buy"]["n"] == SCORECARD_MAX_ROWS + 10
    assert sc["resolved"]["buy"]["hits"] == SCORECARD_MAX_ROWS + 10   # a rising series
    assert sc["since"] == sessions[0] and sc["sessions_logged"] == SCORECARD_MAX_ROWS + 10


def test_horizon_is_the_verdict_layers_own_constant():
    assert scorecard.VERDICT_HORIZON_DAYS == VERDICT_HORIZON_DAYS == 21


# ── disk layer ──────────────────────────────────────────────────────────────

def test_verdict_history_round_trips_and_prunes(tmp_path):
    vh = {"v": 1, "sessions": {f"s{i:04d}": {"calls": {}} for i in range(MAX_VERDICT_HISTORY_SESSIONS + 7)}}
    save_verdict_history(tmp_path, vh)
    back = load_verdict_history(tmp_path)
    assert len(back["sessions"]) == MAX_VERDICT_HISTORY_SESSIONS
    assert "s0000" not in back["sessions"] and f"s{MAX_VERDICT_HISTORY_SESSIONS + 6:04d}" in back["sessions"]
    assert back["v"] == 1


def test_verdict_history_load_is_fail_soft(tmp_path):
    assert load_verdict_history(tmp_path / "nope") == {"v": 1, "sessions": {}}
    (tmp_path / "verdict_history.json").write_text("{bad", encoding="utf-8")
    assert load_verdict_history(tmp_path) == {"v": 1, "sessions": {}}
    (tmp_path / "verdict_history.json").write_text("[1]", encoding="utf-8")
    assert load_verdict_history(tmp_path) == {"v": 1, "sessions": {}}
    (tmp_path / "verdict_history.json").write_text(json.dumps({"v": 1, "sessions": 3}), encoding="utf-8")
    assert load_verdict_history(tmp_path)["sessions"] == {}


# ── build_snapshot wiring ───────────────────────────────────────────────────

def test_build_snapshot_wires_scorecard():
    src = (ROOT / "fetcher" / "build_snapshot.py").read_text(encoding="utf-8")
    assert "import scorecard" in src
    assert '**({"scorecard": scorecard_block} if scorecard_block else {})' in src
    assert "scorecard.save_verdict_history(out_dir, verdict_history)" in src
    # the save sits inside the write_history block, like every history file
    tail = src[src.index("if write_history:\n        save_history(out_dir, history)"):]
    assert "scorecard.save_verdict_history" in tail.split("save_prev_cycle")[0]
