"""Unusual options activity (added 2026-08-21) — options flow flagged as an
outlier against a ticker's OWN trailing baseline, plus a BULLISH/BEARISH/
HEDGING/MIXED heuristic label.

Run: python3 -m pytest fetcher/test_unusual_activity.py

What these tests defend, in order of how badly each would mislead Zach if it
broke:

1. The baseline must never include today's own reading. A trailing average
   contaminated by the very outlier it's measuring understates the ratio —
   exactly the mistake iv_rank's include-today percentile makes for a
   slower-moving series, and the one this feature deliberately avoids for a
   same-day volume spike.
2. Below the minimum history bar, opt_rvol must read None (collecting),
   never a ratio computed against a too-short or empty baseline.
3. HEDGING must fire only for the one signature this data can honestly
   support: put-heavy flow while the stock is NOT falling. A put-heavy day
   where the stock IS falling is BEARISH, not hedging — conflating the two
   would tell Zach a confirmed bearish bet is "just a hedge."
4. Call-heavy flow that disagrees with price action reads MIXED, never
   HEDGING — this data cannot distinguish bought calls from written ones,
   so the mirror-image claim would overreach.
5. The flag threshold gates on the SAME ratio the tests compute — no drift
   between what's stored and what's flagged "unusual."
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_snapshot import (  # noqa: E402
    compute_opt_rvol, options_activity_tag, UOA_HOT_MULT, UOA_MIN_SESSIONS,
    load_history, save_history, MAX_VOL_HISTORY)


# ── compute_opt_rvol ─────────────────────────────────────────────────────────

def test_opt_rvol_collecting_below_minimum_history():
    rvol, collecting = compute_opt_rvol(100_000, [10_000] * (UOA_MIN_SESSIONS - 1))
    assert rvol is None
    assert collecting is True


def test_opt_rvol_computes_once_minimum_history_reached():
    baseline_hist = [10_000] * UOA_MIN_SESSIONS
    rvol, collecting = compute_opt_rvol(30_000, baseline_hist)
    assert collecting is False
    assert rvol == pytest.approx(3.0)


def test_opt_rvol_uses_only_the_trailing_window_not_the_whole_history():
    # 30 sessions of history but only the last UOA_MIN_SESSIONS should count.
    hist = [100_000] * 10 + [10_000] * UOA_MIN_SESSIONS
    rvol, collecting = compute_opt_rvol(30_000, hist)
    assert collecting is False
    assert rvol == pytest.approx(3.0)   # 30k / 10k baseline, the old 100k sessions ignored


def test_opt_rvol_never_divides_by_a_zero_baseline():
    rvol, collecting = compute_opt_rvol(5_000, [0] * UOA_MIN_SESSIONS)
    assert rvol is None
    assert collecting is False   # enough history exists, the baseline is just unusable


def test_opt_rvol_today_is_never_part_of_its_own_baseline():
    # Caller contract: vol_hist_prior must be snapshotted BEFORE today's
    # value is appended. A caller that appended first and passed the
    # resulting list would understate a real 10x spike.
    prior = [10_000] * UOA_MIN_SESSIONS
    today = 100_000
    rvol_correct, _ = compute_opt_rvol(today, prior)
    rvol_contaminated, _ = compute_opt_rvol(today, prior + [today])
    assert rvol_correct == pytest.approx(10.0)
    assert rvol_contaminated < rvol_correct   # the wrong order dilutes the outlier


def test_unusual_flag_threshold_matches_uoa_hot_mult():
    baseline_hist = [10_000] * UOA_MIN_SESSIONS
    rvol_at, _ = compute_opt_rvol(10_000 * UOA_HOT_MULT, baseline_hist)
    # Comfortably below the threshold, clear of compute_opt_rvol's own 2dp rounding.
    rvol_below, _ = compute_opt_rvol(10_000 * (UOA_HOT_MULT - 0.5), baseline_hist)
    assert rvol_at >= UOA_HOT_MULT
    assert rvol_below < UOA_HOT_MULT


# ── options_activity_tag ─────────────────────────────────────────────────────

@pytest.mark.parametrize("flow_side,direction,change_pct,want", [
    ("CALL", "BULL", 2.0, "BULLISH"),
    ("CALL", "BULL", 0.0, "MIXED"),
    ("CALL", "BULL", -1.0, "MIXED"),
    ("PUT", "BEAR", -2.0, "BEARISH"),
    ("PUT", "BEAR", 0.0, "HEDGING"),
    ("PUT", "BEAR", 0.5, "HEDGING"),
    ("PUT", "BEAR", None, "HEDGING"),
    (None, "BULL", 1.0, "BULLISH"),    # no near-money premium -> fall back to direction
    (None, "BEAR", -1.0, "BEARISH"),
])
def test_activity_tag(flow_side, direction, change_pct, want):
    assert options_activity_tag(flow_side, direction, change_pct) == want


def test_hedging_never_fires_when_price_is_actually_falling():
    # The one case this test suite most needs to pin: a confirmed bearish
    # move must never be relabeled a hedge.
    assert options_activity_tag("PUT", "BEAR", -3.5) == "BEARISH"


def test_call_heavy_disagreement_is_mixed_not_a_mirrored_hedge_claim():
    assert options_activity_tag("CALL", "BULL", -2.0) == "MIXED"
    assert options_activity_tag("CALL", "BULL", -2.0) != "HEDGING"


def test_flat_deadband_around_zero_reads_as_flat_both_directions():
    # Small moves inside the deadband must not tip into UP/DOWN.
    assert options_activity_tag("PUT", "BEAR", 0.1) == "HEDGING"
    assert options_activity_tag("PUT", "BEAR", -0.1) == "HEDGING"
    assert options_activity_tag("CALL", "BULL", 0.1) == "MIXED"


# ── history.json vol_history persistence ────────────────────────────────────

def test_vol_history_round_trips_and_defaults_when_absent(tmp_path):
    h = load_history(tmp_path)
    assert h["vol_history"] == {}
    h["vol_history"]["MU"] = [1000.0, 2000.0]
    save_history(tmp_path, h)
    reloaded = load_history(tmp_path)
    assert reloaded["vol_history"]["MU"] == [1000.0, 2000.0]


def test_vol_history_prunes_to_max_length(tmp_path):
    h = load_history(tmp_path)
    h["vol_history"]["MU"] = list(range(MAX_VOL_HISTORY + 10))
    save_history(tmp_path, h)
    reloaded = load_history(tmp_path)
    assert len(reloaded["vol_history"]["MU"]) == MAX_VOL_HISTORY
    # oldest entries dropped, not an arbitrary subset
    assert reloaded["vol_history"]["MU"][0] == 10
    assert reloaded["vol_history"]["MU"][-1] == MAX_VOL_HISTORY + 9


def test_loading_a_legacy_history_file_without_vol_history_key(tmp_path):
    import json
    path = tmp_path / "history.json"
    path.write_text(json.dumps({"sessions": {}, "iv_history": {}}), encoding="utf-8")
    h = load_history(tmp_path)
    assert h["vol_history"] == {}
