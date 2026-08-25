"""gamma_history.json persistence + write-gating (build_snapshot.py).

Added 2026-08-24, Zach's freeze lift "Lift the freeze for gamma snapshots".
Mirrors test_framework_score.py's consensus_history persistence tests in
style — a plain round-trip/prune/fail-soft suite for the disk layer, plus
coverage of apply_gamma_history_cycle's write_history gate, same-session
overwrite, absent/None-gamma no-row rule, and spot recording.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from build_snapshot import (  # noqa: E402
    apply_gamma_history_cycle,
    load_gamma_history,
    save_gamma_history,
    MAX_GAMMA_HISTORY_SESSIONS,
)


def _gamma(spot=100.0):
    return {
        "spot": spot,
        "dte_hi": 45,
        "levels": [{"strike": 100.0, "gamma_oi": 123.0, "oi": 10, "pct": 100.0}],
        "peak_strike": 100.0,
        "total_gamma_oi": 123.0,
        "expiries_used": 1,
        "contracts_used": 20,
        "computed_from": "cboe_delayed_chain",
    }


# ── disk round-trip ─────────────────────────────────────────────────────────

def test_gamma_history_round_trips_through_disk(tmp_path):
    hist = {"v": 1, "daily": {"MU": {"2026-08-24": _gamma()}}}
    save_gamma_history(tmp_path, hist)
    reloaded = load_gamma_history(tmp_path)
    assert reloaded["daily"]["MU"]["2026-08-24"]["spot"] == pytest.approx(100.0)
    assert reloaded["v"] == 1


def test_gamma_history_load_is_fail_soft_on_missing_file(tmp_path):
    reloaded = load_gamma_history(tmp_path / "does-not-exist")
    assert reloaded == {"v": 1, "daily": {}}


def test_gamma_history_load_is_fail_soft_on_corrupt_file(tmp_path):
    path = tmp_path / "gamma_history.json"
    path.write_text("{not valid json", encoding="utf-8")
    reloaded = load_gamma_history(tmp_path)
    assert reloaded == {"v": 1, "daily": {}}


def test_gamma_history_load_rejects_non_dict_payload(tmp_path):
    path = tmp_path / "gamma_history.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    reloaded = load_gamma_history(tmp_path)
    assert reloaded == {"v": 1, "daily": {}}


def test_gamma_history_prunes_to_max_sessions_per_ticker(tmp_path):
    sessions = {f"2020-01-{i:02d}": _gamma() for i in range(1, 32)}
    # pad past MAX_GAMMA_HISTORY_SESSIONS with distinct fabricated keys
    sessions = {f"s{i:04d}": _gamma() for i in range(MAX_GAMMA_HISTORY_SESSIONS + 30)}
    hist = {"v": 1, "daily": {"MU": sessions}}
    save_gamma_history(tmp_path, hist)
    reloaded = load_gamma_history(tmp_path)
    assert len(reloaded["daily"]["MU"]) == MAX_GAMMA_HISTORY_SESSIONS
    # oldest (lowest sort order) keys are the ones dropped
    assert "s0000" not in reloaded["daily"]["MU"]
    assert f"s{MAX_GAMMA_HISTORY_SESSIONS + 29:04d}" in reloaded["daily"]["MU"]


def test_gamma_history_prune_is_per_ticker(tmp_path):
    big = {f"s{i:04d}": _gamma() for i in range(MAX_GAMMA_HISTORY_SESSIONS + 5)}
    small = {"2026-08-24": _gamma()}
    hist = {"v": 1, "daily": {"MU": big, "COHR": small}}
    save_gamma_history(tmp_path, hist)
    reloaded = load_gamma_history(tmp_path)
    assert len(reloaded["daily"]["MU"]) == MAX_GAMMA_HISTORY_SESSIONS
    assert len(reloaded["daily"]["COHR"]) == 1


# ── apply_gamma_history_cycle (the write-gating logic) ─────────────────────

def test_apply_gamma_history_cycle_writes_when_write_history_true():
    gh = {"v": 1, "daily": {}}
    apply_gamma_history_cycle(gh, {"MU": _gamma()}, {"MU": 210.35}, "2026-08-24", True)
    assert gh["daily"]["MU"]["2026-08-24"]["spot"] == pytest.approx(210.35)


def test_apply_gamma_history_cycle_skips_write_when_write_history_false():
    gh = {"v": 1, "daily": {}}
    apply_gamma_history_cycle(gh, {"MU": _gamma()}, {"MU": 210.35}, "2026-08-24", False)
    assert gh["daily"] == {}


def test_apply_gamma_history_cycle_overwrites_same_session():
    gh = {"v": 1, "daily": {}}
    apply_gamma_history_cycle(gh, {"MU": _gamma(spot=100.0)}, {"MU": 100.0}, "2026-08-24", True)
    apply_gamma_history_cycle(gh, {"MU": _gamma(spot=101.0)}, {"MU": 101.0}, "2026-08-24", True)
    assert len(gh["daily"]["MU"]) == 1
    assert gh["daily"]["MU"]["2026-08-24"]["spot"] == pytest.approx(101.0)


def test_apply_gamma_history_cycle_absent_gamma_writes_no_row():
    gh = {"v": 1, "daily": {}}
    apply_gamma_history_cycle(gh, {"MU": None}, {"MU": 210.35}, "2026-08-24", True)
    assert "MU" not in gh["daily"]


def test_apply_gamma_history_cycle_none_gamma_among_others_writes_no_row_for_it():
    gh = {"v": 1, "daily": {}}
    apply_gamma_history_cycle(
        gh, {"MU": _gamma(), "SKHY": None}, {"MU": 210.35, "SKHY": 50.0},
        "2026-08-24", True,
    )
    assert "MU" in gh["daily"]
    assert "SKHY" not in gh["daily"]


def test_apply_gamma_history_cycle_records_spot_alongside_gamma_object():
    gh = {"v": 1, "daily": {}}
    g = _gamma(spot=210.35)
    apply_gamma_history_cycle(gh, {"MU": g}, {"MU": 210.35}, "2026-08-24", True)
    row = gh["daily"]["MU"]["2026-08-24"]
    assert row["spot"] == pytest.approx(210.35)
    # the rest of the published gamma object rides along unchanged
    assert row["peak_strike"] == pytest.approx(100.0)
    assert row["contracts_used"] == 20


def test_apply_gamma_history_cycle_preserves_prior_sessions_for_same_ticker():
    gh = {"v": 1, "daily": {}}
    apply_gamma_history_cycle(gh, {"MU": _gamma()}, {"MU": 100.0}, "2026-08-20", True)
    apply_gamma_history_cycle(gh, {"MU": _gamma()}, {"MU": 105.0}, "2026-08-24", True)
    assert set(gh["daily"]["MU"].keys()) == {"2026-08-20", "2026-08-24"}


# ── null-spot guard + absent-ticker leave-alone (2026-08-24 review fixes) ───

def test_apply_gamma_history_cycle_null_spot_writes_no_row():
    gh = {"v": 1, "daily": {}}
    apply_gamma_history_cycle(gh, {"MU": _gamma()}, {"MU": None}, "2026-08-24", True)
    assert "MU" not in gh["daily"]


def test_apply_gamma_history_cycle_nonpositive_spot_writes_no_row():
    gh = {"v": 1, "daily": {}}
    apply_gamma_history_cycle(gh, {"MU": _gamma()}, {"MU": 0}, "2026-08-24", True)
    assert "MU" not in gh["daily"]


def test_apply_gamma_history_cycle_null_spot_leaves_prior_same_session_entry():
    gh = {"v": 1, "daily": {"MU": {"2026-08-24": {**_gamma(), "spot": 101.5}}}}
    apply_gamma_history_cycle(gh, {"MU": _gamma()}, {"MU": None}, "2026-08-24", True)
    assert gh["daily"]["MU"]["2026-08-24"]["spot"] == 101.5


def test_apply_gamma_history_cycle_ticker_absent_from_cycle_leaves_entry_untouched():
    gh = {"v": 1, "daily": {"MU": {"2026-08-24": {**_gamma(), "spot": 101.5}}}}
    apply_gamma_history_cycle(gh, {"CRWD": _gamma()}, {"CRWD": 400.0}, "2026-08-24", True)
    assert gh["daily"]["MU"]["2026-08-24"]["spot"] == 101.5
    assert "CRWD" in gh["daily"]
