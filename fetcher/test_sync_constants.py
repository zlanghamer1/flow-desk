"""Cross-file constant sync guards (2026-08-23 Fable architect pass, finding
5.1), in the same deliberately-dumb regex style as test_tips_sync.py — three
pairs of hand-duplicated constants had no test pinning them together before
this, unlike the TIPS<->scoring pair, which only got one after three real
drifts got through:

  1. TRACK_ONLY (fetcher/build_snapshot.py) <-> TRACK_ONLY_SYMS (index.html):
     if a name is added to one and not the other, the frontend's
     stageFlowSecHTML (and boardCoverageHTML's "quote-only by design" note)
     silently mis-classifies it.
  2. The Morning Brief's high_conviction threshold (score_conv >= 60,
     hardcoded in build_snapshot.py) <-> BOARD_SCORE_FLOOR (index.html): the
     "score 60+" tile and the board cut must agree by construction, not by
     coincidence of two literals.
  3. market_guard.py's MARKET_HOLIDAYS/MARKET_HALF_DAYS <-> index.html's own
     tables (see test_market_guard.py for the guard's own behavioral tests;
     this file only pins the two date sets equal).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
SNAP = (ROOT / "fetcher" / "build_snapshot.py").read_text(encoding="utf-8")
GUARD = (ROOT / "fetcher" / "market_guard.py").read_text(encoding="utf-8")


def test_track_only_sets_match():
    m = re.search(r'TRACK_ONLY = \{([^}]*)\}', SNAP)
    assert m, "TRACK_ONLY set not found in build_snapshot.py"
    fetcher_set = set(re.findall(r'"([A-Z]+)"', m.group(1)))
    assert fetcher_set, "TRACK_ONLY parsed empty — regex drifted from the source"

    m2 = re.search(r'var TRACK_ONLY_SYMS = \{([^}]*)\}', INDEX)
    assert m2, "TRACK_ONLY_SYMS not found in index.html"
    frontend_set = set(re.findall(r'([A-Z]+):1', m2.group(1)))
    assert frontend_set, "TRACK_ONLY_SYMS parsed empty — regex drifted from the source"

    assert fetcher_set == frontend_set, (
        f"TRACK_ONLY (fetcher) and TRACK_ONLY_SYMS (frontend) disagree: "
        f"fetcher-only={fetcher_set - frontend_set} frontend-only={frontend_set - fetcher_set}"
    )


def test_board_score_floor_matches_high_conviction_threshold():
    m = re.search(r'high_conviction = sum\(1 for v in by_ticker\.values\(\)\s*\n\s*if v\.get\("score_conv"\) is not None and v\["score_conv"\] >= (\d+)\)', SNAP)
    assert m, "high_conviction threshold not found in build_snapshot.py (regex drifted?)"
    fetcher_floor = int(m.group(1))

    m2 = re.search(r'var BOARD_SCORE_FLOOR = (\d+);', INDEX)
    assert m2, "BOARD_SCORE_FLOOR not found in index.html"
    frontend_floor = int(m2.group(1))

    assert fetcher_floor == frontend_floor, (
        f"the Morning Brief's high_conviction threshold ({fetcher_floor}) and "
        f"BOARD_SCORE_FLOOR ({frontend_floor}) disagree — the header tile and "
        f"the board cut would count different names as 'score 60+'"
    )


def _dates_from(text: str, var_name: str) -> set[str]:
    m = re.search(re.escape(var_name) + r'\s*=\s*[\{\[]([^}\]]*)[\}\]]', text, re.DOTALL)
    assert m, f"{var_name} not found"
    return set(re.findall(r'"(\d{4}-\d{2}-\d{2})"', m.group(1)))


def test_holiday_tables_match_across_fetcher_and_frontend():
    fetcher_holidays = _dates_from(GUARD, "MARKET_HOLIDAYS")
    frontend_holidays = _dates_from(INDEX, "var MARKET_HOLIDAYS")
    assert fetcher_holidays == frontend_holidays, (
        f"MARKET_HOLIDAYS disagree: fetcher-only={fetcher_holidays - frontend_holidays} "
        f"frontend-only={frontend_holidays - fetcher_holidays}"
    )

    fetcher_half = _dates_from(GUARD, "MARKET_HALF_DAYS")
    frontend_half = _dates_from(INDEX, "var MARKET_HALF_DAYS")
    assert fetcher_half == frontend_half, (
        f"MARKET_HALF_DAYS disagree: fetcher-only={fetcher_half - frontend_half} "
        f"frontend-only={frontend_half - fetcher_half}"
    )
