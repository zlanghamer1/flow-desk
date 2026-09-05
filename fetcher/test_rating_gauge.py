"""The analyst rating gauge and its five buckets (added 2026-09-05).

Three bugs shipped together on the Forecast tab and each hid the next:

1. The fetch asked for three of the scanner's five rating buckets and printed
   the shortfall as "N of M not bucketed by the feed". The gap was ours.
2. TradingView's column names understate two buckets: `recommendation_buy`
   weighs 1.0 (a STRONG buy) and `recommendation_sell` 3.0 (a STRONG sell);
   `recommendation_over` (1.5) and `recommendation_under` (2.5) are the plain
   buy and sell.
3. `recommendation_mark` runs 1..3 with 2 neutral, and the gauge drew 1..5, so
   every name read more bullish than it was.

These tests pin the arithmetic against real rows Zach checked, and pin the
page and fetcher to requesting all five buckets on a 1..3 arc. If TradingView
ever changes its scale the weighted-mean test fails first, which is the point:
predict the number, then compare.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
FETCHER = (ROOT / "fetcher" / "build_snapshot.py").read_text(encoding="utf-8")

BUCKETS = ("recommendation_buy", "recommendation_over", "recommendation_hold",
           "recommendation_under", "recommendation_sell")
WEIGHTS = {"buy": 1.0, "over": 1.5, "hold": 2.0, "under": 2.5, "sell": 3.0}


def weighted_mark(buy=0, over=0, hold=0, under=0, sell=0) -> float:
    n = buy + over + hold + under + sell
    return (buy * 1.0 + over * 1.5 + hold * 2.0 + under * 2.5 + sell * 3.0) / n


# Live rows recorded 2026-09-05 alongside the mark TradingView published.
LIVE_ROWS = [
    # (buy, over, hold, under, sell, total, published mark)
    ("AAOI", 4, 1, 3, 0, 0, 8, 1.4375),
    ("SEI", 15, 2, 0, 0, 0, 17, 1.0588),
    ("MU", 46, 8, 3, 0, 0, 57, 1.1228),
    ("EROC", 7, 1, 0, 0, 0, 8, 1.0625),
]


@pytest.mark.parametrize("sym,buy,over,hold,under,sell,total,mark", LIVE_ROWS)
def test_five_buckets_sum_to_total_and_reproduce_the_mark(sym, buy, over, hold, under, sell, total, mark):
    assert buy + over + hold + under + sell == total, f"{sym}: buckets do not sum to the analyst count"
    assert weighted_mark(buy, over, hold, under, sell) == pytest.approx(mark, abs=5e-4), (
        f"{sym}: the 1/1.5/2/2.5/3 weighting no longer reproduces the vendor's mark; "
        "re-derive the scale before touching the gauge"
    )


def test_scale_bounds_are_one_to_three():
    assert weighted_mark(buy=10) == 1.0
    assert weighted_mark(hold=10) == 2.0
    assert weighted_mark(sell=10) == 3.0


def test_page_requests_all_five_buckets_in_every_fetch_path():
    for col in BUCKETS + ("recommendation_total", "recommendation_mark"):
        assert INDEX.count(f'"{col}"') >= 1, f"index.html never requests {col}"
    for col in BUCKETS + ("recommendation_total",):
        assert f'"{col}"' in FETCHER, f"build_snapshot.py never requests {col}"
    for key in ("rec_buy", "rec_over", "rec_hold", "rec_under", "rec_sell", "rec_total"):
        assert f'"{key}"' in FETCHER, f"build_snapshot.py does not publish {key}"


def _gauge_body() -> str:
    start = INDEX.index("function fcGaugeSVG(")
    end = INDEX.index("\nfunction ", start + 1)
    return INDEX[start:end]


def test_gauge_draws_a_one_to_three_arc():
    body = _gauge_body()
    assert "Math.max(1, Math.min(3, m))" in body, "the mark must be clamped to 1..3, not 1..5"
    assert re.search(r"function ang\(v\)\{\s*return \(v-1\)/2\*180;", body), (
        "ang() must map 1..3 onto 0..180 degrees; (v-1)/4*180 is the 1..5 bug"
    )
    assert "/4*180" not in body


def test_rating_bars_label_strong_versus_plain():
    start = INDEX.index("function fcRatingSecHTML(")
    body = INDEX[start:INDEX.index("\nfunction ", start + 1)]
    assert "fcNum(f.rec_buy)" in body and "fcNum(f.rec_over)" in body
    assert "fcNum(f.rec_under)" in body and "fcNum(f.rec_sell)" in body
    for label in ('row("Strong buy",sbuy)', 'row("Buy",buy)', 'row("Hold",hold)',
                  'row("Sell",sell)', 'row("Strong sell",ssell)'):
        assert label in body, f"rating bar {label} missing or relabelled"


def test_no_stale_one_to_five_comments_remain():
    """Rule 8: one bug of a kind means look for the rest of that kind."""
    for name, text in (("index.html", INDEX), ("build_snapshot.py", FETCHER)):
        for m in re.finditer(r"1\s*=\s*strong buy\s*\.\.\s*5", text):
            pytest.fail(f"{name} still describes the mark as 1..5 near: {text[m.start()-40:m.end()+20]!r}")
