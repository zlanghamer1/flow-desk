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
    (3, 3, "ADD"),          # only 3 filters evaluated, all 3 pass -> still ADD
    (2, 2, "BUILDING"),     # fewer than FRAMEWORK_MIN_EVALUATED (3) -> never a tier
    (0, 0, "BUILDING"),
])
def test_verdict_tiers(passed, evaluated, want):
    assert context._framework_verdict(passed, evaluated) == want


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
