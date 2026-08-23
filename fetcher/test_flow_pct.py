"""FLOW % (flow_pct / flow_side) — the near-money premium-weighted put/call split.

Run: python3 -m pytest fetcher/test_flow_pct.py

Why the near-money restriction exists (2026-07-28): premium is intrinsic +
extrinsic value, and a deep-ITM contract costs almost exactly what it is
already worth. A handful of those carry enormous "premium" while betting on
nothing — they are a way of holding the stock. Weighting the whole 0-7 DTE
bucket by dollars let that paper dictate the reading: LLY on 2026-07-27
printed 84% CALL off seven Jul-31 strikes ~35% below a ~$1,205 spot.

These tests pin the fix AND pin the thing the fix must not touch: net_flow
keeps its whole-bucket definition, because net_flow is a scoring input.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_snapshot import (  # noqa: E402
    analyze_ticker, MONEYNESS_BAND, _so_delta_is_split, build_etf_flows)

SESSION = date(2026, 7, 27)


def _occ(root: str, expiry: str, cp: str, strike: float) -> str:
    return f"{root}{expiry}{cp}{int(round(strike * 1000)):08d}"


def _opt(root, expiry, cp, strike, vol, last, oi=100, bid=None, ask=None):
    return {
        "option": _occ(root, expiry, cp, strike),
        "volume": vol, "last_trade_price": last, "open_interest": oi,
        "bid": bid if bid is not None else max(0.0, last - 0.05),
        "ask": ask if ask is not None else last + 0.05,
        "delta": 0.5, "iv": 0.4,
    }


def _chain(spot, options, iv30=0.4):
    return {"spot": spot, "iv30": iv30, "options": options}


# expiry 2 days after SESSION -> inside the 0-7 DTE bucket
EXP = "260729"


def test_deep_itm_stock_replacement_no_longer_sets_the_split():
    """The LLY shape, reduced: a wall of cheap near-money puts against a few
    very expensive deep-ITM calls. Whole-bucket dollars say CALL; the honest
    near-money read says PUT."""
    spot = 1200.0
    options = [
        # deep-ITM calls ~34% below spot: ~100% intrinsic, not a bet
        _opt("LLY", EXP, "C", 790.0, 64, 409.0),   # $2.62M
        _opt("LLY", EXP, "C", 795.0, 64, 404.0),   # $2.59M
        # real near-money book: puts outspend calls
        _opt("LLY", EXP, "C", 1200.0, 200, 18.0),  # $0.36M
        _opt("LLY", EXP, "P", 1190.0, 500, 20.0),  # $1.00M
    ]
    a = analyze_ticker("LLY", _chain(spot, options), SESSION)

    # near-money only: calls $0.36M vs puts $1.00M -> 73.5% PUT
    assert a["flow_side"] == "PUT"
    assert a["flow_pct"] == pytest.approx(73.5, abs=0.1)

    # net_flow is deliberately UNCHANGED — whole bucket, deep-ITM calls included
    assert a["net_flow"] == pytest.approx(
        (64 * 409.0 + 64 * 404.0 + 200 * 18.0 - 500 * 20.0) * 100)
    assert a["direction"] == "BULL"     # and it still reads BULL off that


def test_split_ignores_strikes_outside_the_band_on_both_sides():
    """Symmetry: deep-OTM lottery strikes and deep-ITM strikes are both out."""
    spot = 100.0
    far_call = 100.0 * (1 + MONEYNESS_BAND) + 1.0    # just outside
    far_put = 100.0 * (1 - MONEYNESS_BAND) - 1.0     # just outside
    options = [
        _opt("T", EXP, "C", far_call, 10_000, 0.02),   # deep OTM churn
        _opt("T", EXP, "P", far_put, 10_000, 0.02),
        _opt("T", EXP, "C", 40.0, 50, 60.0),          # deep ITM call
        _opt("T", EXP, "P", 160.0, 50, 60.0),         # deep ITM put
        _opt("T", EXP, "C", 100.0, 100, 2.0),         # the only real bets
        _opt("T", EXP, "P", 100.0, 300, 2.0),
    ]
    a = analyze_ticker("T", _chain(spot, options), SESSION)
    # $20k calls vs $60k puts -> 75% PUT
    assert a["flow_side"] == "PUT"
    assert a["flow_pct"] == pytest.approx(75.0, abs=0.1)


def test_strike_exactly_on_the_band_edge_is_included():
    spot = 100.0
    options = [
        _opt("T", EXP, "C", spot * (1 + MONEYNESS_BAND), 100, 1.0),
        _opt("T", EXP, "P", spot * (1 - MONEYNESS_BAND), 100, 3.0),
    ]
    a = analyze_ticker("T", _chain(spot, options), SESSION)
    assert a["flow_pct"] == pytest.approx(75.0, abs=0.1)
    assert a["flow_side"] == "PUT"


def test_no_near_money_premium_reports_nothing_rather_than_guessing():
    """All the volume is far from the money -> the split is unknown, and the
    card must show a dash instead of a number nobody can defend."""
    spot = 100.0
    options = [
        _opt("T", EXP, "C", 40.0, 500, 60.0),
        _opt("T", EXP, "P", 300.0, 500, 200.0),
    ]
    a = analyze_ticker("T", _chain(spot, options), SESSION)
    assert a["flow_pct"] is None and a["flow_side"] is None
    # but the raw bucket still reported, so net_flow/score are unaffected
    assert a["net_flow"] != 0


def test_missing_spot_fails_closed():
    """With no spot there is no way to tell a stock-replacement strike from a
    bet, so the split must be withheld, not guessed."""
    options = [_opt("T", EXP, "C", 100.0, 100, 1.0),
               _opt("T", EXP, "P", 100.0, 100, 3.0)]
    a = analyze_ticker("T", _chain(None, options), SESSION)
    assert a["flow_pct"] is None and a["flow_side"] is None


def test_split_is_always_the_dominant_side_between_50_and_100():
    spot = 100.0
    for cpx, ppx in ((1.0, 4.0), (4.0, 1.0), (2.0, 2.0), (0.05, 9.9)):
        options = [_opt("T", EXP, "C", 100.0, 500, cpx),
                   _opt("T", EXP, "P", 100.0, 500, ppx)]
        a = analyze_ticker("T", _chain(spot, options), SESSION)
        assert 50.0 <= a["flow_pct"] <= 100.0


def test_exact_tie_resolves_to_put():
    spot = 100.0
    options = [_opt("T", EXP, "C", 100.0, 100, 2.0),
               _opt("T", EXP, "P", 100.0, 100, 2.0)]
    a = analyze_ticker("T", _chain(spot, options), SESSION)
    assert a["flow_pct"] == pytest.approx(50.0)
    assert a["flow_side"] == "PUT"


def test_contracts_outside_the_dte_bucket_never_count():
    """FLOW % is a 0-7 DTE reading; a near-money 30-day contract is not it."""
    spot = 100.0
    options = [
        _opt("T", EXP, "C", 100.0, 100, 1.0),
        _opt("T", "260901", "P", 100.0, 10_000, 50.0),   # ~37 DTE, huge
    ]
    a = analyze_ticker("T", _chain(spot, options), SESSION)
    assert a["flow_side"] == "CALL"
    assert a["flow_pct"] == pytest.approx(100.0)


# ── SO-based ETF flow: split guard (added 2026-07-28) ────────────────────────
# flow_1d = ΔSO x NAV is only money-in/out while the share count moves for
# creation/redemption reasons. SOXL and SOXS reverse-split routinely, and a
# 1-for-10 divides SO by 10 overnight -> a naive read prints an outflow of ~90%
# of the fund's AUM on a day nobody moved a dollar. Same fabricated-number
# class as the CRWD 4-for-1 that printed a fake -74.9% in the Jul 1 2026 brief.
@pytest.mark.parametrize("ratio", [2, 3, 4, 5, 6, 8, 10, 20])
def test_reverse_split_detected_from_reciprocal_so_and_nav(ratio):
    assert _so_delta_is_split(1_000_000.0, 1_000_000.0 / ratio, 20.0, 20.0 * ratio)


@pytest.mark.parametrize("ratio", [2, 3, 4, 10])
def test_forward_split_detected(ratio):
    assert _so_delta_is_split(1_000_000.0, 1_000_000.0 * ratio, 400.0, 400.0 / ratio)


def test_real_creations_are_not_a_split():
    """SO up 3% with NAV essentially flat is money in, and must survive."""
    assert not _so_delta_is_split(1_000_000.0, 1_030_000.0, 20.0, 20.10)


def test_big_real_redemption_is_not_a_split():
    """SO halves while NAV barely moves -> a genuine, large outflow."""
    assert not _so_delta_is_split(1_000_000.0, 500_000.0, 20.0, 20.05)


def test_split_shaped_move_without_nav_is_withheld():
    """Cannot confirm without both NAVs; split-shaped means withhold rather
    than print a probably-fabricated number."""
    assert _so_delta_is_split(1_000_000.0, 100_000.0, None, 20.0)
    assert _so_delta_is_split(1_000_000.0, 100_000.0, 20.0, None)


def test_non_split_ratio_without_nav_is_kept():
    """A 3% move is not a split factor, so a missing NAV must not hide it."""
    assert not _so_delta_is_split(1_000_000.0, 1_030_000.0, None, None)


def test_bad_inputs_are_not_splits():
    for args in ((0, 100, 1, 1), (100, 0, 1, 1), (None, 100, 1, 1),
                 ("x", 100, 1, 1)):
        assert not _so_delta_is_split(*args)


def _etf_history(rows):
    """rows: {ticker: {session: {"so":..,"nav":..}}}"""
    return {"etf_so": rows}


def test_build_etf_flows_withholds_the_flow_on_a_split(monkeypatch):
    import build_snapshot as bs
    monkeypatch.setattr(bs, "ETF_FLOW_FUNDS", ["SOXS"])
    # live row: post-reverse-split SO and NAV
    monkeypatch.setattr(bs, "fetch_etf_fund_rows",
                        lambda: {"SOXS": {"so": 1_000_000.0, "nav": 615.10,
                                          "aum": None, "flow_1m": None}})
    hist = _etf_history({"SOXS": {"2026-07-27": {"so": 10_000_000.0,
                                                 "nav": 61.51}}})
    out = bs.build_etf_flows(hist, "2026-07-28", write_history=False)
    fund = out["funds"][0]
    assert fund["split_suppressed"] is True
    assert fund["flow_1d"] is None, "a split must never print as a flow"
    # DATA_CONTRACT.md: both null when flow_1d is null (2026-08-23 Fable
    # architect pass, finding 2.5) — a split day used to publish streak:0 and
    # a real baseline_session date, contradicting the contract.
    assert fund["baseline_session"] is None
    assert fund["streak"] is None
    assert fund["flow_session"] is None


def test_build_etf_flows_still_reports_an_ordinary_day(monkeypatch):
    import build_snapshot as bs
    monkeypatch.setattr(bs, "ETF_FLOW_FUNDS", ["SMH"])
    monkeypatch.setattr(bs, "fetch_etf_fund_rows",
                        lambda: {"SMH": {"so": 10_200_000.0, "nav": 531.35,
                                         "aum": None, "flow_1m": None}})
    hist = _etf_history({"SMH": {"2026-07-27": {"so": 10_000_000.0,
                                                "nav": 528.00}}})
    out = bs.build_etf_flows(hist, "2026-07-28", write_history=False)
    fund = out["funds"][0]
    assert fund["split_suppressed"] is False
    assert fund["flow_1d"] == pytest.approx(200_000 * 531.35)


def test_build_etf_flows_labels_the_flow_session_not_the_capture_date():
    """ONE-SESSION PUBLICATION LAG (measured 2026-07-28): the vendor record read
    during session S carries the official shares/NAV struck at the close of S-1.
    The arithmetic is unaffected, but labelling a flow with the capture date
    claims a day of freshness it does not have."""
    import build_snapshot as bs
    import pytest as _pytest

    monkey = _pytest.MonkeyPatch()
    try:
        monkey.setattr(bs, "ETF_FLOW_FUNDS", ["SMH"])
        monkey.setattr(bs, "fetch_etf_fund_rows",
                       lambda: {"SMH": {"so": 10_200_000.0, "nav": 531.35,
                                        "aum": None, "flow_1m": None}})
        hist = {"etf_so": {"SMH": {"2026-07-27": {"so": 10_000_000.0,
                                                  "nav": 528.00}}}}
        out = bs.build_etf_flows(hist, "2026-07-28", write_history=False)
    finally:
        monkey.undo()

    assert out["as_of_session"] == "2026-07-28", "capture date is still reported"
    assert out["flow_session"] == "2026-07-27", "the flow belongs to Jul 27"
    assert out["funds"][0]["flow_session"] == "2026-07-27"


def test_near_money_premium_inputs_are_exposed_for_archival():
    """FLOW % is a ratio; a ratio cannot be re-weighted or re-derived after the
    fact. The accuracy backtest (2026-07-28) found history had stored only
    net_flow and gross premium, so not one day of historical FLOW % existed.
    These two fields are what make a future determination possible."""
    spot = 100.0
    options = [
        _opt("T", EXP, "C", 100.0, 200, 2.0),      # $40k near-money calls
        _opt("T", EXP, "P", 100.0, 300, 2.0),      # $60k near-money puts
        _opt("T", EXP, "C", 40.0, 50, 60.0),       # deep ITM — excluded
    ]
    a = analyze_ticker("T", _chain(spot, options), SESSION)
    assert a["nm_call_prem_0_7"] == pytest.approx(40_000.0)
    assert a["nm_put_prem_0_7"] == pytest.approx(60_000.0)
    # and they must reproduce the published ratio exactly
    tot = a["nm_call_prem_0_7"] + a["nm_put_prem_0_7"]
    assert round(100 * a["nm_put_prem_0_7"] / tot, 1) == pytest.approx(a["flow_pct"])
    assert a["flow_side"] == "PUT"
