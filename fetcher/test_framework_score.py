"""5-metric scoring framework (added 2026-08-21) — repricing/validation/
sustainability filters that surface as a chip on the chart's Overview tab.

Run: python3 -m pytest fetcher/test_framework_score.py

What these tests defend, in order of how badly each would mislead Zach if it
broke:

1. A filter with no real data must read UNKNOWN (None), never a guessed pass
   or fail. The two consensus-history filters (forward EPS revision, analyst
   velocity) start UNKNOWN on a fresh deployment — there is no 3/6-month-old
   snapshot yet — and must stay that way rather than silently defaulting to
   either verdict.
2. The verdict must never claim more confidence than the data supports:
   "BUILDING" while fewer than 3 of 5 filters have resolved, never a tier
   word computed from a minority of the filters.
3. The weekly consensus snapshot must fire once per ISO week, not once per
   cycle — a snapshot on every ~7-minute cycle would make the file huge and
   would poison the 3/6-month lookback with same-week noise.
4. The lookback must tolerate a missed week (a loop outage, a holiday) by
   searching adjacent weeks, but must never invent a value for a ticker that
   truly has no snapshot in range.
5. Thresholds (20% NTM revenue growth, 50bps OpMargin expansion) must gate
   exactly at their boundary, not off by a sign or an inequality direction.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import context  # noqa: E402
from build_snapshot import (  # noqa: E402
    load_consensus_history, save_consensus_history, MAX_CONSENSUS_WEEKS)


SESSION = date(2026, 8, 21)


def _fund(revenue=None, fcf=None, opinc=None, annual_revenue=None):
    """Minimal fund/{SYM}.json-shaped dict — only what score_framework reads."""
    return {
        "quarterly": {
            "revenue": revenue or [], "fcf": fcf or [], "opinc": opinc or [],
        },
        "annual": {"revenue": annual_revenue or []},
    }


# ── Filter 2: NTM revenue growth ────────────────────────────────────────────

def test_revenue_growth_passes_above_20_percent():
    fund = _fund(annual_revenue=[100.0])
    f = {"eps_ntm": None, "rev_ntm": 121.0}   # +21%
    out = context.score_framework("X", f, fund, {"weekly": {}}, SESSION)
    assert out["filters"]["revenue_growth"] is True
    assert out["metrics"]["revenue_growth_ntm_pct"] == pytest.approx(21.0)


def test_revenue_growth_fails_at_exactly_20_percent():
    # Threshold is strictly > 20%, not >=, so the boundary itself fails.
    fund = _fund(annual_revenue=[100.0])
    f = {"eps_ntm": None, "rev_ntm": 120.0}
    out = context.score_framework("X", f, fund, {"weekly": {}}, SESSION)
    assert out["filters"]["revenue_growth"] is False


def test_revenue_growth_unknown_with_no_rev_ntm():
    fund = _fund(annual_revenue=[100.0])
    f = {"eps_ntm": None, "rev_ntm": None}
    out = context.score_framework("X", f, fund, {"weekly": {}}, SESSION)
    assert out["filters"]["revenue_growth"] is None
    assert "revenue_growth_ntm_pct" not in out["metrics"]


def test_revenue_growth_unknown_on_an_implausible_ntm_swing():
    # Live MU shape (2026-08-26 review round 19, the round's one blocker):
    # rev_ntm (TV next-FY consensus) vs. a stockanalysis.com-derived last
    # annual figure PASSed at "+246.18% NTM revenue growth" — two vendors
    # whose fiscal-year alignment is unverified, so an extreme ratio reads
    # as a period-alignment artifact, never a confident PASS. This test
    # uses a value past the 300% ceiling.
    fund = _fund(annual_revenue=[100.0])
    f = {"eps_ntm": None, "rev_ntm": 450.0}   # +350%
    out = context.score_framework("X", f, fund, {"weekly": {}}, SESSION)
    assert out["filters"]["revenue_growth"] is None
    assert "revenue_growth_ntm_pct" not in out["metrics"]
    assert out["filter_flags"]["revenue_growth"] == "implausible_swing"


def test_revenue_growth_still_resolves_just_inside_the_plausible_ceiling():
    fund = _fund(annual_revenue=[100.0])
    f = {"eps_ntm": None, "rev_ntm": 390.0}   # +290%, under the 300% ceiling
    out = context.score_framework("X", f, fund, {"weekly": {}}, SESSION)
    assert out["filters"]["revenue_growth"] is True
    assert out["metrics"]["revenue_growth_ntm_pct"] == pytest.approx(290.0)


def test_revenue_growth_unknown_with_no_fund_annual():
    f = {"eps_ntm": None, "rev_ntm": 121.0}
    out = context.score_framework("X", f, None, {"weekly": {}}, SESSION)
    assert out["filters"]["revenue_growth"] is None


# ── Filter 4: operating-margin expansion ────────────────────────────────────

def test_opmargin_expansion_passes_above_50bps():
    # 5 quarters oldest-first: index -5 is a year ago, -1 is latest.
    revenue = [100.0, 100.0, 100.0, 100.0, 100.0]
    opinc = [20.0, 20.0, 20.0, 20.0, 20.6]   # margin 20% -> 20.6%: +60bps
    fund = _fund(revenue=revenue, opinc=opinc)
    out = context.score_framework("X", {}, fund, {"weekly": {}}, SESSION)
    assert out["filters"]["opmargin_expansion"] is True
    assert out["metrics"]["opmargin_expansion_bps"] == pytest.approx(60.0, abs=0.1)


def test_opmargin_expansion_fails_below_50bps():
    revenue = [100.0, 100.0, 100.0, 100.0, 100.0]
    opinc = [20.0, 20.0, 20.0, 20.0, 20.3]   # +30bps
    fund = _fund(revenue=revenue, opinc=opinc)
    out = context.score_framework("X", {}, fund, {"weekly": {}}, SESSION)
    assert out["filters"]["opmargin_expansion"] is False


def test_opmargin_expansion_unknown_with_fewer_than_5_quarters():
    fund = _fund(revenue=[100.0, 100.0], opinc=[20.0, 20.0])
    out = context.score_framework("X", {}, fund, {"weekly": {}}, SESSION)
    assert out["filters"]["opmargin_expansion"] is None


def test_opmargin_expansion_unknown_when_a_quarter_is_null():
    revenue = [100.0, 100.0, 100.0, 100.0, 100.0]
    opinc = [None, 20.0, 20.0, 20.0, 20.6]
    fund = _fund(revenue=revenue, opinc=opinc)
    out = context.score_framework("X", {}, fund, {"weekly": {}}, SESSION)
    assert out["filters"]["opmargin_expansion"] is None


def test_opmargin_expansion_unknown_on_an_implausible_yoy_swing():
    # Live MU sidecar shape: a >20pp YoY opmargin swing reads as a probable
    # quarter-misalignment/duplicate-row artifact, not a real reading, and
    # must not silently PASS (2026-08-22 review, data honesty finding #1).
    revenue = [100.0, 100.0, 100.0, 100.0, 100.0]
    opinc = [23.0, 23.0, 23.0, 23.0, 80.0]   # 23% -> 80%: +5700bps
    fund = _fund(revenue=revenue, opinc=opinc)
    out = context.score_framework("X", {}, fund, {"weekly": {}}, SESSION)
    assert out["filters"]["opmargin_expansion"] is None
    assert "opmargin_expansion_bps" not in out["metrics"]
    # A ceiling rejection is a PERMANENT data-quality flag, not a "still
    # building" gap that will resolve by waiting — the two must be
    # distinguishable so the frontend never tells the reader a flagged
    # reading might arrive next week (2026-08-22 review round 11, data
    # honesty finding #1).
    assert out["filter_flags"]["opmargin_expansion"] == "implausible_swing"


def test_opmargin_expansion_still_resolves_just_inside_the_plausible_ceiling():
    revenue = [100.0, 100.0, 100.0, 100.0, 100.0]
    opinc = [20.0, 20.0, 20.0, 20.0, 39.9]   # +1990bps, just under the 2000bps ceiling
    fund = _fund(revenue=revenue, opinc=opinc)
    out = context.score_framework("X", {}, fund, {"weekly": {}}, SESSION)
    assert out["filters"]["opmargin_expansion"] is True
    assert out["metrics"]["opmargin_expansion_bps"] == pytest.approx(1990.0, abs=0.1)


# ── Filter 5: FCF growth ─────────────────────────────────────────────────────

def test_fcf_growth_passes_when_positive_and_faster_than_revenue():
    # oldest-first, 8 quarters: [-8:-4] is the prior TTM, [-4:] is the current TTM.
    fcf = [10.0, 10.0, 10.0, 10.0, 15.0, 15.0, 15.0, 15.0]      # 40 -> 60: +50%
    revenue = [100.0, 100.0, 100.0, 100.0, 110.0, 110.0, 110.0, 110.0]  # +10%
    fund = _fund(revenue=revenue, fcf=fcf)
    out = context.score_framework("X", {}, fund, {"weekly": {}}, SESSION)
    assert out["filters"]["fcf_growth"] is True
    assert out["metrics"]["fcf_growth_ttm_pct"] == pytest.approx(50.0)
    assert out["metrics"]["revenue_growth_ttm_pct"] == pytest.approx(10.0)


def test_fcf_growth_fails_when_growing_slower_than_revenue():
    fcf = [10.0, 10.0, 10.0, 10.0, 11.0, 11.0, 11.0, 11.0]      # +10%
    revenue = [100.0, 100.0, 100.0, 100.0, 150.0, 150.0, 150.0, 150.0]  # +50%
    fund = _fund(revenue=revenue, fcf=fcf)
    out = context.score_framework("X", {}, fund, {"weekly": {}}, SESSION)
    assert out["filters"]["fcf_growth"] is False


def test_fcf_growth_fails_when_ttm_fcf_is_negative_even_if_improving():
    fcf = [-40.0, -40.0, -40.0, -40.0, -10.0, -10.0, -10.0, -10.0]  # -160 -> -40, improving but still negative
    revenue = [100.0] * 8
    fund = _fund(revenue=revenue, fcf=fcf)
    out = context.score_framework("X", {}, fund, {"weekly": {}}, SESSION)
    assert out["filters"]["fcf_growth"] is False


def test_fcf_growth_handles_a_negative_prior_ttm_recovering_to_positive():
    # prior TTM = -100, current TTM = +50: (50 - (-100)) / 100 = +150%
    fcf = [-25.0, -25.0, -25.0, -25.0, 12.5, 12.5, 12.5, 12.5]
    revenue = [100.0] * 8
    fund = _fund(revenue=revenue, fcf=fcf)
    out = context.score_framework("X", {}, fund, {"weekly": {}}, SESSION)
    assert out["metrics"]["fcf_growth_ttm_pct"] == pytest.approx(150.0)
    assert out["filters"]["fcf_growth"] is True   # positive TTM now, and growth beats flat 0% revenue


def test_fcf_growth_unknown_with_fewer_than_8_quarters():
    fund = _fund(revenue=[100.0] * 4, fcf=[10.0] * 4)
    out = context.score_framework("X", {}, fund, {"weekly": {}}, SESSION)
    assert out["filters"]["fcf_growth"] is None


def test_fcf_growth_unknown_on_an_implausible_ttm_swing():
    # Live MU sidecar shape: +1291% TTM FCF growth reads as a probable
    # quarter-alignment artifact, not a real reading (2026-08-22 review,
    # data honesty finding #1).
    revenue = [100.0] * 8
    fcf = [10.0, 10.0, 10.0, 10.0, 50.0, 50.0, 50.0, 50.0]   # 40 -> 200: +400%
    fund = _fund(revenue=revenue, fcf=fcf)
    out = context.score_framework("X", {}, fund, {"weekly": {}}, SESSION)
    assert out["filters"]["fcf_growth"] is None
    assert "fcf_growth_ttm_pct" not in out["metrics"]
    assert out["filter_flags"]["fcf_growth"] == "implausible_swing"


def test_filter_flags_empty_when_nothing_is_flagged():
    hist = {"weekly": {}}
    fund = _fund(
        revenue=[100.0] * 8, opinc=[20.0, 20.0, 20.0, 20.0, 22.0, 22.0, 22.0, 22.0],
        fcf=[10.0, 10.0, 10.0, 10.0, 15.0, 15.0, 15.0, 15.0],
        annual_revenue=[100.0],
    )
    out = context.score_framework("X", {"eps_ntm": None, "rev_ntm": 130.0}, fund, hist, SESSION)
    assert out["filter_flags"] == {}


def test_fcf_growth_still_resolves_just_inside_the_plausible_ceiling():
    fcf = [10.0, 10.0, 10.0, 10.0, 39.0, 39.0, 39.0, 39.0]   # 40 -> 156: +290%, under the 300% ceiling
    revenue = [100.0] * 8
    fund = _fund(revenue=revenue, fcf=fcf)
    out = context.score_framework("X", {}, fund, {"weekly": {}}, SESSION)
    assert out["filters"]["fcf_growth"] is True
    assert out["metrics"]["fcf_growth_ttm_pct"] == pytest.approx(290.0, abs=0.1)


# ── Filters 1 & 3: consensus-history-dependent, and never fabricated ────────

def test_forward_eps_revision_and_velocity_unknown_with_no_history():
    f = {"eps_ntm": 10.0, "rev_ntm": None}
    out = context.score_framework("X", f, None, {"weekly": {}}, SESSION)
    assert out["filters"]["forward_eps_revision"] is None
    assert out["filters"]["analyst_velocity"] is None
    assert out["filters_unknown"] >= 2


def test_forward_eps_revision_passes_when_consensus_rose_over_6_months():
    hist = {"weekly": {}}
    d_6m_ago = SESSION - timedelta(weeks=context.FRAMEWORK_WEEKS_6M)
    hist["weekly"][context._iso_week_key(d_6m_ago)] = {"X": {"eps_ntm": 8.0}}
    f = {"eps_ntm": 10.0, "rev_ntm": None}
    out = context.score_framework("X", f, None, hist, SESSION)
    assert out["filters"]["forward_eps_revision"] is True
    assert out["metrics"]["eps_revision_6m_pct"] == pytest.approx(25.0)


def test_forward_eps_revision_fails_when_consensus_fell():
    hist = {"weekly": {}}
    d_6m_ago = SESSION - timedelta(weeks=context.FRAMEWORK_WEEKS_6M)
    hist["weekly"][context._iso_week_key(d_6m_ago)] = {"X": {"eps_ntm": 12.0}}
    f = {"eps_ntm": 10.0, "rev_ntm": None}
    out = context.score_framework("X", f, None, hist, SESSION)
    assert out["filters"]["forward_eps_revision"] is False


def test_forward_eps_revision_unknown_on_a_split_sized_jump():
    # 5.0 -> 20.0 is a clean 4x, outside the "not a break" band (2.5x) and
    # landing exactly on a SPLIT_RATIOS entry — read as a probable unadjusted
    # split in the consensus number, not a real quadrupling of the forward
    # EPS estimate (2026-08-22 review, data honesty finding #2).
    hist = {"weekly": {}}
    d_6m_ago = SESSION - timedelta(weeks=context.FRAMEWORK_WEEKS_6M)
    hist["weekly"][context._iso_week_key(d_6m_ago)] = {"X": {"eps_ntm": 5.0}}
    f = {"eps_ntm": 20.0, "rev_ntm": None}
    out = context.score_framework("X", f, None, hist, SESSION)
    assert out["filters"]["forward_eps_revision"] is None
    assert "eps_revision_6m_pct" not in out["metrics"]


def test_forward_eps_revision_not_flagged_for_an_ordinary_large_revision():
    # 5.0 -> 9.0 is a genuinely large (+80%) revision, but inside the 2.5x
    # "not a break" band _repair_split_breaks itself uses for price bars —
    # a real analyst re-rating, not a split artifact, and must still resolve.
    hist = {"weekly": {}}
    d_6m_ago = SESSION - timedelta(weeks=context.FRAMEWORK_WEEKS_6M)
    hist["weekly"][context._iso_week_key(d_6m_ago)] = {"X": {"eps_ntm": 5.0}}
    f = {"eps_ntm": 9.0, "rev_ntm": None}
    out = context.score_framework("X", f, None, hist, SESSION)
    assert out["filters"]["forward_eps_revision"] is True
    assert out["metrics"]["eps_revision_6m_pct"] == pytest.approx(80.0)


def test_forward_eps_revision_unknown_on_an_implausible_non_split_swing():
    # 1.0 -> 70.0 is a 70x ratio — the one band above 2.5x where nothing
    # sits within SPLIT_SNAP_TOL of a clean factor (between 50 and 100), so
    # the split guard passes it through — but it's a consensus swing far
    # past the 300% plausibility ceiling: a vendor rebasing or a data error
    # the clean-factor test can't catch, so it reads UNKNOWN with the
    # permanent flag (2026-08-26 review round 19).
    hist = {"weekly": {}}
    d_6m_ago = SESSION - timedelta(weeks=context.FRAMEWORK_WEEKS_6M)
    hist["weekly"][context._iso_week_key(d_6m_ago)] = {"X": {"eps_ntm": 1.0}}
    f = {"eps_ntm": 70.0, "rev_ntm": None}
    out = context.score_framework("X", f, None, hist, SESSION)
    assert out["filters"]["forward_eps_revision"] is None
    assert "eps_revision_6m_pct" not in out["metrics"]
    assert out["filter_flags"]["forward_eps_revision"] == "implausible_swing"


def test_analyst_velocity_unknown_on_an_implausible_non_split_swing():
    hist = {"weekly": {}}
    d_3m_ago = SESSION - timedelta(weeks=context.FRAMEWORK_WEEKS_3M)
    hist["weekly"][context._iso_week_key(d_3m_ago)] = {"X": {"eps_ntm": 1.0}}
    f = {"eps_ntm": 70.0, "rev_ntm": None}
    out = context.score_framework("X", f, None, hist, SESSION)
    assert out["filters"]["analyst_velocity"] is None
    assert "eps_velocity_3m_pct" not in out["metrics"]
    assert out["filter_flags"]["analyst_velocity"] == "implausible_swing"


def test_lookback_tolerates_a_one_week_gap():
    # The exact 6-month week is missing (a loop outage); one week later exists.
    hist = {"weekly": {}}
    d_6m_ago = SESSION - timedelta(weeks=context.FRAMEWORK_WEEKS_6M)
    nearby = d_6m_ago + timedelta(weeks=1)
    hist["weekly"][context._iso_week_key(nearby)] = {"X": {"eps_ntm": 8.0}}
    v = context._consensus_lookback(hist, "X", SESSION, context.FRAMEWORK_WEEKS_6M)
    assert v == pytest.approx(8.0)


def test_lookback_returns_none_beyond_tolerance():
    hist = {"weekly": {}}
    d_6m_ago = SESSION - timedelta(weeks=context.FRAMEWORK_WEEKS_6M)
    far = d_6m_ago + timedelta(weeks=3)   # outside the +/-1 week tolerance
    hist["weekly"][context._iso_week_key(far)] = {"X": {"eps_ntm": 8.0}}
    v = context._consensus_lookback(hist, "X", SESSION, context.FRAMEWORK_WEEKS_6M)
    assert v is None


def test_lookback_never_returns_a_different_tickers_value():
    hist = {"weekly": {}}
    d_6m_ago = SESSION - timedelta(weeks=context.FRAMEWORK_WEEKS_6M)
    hist["weekly"][context._iso_week_key(d_6m_ago)] = {"OTHER": {"eps_ntm": 999.0}}
    v = context._consensus_lookback(hist, "X", SESSION, context.FRAMEWORK_WEEKS_6M)
    assert v is None


# ── Weekly snapshot cadence ──────────────────────────────────────────────────

def test_snapshot_fires_once_per_iso_week_not_every_call():
    hist = {"weekly": {}}
    facts = {"X": {"eps_ntm": 10.0}}
    hist = context._snapshot_consensus(hist, facts, SESSION)
    assert len(hist["weekly"]) == 1
    # Same week, different day, different value offered: must NOT overwrite.
    facts2 = {"X": {"eps_ntm": 999.0}}
    hist = context._snapshot_consensus(hist, facts2, SESSION + timedelta(days=1))
    assert len(hist["weekly"]) == 1
    wk = context._iso_week_key(SESSION)
    assert hist["weekly"][wk]["X"]["eps_ntm"] == pytest.approx(10.0)


def test_snapshot_fires_again_in_a_new_iso_week():
    hist = {"weekly": {}}
    facts = {"X": {"eps_ntm": 10.0}}
    hist = context._snapshot_consensus(hist, facts, SESSION)
    hist = context._snapshot_consensus(hist, {"X": {"eps_ntm": 11.0}}, SESSION + timedelta(weeks=1))
    assert len(hist["weekly"]) == 2


def test_snapshot_skips_a_ticker_with_no_eps_ntm():
    hist = {"weekly": {}}
    facts = {"X": {"eps_ntm": None}, "Y": {"eps_ntm": 5.0}}
    hist = context._snapshot_consensus(hist, facts, SESSION)
    wk = context._iso_week_key(SESSION)
    assert "X" not in hist["weekly"][wk]
    assert hist["weekly"][wk]["Y"]["eps_ntm"] == pytest.approx(5.0)


# ── Verdict tiers ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("passed,evaluated,want", [
    (5, 5, "BUY_5"), (4, 5, "BUY_4"), (3, 5, "ADD"), (2, 5, "HOLD"),
    (1, 5, "AVOID"), (0, 5, "AVOID"),
    # Fewer than all 5 filters resolved: the tier word carries "_BUILDING" so
    # it can never render byte-identical to the same tier reached with a
    # complete, genuinely mixed record (2026-08-22 review, data honesty
    # finding #3 — this parametrization's own (3, 3, "ADD") case used to be
    # exactly the collision the finding flagged, indistinguishable from
    # (3, 5, "ADD") above where the other 2 filters had actually FAILED).
    (3, 3, "ADD_BUILDING"), (4, 4, "BUY_4_BUILDING"), (1, 4, "AVOID_BUILDING"),
    (2, 2, "BUILDING"),     # fewer than FRAMEWORK_MIN_EVALUATED (3) -> never a tier
    (0, 0, "BUILDING"),
])
def test_verdict_tiers(passed, evaluated, want):
    assert context._framework_verdict(passed, evaluated) == want


def test_verdict_capped_when_every_unresolved_filter_is_flagged():
    # 2 unresolved (5-3), both flagged -- this verdict can NEVER move by
    # waiting, unlike a genuine "_BUILDING" gap (2026-08-22 review round
    # 12, data honesty finding #2).
    assert context._framework_verdict(3, 3, flagged=2) == "ADD_CAPPED"


def test_verdict_still_building_when_only_some_unresolved_filters_are_flagged():
    # 2 unresolved, only 1 flagged -- the other is genuinely still pending,
    # so the verdict COULD still move once it reports.
    assert context._framework_verdict(3, 3, flagged=1) == "ADD_BUILDING"


def test_verdict_capped_never_fires_below_min_evaluated():
    # Below FRAMEWORK_MIN_EVALUATED, the verdict is plain BUILDING regardless
    # of how many unresolved filters are flagged.
    assert context._framework_verdict(2, 2, flagged=3) == "BUILDING"


def test_score_framework_verdict_is_capped_when_only_flagged_filters_remain_unresolved():
    # Filters 1/3 (consensus-history) both resolve and pass; filters 2
    # (revenue growth, no rev_ntm here) is unknown for an unrelated reason
    # that keeps evaluated at 2 -- raise it to 3 by also passing filter 2,
    # so only 4/5 and 5's ceiling-rejections are left unresolved, both
    # flagged.
    hist = {"weekly": {}}
    d_6m = SESSION - timedelta(weeks=context.FRAMEWORK_WEEKS_6M)
    d_3m = SESSION - timedelta(weeks=context.FRAMEWORK_WEEKS_3M)
    hist["weekly"][context._iso_week_key(d_6m)] = {"X": {"eps_ntm": 8.0}}
    hist["weekly"][context._iso_week_key(d_3m)] = {"X": {"eps_ntm": 9.0}}
    fund = _fund(
        revenue=[100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
        opinc=[23.0, 23.0, 23.0, 23.0, 23.0, 23.0, 23.0, 80.0],   # +5700bps: flagged
        fcf=[10.0, 10.0, 10.0, 10.0, 50.0, 50.0, 50.0, 50.0],     # +400%: flagged
        annual_revenue=[100.0],
    )
    f = {"eps_ntm": 10.0, "rev_ntm": 130.0}
    out = context.score_framework("X", f, fund, hist, SESSION)
    assert out["filters"]["opmargin_expansion"] is None
    assert out["filters"]["fcf_growth"] is None
    assert set(out["filter_flags"].keys()) == {"opmargin_expansion", "fcf_growth"}
    assert out["filters_passed"] == 3   # forward_eps_revision, revenue_growth, analyst_velocity
    assert out["verdict"] == "ADD_CAPPED"


def test_full_5_of_5_verdict_end_to_end():
    hist = {"weekly": {}}
    d_6m = SESSION - timedelta(weeks=context.FRAMEWORK_WEEKS_6M)
    d_3m = SESSION - timedelta(weeks=context.FRAMEWORK_WEEKS_3M)
    hist["weekly"][context._iso_week_key(d_6m)] = {"X": {"eps_ntm": 8.0}}
    hist["weekly"][context._iso_week_key(d_3m)] = {"X": {"eps_ntm": 9.0}}
    fund = _fund(
        revenue=[100.0] * 8, opinc=[20.0, 20.0, 20.0, 20.0, 22.0, 22.0, 22.0, 22.0],
        fcf=[10.0, 10.0, 10.0, 10.0, 15.0, 15.0, 15.0, 15.0],
        annual_revenue=[100.0],
    )
    f = {"eps_ntm": 10.0, "rev_ntm": 130.0}
    out = context.score_framework("X", f, fund, hist, SESSION)
    assert out["filters_passed"] == 5
    assert out["filters_unknown"] == 0
    assert out["verdict"] == "BUY_5"


def test_missing_fund_never_fabricates_the_three_fund_dependent_filters():
    f = {"eps_ntm": 10.0, "rev_ntm": None}
    out = context.score_framework("X", f, None, {"weekly": {}}, SESSION)
    assert out["filters"]["revenue_growth"] is None
    assert out["filters"]["opmargin_expansion"] is None
    assert out["filters"]["fcf_growth"] is None
    assert out["metrics"] == {}


# ── consensus_history.json persistence (build_snapshot.py) ─────────────────

def test_consensus_history_round_trips_through_disk(tmp_path):
    hist = {"v": 1, "weekly": {"2026-W10": {"MU": {"eps_ntm": 12.3}}}}
    save_consensus_history(tmp_path, hist)
    reloaded = load_consensus_history(tmp_path)
    assert reloaded["weekly"]["2026-W10"]["MU"]["eps_ntm"] == pytest.approx(12.3)


def test_consensus_history_load_is_fail_soft_on_missing_file(tmp_path):
    reloaded = load_consensus_history(tmp_path / "does-not-exist")
    assert reloaded == {"v": 1, "weekly": {}}


def test_consensus_history_prunes_to_max_weeks(tmp_path):
    hist = {"v": 1, "weekly": {f"2020-W{i:02d}": {"X": {"eps_ntm": 1.0}} for i in range(1, 53)}}
    save_consensus_history(tmp_path, hist)
    reloaded = load_consensus_history(tmp_path)
    assert len(reloaded["weekly"]) == MAX_CONSENSUS_WEEKS
    # The oldest weeks are the ones dropped, not an arbitrary subset.
    assert "2020-W01" not in reloaded["weekly"]
    assert f"2020-W{52:02d}" in reloaded["weekly"]


# ── sec_type gate: a fund can never resolve a filter (added 2026-09-03) ─────
# Zach's report: "LLY is not a fund but says building as well?" — which
# surfaced that the panel used one word, "building", for three unrelated
# states. A fund's is the worst of the three: it promised a result that
# structurally cannot arrive, on 25 of the 63 scored names.

def test_fund_reads_not_applicable_never_building():
    """A fund has no revenue/margin/cash flow of its own, so "still gathering
    data" is a false promise for it — the verdict must say so outright."""
    f = {"sec_type": "fund", "eps_ntm": 5.0, "rev_ntm": 200.0}
    out = context.score_framework("SPY", f, _fund(annual_revenue=[100.0]), {"weekly": {}}, SESSION)
    assert out["verdict"] == "NOT_APPLICABLE"
    assert out["filters_passed"] == 0
    assert out["filters_failed"] == 0
    assert all(v is None for v in out["filters"].values())
    assert out["metrics"] == {}
    assert out["filter_flags"] == {}


def test_fund_gate_wins_even_when_a_filter_would_have_passed():
    """The rev_ntm/annual pair here would score revenue_growth True on any
    ordinary name. A fund must not borrow a passing filter from vendor data
    that does not describe a company."""
    f = {"sec_type": "fund", "rev_ntm": 200.0}
    out = context.score_framework("QQQ", f, _fund(annual_revenue=[100.0]), {"weekly": {}}, SESSION)
    assert out["verdict"] == "NOT_APPLICABLE"
    assert out["filters"]["revenue_growth"] is None


@pytest.mark.parametrize("sec_type", ["dr", "stock", None, "", "DR"])
def test_non_fund_types_keep_their_score(sec_type):
    """"dr" is a depositary receipt — an ADR of a real foreign operating
    company (TSM, SKHY) with real financials — and must keep its score. A
    null/blank type is an absent reading, never grounds for a verdict. Only
    "fund" is excluded; a blanket "anything that isn't stock" would have
    silently killed two real companies on the pinned list."""
    f = {"sec_type": sec_type, "rev_ntm": 121.0}
    out = context.score_framework("TSM", f, _fund(annual_revenue=[100.0]), {"weekly": {}}, SESSION)
    assert out["verdict"] != "NOT_APPLICABLE"
    assert out["filters"]["revenue_growth"] is True


def test_fund_gate_is_case_insensitive():
    f = {"sec_type": "Fund"}
    out = context.score_framework("SPY", f, None, {"weekly": {}}, SESSION)
    assert out["verdict"] == "NOT_APPLICABLE"


def test_not_applicable_emits_the_same_filter_keys_a_real_score_does():
    """The early return builds its filter map from FRAMEWORK_FILTER_KEYS
    rather than a hand-copied literal, so a sixth filter can never leave the
    two shapes disagreeing. This test is what makes that guarantee real."""
    scored = context.score_framework("X", {"rev_ntm": 121.0}, _fund(annual_revenue=[100.0]),
                                     {"weekly": {}}, SESSION)
    na = context.score_framework("SPY", {"sec_type": "fund"}, None, {"weekly": {}}, SESSION)
    assert set(na["filters"]) == set(scored["filters"])
    assert set(na) == set(scored)


def test_sec_type_rides_the_scanner_quote_into_facts():
    """facts.<T>.sec_type is what score_framework gates on, so the column has
    to actually survive the quote -> facts hop."""
    quotes = {"SPY": {"sec_type": "fund"}, "MU": {"sec_type": "stock"}, "X": {}}
    facts = context.fetch_earnings_days(quotes, SESSION)
    assert facts["SPY"]["sec_type"] == "fund"
    assert facts["MU"]["sec_type"] == "stock"
    assert facts["X"]["sec_type"] is None


def test_type_column_is_fetched_and_parsed_end_to_end():
    """The full chain the fund gate depends on: TV_COLUMNS asks for `type`,
    _row_to_quote lifts it onto the quote as sec_type, fetch_earnings_days
    carries it into facts, and score_framework gates on it. Any one of those
    four hops silently dropping the field would put every fund back on the
    bare "BUILDING" verdict with no test failing."""
    from build_snapshot import TV_COLUMNS, _COL, _row_to_quote

    assert "type" in TV_COLUMNS, "the fund gate has no signal without this column"

    row = [None] * len(TV_COLUMNS)
    row[_COL["close"]] = 640.0
    row[_COL["type"]] = "fund"
    quote = _row_to_quote("AMEX:SPY", row)
    assert quote is not None and quote["sec_type"] == "fund"

    facts = context.fetch_earnings_days({"SPY": quote}, SESSION)
    out = context.score_framework("SPY", facts["SPY"], None, {"weekly": {}}, SESSION)
    assert out["verdict"] == "NOT_APPLICABLE"


# ── Filter 3 from Yahoo's own revision trend (added 2026-09-03) ─────────────
# Zach: "The things that are building that require historical data — are they
# not able to be deduced from tradingview or any other free source to know
# now?" For the 3-month filter, yes: Yahoo publishes the next-FY consensus as
# it stood 90 days ago. The 6-month filter still has no free source.

def _trend(current, d90):
    return {"quarterly": {"revenue": [], "fcf": [], "opinc": []}, "annual": {"revenue": []},
            "eps_trend": {"current": current, "d90": d90, "period_end": "2027-08-31"}}


def test_analyst_velocity_resolves_today_from_the_yahoo_trend():
    """No consensus history at all, and the filter still answers — that is the
    whole point of the change."""
    out = context.score_framework("MU", {"eps_ntm": 155.0}, _trend(155.02524, 102.72243),
                                  {"weekly": {}}, SESSION)
    assert out["filters"]["analyst_velocity"] is True
    assert out["metrics"]["eps_velocity_3m_pct"] == pytest.approx(50.92, abs=0.02)


def test_analyst_velocity_reads_a_downgrade_as_false():
    out = context.score_framework("CRWD", {"eps_ntm": 1.6}, _trend(1.59788, 1.6227),
                                  {"weekly": {}}, SESSION)
    assert out["filters"]["analyst_velocity"] is False


def test_analyst_velocity_handles_a_profit_to_loss_sign_flip():
    """Measured live 2026-09-03: CLSK -129.7%, NBIS -139.2%, both real flips
    from a positive consensus to a negative one. A plain magnitude comparison
    must call that a downgrade, not a pass, and must stay inside the 300%
    implausibility ceiling rather than reading UNKNOWN."""
    out = context.score_framework("CLSK", {"eps_ntm": -0.03}, _trend(-0.03, 0.10),
                                  {"weekly": {}}, SESSION)
    assert out["filters"]["analyst_velocity"] is False
    assert "analyst_velocity" not in out["filter_flags"]
    assert out["metrics"]["eps_velocity_3m_pct"] == pytest.approx(-130.0)


def test_yahoo_trend_never_pairs_with_tradingviews_eps_ntm():
    """Both legs of the ratio must come from the eps_trend object. If the
    numerator silently fell back to facts.eps_ntm (a DIFFERENT vendor's
    estimate) this would compute 300/102.7 = +192% instead of the real
    +50.9% — the cross-vendor artifact round 19 had to cap on Filter 2."""
    out = context.score_framework("MU", {"eps_ntm": 300.0}, _trend(155.02524, 102.72243),
                                  {"weekly": {}}, SESSION)
    assert out["metrics"]["eps_velocity_3m_pct"] == pytest.approx(50.92, abs=0.02)


def test_missing_yahoo_trend_falls_back_to_the_accumulated_snapshots():
    """Funds and a few thin names get no module from Yahoo. Those tickers must
    behave exactly as they did before this change, not regress to UNKNOWN."""
    hist = {"weekly": {context._iso_week_key(SESSION - timedelta(weeks=13)): {"X": {"eps_ntm": 10.0}}}}
    out = context.score_framework("X", {"eps_ntm": 12.0}, _fund(), hist, SESSION)
    assert out["filters"]["analyst_velocity"] is True
    assert out["metrics"]["eps_velocity_3m_pct"] == pytest.approx(20.0)


@pytest.mark.parametrize("trend", [
    {"current": 5.0, "d90": 0},        # divide-by-zero
    {"current": 5.0, "d90": None},     # half-populated
    {"current": None, "d90": 5.0},
])
def test_unusable_trend_object_does_not_crash_or_guess(trend):
    out = context.score_framework("X", {"eps_ntm": None},
                                  {"quarterly": {}, "annual": {}, "eps_trend": trend},
                                  {"weekly": {}}, SESSION)
    assert out["filters"]["analyst_velocity"] is None


# ── the Yahoo parser itself ─────────────────────────────────────────────────

def test_parse_eps_trend_takes_the_next_fiscal_year_row():
    mod = {"trend": [
        {"period": "0y",  "endDate": "2026-08-31", "epsTrend": {"current": {"raw": 73.4}, "90daysAgo": {"raw": 58.3}}},
        {"period": "+1y", "endDate": "2027-08-31", "epsTrend": {"current": {"raw": 155.0}, "90daysAgo": {"raw": 102.7}}},
    ]}
    out = context._parse_eps_trend(mod)
    assert out == {"current": 155.0, "d90": 102.7, "period_end": "2027-08-31"}


@pytest.mark.parametrize("mod", [
    None, {}, {"trend": []}, {"trend": "nope"},
    {"trend": [{"period": "0y", "epsTrend": {"current": {"raw": 1.0}, "90daysAgo": {"raw": 1.0}}}]},
    {"trend": [{"period": "+1y", "epsTrend": {"current": {"raw": 1.0}}}]},
    {"trend": [{"period": "+1y", "epsTrend": {"current": {"raw": 1.0}, "90daysAgo": {"raw": 0}}}]},
])
def test_parse_eps_trend_is_none_rather_than_partial(mod):
    """A half-populated dict would read as "we have a trend" to any caller
    that truthiness-checks it, then divide by a missing number."""
    assert context._parse_eps_trend(mod) is None


# ── Forecast tab columns (added 2026-09-03) ─────────────────────────────────

def test_forecast_columns_are_fetched_and_reach_facts():
    """The Forecast tab draws entirely from these seven scanner fields. They
    ride the batch quote every other fact already uses, so a silent drop
    anywhere in the chain would empty the tab with nothing failing."""
    from build_snapshot import TV_COLUMNS, _COL, _row_to_quote

    for col in ("price_target_high", "price_target_low", "price_target_median",
                "recommendation_total", "recommendation_buy", "recommendation_hold",
                "recommendation_sell"):
        assert col in TV_COLUMNS, col

    # AAOI's live 2026-09-03 reading, checked against TradingView's own
    # Forecast page for the same symbol that day.
    row = [None] * len(TV_COLUMNS)
    row[_COL["close"]] = 101.5
    row[_COL["price_target_average"]] = 170.5
    row[_COL["price_target_high"]] = 220.0
    row[_COL["price_target_low"]] = 109.0
    row[_COL["price_target_median"]] = 184.0
    row[_COL["recommendation_total"]] = 8
    row[_COL["recommendation_buy"]] = 4
    row[_COL["recommendation_hold"]] = 3
    row[_COL["recommendation_sell"]] = 0
    q = _row_to_quote("NASDAQ:AAOI", row)
    facts = context.fetch_earnings_days({"AAOI": q}, SESSION)["AAOI"]
    assert facts["target"] == 170.5 and facts["target_high"] == 220.0
    assert facts["target_low"] == 109.0 and facts["target_median"] == 184.0
    assert facts["rec_total"] == 8 and facts["rec_buy"] == 4
    assert facts["rec_hold"] == 3 and facts["rec_sell"] == 0
    # The vendor's own buckets sum to less than its own total here. The tab
    # discloses the shortfall rather than reshaping the bars, so this stays
    # a documented property of the data, not a bug to "fix" by rescaling.
    assert facts["rec_buy"] + facts["rec_hold"] + facts["rec_sell"] < facts["rec_total"]
