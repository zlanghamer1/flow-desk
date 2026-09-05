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


def test_adhoc_facts_request_the_full_analyst_row() -> None:
    """A searched name needs the same analyst fields a tracked one carries.

    ADHOC_FACTS_COLS asked for price_target_average and recommendation_mark and
    nothing else in that family, so a searched name reached the Forecast tab
    with an average and a needle: Median/Highest/Lowest dashed, no analyst
    count under the gauge, no Buy/Hold/Sell bars, and a fan drawn with only the
    average line because fcProjectionSVG had no hi/lo to build wedges to. The
    scanner publishes all of it on the same row -- SEI carries high 120, low
    73, median 90 and 17 analysts -- so the request was narrower than the feed.

    The six columns are appended at the END of the list on purpose: every
    mapping below reads by position, so inserting one anywhere else silently
    shifts n(0)..n(21) onto the wrong fields.
    """
    cols = re.search(r"var ADHOC_FACTS_COLS = \[(.*?)\];", INDEX, re.S)
    assert cols, "ADHOC_FACTS_COLS is gone"
    names = re.findall(r'"([A-Za-z0-9_]+)"', cols.group(1))
    for i, want in enumerate(
        [
            "price_target_high",
            "price_target_low",
            "price_target_median",
            "recommendation_total",
            "recommendation_buy",
            "recommendation_hold",
            "recommendation_sell",
        ],
        start=23,
    ):
        assert names[i] == want, (
            f"column {i} is {names[i]!r}, expected {want!r} -- the mapping "
            "reads by position, so a reordered list writes the wrong field"
        )
    assert names.index("price_target_average") == 18, "target average moved"
    assert names.index("recommendation_mark") == 19, "rating mark moved"

    for field, idx in [
        ("target_high", 23),
        ("target_low", 24),
        ("target_median", 25),
        ("rec_total", 26),
        ("rec_buy", 27),
        ("rec_hold", 28),
        ("rec_sell", 29),
    ]:
        assert re.search(rf"{field}:n\({idx}\)", INDEX), (
            f"{field} is not mapped from column {idx}"
        )


def _fc_gauge() -> str:
    start = INDEX.index("function fcGaugeSVG(")
    end = INDEX.index("\nfunction ", start + 1)
    return INDEX[start:end]


def test_gauge_scale_is_one_to_three() -> None:
    """recommendation_mark runs 1..3, not 1..5.

    Solving the weighted mean that reproduces the vendor's own mark gives
    buy 1.0, over 1.5, hold 2.0, under 2.5, sell 3.0 -- exact on every live row
    tested, from the market's best consensus (1.0000, all strong buys) to its
    worst (2.7143). Drawn on a 1..5 arc the whole real range collapsed into the
    left half: a dead-neutral 2.00 pointed at "Buy" and the most bearish name in
    the US market stopped short of "Neutral", so every stock read more bullish
    than it was.

    AAOI is the independent check. Its 1.4375 lands at 39.6 degrees, inside the
    Buy anchor's neighbourhood, which is what TradingView's own gauge says. On
    the 1..5 arc it read "Strong buy" and disagreed with them.
    """
    body = _fc_gauge()
    assert "Math.min(3, m)" in body, "the mark is not clamped to the 1..3 scale"
    assert "Math.min(5, m)" not in body, "the 1..5 clamp is back"
    assert re.search(r"function ang\(v\)\{ return \(v-1\)/2\*180; \}", body), (
        "the needle angle must map 1..3 across the half-circle"
    )
    assert "(v-1)/4*180" not in body, "the 1..5 angle mapping is back"
    assert "[1.5,2,2.5].forEach" in body, (
        "notches must sit at the interior anchors of the 1..3 scale"
    )
    assert "1-to-3 scale" in body, "the alt text still describes the wrong scale"


def test_all_five_rating_buckets_are_read_and_labelled() -> None:
    """TV's column names understate two buckets; the labels must not repeat it.

    recommendation_buy weighs 1.0 and recommendation_sell 3.0, so they are the
    STRONG ends, with over/under carrying the plain ones. Labelling rec_buy as
    plain "Buy" put the bars in contradiction with the needle above them.
    """
    start = INDEX.index("function fcRatingSecHTML(")
    body = INDEX[start : INDEX.index("\nfunction ", start + 1)]
    for field in ("rec_buy", "rec_over", "rec_hold", "rec_under", "rec_sell"):
        assert f"f.{field}" in body, f"{field} is not read into the rating section"
    for label, field in [
        ('row("Strong buy",sbuy)', "rec_buy"),
        ('row("Buy",buy)', "rec_over"),
        ('row("Sell",sell)', "rec_under"),
        ('row("Strong sell",ssell)', "rec_sell"),
    ]:
        assert label in body, f"{label} is missing -- {field} must carry that label"
    assert "var sbuy = fcNum(f.rec_buy)" in body, "rec_buy must be the STRONG buy bucket"
    assert "ssell = fcNum(f.rec_sell)" in body, "rec_sell must be the STRONG sell bucket"


def test_both_fetch_paths_request_all_five_buckets() -> None:
    """The client-side and server-side column lists must not diverge."""
    cols = re.search(r"var ADHOC_FACTS_COLS = \[(.*?)\];", INDEX, re.S).group(1)
    names = re.findall(r'"([A-Za-z0-9_]+)"', cols)
    assert names[30] == "recommendation_over", f"col 30 is {names[30]!r}"
    assert names[31] == "recommendation_under", f"col 31 is {names[31]!r}"
    assert re.search(r"rec_over:n\(30\)", INDEX) and re.search(r"rec_under:n\(31\)", INDEX), (
        "over/under are requested but never mapped into ADHOC_FACTS"
    )

    snap = (ROOT / "fetcher" / "build_snapshot.py").read_text(encoding="utf-8")
    for col in ("recommendation_over", "recommendation_under"):
        assert f'"{col}"' in snap, f"{col} missing from the server-side TV_COLUMNS"
    for key, col in [("rec_over", "recommendation_over"), ("rec_under", "recommendation_under")]:
        assert re.search(rf'"{key}": _num\(_COL\["{col}"\]\)', snap), (
            f"{key} is not mapped in build_snapshot"
        )
