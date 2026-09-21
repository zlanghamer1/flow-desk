"""US fund-flow history — ICI's weekly estimates accumulated over time
(added 2026-09-21, Zach's ask: "build the weekly history so it charts over
time — I need to see the in & outflows over time accumulating").

Payload shape: DATA_CONTRACT.md -> "US fund flows history" and
"fund_flows_history.json".

`data.json.fund_flows` carries only the five weeks ICI's combined-flows page
shows, so the card could never draw more than five bars. This module keeps
every week the loop has ever seen in `fund_flows_history.json` on the `data`
branch (same home as gamma_history.json and verdict_history.json, never the
gitignored job-local cache) and publishes the whole run, oldest first, as
`data.json.fund_flows_history` for the page to chart.

Two sources feed the file:

* **The live page**, every cycle: `context.fetch_fund_flows`'s five weeks
  (or the keep-last-good cached release) are merged in by `week_ended`. A
  week already on file is OVERWRITTEN by the live row — ICI revises its
  estimates, and the newest print is the one to keep.
* **A one-time seed** (`fetcher/seed/ici_flows_seed.json`), read once from
  ICI's own yearly data file (the `.xls` the combined-flows page links).
  It carries the weekly rows the page no longer shows plus ICI's MONTHLY
  actuals back to January 2024 — a separate series (actual monthly
  net new cash flow, not the weekly estimate), kept under its own key and
  never summed with the weekly rows. A seed row never overwrites a row
  already on file; the loop's own observations win. The runner is pure
  stdlib and cannot read the `.xls`, so the monthly series is static until
  the seed is regenerated; the payload's `monthly_through` says how far it
  runs, and the page prints that.

Same `write_history` gate as every history file: a forced closed-day run
merges in memory (so the published block is still complete) but never
writes the file. Nothing here feeds a board score or a verdict.

Run: python3 -m pytest fetcher/test_fund_flows_history.py -q
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

HISTORY_FILENAME = "fund_flows_history.json"
SEED_PATH = Path(__file__).resolve().parent / "seed" / "ici_flows_seed.json"

# Weeks kept on file, oldest pruned first on save: ten years of weekly rows.
MAX_FUND_FLOWS_HISTORY_WEEKS = 520

# The nine ICI columns, the same keys context.parse_ici_combined_flows emits.
FLOW_KEYS = (
    "total", "equity", "domestic_equity", "world_equity", "hybrid",
    "bond", "taxable_bond", "municipal_bond", "commodity",
)


def _clean_row(row) -> Optional[dict]:
    """A row is the nine flow keys, each a number or None. Anything that is
    not a dict, or carries no numeric reading at all, is not a row."""
    if not isinstance(row, dict):
        return None
    out = {}
    any_num = False
    for k in FLOW_KEYS:
        v = row.get(k)
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            out[k] = None
        else:
            out[k] = float(v)
            any_num = True
    return out if any_num else None


def _clean_table(tbl) -> dict:
    if not isinstance(tbl, dict):
        return {}
    out = {}
    for k, row in tbl.items():
        if not isinstance(k, str) or len(k) != 10:
            continue
        r = _clean_row(row)
        if r is not None:
            out[k] = r
    return out


def load_seed(path: Path = SEED_PATH) -> Optional[dict]:
    """The checked-in seed, or None when it is missing or unreadable.
    Never raises: a bad seed means the history simply starts from the
    loop's own observations."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return None
        return {
            "url": raw.get("url") if isinstance(raw.get("url"), str) else None,
            "fetched": raw.get("fetched") if isinstance(raw.get("fetched"), str) else None,
            "weekly": _clean_table(raw.get("weekly")),
            "monthly": _clean_table(raw.get("monthly")),
        }
    except Exception:
        return None


def load_history(out_dir) -> dict:
    """fund_flows_history.json from OUT_DIR, fail-soft: a missing, corrupt
    or non-dict file reads as an empty history, never raises. Known fail-soft
    weakness shared with load_gamma_history: a transient read error returns
    an empty structure and the next save overwrites the remote file — the
    seed merge in apply_cycle then rebuilds most of it."""
    path = Path(out_dir) / HISTORY_FILENAME
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("not a dict")
    except Exception:
        raw = {}
    return {
        "v": 1,
        "unit": "USD millions",
        "source": "ICI",
        "weekly": _clean_table(raw.get("weekly")),
        "monthly": _clean_table(raw.get("monthly")),
        "seed_fetched": raw.get("seed_fetched") if isinstance(raw.get("seed_fetched"), str) else None,
        "last_release": raw.get("last_release") if isinstance(raw.get("last_release"), str) else None,
    }


def apply_cycle(history: dict, fund_flows: Optional[dict], seed: Optional[dict]) -> dict:
    """Fold the seed and this cycle's live release into `history` in place.

    Order matters: the seed fills only weeks and months NOT already on file
    (the loop's own observations win over a static file), then the live
    release overwrites any week it carries (ICI revises; newest print wins).
    Returns a small summary for the log. Pure in-memory — the write_history
    gate lives on save_history, so a forced closed-day cycle still publishes
    a complete block without touching the file.
    """
    weekly = history.setdefault("weekly", {})
    monthly = history.setdefault("monthly", {})
    added_seed = added_live = revised = 0
    if isinstance(seed, dict):
        for k, row in (seed.get("weekly") or {}).items():
            if k not in weekly:
                weekly[k] = dict(row)
                added_seed += 1
        for k, row in (seed.get("monthly") or {}).items():
            if k not in monthly:
                monthly[k] = dict(row)
                added_seed += 1
        if seed.get("fetched") and not history.get("seed_fetched"):
            history["seed_fetched"] = seed["fetched"]
    if isinstance(fund_flows, dict) and isinstance(fund_flows.get("weeks"), list):
        for w in fund_flows["weeks"]:
            if not isinstance(w, dict):
                continue
            k = w.get("week_ended")
            row = _clean_row(w)
            if not isinstance(k, str) or len(k) != 10 or row is None:
                continue
            if k in weekly:
                if weekly[k] != row:
                    revised += 1
            else:
                added_live += 1
            weekly[k] = row
        rel = fund_flows.get("released")
        if isinstance(rel, str):
            history["last_release"] = rel
    return {"added_seed": added_seed, "added_live": added_live, "revised": revised,
            "weeks": len(weekly), "months": len(monthly)}


def save_history(out_dir, history: dict) -> None:
    weekly = history.get("weekly", {})
    if isinstance(weekly, dict) and len(weekly) > MAX_FUND_FLOWS_HISTORY_WEEKS:
        for k in sorted(weekly.keys())[:-MAX_FUND_FLOWS_HISTORY_WEEKS]:
            del weekly[k]
    history["v"] = 1
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / HISTORY_FILENAME
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(history, indent=2), encoding="utf-8")
    tmp.replace(path)


def publish_block(history: dict) -> Optional[dict]:
    """The data.json `fund_flows_history` object, or None when nothing is on
    file (the key is then omitted, per the optional-key rule)."""
    weekly = history.get("weekly") if isinstance(history.get("weekly"), dict) else {}
    monthly = history.get("monthly") if isinstance(history.get("monthly"), dict) else {}
    if not weekly and not monthly:
        return None
    wk = [{"week_ended": k, **weekly[k]} for k in sorted(weekly)]
    mo = [{"month_ended": k, **monthly[k]} for k in sorted(monthly)]
    return {
        "v": 1,
        "source": "ICI",
        "unit": "USD millions",
        "weekly": wk,
        "monthly": mo,
        "n_weeks": len(wk),
        "first_week": wk[0]["week_ended"] if wk else None,
        "last_week": wk[-1]["week_ended"] if wk else None,
        "n_months": len(mo),
        "monthly_through": mo[-1]["month_ended"] if mo else None,
        "seed_fetched": history.get("seed_fetched"),
        "last_release": history.get("last_release"),
        "max_weeks": MAX_FUND_FLOWS_HISTORY_WEEKS,
    }
