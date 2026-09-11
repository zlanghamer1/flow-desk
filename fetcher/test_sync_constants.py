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
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
SNAP = (ROOT / "fetcher" / "build_snapshot.py").read_text(encoding="utf-8")
GUARD = (ROOT / "fetcher" / "market_guard.py").read_text(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verdict  # noqa: E402 -- fetcher-side VERDICT_INPUT_ORDER, imported not regex-parsed (F6)


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


def test_big_orders_baseline_sessions_match():
    """BIG_ORDERS_BASELINE_SESSIONS (fetcher, = UOA_MIN_SESSIONS) <-> the
    frontend's BIG_ORDERS_BASELINE_SESSIONS literal, which the × normal cell's
    'no baseline yet' tooltip prints (2026-09-03). Two files, one number."""
    m = re.search(r"UOA_MIN_SESSIONS\s*=\s*(\d+)", SNAP)
    assert m, "UOA_MIN_SESSIONS not found"
    assert "BIG_ORDERS_BASELINE_SESSIONS = UOA_MIN_SESSIONS" in SNAP
    m2 = re.search(r"var BIG_ORDERS_BASELINE_SESSIONS = (\d+);", INDEX)
    assert m2, "BIG_ORDERS_BASELINE_SESSIONS not found in index.html"
    assert int(m2.group(1)) == int(m.group(1))
    # The tooltip that used to print this number is gone with TIPS
    # (Zach's 2026-09-05 no-explanation-text ruling); the two-file constant
    # check above is what this test was really for.


def test_verdict_input_set_matches_page():
    """VERDICT_INPUT_ORDER (fetcher/verdict.py) <-> VERDICT_INPUT_LABELS
    (index.html) — the design doc requires the two key sets to match
    exactly, same count included, or the Verdicts board renders a chip with
    no label (or a label with no chip) for whichever key drifted
    (2026-09-11 desk-verdicts design).

    F6 (2026-09-11 fix): the fetcher side used to be regex-parsed with
    `"([a-z_]+)"`, which cannot match a key with a digit in it -- "rs63"
    silently vanished from BOTH sides' parsed sets (8 of the real 9 keys
    each), so a renamed or dropped rs63 on either file would still have
    passed. The fetcher side is now imported directly; only the page side
    (no Python symbol to import) still needs a regex, corrected to admit
    digits.
    """
    fetcher_keys = list(verdict.VERDICT_INPUT_ORDER)
    assert fetcher_keys, "VERDICT_INPUT_ORDER is empty"
    assert len(fetcher_keys) == len(set(fetcher_keys)), "VERDICT_INPUT_ORDER has a duplicate key"

    m2 = re.search(r'var VERDICT_INPUT_LABELS = \{([^}]*)\};', INDEX)
    assert m2, "VERDICT_INPUT_LABELS not found in index.html"
    page_keys = re.findall(r'([A-Za-z_][A-Za-z0-9_]*)\s*:', m2.group(1))
    assert page_keys, "VERDICT_INPUT_LABELS parsed empty — regex drifted from the source"
    assert len(page_keys) == len(set(page_keys)), "VERDICT_INPUT_LABELS has a duplicate key"

    assert set(fetcher_keys) == set(page_keys), (
        f"VERDICT_INPUT_ORDER (fetcher) and VERDICT_INPUT_LABELS (page) disagree: "
        f"fetcher-only={set(fetcher_keys) - set(page_keys)} "
        f"page-only={set(page_keys) - set(fetcher_keys)}"
    )
    # eight since 2026-09-11 (attempt #3 amendment removed `market`; the
    # brief verdict prints as a chip on the board, not as an input)
    assert len(fetcher_keys) == len(page_keys) == 8, (
        "VERDICT_INPUT_ORDER and VERDICT_INPUT_LABELS must both have exactly 8 keys "
        f"(fetcher has {len(fetcher_keys)}, page has {len(page_keys)})"
    )
