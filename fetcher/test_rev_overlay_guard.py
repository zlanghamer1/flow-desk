"""The chart-stage revenue-growth overlay (Rev button, added 2026-09-07).

One block per fiscal quarter, height scaled to that quarter's year-over-year
revenue growth, drawn along the candle pane on its own scale. These assertions
pin the shape that keeps it honest:

- the YoY math is shared with the Financials tab (revYoyAll / revDupIdx), so
  the block under the candles and the bar on the Financials tab can never
  print two different growth numbers for one quarter;
- the primitive is torn down with the other overlays on a symbol switch;
- the toggle is off by default and disabled on the intraday intervals, with
  the reason printed rather than left as a lit button over an empty chart;
- fractional bar positions are snapped to an integer logical index plus a
  fraction of a bar spacing, because the vendored Lightweight Charts build
  returns 0 for a fractional logical (measured live: 371 -> 336px, 371.33 -> 0).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    start = INDEX.index(f"function {name}(")
    end = INDEX.index("\nfunction ", start + 1)
    return INDEX[start:end]


def test_rev_toggle_exists_and_defaults_off() -> None:
    assert '["rev","Rev"]' in INDEX, "the Rev overlay button is gone from the overlay bar"
    defaults = _fn("taDefaults")
    assert "rev:false" in defaults, "rev must default OFF like every overlay except BB"
    assert "rev:!!v.rev" in _fn("taPrefs"), "taPrefs must read the stored rev flag"


def test_rev_is_disabled_off_daily_and_weekly_with_a_printed_reason() -> None:
    assert re.search(r'var revOffIntra = \(STAGE\.iv !== "1D" && STAGE\.iv !== "1W"\);', INDEX)
    assert '(t[0]==="rev" && revOffIntra)' in INDEX
    assert "revenue growth blocks draw on the 1D and 1W views only" in INDEX, (
        "a disabled toggle must say why in the chart-notes legend"
    )


def test_overlay_shares_the_financials_tabs_yoy_math() -> None:
    growth = _fn("renderGrowth")
    assert "revYoyAll(revNums, q.labels, ppyRaw, ppy, dupIdx)" in growth
    assert "revDupIdx(q)" in growth
    assert "function yoyDenomDiscontinuous" not in growth, (
        "the discontinuity check must live in revDenomDiscontinuous, not an inline copy"
    )
    overlay = _fn("revOverlayPoints")
    assert "revYoyAll(" in overlay and "revDupIdx(q)" in overlay
    assert "periodsPerYear(q.labels)" in overlay, "no YoY without a resolved filing cadence"


def test_no_data_is_a_reason_never_a_blank_chart() -> None:
    overlay = _fn("revOverlayPoints")
    for reason in (
        "no financials for this name",
        "no quarterly revenue history",
        "filing cadence unresolved",
        "no period dates to place the quarters on",
        "fewer than a year of comparable periods",
    ):
        assert reason in overlay, f"missing failure reason: {reason}"
    legend = _fn("stageTALegend")
    assert 'failedOv.push("revenue growth")' in legend
    assert "none in view: the latest block ends" in legend


def test_primitive_is_torn_down_with_the_other_overlays() -> None:
    clear = _fn("stageTAClear")
    assert "detachPrimitive(STAGE.revPrim)" in clear
    assert "STAGE.revData = null" in clear


def test_fractional_logical_is_snapped_by_hand() -> None:
    prim = _fn("revBuildPrimitive")
    assert "Math.floor(l)" in prim and "(l-base)*barSp" in prim
    assert "ts.logicalToCoordinate(l0)" not in prim, (
        "a fractional logical handed straight to the library draws at x=0"
    )


def test_blocks_stand_above_the_volume_histogram() -> None:
    prim = _fn("revBuildPrimitive")
    assert "paneH * 0.80" in prim, "baseline must clear the volume scale's 0.82 top margin"
    assert 'scaleMargins:{top:0.82, bottom:0}' in INDEX
