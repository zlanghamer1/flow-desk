"""TIPS-stays-empty guard (rewritten 2026-09-05).

This file used to grep the scoring weights out of index.html's TIPS tooltips
and assert they matched build_snapshot.py, because three drifts had shipped
(an IV-rank tooltip claiming a year of history against a 60-session cap; both
score tooltips omitting partial credits and agreement bonuses).

Zach removed the tooltips: "Trim out all explanation text. I don't want it
either in mobile or on the web." (2026-09-05, recorded in CLAUDE.md under
"NO EXPLANATION TEXT ON THE PAGE"). With no prose to drift, the old assertions
have no subject. The guard is inverted instead: TIPS must stay an empty
lookup, so a later session cannot quietly refill it and reintroduce both the
explanation text and the drift class that needed policing.

The scoring constants themselves are still pinned two files apart by
test_sync_constants.py.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")


def test_tips_is_an_empty_lookup():
    """`var TIPS` resolves every key to "" and holds no prose of its own."""
    m = re.search(r"var TIPS = (.*)", INDEX)
    assert m, "var TIPS not found in index.html"
    decl = m.group(1)
    assert "new Proxy({}" in decl, f"TIPS is no longer an empty lookup: {decl[:120]!r}"
    # An object literal with entries would mean someone refilled it.
    assert not re.search(r"var TIPS = \{\s*[\"'a-zA-Z]", INDEX), \
        "TIPS was refilled with entries — see CLAUDE.md, NO EXPLANATION TEXT ON THE PAGE"


def test_no_tips_prose_left_behind():
    """No `"tip-...": "sentence"` pairs survive anywhere in the page."""
    leftovers = re.findall(r'"(tip-[a-z0-9-]+)"\s*:\s*"[^"]{40,}"', INDEX)
    assert not leftovers, f"methodology prose still in index.html for: {sorted(set(leftovers))}"
