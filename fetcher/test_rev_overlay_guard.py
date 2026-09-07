"""The chart-stage fundamentals block overlays (Rev and FCF buttons, 2026-09-07).

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
    assert '["fcf","FCF"]' in INDEX, "the FCF overlay button is gone from the overlay bar"
    defaults = _fn("taDefaults")
    assert "rev:false" in defaults and "fcf:false" in defaults, "block overlays default OFF like every overlay except BB"
    prefs = _fn("taPrefs")
    assert "rev:!!v.rev" in prefs and "fcf:!!v.fcf" in prefs, "taPrefs must read both stored flags"


def test_rev_is_disabled_off_daily_and_weekly_with_a_printed_reason() -> None:
    assert re.search(r'var revOffIntra = \(STAGE\.iv !== "1D" && STAGE\.iv !== "1W"\);', INDEX)
    assert '((t[0]==="rev" || t[0]==="fcf") && revOffIntra)' in INDEX
    assert "revenue growth and free cash flow blocks draw on the 1D and 1W views only" in INDEX, (
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
    assert 'failedOv.push("free cash flow")' in legend
    assert "none in view: the latest block ends" in legend
    fcf = _fn("fcfOverlayPoints")
    for reason in ("no financials for this name", "no free cash flow on the feed",
                   "no period dates to place the quarters on"):
        assert reason in fcf, f"missing FCF failure reason: {reason}"


def test_fcf_is_dollars_not_a_growth_rate() -> None:
    fcf = _fn("fcfOverlayPoints")
    assert "revYoyAll(" not in fcf and "yoyPct(" not in fcf, (
        "FCF crosses zero; a YoY percentage across a sign flip is not a number"
    )
    assert "text:fmtCompact(v)" in fcf, "the block label is the same compact money format the Financials tab uses"
    assert "revPeriodEnds(fund, q, ppy)" in fcf, "FCF blocks must be placed by the same period-end function as Rev"


def test_both_overlays_share_one_primitive_with_a_label_pass() -> None:
    ta = _fn("stageTA")
    assert 'STAGE.revPrim = blockBuildPrimitive(blockKeys)' in ta
    assert "blockBuildPrimitive(" in ta and ta.count("attachPrimitive(STAGE.revPrim)") == 1, (
        "one primitive draws both datasets so no block paints over the other's labels"
    )
    prim = _fn("blockBuildPrimitive")
    assert "drawn.forEach" in prim and "Object.keys(spans)" in prim, "label pass after every fill is gone"
    assert "span*0.48" in prim and "span*0.52" in prim, "side-by-side halves when both are on"


def test_primitive_is_torn_down_with_the_other_overlays() -> None:
    clear = _fn("stageTAClear")
    assert "detachPrimitive(STAGE.revPrim)" in clear
    assert "STAGE.revData = null" in clear and "STAGE.fcfData = null" in clear


def test_fractional_logical_is_snapped_by_hand() -> None:
    prim = _fn("blockBuildPrimitive")
    assert "Math.floor(l)" in prim and "(l-base)*barSp" in prim
    assert "ts.logicalToCoordinate(l0)" not in prim, (
        "a fractional logical handed straight to the library draws at x=0"
    )


def test_blocks_stand_above_the_volume_histogram() -> None:
    prim = _fn("blockBuildPrimitive")
    assert "paneH * 0.80" in prim, "baseline must clear the volume scale's 0.82 top margin"
    assert 'scaleMargins:{top:0.82, bottom:0}' in INDEX
