"""fund_flows_history — ICI weekly flows accumulated across cycles (2026-09-21).

Pins: the seed never overwrites an observed week; the live release does
(ICI revises); the published block is oldest-first and reconciles with the
file; the monthly series stays a separate key; retention prunes oldest
first; a bad or missing file / seed reads as empty, never raises; the
checked-in seed itself reconciles (equity = domestic + world, and so on).

Run: python3 -m pytest fetcher/test_fund_flows_history.py -q
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fund_flows_history as ffh  # noqa: E402


def _row(v: float) -> dict:
    """A full nine-key row whose components reconcile to `total` v."""
    return {"total": v, "equity": v / 2, "domestic_equity": v / 4, "world_equity": v / 4,
            "hybrid": 0.0, "bond": v / 2, "taxable_bond": v / 2, "municipal_bond": 0.0,
            "commodity": 0.0}


def _live(weeks: dict, released="2026-09-16") -> dict:
    return {"released": released,
            "weeks": [{"week_ended": k, **r} for k, r in sorted(weeks.items(), reverse=True)]}


def test_seed_fills_gaps_and_never_overwrites_an_observed_week():
    hist = ffh.load_history(Path("/nonexistent"))
    hist["weekly"]["2026-08-05"] = _row(100.0)          # the loop's own observation
    seed = {"fetched": "2026-09-21",
            "weekly": {"2026-08-05": _row(999.0), "2026-07-29": _row(50.0)},
            "monthly": {"2026-07-31": _row(1000.0)}}
    s = ffh.apply_cycle(hist, None, seed)
    assert hist["weekly"]["2026-08-05"]["total"] == 100.0    # observed row kept
    assert hist["weekly"]["2026-07-29"]["total"] == 50.0     # gap filled
    assert hist["monthly"]["2026-07-31"]["total"] == 1000.0
    assert s == {"added_seed": 2, "added_live": 0, "revised": 0, "weeks": 2, "months": 1}
    assert hist["seed_fetched"] == "2026-09-21"


def test_live_release_overwrites_a_revised_week_and_stamps_the_release():
    hist = ffh.load_history(Path("/nonexistent"))
    hist["weekly"]["2026-09-02"] = _row(8120.0)          # last week's print
    s = ffh.apply_cycle(hist, _live({"2026-09-02": _row(8131.0), "2026-09-09": _row(1559.0)}), None)
    assert hist["weekly"]["2026-09-02"]["total"] == 8131.0  # ICI's revision wins
    assert hist["weekly"]["2026-09-09"]["total"] == 1559.0
    assert s["added_live"] == 1 and s["revised"] == 1
    assert hist["last_release"] == "2026-09-16"


def test_live_row_without_a_numeric_reading_or_a_date_is_not_a_row():
    hist = ffh.load_history(Path("/nonexistent"))
    live = {"weeks": [{"week_ended": "2026-09-09"},              # no numbers
                      {"week_ended": "bad", "total": 1.0},        # bad key
                      {"total": 1.0},                             # no key
                      "junk"]}
    s = ffh.apply_cycle(hist, live, None)
    assert hist["weekly"] == {} and s["added_live"] == 0


def test_publish_block_is_oldest_first_and_keeps_monthly_separate():
    hist = ffh.load_history(Path("/nonexistent"))
    ffh.apply_cycle(hist, _live({"2026-09-09": _row(1.0), "2026-08-26": _row(-3.0), "2026-09-02": _row(2.0)}),
                    {"weekly": {}, "monthly": {"2026-07-31": _row(7.0), "2026-06-30": _row(6.0)}})
    b = ffh.publish_block(hist)
    assert [w["week_ended"] for w in b["weekly"]] == ["2026-08-26", "2026-09-02", "2026-09-09"]
    assert [m["month_ended"] for m in b["monthly"]] == ["2026-06-30", "2026-07-31"]
    assert b["n_weeks"] == 3 and b["first_week"] == "2026-08-26" and b["last_week"] == "2026-09-09"
    assert b["n_months"] == 2 and b["monthly_through"] == "2026-07-31"
    assert b["unit"] == "USD millions" and b["source"] == "ICI"
    assert set(b["weekly"][0]) == {"week_ended", *ffh.FLOW_KEYS}
    # nothing on file -> no block, so the key is omitted rather than null
    assert ffh.publish_block(ffh.load_history(Path("/nonexistent"))) is None


def test_save_prunes_oldest_weeks_and_reloads_clean(tmp_path):
    hist = ffh.load_history(tmp_path)
    for i in range(ffh.MAX_FUND_FLOWS_HISTORY_WEEKS + 7):
        hist["weekly"][f"{2000 + i // 12:04d}-{(i % 12) + 1:02d}-01"] = _row(float(i))
    keys_sorted = sorted(hist["weekly"])
    ffh.save_history(tmp_path, hist)
    back = ffh.load_history(tmp_path)
    assert len(back["weekly"]) == ffh.MAX_FUND_FLOWS_HISTORY_WEEKS
    assert keys_sorted[-1] in back["weekly"] and keys_sorted[0] not in back["weekly"]
    assert back["v"] == 1


def test_corrupt_file_and_missing_seed_read_as_empty_never_raise(tmp_path):
    (tmp_path / ffh.HISTORY_FILENAME).write_text("{not json", encoding="utf-8")
    hist = ffh.load_history(tmp_path)
    assert hist["weekly"] == {} and hist["monthly"] == {}
    (tmp_path / ffh.HISTORY_FILENAME).write_text(json.dumps({"weekly": {"2026-09-09": {"total": "x"}}}),
                                                 encoding="utf-8")
    assert ffh.load_history(tmp_path)["weekly"] == {}     # a row with no number is not a row
    assert ffh.load_seed(tmp_path / "missing.json") is None
    assert ffh.apply_cycle(ffh.load_history(tmp_path), None, None)["weeks"] == 0


def test_checked_in_seed_reconciles_and_covers_the_page_gap():
    seed = ffh.load_seed()
    assert seed is not None and seed["url"] and seed["fetched"]
    assert len(seed["monthly"]) >= 31 and min(seed["monthly"]) == "2024-01-31"
    assert "2026-08-05" in seed["weekly"]     # the week ICI's page had already dropped
    for tbl in (seed["weekly"], seed["monthly"]):
        for k, r in tbl.items():
            assert abs(r["total"] - (r["equity"] + r["hybrid"] + r["bond"] + r["commodity"])) <= 2, k
            assert abs(r["equity"] - (r["domestic_equity"] + r["world_equity"])) <= 2, k
            assert abs(r["bond"] - (r["taxable_bond"] + r["municipal_bond"])) <= 2, k
    # The seed's newest week matches the live release the page fixture holds.
    assert seed["weekly"]["2026-09-09"]["domestic_equity"] == -13376.0
