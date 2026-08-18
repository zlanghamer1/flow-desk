"""Split-adjustment repair in fetcher/context.py.

Run: python3 -m pytest fetcher/test_split_repair.py -q

Why this exists: Yahoo's chart series for SOXS returned every bar before
2026-05-26 multiplied by exactly 15.0 (1159.50 where Polygon and TradingView
both read 77.30), which drew the drawer's 3M chart as a flat line at the
bottom of a $31-to-$1,660 axis. These tests pin the two halves of the fix that
would hurt if they drifted:

1. A split-sized OVERNIGHT break gets repaired, prices and volumes moving
   reciprocally, and the estimated factor snaps to the clean ratio.
2. A real crash — a modest gap followed by a big INTRADAY move — is left
   alone. The live universe's only other outsized gaps (NBIS, BE, APLD, all
   ~0.65) are real news, and rescaling any of them would invent a history.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import context  # noqa: E402


def _bar(o, h, l, c, v):
    return [o, h, l, c, v]


def test_repairs_a_split_sized_overnight_break():
    # the live SOXS shape: four bars near 1,200 (15x too high), then the same
    # fund trading in the 60s from the break onward
    rows = [_bar(1200, 1209, 1125, 1159.5, 1_883_589),
            _bar(69.0, 69.5, 61.9, 62.9, 40_368_300),
            _bar(58.3, 69.1, 58.3, 65.3, 53_730_730)]
    f = context._repair_split_breaks(rows, "SOXS")
    assert f == 15.0                                   # 16.80 raw, snapped
    assert round(rows[0][3], 2) == 77.30               # matches Polygon/TV
    assert rows[0][4] == 28_253_835                    # volume scaled the other way
    assert rows[1][3] == 62.9 and rows[2][3] == 65.3   # newer bars untouched


def test_leaves_a_real_crash_alone():
    # 2025-04-09: SOXS closed -56% but OPENED only -2% — the move was intraday,
    # which is exactly what separates a crash from a split.
    rows = [_bar(112200, 150510, 106500, 141060, 26965),
            _bar(137910, 141600, 57000, 62100, 56501),
            _bar(70710, 82920, 69510, 76350, 44542)]
    before = [r[:] for r in rows]
    assert context._repair_split_breaks(rows, "SOXS") is None
    assert rows == before


def test_leaves_a_real_news_gap_alone():
    # NBIS's live 0.66 overnight gap — the largest real one in the universe
    rows = [_bar(63.0, 65.0, 62.0, 64.06, 5_000_000),
            _bar(97.2, 99.0, 94.0, 95.5, 20_000_000)]
    before = [r[:] for r in rows]
    assert context._repair_split_breaks(rows, "NBIS") is None
    assert rows == before


def test_multiple_breaks_compose():
    rows = [_bar(1000, 1010, 990, 1000, 100),
            _bar(100, 105, 95, 100, 1000),      # 10x break
            _bar(25, 26, 24, 25, 4000),         # 4x break
            _bar(25, 27, 24, 26, 4100)]
    f = context._repair_split_breaks(rows, "TEST")
    assert f == 40.0
    assert rows[0][3] == 25.0 and rows[1][3] == 25.0
    assert rows[0][4] == 4000 and rows[1][4] == 4000


def test_intraday_rows_use_the_timestamp_offset():
    rows = [[1000, 1200, 1209, 1125, 1159.5, 1_883_589],
            [2000, 69.0, 69.5, 61.9, 62.9, 40_368_300]]
    assert context._repair_split_breaks(rows, "SOXS", off=1) == 15.0
    assert rows[0][0] == 1000                          # timestamp never rescaled
    assert round(rows[0][4], 2) == 77.30


def test_missing_volume_stays_none():
    rows = [_bar(1200, 1209, 1125, 1159.5, None),
            _bar(69.0, 69.5, 61.9, 62.9, 40_368_300)]
    context._repair_split_breaks(rows, "SOXS")
    assert rows[0][4] is None


def test_short_or_empty_series_is_a_no_op():
    assert context._repair_split_breaks([], "X") is None
    assert context._repair_split_breaks([_bar(1, 1, 1, 1, 1)], "X") is None


def test_unclean_factor_is_used_as_measured():
    # nothing within 15% of a clean ratio -> rescale by the raw estimate rather
    # than snapping to a wrong one
    assert context._snap_split_ratio(1.4) == 1.4
    assert context._snap_split_ratio(9.7) == 10.0
    assert round(context._snap_split_ratio(1 / 16.8), 5) == round(1 / 15.0, 5)
