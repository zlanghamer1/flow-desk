"""Gamma concentration levels — unsigned options-positioning walls.

Run: python3 -m pytest fetcher/test_gamma.py

Design authority: docs/GAMMA_LEVELS_DESIGN.md (Fable, 2026-08-22). Every test
here calls the REAL `analyze_ticker` with a synthetic chain and reads
`result["gamma"]` — never a copied-out aggregation loop. This is the
round-6/round-7 lesson, twice burned: a test that mirrors the fetcher's logic
keeps passing against a copy of a bug instead of the fetcher's real code.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_snapshot import (  # noqa: E402
    analyze_ticker, GAMMA_DTE_HI, GAMMA_MIN_CONTRACTS, GAMMA_TOP_K)

SESSION = date(2026, 8, 22)


def _occ(root: str, expiry: str, cp: str, strike: float) -> str:
    return f"{root}{expiry}{cp}{int(round(strike * 1000)):08d}"


def _expiry_str(dte: int) -> str:
    from datetime import timedelta
    d = SESSION + timedelta(days=dte)
    return d.strftime("%y%m%d")


def _opt(root, dte, cp, strike, gamma, oi=100, vol=0, last=1.0):
    return {
        "option": _occ(root, _expiry_str(dte), cp, strike),
        "gamma": gamma,
        "open_interest": oi,
        "volume": vol,
        "last_trade_price": last,
        "delta": 0.5,
        "iv": 0.4,
        "bid": max(0.0, last - 0.05),
        "ask": last + 0.05,
    }


def _chain(spot, options, iv30=0.4):
    return {"spot": spot, "iv30": iv30, "options": options}


def _fill(root, dte, n, gamma=0.05, oi=10):
    """n filler contracts (spread across strikes) to clear GAMMA_MIN_CONTRACTS
    without disturbing the strikes under test."""
    return [
        _opt(root, dte, "C", 900.0 + i, gamma, oi=oi)
        for i in range(n)
    ]


# ── 1. call + put at one strike both add (unsigned) ──────────────────────────

def test_call_and_put_at_one_strike_both_add_unsigned():
    spot = 100.0
    options = [
        _opt("T", 10, "C", 100.0, gamma=0.05, oi=1000),
        _opt("T", 10, "P", 100.0, gamma=0.05, oi=1000),
    ] + _fill("T", 10, GAMMA_MIN_CONTRACTS)
    g = analyze_ticker("T", _chain(spot, options), SESSION)["gamma"]
    assert g is not None
    lvl = next(l for l in g["levels"] if l["strike"] == 100.0)
    expected = 2 * (0.05 * 1000 * 100.0)
    assert lvl["gamma_oi"] == pytest.approx(expected)
    assert lvl["oi"] == 2000


# ── 2. negative vendor gamma adds its absolute value ─────────────────────────

def test_negative_vendor_gamma_uses_absolute_value():
    spot = 100.0
    options = [
        _opt("T", 10, "C", 105.0, gamma=-0.08, oi=500),
    ] + _fill("T", 10, GAMMA_MIN_CONTRACTS)
    g = analyze_ticker("T", _chain(spot, options), SESSION)["gamma"]
    assert g is not None
    lvl = next(l for l in g["levels"] if l["strike"] == 105.0)
    assert lvl["gamma_oi"] == pytest.approx(0.08 * 500 * 100.0)


# ── 3. dte boundary, both sides ───────────────────────────────────────────────

def test_dte_45_included_dte_46_excluded():
    spot = 100.0
    options = [
        _opt("T", GAMMA_DTE_HI, "C", 110.0, gamma=0.02, oi=1000),
        _opt("T", GAMMA_DTE_HI + 1, "C", 120.0, gamma=0.02, oi=1000),
    ] + _fill("T", 10, GAMMA_MIN_CONTRACTS)
    g = analyze_ticker("T", _chain(spot, options), SESSION)["gamma"]
    assert g is not None
    strikes = {l["strike"] for l in g["levels"]}
    assert 110.0 in strikes
    assert 120.0 not in strikes
    assert g["contracts_used"] == GAMMA_MIN_CONTRACTS + 1


# ── 4. top-K selection order and pct math ────────────────────────────────────

def test_top_k_order_and_pct_math():
    spot = 100.0
    # 5 distinct strikes with distinct gamma_oi, more than GAMMA_TOP_K, so the
    # reduction must pick the top K by gamma_oi and drop the rest.
    per_strike_oi = 1000
    gammas = [0.10, 0.08, 0.06, 0.04, 0.02]
    strikes = [90.0, 95.0, 100.0, 105.0, 110.0]
    options = [
        _opt("T", 10, "C", s, gamma=g, oi=per_strike_oi)
        for s, g in zip(strikes, gammas)
    ] + _fill("T", 10, GAMMA_MIN_CONTRACTS)
    g = analyze_ticker("T", _chain(spot, options), SESSION)["gamma"]
    assert g is not None
    assert len(g["levels"]) == GAMMA_TOP_K
    got_strikes = [l["strike"] for l in g["levels"]]
    assert got_strikes == [90.0, 95.0, 100.0, 105.0]  # desc by gamma_oi
    assert g["peak_strike"] == 90.0

    total = g["total_gamma_oi"]
    expected_total = sum(gm * per_strike_oi * 100.0 for gm in gammas) \
        + GAMMA_MIN_CONTRACTS * 0.05 * 10 * 100.0
    assert total == pytest.approx(expected_total)
    top_gamma_oi = gammas[0] * per_strike_oi * 100.0
    assert g["levels"][0]["pct"] == pytest.approx(round(top_gamma_oi / total * 100, 1))


# ── 5. fewer than GAMMA_MIN_CONTRACTS -> gamma is None ───────────────────────

def test_too_few_contracts_yields_none():
    spot = 100.0
    options = [
        _opt("T", 10, "C", 100.0, gamma=0.05, oi=1000),
    ] + _fill("T", 10, GAMMA_MIN_CONTRACTS - 2 - 1)  # total < GAMMA_MIN_CONTRACTS
    g = analyze_ticker("T", _chain(spot, options), SESSION)["gamma"]
    assert g is None


# ── 6. a contract with gamma missing is skipped, not counted ────────────────

def test_missing_gamma_contract_is_skipped_and_not_counted():
    spot = 100.0
    no_gamma = _opt("T", 10, "C", 100.0, gamma=0.05, oi=1000)
    del no_gamma["gamma"]
    options = [no_gamma] + _fill("T", 10, GAMMA_MIN_CONTRACTS)
    g = analyze_ticker("T", _chain(spot, options), SESSION)["gamma"]
    assert g is not None
    assert g["contracts_used"] == GAMMA_MIN_CONTRACTS
    assert all(l["strike"] != 100.0 for l in g["levels"])


# ── 7. oi missing/0 with gamma present: counts as contract, contributes 0 ───

def test_zero_oi_contract_counts_but_contributes_zero_and_excluded_from_levels():
    spot = 100.0
    options = [
        _opt("T", 10, "C", 100.0, gamma=0.05, oi=0),
    ] + _fill("T", 10, GAMMA_MIN_CONTRACTS)
    g = analyze_ticker("T", _chain(spot, options), SESSION)["gamma"]
    assert g is not None
    assert g["contracts_used"] == GAMMA_MIN_CONTRACTS + 1
    # gamma_oi at that strike is 0 -> strike excluded from levels entirely
    assert all(l["strike"] != 100.0 for l in g["levels"])


# ── 8. spot None chain still produces a full object with spot: None ─────────

def test_spot_none_chain_still_produces_full_object():
    options = _fill("T", 10, GAMMA_MIN_CONTRACTS)
    g = analyze_ticker("T", _chain(None, options), SESSION)["gamma"]
    assert g is not None
    assert g["spot"] is None
    assert g["levels"]


# ── 9. expiries_used counts distinct expiries, contracts_used counts contracts

def test_expiries_used_distinct_contracts_used_total():
    spot = 100.0
    options = [
        _opt("T", 10, "C", 100.0, gamma=0.05, oi=100),
        _opt("T", 10, "P", 100.0, gamma=0.05, oi=100),  # same expiry
        _opt("T", 20, "C", 105.0, gamma=0.05, oi=100),  # different expiry
    ] + _fill("T", 10, GAMMA_MIN_CONTRACTS)
    g = analyze_ticker("T", _chain(spot, options), SESSION)["gamma"]
    assert g is not None
    assert g["expiries_used"] == 2
    assert g["contracts_used"] == GAMMA_MIN_CONTRACTS + 3
