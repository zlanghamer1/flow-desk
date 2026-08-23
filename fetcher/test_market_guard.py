"""Pytest coverage for market_guard's holiday/half-day awareness
(2026-08-23 Fable architect pass, finding 1.1).

Before this, market_guard.py was a pure weekday+clock test with zero holiday
awareness: on a weekday market closure (Labor Day, Thanksgiving, Christmas,
...) should_publish() returned True all day and run_cycle's own market_state
block computed "open", fabricating a phantom trading session into history.json
from stale vendor data. These tests pin the fix at both the guard level and
the day-boundary edges of the half-day shrink.
"""
from __future__ import annotations

from datetime import datetime

from market_guard import (
    TZ_CT,
    _in_session,
    in_extended_window,
    is_market_half_day,
    is_market_holiday,
)


def _ct(y, m, d, h, mi):
    return datetime(y, m, d, h, mi, 0, tzinfo=TZ_CT)


def test_labor_day_2026_is_recognized_as_a_holiday():
    assert is_market_holiday(_ct(2026, 9, 7, 9, 0))
    assert not is_market_holiday(_ct(2026, 9, 8, 9, 0))


def test_labor_day_blocks_both_windows_all_day():
    # An ordinary Monday at 09:00 would be well inside both windows.
    for h, m in [(8, 0), (9, 0), (12, 0), (14, 59), (15, 20)]:
        t = _ct(2026, 9, 7, h, m)
        assert not _in_session(t), f"strict window should reject Labor Day {h}:{m:02d}"
        assert not in_extended_window(t), f"extended window should reject Labor Day {h}:{m:02d}"


def test_thanksgiving_2026_half_day_recognized():
    assert is_market_half_day(_ct(2026, 11, 27, 9, 0))
    assert not is_market_half_day(_ct(2026, 11, 26, 9, 0))  # Thanksgiving itself is a full holiday
    assert is_market_holiday(_ct(2026, 11, 26, 9, 0))


def test_half_day_shrinks_close_to_noon_with_each_windows_own_buffer():
    d = (2026, 11, 27)
    # Morning: both windows open normally.
    assert _in_session(_ct(*d, 9, 0))
    assert in_extended_window(_ct(*d, 9, 0))
    # Strict window's normal +5min buffer becomes 12:05, not 15:05.
    assert _in_session(_ct(*d, 12, 5))
    assert not _in_session(_ct(*d, 12, 6)), "strict window should close at the half-day's own +5min buffer"
    # Extended window's normal +20min buffer becomes 12:20, not 15:20.
    assert in_extended_window(_ct(*d, 12, 20))
    assert not in_extended_window(_ct(*d, 12, 21))


def test_ordinary_weekday_unaffected():
    t = _ct(2026, 9, 8, 9, 0)  # Tuesday, no holiday
    assert _in_session(t)
    assert in_extended_window(t)
