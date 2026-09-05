"""The forecast chart must not depend on a live quote (added 2026-09-05).

The chart shipped gated on the live poll alone: fcTargetSecHTML read
dispQuote(liveBySym(sym)).px and handed it straight to fcProjectionSVG, whose
first guard is `if(px==null || !(px>0)) return ""`. The forecast panel does not
re-render when a quote lands later, so any visit where the poll had not yet
returned showed the targets with no chart underneath -- permanently, for that
visit.

That failed hardest on the device it was built for. A phone is a slower,
colder network, so the poll routinely landed after Zach had already opened the
Forecast tab, and the chart he asked for was the one thing missing. It drew
fine on a desktop, which is why it looked like a mobile layout bug.

The fix reads the newest daily close out of barsOf(sym) -- already in memory,
502 bars deep -- whenever the live price is absent, and labels the sub-line
"at the last close" so the reader knows which price is on screen. These
assertions pin that shape so a later edit cannot quietly restore the
live-only dependency.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")


def _fc_target_sec() -> str:
    """The body of fcTargetSecHTML, up to the next top-level function."""
    start = INDEX.index("function fcTargetSecHTML(")
    end = INDEX.index("\nfunction ", start + 1)
    return INDEX[start:end]


def test_chart_is_handed_the_fallback_price_not_the_live_one() -> None:
    body = _fc_target_sec()
    assert "fcProjectionSVG(sym, pxRef, avg, hi, lo)" in body, (
        "the chart must be drawn from pxRef (live price, else last close), "
        "not from the live-only px -- a null px returns '' and draws nothing"
    )
    assert "fcProjectionSVG(sym, px," not in body, (
        "fcProjectionSVG is being handed the live-only price again"
    )


def test_last_close_fallback_exists() -> None:
    body = _fc_target_sec()
    assert re.search(r"var fromClose = false, pxRef = px;", body), (
        "the pxRef fallback declaration is gone"
    )
    assert "fcHistory(sym).closes" in body, (
        "the fallback must read fcHistory, the same source the chart uses -- "
        "reading barsOf() alone misses every searched name"
    )
    assert re.search(r"pxRef = hist\[bi\]; fromClose = true;", body), (
        "the loop that walks back to the newest usable close is gone"
    )


def test_sub_line_says_which_price_is_on_screen() -> None:
    """A close standing in for a live price is a disclosure, not explanation."""
    body = _fc_target_sec()
    assert "at the last close" in body, (
        "the reader must be told when the comparison price is a close rather "
        "than a live quote"
    )


def _fc_projection() -> str:
    start = INDEX.index("function fcProjectionSVG(")
    end = INDEX.index("\nfunction ", start + 1)
    return INDEX[start:end]


def test_chart_reads_both_history_sources() -> None:
    """A searched name keeps its dailies in ADHOC_BARS, not bars.json.

    EROC and SEI both publish a full analyst row -- targets, a rating mark, a
    coverage count -- and neither is one of the 69 symbols in bars.json. The
    chart read barsOf() alone, got an empty array, and returned "" at the n<60
    guard, so both drew the gauge and no chart. seriesFull() has consulted both
    sources since ad-hoc search shipped; fcHistory is that same fallback.
    """
    assert "function fcHistory(sym)" in INDEX, "the fcHistory helper is gone"
    assert "ADHOC_BARS[sym] && ADHOC_BARS[sym].D" in INDEX, (
        "fcHistory no longer falls back to a searched name's dailies"
    )
    body = _fc_projection()
    assert "fcHistory(sym)" in body, (
        "fcProjectionSVG must source history through fcHistory"
    )
    assert not re.search(r"var full = barsOf\(sym\)", body), (
        "fcProjectionSVG is reading barsOf() directly again -- that is empty "
        "for every searched name"
    )


def test_searched_name_history_is_requested_once() -> None:
    """The panel has no re-render on data arrival, so it must ask and redraw."""
    assert "var FC_DAILY_TRIED = {}" in INDEX, (
        "the per-symbol one-shot flag is gone; without it a resolve that "
        "yields no usable rows can spin the redraw"
    )
    assert re.search(r"FC_DAILY_TRIED\[sym\] = true;", INDEX), (
        "the one-shot flag is never set"
    )
    assert re.search(
        r"adhocEnsureDaily\(sym\)\.then\(function\(\)\{\s*"
        r"if\(STAGE\.sym===fcWant && STAGE\.tab===\"fcst\"\) renderStageTab\(\);",
        INDEX,
    ), "the guarded one-shot redraw after the history fetch is gone"
