"""TIPS <-> scoring sync guard (2026-08-18).

CLAUDE.md's hard guardrail — "Keep index.html's TIPS text in sync with
build_snapshot.py scoring" — was enforced by nothing, and three drifts got
through (an IV-rank tooltip claiming a year of history against a 60-session
cap; both score tooltips omitting partial credits and agreement bonuses).
This test greps the numbers out of both files. It is deliberately dumb:
if a weight moves in one file and not the other, a substring goes missing
and the test names it.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
SNAP = (ROOT / "fetcher" / "build_snapshot.py").read_text(encoding="utf-8")


def tip(key: str) -> str:
    m = re.search(r'"%s":\s*"((?:[^"\\]|\\.)*)"' % re.escape(key), INDEX)
    assert m, f"TIPS key {key!r} not found in index.html"
    return m.group(1)


def test_conviction_score_tip_matches_code():
    t = tip("tip-score-conviction")
    # Weights as the tooltip states them
    for frag in ["RVOL 25", "momentum 20", "flow magnitude 25",
                 "call/put extremity 15", "volume-vs-OI 10",
                 "contract concentration 5", "±5"]:
        assert frag in t, f"conviction tip lost {frag!r}"
    # The split behind the lumped 20/25 (agreement bonuses) must be disclosed
    assert "+5" in t and "15 for the size" in t and "20 for size" in t
    # And the code must still implement exactly those constants
    body = SNAP.split("def conviction_score", 1)[1].split("def swing_score", 1)[0]
    for frag in ["* 25", "* 15", "mom += 5", "* 20", "flow += 5", "* 10", "* 5"]:
        assert frag in body, f"conviction_score lost {frag!r}"


def test_swing_score_tip_matches_code():
    t = tip("tip-score-swing")
    for frag in ["persistence 35", "5-day flow magnitude 20", "OI build 15",
                 "trend alignment 15", "MIXED trend earns 7",
                 "neutral 5", "call/put skew 5",
                 "+5 (OPENING)", "-10 (CLOSING)"]:
        assert frag in t, f"swing tip lost {frag!r}"
    body = SNAP.split("def swing_score", 1)[1].split("\n\n\n", 1)[0]
    for frag in ["* 35", "* 20", "* 15", "pts += 15", "pts += 7",
                 "pts += 5", "10 * (1 - iv_rank / 100)"]:
        assert frag in body, f"swing_score lost {frag!r}"


def test_iv_rank_tip_matches_history_cap():
    m = re.search(r"MAX_IV_HISTORY\s*=\s*(\d+)", SNAP)
    assert m, "MAX_IV_HISTORY not found"
    cap = int(m.group(1))
    t = tip("tip-ivrank")
    assert f"{cap} trading sessions" in t, (
        f"IV-rank tip must state the real basis ({cap} sessions); "
        "it once claimed a full year")
    assert "past year" not in t


def test_reference_level_tips_match_constants():
    assert "30%" in tip("tip-stop-ref")
    assert "105%" in tip("tip-target-ref")
    assert "0.70" in SNAP and "2.05" in SNAP, "suggested-contract stop/target constants moved"


def test_flowpct_tip_matches_moneyness_band():
    m = re.search(r"MONEYNESS_BAND\s*=\s*0?\.(\d+)", SNAP)
    assert m, "MONEYNESS_BAND not found"
    pct = int(m.group(1).ljust(2, "0")[:2])
    assert f"{pct}%" in tip("tip-flowpct"), (
        f"flow-% tip must state the ±{pct}% near-money band")
