"""Flow Desk — context layer: vault brief/catalysts/news/facts + daily bars.

Free-data only, Python stdlib only (urllib/json/csv/datetime/zoneinfo/math/
os/re). Every network call is fail-soft — one bad leg logs a single warn line
and returns None/[]/{} depending on its shape; nothing here ever raises out to
build_snapshot.run_cycle. See /home/user/flow-desk/DATA_CONTRACT.md for the
authoritative shape of every field this module produces (the new data.json
keys: brief, catalysts, news, facts, desk_private, context_updated_at; and
the new sidecar file bars.json).

────────────────────────────────────────────────────────────────────────────
SOURCES (see ClaudeVault's market-data/DATA_SOURCES.md for the routing table
this build follows; every endpoint below was live-verified from this
environment while building this module, 2026-08)
────────────────────────────────────────────────────────────────────────────
- Vault files (brief_summary.json, desk_private.enc.json, memory_events.csv,
  econ_calendar.csv) — GET raw.githubusercontent.com/zlanghamer1/ClaudeVault/
  main/<path> with a bearer token from env VAULT_READ_TOKEN. If the token is
  absent, every vault fetch returns empty/None WITHOUT attempting a request —
  there is nothing wrong with running this loop with no token configured, it
  just means brief/desk_private/memory/csv-mirror content stays absent.
- TradingView economic calendar (economic-calendar.tradingview.com/events) —
  needs Origin+Referer set to tradingview.com or it 403s (confirmed live
  2026-08; a bare User-Agent alone was NOT enough, contrary to what a plain
  reading of "send a browser-ish UA" might suggest — the Origin/Referer pair
  turned out to be what actually gates this endpoint).
- TradingView news (news-mediator.tradingview.com/public/view/v1/symbol) —
  a plain User-Agent was sufficient live; no special headers needed.
- Yahoo v8 chart API (query1.finance.yahoo.com/v8/finance/chart/<SYM>) — a
  plain User-Agent was sufficient live.
- TradingView scanner facts columns (price_52_week_high/low, beta_1_year,
  average_volume_10d_calc, RSI, earnings_release_next_date, market_cap_basic)
  all resolved live for the whole pinned universe. Short interest did NOT:
  every candidate column (short_percent_float, short_interest_percent,
  short_interest, shares_short, short_percent_of_float,
  shares_short_prior_month, days_to_cover_short) came back null for every
  ticker tried — the free scanner simply doesn't carry it (matches
  DATA_SOURCES.md, which already routes short interest to Yahoo
  quoteSummary, a second vendor this build deliberately did not add).
  facts.short_pct is therefore ALWAYS None; see DATA_CONTRACT.md.

────────────────────────────────────────────────────────────────────────────
TESTABILITY SEAM
────────────────────────────────────────────────────────────────────────────
Every function that hits the network takes an optional `_get` parameter: a
callable `(url, headers) -> bytes`. Production code never passes it (the
real `_default_get` is used); tests inject a fake to keep the whole suite off
the network. Nothing here ever calls `_default_get` directly except
`_http_get`'s own default.

────────────────────────────────────────────────────────────────────────────
JOB-LOCAL CACHE — fetcher/.context_cache.json (gitignored, NOT the data
branch; same pattern as build_snapshot.py's .prev_cycle.json but a SEPARATE
file so the two caches' read-at-start/write-at-end lifecycles inside one
run_cycle can't clobber each other)
────────────────────────────────────────────────────────────────────────────
{
  "context_fetched_at": "2026-08-15T14:32:00Z",   // last time the hourly-gated
                                                   // vault/econ/news fetch ran
  "bars_built_date": "2026-08-15",                 // last session bars.json built for
  "avg_move": {"MU": 3.45, ...},                   // carried forward on cycles that
                                                    // don't rebuild bars
  "brief": {...} | null,                           // last-fetched values, carried
  "catalysts": [...],                              // forward on cycles that don't
  "news": {...} | null,                            // refetch, so data.json's fields
  "desk_private": {...} | null                     // don't flicker in/out hourly
}
Fail-soft: a missing/corrupt file reads as "never fetched, never built" —
worst case one extra fetch that cycle, never a crash.
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional
from zoneinfo import ZoneInfo

TZ_CT = ZoneInfo("America/Chicago")
TZ_ET = ZoneInfo("America/New_York")

ROOT = Path(__file__).resolve().parent
CONTEXT_CACHE_FILE = ROOT / ".context_cache.json"

UA = "Mozilla/5.0 (flow-desk)"
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
TIMEOUT = 20

VAULT_OWNER_REPO = "zlanghamer1/ClaudeVault"
VAULT_RAW_BASE = f"https://raw.githubusercontent.com/{VAULT_OWNER_REPO}/main/"
VAULT_BRIEF_PATH = "market-data/data/brief_summary.json"
VAULT_DESK_PRIVATE_PATH = "market-data/data/desk_private.enc.json"
VAULT_MEMORY_EVENTS_PATH = "market-data/data/memory_events.csv"
VAULT_ECON_CSV_PATH = "market-data/data/econ_calendar.csv"

TV_ECON_URL = "https://economic-calendar.tradingview.com/events"
TV_NEWS_URL = "https://news-mediator.tradingview.com/public/view/v1/symbol"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}"

ECON_WINDOW_DAYS = 28        # display window for TV/csv econ rows and OpEx
NEWS_CAP = 20                 # total items across the whole pinned universe
BARS_MAX = 252                 # cap on daily closes kept per ticker
BARS_SLEEP_SEC = 0.25          # between per-symbol Yahoo calls
AVG_MOVE_WINDOW = 20            # "last 20 closes" -> 19 day-over-day changes
FETCH_STALE_SEC = 55 * 60       # hourly gate for vault/econ/news

_IMPORTANCE_MAP = {-1: "LOW", 0: "MEDIUM", 1: "HIGH"}

# Rotation / derisking language — copied VERBATIM from
# market-data/morning-report/sections/headlines.py's ROTATION_KEYWORDS
# (ClaudeVault repo) so the two lists can't silently drift apart.
ROTATION_KEYWORDS = [
    "rotation", "rotating", "rotate out", "sell-off", "selloff", "sell off",
    "correction", "pullback", "profit-taking", "profit taking", "hedging",
    "plunge", "tumble", "slump", "unwind", "derisk", "de-risk", "dump",
    "bubble", "overvalued", "stretched valuations",
]

_FOMC_RE = re.compile(r"fomc.*rate decision", re.IGNORECASE)
_CPI_RE = re.compile(r"\bcpi\b", re.IGNORECASE)
_PAREN_RE = re.compile(r"\([^)]*\)")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9 ]")
_TICKER_RE = re.compile(r"^[A-Z]{1,5}$")


def log(msg: str) -> None:
    print(f"[context] {msg}")


# ── HTTP seam ────────────────────────────────────────────────────────────────

def _default_get(url: str, headers: dict) -> bytes:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def _http_get(url: str, headers: dict, _get: Optional[Callable] = None) -> bytes:
    getter = _get or _default_get
    return getter(url, headers)


def _num_or_none(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


# ── Vault file fetchers ──────────────────────────────────────────────────────

def fetch_vault_file(path: str, token: Optional[str], _get: Optional[Callable] = None) -> Optional[str]:
    """GET a file from the ClaudeVault repo's raw-content API -> decoded text.

    None on: missing token (request is never attempted — no env var means no
    call), network error, non-2xx, or a decode failure. NEVER logs the
    response body or the token itself (these are public Actions logs) — only
    the path and the exception's class name.
    """
    if not token:
        log(f"vault fetch skipped (no VAULT_READ_TOKEN): {path}")
        return None
    url = VAULT_RAW_BASE + path
    headers = {"Authorization": f"Bearer {token}", "User-Agent": UA}
    try:
        raw = _http_get(url, headers, _get=_get)
        return raw.decode("utf-8")
    except Exception as e:
        log(f"WARN vault fetch failed: {path} ({type(e).__name__})")
        return None


def fetch_brief(token: Optional[str], session_date: date, _get: Optional[Callable] = None) -> Optional[dict]:
    """Vault brief_summary.json -> dict, with `stale` added.

    stale = brief["date"] < session_date, using the exact same session_date
    build_snapshot.run_cycle computes (today's CT calendar date — no
    trading-day walk-back). A missing/unparseable date is treated as stale
    (never presented as fresh when we can't confirm it).
    """
    text = fetch_vault_file(VAULT_BRIEF_PATH, token, _get=_get)
    if text is None:
        return None
    try:
        obj = json.loads(text)
    except Exception:
        log("WARN brief fetch: invalid JSON")
        return None
    if not isinstance(obj, dict):
        log("WARN brief fetch: not a JSON object")
        return None
    stale = True
    brief_date = obj.get("date")
    if isinstance(brief_date, str):
        try:
            stale = date.fromisoformat(brief_date) < session_date
        except ValueError:
            stale = True
    obj["stale"] = stale
    return obj


def fetch_desk_private(token: Optional[str], _get: Optional[Callable] = None) -> Optional[dict]:
    """Vault desk_private.enc.json -> whatever it parses to, verbatim.

    Opaque passthrough: this loop never decrypts or inspects the payload
    beyond confirming it is valid JSON. None if the fetch or parse fails.
    """
    text = fetch_vault_file(VAULT_DESK_PRIVATE_PATH, token, _get=_get)
    if text is None:
        return None
    try:
        return json.loads(text)
    except Exception:
        log("WARN desk_private fetch: invalid JSON")
        return None


def _looks_like_us_ticker(scope: str) -> bool:
    """1-5 uppercase letters, no digits — rules out the KRX/TSE numeric-or-
    digit scope codes memory_events.csv also carries (005930, 000660, 285A),
    and explicitly excludes the CSV's own "ALL" sentinel (used throughout
    that file to mean "applies broadly", not the Allstate ticker)."""
    return bool(scope) and scope != "ALL" and bool(_TICKER_RE.match(scope))


def fetch_memory_events(token: Optional[str], _get: Optional[Callable] = None) -> list[dict]:
    """Vault memory_events.csv -> catalyst dicts, kind="memory". [] on failure.

    ticker = row's scope when it looks like a US ticker (see
    _looks_like_us_ticker), else None. Rows with an unparseable date are
    dropped rather than guessed at.
    """
    text = fetch_vault_file(VAULT_MEMORY_EVENTS_PATH, token, _get=_get)
    if text is None:
        return []
    out: list[dict] = []
    try:
        reader = csv.DictReader(io.StringIO(text))
        for r in reader:
            d = (r.get("date") or "").strip()
            event = (r.get("event") or "").strip()
            if not d or not event:
                continue
            try:
                date.fromisoformat(d)
            except ValueError:
                continue
            scope = (r.get("scope") or "").strip()
            imp_raw = (r.get("importance") or "").strip().upper()
            importance = imp_raw if imp_raw in ("HIGH", "MEDIUM", "LOW") else "MEDIUM"
            out.append({
                "date": d,
                "time_ct": None,
                "title": event,
                "importance": importance,
                "kind": "memory",
                "ticker": scope if _looks_like_us_ticker(scope) else None,
                "session": None,
                "forecast": None,
                "prior": None,
                "actual": None,
                "anchor": False,
                "source": "memory_events",
            })
    except Exception as e:
        log(f"WARN memory_events.csv parse failed: {type(e).__name__}")
        return []
    return out


def fetch_econ_calendar_csv(token: Optional[str], _get: Optional[Callable] = None) -> list[dict]:
    """Vault's hand-kept market-data/data/econ_calendar.csv -> catalyst dicts.

    kind="econ", source="econ_calendar". This is Zach's verified source and
    wins over the raw TV feed on same-day+similar-title conflicts (see
    build_catalysts) — and, because the vault keeps this CSV populated many
    months out, it is also the practical source for the FOMC/CPI anchors
    (TV's own feed is only ever fetched ECON_WINDOW_DAYS ahead).
    """
    text = fetch_vault_file(VAULT_ECON_CSV_PATH, token, _get=_get)
    if text is None:
        return []
    out: list[dict] = []
    try:
        reader = csv.DictReader(io.StringIO(text))
        for r in reader:
            d = (r.get("date") or "").strip()
            title = (r.get("event") or "").strip()
            if not d or not title:
                continue
            try:
                date.fromisoformat(d)
            except ValueError:
                continue
            time_ct = (r.get("time_ct") or "").strip() or None
            imp_raw = (r.get("importance") or "").strip().upper()
            importance = imp_raw if imp_raw in ("HIGH", "MEDIUM", "LOW") else "MEDIUM"
            out.append({
                "date": d,
                "time_ct": time_ct,
                "title": title,
                "importance": importance,
                "kind": "econ",
                "ticker": None,
                "session": None,
                "forecast": None,
                "prior": None,
                "actual": None,
                "anchor": False,
                "source": "econ_calendar",
            })
    except Exception as e:
        log(f"WARN econ_calendar.csv parse failed: {type(e).__name__}")
        return []
    return out


# ── TradingView fetchers (no vault token needed) ────────────────────────────

def fetch_econ_tv(days: int = 28, _get: Optional[Callable] = None) -> list[dict]:
    """TradingView economic calendar, next `days` days, US only -> catalyst dicts.

    kind="econ", source="tv_calendar". Needs Origin+Referer set to
    tradingview.com (confirmed live 2026-08 — a bare User-Agent alone 403s).
    importance -1/0/1 -> LOW/MEDIUM/HIGH (unmapped/missing -> MEDIUM).
    """
    now = datetime.now(timezone.utc)
    frm = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    to = (now + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    url = f"{TV_ECON_URL}?from={frm}&to={to}&countries=US"
    headers = {
        "User-Agent": BROWSER_UA,
        "Origin": "https://www.tradingview.com",
        "Referer": "https://www.tradingview.com/",
    }
    try:
        raw = _http_get(url, headers, _get=_get)
        obj = json.loads(raw)
    except Exception as e:
        log(f"WARN econ calendar fetch failed: {type(e).__name__}")
        return []
    rows = obj.get("result") if isinstance(obj, dict) else None
    if not isinstance(rows, list):
        log("WARN econ calendar: unexpected response shape")
        return []
    out: list[dict] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        title = r.get("title")
        date_str = r.get("date")
        if not isinstance(title, str) or not title or not isinstance(date_str, str):
            continue
        try:
            dt_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            continue
        dt_ct = dt_utc.astimezone(TZ_CT)
        imp_raw = r.get("importance")
        importance = _IMPORTANCE_MAP.get(imp_raw, "MEDIUM") if isinstance(imp_raw, (int, float)) else "MEDIUM"
        # Importance floor (Fable, 2026-08-15): the raw TV feed has no floor and
        # returned 299 rows / ~129KB for a 28-day US window in the build's live
        # probe — mostly LOW auction/data-release noise. The desk's catalyst rail
        # is curated by design ("filter ruthlessly"), so LOW econ rows are
        # dropped at fetch. LOW survives only on market_calendar rows (weekly
        # OpEx) and anything the hand-kept CSV mirror deliberately carries.
        if importance == "LOW":
            continue
        out.append({
            "date": dt_ct.date().isoformat(),
            "time_ct": dt_ct.strftime("%H:%M"),
            "title": title,
            "importance": importance,
            "kind": "econ",
            "ticker": None,
            "session": None,
            "forecast": _num_or_none(r.get("forecast")),
            "prior": _num_or_none(r.get("previous")),
            "actual": _num_or_none(r.get("actual")),
            "anchor": False,
            "source": "tv_calendar",
        })
    return out


def _rotation_banner(items: list[dict]) -> bool:
    hits = 0
    for it in items:
        title = (it.get("title") or "").lower()
        if any(kw in title for kw in ROTATION_KEYWORDS):
            hits += 1
    return hits >= 2


def fetch_news(symbols: list[str], _get: Optional[Callable] = None) -> Optional[dict]:
    """TradingView per-symbol news -> {"items": [...], "rotation_banner": bool}.

    symbols: exchange-prefixed tv_symbol strings (e.g. "NASDAQ:MU"), matching
    the news endpoint's own filter parameter and the ticker/quote shape the
    rest of this codebase already uses. Cap NEWS_CAP items TOTAL (not per
    symbol) across the whole pinned universe, newest first. None if nothing
    at all came back for any symbol (fail-soft; a single symbol's failure
    just contributes nothing, it never aborts the others).
    """
    pooled: list[dict] = []
    for tv_symbol in symbols:
        if not isinstance(tv_symbol, str) or not tv_symbol:
            continue
        url = f"{TV_NEWS_URL}?filter=lang:en&filter=symbol:{tv_symbol}&client=web"
        headers = {"User-Agent": UA}
        try:
            raw = _http_get(url, headers, _get=_get)
            obj = json.loads(raw)
        except Exception as e:
            log(f"WARN news fetch failed for {tv_symbol}: {type(e).__name__}")
            continue
        items = obj.get("items") if isinstance(obj, dict) else None
        if not isinstance(items, list):
            continue
        ticker = tv_symbol.split(":", 1)[-1] if ":" in tv_symbol else tv_symbol
        for it in items:
            if not isinstance(it, dict):
                continue
            title = it.get("title")
            published = it.get("published")
            if not isinstance(title, str) or not title or not isinstance(published, (int, float)):
                continue
            url_out = it.get("link")
            if not isinstance(url_out, str) or not url_out:
                story_path = it.get("storyPath")
                url_out = ("https://www.tradingview.com" + story_path
                           if isinstance(story_path, str) and story_path else None)
            try:
                ts_iso = datetime.fromtimestamp(published, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                continue
            pooled.append({"ticker": ticker, "title": title, "ts": ts_iso, "url": url_out,
                            "_sort": published})
    if not pooled:
        return None
    pooled.sort(key=lambda x: x["_sort"], reverse=True)
    capped = [{"ticker": x["ticker"], "title": x["title"], "ts": x["ts"], "url": x["url"]}
              for x in pooled[:NEWS_CAP]]
    return {"items": capped, "rotation_banner": _rotation_banner(capped)}


# ── Facts (rides the existing per-cycle scanner call — no gate) ─────────────

def fetch_earnings_days(tv_rows: dict[str, dict], session_date: date) -> dict[str, dict]:
    """Build the `facts` map from the extended TV scanner quotes.

    tv_rows: {ticker: quote}, as returned by build_snapshot's
    build_universe()/_resolve_core_tv() — this build extends build_snapshot's
    TV_COLUMNS with price_52_week_high/low, beta_1_year,
    average_volume_10d_calc and RSI (market_cap_basic and
    earnings_release_next_date were already fetched), so every quote dict
    already carries hi52/lo52/beta/avol/rsi/market_cap/earnings_ts.

    avg_move is NOT set here (always None) — the orchestrator (build_context)
    merges it in afterward from the once-daily bars cache; this function has
    no access to bars history and shouldn't guess.

    short_pct is ALWAYS None — see the module docstring's live-probe note.
    """
    facts: dict[str, dict] = {}
    for ticker, q in tv_rows.items():
        if not isinstance(q, dict):
            continue
        earn_days = None
        earnings_ts = q.get("earnings_ts")
        if isinstance(earnings_ts, (int, float)):
            try:
                edt = datetime.fromtimestamp(earnings_ts, tz=timezone.utc).date()
                delta = (edt - session_date).days
                if delta >= 0:
                    earn_days = delta
            except Exception:
                earn_days = None
        facts[ticker] = {
            "hi52": q.get("hi52"),
            "lo52": q.get("lo52"),
            "cap": q.get("market_cap"),
            "beta": q.get("beta"),
            "avol": q.get("avol"),
            "short_pct": None,
            "earn_days": earn_days,
            "rsi": q.get("rsi"),
            "avg_move": None,
        }
    return facts


# ── Catalysts ────────────────────────────────────────────────────────────────

def _title_key(title: str) -> str:
    """Normalize a title for same-day conflict matching: strip parentheticals
    (which usually carry only the reporting period, e.g. "(July)"), drop
    punctuation, lowercase, collapse whitespace."""
    cleaned = _PAREN_RE.sub(" ", title or "").lower()
    cleaned = _NON_ALNUM_RE.sub(" ", cleaned)
    return " ".join(cleaned.split())


def _titles_conflict(a: str, b: str) -> bool:
    ka, kb = _title_key(a), _title_key(b)
    if not ka or not kb:
        return False
    return ka == kb or ka in kb or kb in ka


def _dedup_econ(tv_rows: list[dict], csv_rows: list[dict]) -> list[dict]:
    """CSV rows always survive; a TV row is dropped when it conflicts
    (same date + similar title, see _titles_conflict) with a CSV row — the
    hand-kept CSV is the verified source and wins.

    Returns fresh dict copies (never the caller's own row objects) so later
    in-place edits (see build_catalysts's anchor promotion) can never leak
    back into csv_mirror/econ_rows behind the caller's back.
    """
    out = [dict(r) for r in csv_rows]
    for tv_row in tv_rows:
        conflict = any(
            c["date"] == tv_row["date"] and _titles_conflict(c["title"], tv_row["title"])
            for c in csv_rows
        )
        if not conflict:
            out.append(dict(tv_row))
    return out


def _next_matching(rows: list[dict], session_date: date, pattern: re.Pattern) -> Optional[dict]:
    """Earliest row (date >= session_date) whose title matches `pattern`.
    Ties keep the caller's ordering (stable sort) — callers list CSV rows
    before TV rows so a same-day CSV/TV tie resolves to the CSV row."""
    candidates = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        if not pattern.search(r.get("title") or ""):
            continue
        try:
            d = date.fromisoformat(r.get("date", ""))
        except (TypeError, ValueError):
            continue
        if d < session_date:
            continue
        candidates.append((d, r))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def _third_friday(year: int, month: int) -> date:
    first_of_month = date(year, month, 1)
    offset = (4 - first_of_month.weekday()) % 7   # Friday == weekday() 4
    first_friday = first_of_month + timedelta(days=offset)
    return first_friday + timedelta(days=14)


def _fridays_in_range(start: date, end: date) -> list[date]:
    offset = (4 - start.weekday()) % 7
    d = start + timedelta(days=offset)
    out = []
    while d <= end:
        out.append(d)
        d += timedelta(days=7)
    return out


def _build_opex_rows(session_date: date, days: int = ECON_WINDOW_DAYS) -> list[dict]:
    """Locally-computed options-expiration rows for the next `days` days.

    Third Friday of the month = "Monthly options expiration" MEDIUM, UNLESS
    that month is a calendar-quarter-end month (Mar/Jun/Sep/Dec), in which
    case it is the quarterly ("quadruple witching") expiration — still
    MEDIUM, distinct title. Every other Friday = "Weekly options expiration"
    LOW. kind="market", source="market_calendar".
    """
    end = session_date + timedelta(days=days)
    out = []
    for fri in _fridays_in_range(session_date, end):
        is_third = fri == _third_friday(fri.year, fri.month)
        if is_third and fri.month in (3, 6, 9, 12):
            title, importance = "Quarterly options expiration (quadruple witching)", "MEDIUM"
        elif is_third:
            title, importance = "Monthly options expiration", "MEDIUM"
        else:
            title, importance = "Weekly options expiration", "LOW"
        out.append({
            "date": fri.isoformat(),
            "time_ct": None,
            "title": title,
            "importance": importance,
            "kind": "market",
            "ticker": None,
            "session": None,
            "forecast": None,
            "prior": None,
            "actual": None,
            "anchor": False,
            "source": "market_calendar",
        })
    return out


def _earnings_session(ts) -> Optional[str]:
    """Classify an earnings timestamp's LOCAL (US market) time of day into
    "premarket" / "afterhours" / None (during hours, or no clean read).

    NOTE: TradingView's earnings_release_next_date frequently carries no
    real intraday precision — several pinned names were observed (2026-08
    live probe) stamped at exactly 12:00 UTC (8am/7am ET depending on DST),
    which reads like a not-yet-confirmed placeholder on this vendor rather
    than a real premarket call, and the feed gives no way to tell a
    confirmed time from that placeholder. This classifies by the plain
    market-hours threshold either way and accepts that a handful of
    "premarket" reads may really mean "unconfirmed". Display-only field —
    never a scoring input.
    """
    try:
        dt_et = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(TZ_ET)
    except Exception:
        return None
    minute_of_day = dt_et.hour * 60 + dt_et.minute
    if minute_of_day < 9 * 60 + 30:
        return "premarket"
    if minute_of_day >= 16 * 60:
        return "afterhours"
    return None


def build_catalysts(econ_rows: list[dict], memory_rows: list[dict],
                     earn_map: dict[str, dict], csv_mirror: list[dict],
                     session_date: date, days: int = ECON_WINDOW_DAYS) -> list[dict]:
    """Merge every catalyst source into one datetime-sorted list.

    econ_rows    — fetch_econ_tv() output (kind="econ", source="tv_calendar").
    memory_rows  — fetch_memory_events() output (kind="memory"). Included
                   UNBOUNDED (not day-windowed): the source is small and
                   hand-curated (a couple dozen rows spanning a year), so
                   showing all of it is the point, not noise — unlike the
                   TV econ feed (hundreds of rows in the same window), which
                   genuinely needs the window to stay readable.
    earn_map     — {ticker: {"ts": unix_seconds, "days": int|None}} for the
                   pinned universe (days already excludes past dates — see
                   the caller, build_context). One "earnings" catalyst per
                   entry with a known (non-None) days value, UNCONDITIONALLY
                   marked anchor=True (earnings are explicitly one of the
                   three anchor types regardless of whether the date falls
                   inside or outside the display window).
    csv_mirror   — fetch_econ_calendar_csv() output (kind="econ",
                   source="econ_calendar"). Wins same-day+similar-title
                   conflicts against econ_rows (see _dedup_econ), and is the
                   practical source the FOMC/CPI anchors are found in, since
                   it realistically extends past the `days` window while
                   econ_rows (fetched with a fixed `days` horizon) usually
                   does not.
    session_date — anchors the display window and the "days to earnings"/
                   OpEx math; the same value build_snapshot.run_cycle already
                   computes each cycle.

    Anchors (FOMC rate decision, CPI, each pinned earnings) are always
    included even when they fall past the `days` window — everything else
    (regular econ rows, OpEx) is bounded to it.
    """
    window_end = session_date + timedelta(days=days)

    def _in_window(row: dict) -> bool:
        try:
            d = date.fromisoformat(row["date"])
        except Exception:
            return False
        return session_date <= d <= window_end

    tv_in_window = [r for r in econ_rows if _in_window(r)]
    csv_in_window = [r for r in csv_mirror if _in_window(r)]
    out = _dedup_econ(tv_in_window, csv_in_window)
    out.extend(_build_opex_rows(session_date, days=days))
    out.extend(memory_rows)

    for ticker, info in (earn_map or {}).items():
        if not isinstance(info, dict):
            continue
        ts = info.get("ts")
        days_out = info.get("days")
        if days_out is None or not isinstance(ts, (int, float)):
            continue
        try:
            edt_ct = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(TZ_CT)
        except Exception:
            continue
        out.append({
            "date": edt_ct.date().isoformat(),
            "time_ct": edt_ct.strftime("%H:%M"),
            "title": f"{ticker} earnings",
            "importance": "HIGH",
            "kind": "earnings",
            "ticker": ticker,
            "session": _earnings_session(ts),
            "forecast": None,
            "prior": None,
            "actual": None,
            "anchor": True,
            "source": "tv_earnings",
        })

    # FOMC / CPI anchors: search the FULL (not window-filtered) csv+TV rows
    # for the next occurrence >= session_date. CSV rows are listed first so
    # a same-day CSV/TV tie resolves to the CSV row (same precedence as
    # _dedup_econ above). If a row with the same (date, title) already made
    # it into `out` (it will have, whenever it falls inside the window),
    # promote THAT copy to anchor=True instead of appending a duplicate —
    # matched purely on (date, title-key), not object identity: `out` holds
    # independent copies (see _dedup_econ), so identity would never match.
    all_econ = list(csv_mirror) + list(econ_rows)
    for pattern in (_FOMC_RE, _CPI_RE):
        row = _next_matching(all_econ, session_date, pattern)
        if row is None:
            continue
        existing = next(
            (o for o in out if o.get("kind") == "econ"
             and o["date"] == row["date"] and _title_key(o["title"]) == _title_key(row["title"])),
            None,
        )
        if existing is not None:
            existing["anchor"] = True
        else:
            promoted = dict(row)
            promoted["anchor"] = True
            out.append(promoted)

    out.sort(key=lambda r: (r["date"], r.get("time_ct") or "99:99"))
    return out


# ── Bars (Yahoo daily closes, at most once per day) ─────────────────────────

def _extract_yahoo_closes(obj) -> Optional[list[float]]:
    try:
        result = obj["chart"]["result"][0]
        closes = result["indicators"]["quote"][0]["close"]
    except Exception:
        return None
    if not isinstance(closes, list):
        return None
    out = [c for c in closes if isinstance(c, (int, float)) and not isinstance(c, bool)]
    return out or None


def _avg_move(closes: list[float]) -> Optional[float]:
    """Mean of abs(daily % change) over the last 20 closes, 2dp. None if
    fewer than 2 closes are available (nothing to difference)."""
    window = closes[-AVG_MOVE_WINDOW:]
    if len(window) < 2:
        return None
    changes = [abs((b - a) / a) * 100.0 for a, b in zip(window, window[1:]) if a]
    if not changes:
        return None
    return round(sum(changes) / len(changes), 2)


def build_bars(universe: list[str], session_date: date,
                _get: Optional[Callable] = None) -> tuple[dict, dict[str, float]]:
    """Yahoo v8 chart API per symbol -> (bars_payload, avg_move_map).

    bars_payload matches bars.json's shape exactly: {"built": <session_date
    ISO>, "bars": {ticker: [closes]}}. avg_move_map ({ticker: float}) is a
    SEPARATE return value for facts.*.avg_move — it is not part of bars.json.

    0.25s sleep between calls (skips the sleep before the first). A symbol
    that fails to fetch, or returns an unusable shape, is simply absent from
    both outputs — fail-soft, never zero-filled.
    """
    bars: dict[str, list[float]] = {}
    avg_move: dict[str, float] = {}
    for i, sym in enumerate(universe):
        if i > 0:
            time.sleep(BARS_SLEEP_SEC)
        url = YAHOO_CHART_URL.format(sym=sym) + "?range=1y&interval=1d"
        headers = {"User-Agent": UA}
        try:
            raw = _http_get(url, headers, _get=_get)
            obj = json.loads(raw)
        except Exception as e:
            log(f"skip {sym}: bars fetch failed ({type(e).__name__})")
            continue
        closes = _extract_yahoo_closes(obj)
        if not closes:
            log(f"skip {sym}: no usable close series")
            continue
        closes = closes[-BARS_MAX:]
        bars[sym] = [round(c, 2) for c in closes]
        mv = _avg_move(closes)
        if mv is not None:
            avg_move[sym] = mv
    payload = {"built": session_date.isoformat(), "bars": bars}
    return payload, avg_move


# ── Job-local cache (fetcher/.context_cache.json) ───────────────────────────

def load_context_cache() -> dict:
    """Fail-soft load: a missing/corrupt file reads as "never fetched,
    never built" — every field defaults to its empty/absent form."""
    try:
        raw = json.loads(CONTEXT_CACHE_FILE.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("not a dict")
    except Exception:
        raw = {}
    return {
        "context_fetched_at": raw.get("context_fetched_at") if isinstance(raw.get("context_fetched_at"), str) else None,
        "bars_built_date": raw.get("bars_built_date") if isinstance(raw.get("bars_built_date"), str) else None,
        "avg_move": raw.get("avg_move") if isinstance(raw.get("avg_move"), dict) else {},
        "brief": raw.get("brief") if isinstance(raw.get("brief"), dict) else None,
        "catalysts": raw.get("catalysts") if isinstance(raw.get("catalysts"), list) else [],
        "news": raw.get("news") if isinstance(raw.get("news"), dict) else None,
        "desk_private": raw.get("desk_private") if raw.get("desk_private") is not None else None,
    }


def save_context_cache(cache: dict) -> None:
    try:
        CONTEXT_CACHE_FILE.write_text(json.dumps(cache), encoding="utf-8")
    except Exception as e:
        log(f"WARN could not write context cache: {type(e).__name__}")


def _is_context_stale(cache: dict, now_utc: datetime) -> bool:
    """True when never fetched, or fetched more than FETCH_STALE_SEC ago."""
    ts = cache.get("context_fetched_at")
    if not isinstance(ts, str):
        return True
    try:
        prev = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return True
    return (now_utc - prev).total_seconds() > FETCH_STALE_SEC


# ── Orchestrator ─────────────────────────────────────────────────────────────

def build_context(quotes: dict[str, dict], pinned: list[str], session_date: date,
                   now_utc: datetime, _get: Optional[Callable] = None,
                   ) -> tuple[dict, Optional[dict]]:
    """Run the whole context layer for one build_snapshot.run_cycle call.

    Returns (fields, bars_payload):
      fields       — ONLY the keys that belong in data.json this cycle
                     (brief/catalysts/news/facts/desk_private/
                     context_updated_at), each omitted entirely when there is
                     nothing to show (see DATA_CONTRACT.md). The caller
                     (build_snapshot.run_cycle) folds this straight into the
                     snapshot dict.
      bars_payload — the bars.json body when bars were (re)built this cycle,
                     else None (nothing new to write — the file on disk from
                     an earlier cycle today is still current). The caller
                     writes it to OUT_DIR/bars.json using the same tmp-file-
                     then-replace pattern data.json/history.json already use.

    quotes  — {ticker: quote} from build_snapshot.build_universe(), with this
              build's extended TV_COLUMNS (hi52/lo52/beta/avol/rsi/
              earnings_ts/market_cap/tv_symbol already present per quote).
    pinned  — build_snapshot.PINNED (the bars universe).
    """
    token = os.environ.get("VAULT_READ_TOKEN")
    cache = load_context_cache()

    # facts: rides the existing per-cycle scanner call, no gate.
    facts = fetch_earnings_days(quotes, session_date)
    for ticker, f in facts.items():
        cached_mv = cache["avg_move"].get(ticker)
        if isinstance(cached_mv, (int, float)):
            f["avg_move"] = cached_mv

    # ── hourly-gated vault/econ/news fetch ──────────────────────────────
    if _is_context_stale(cache, now_utc):
        brief = fetch_brief(token, session_date, _get=_get)
        desk_private = fetch_desk_private(token, _get=_get)
        memory_rows = fetch_memory_events(token, _get=_get)
        csv_mirror = fetch_econ_calendar_csv(token, _get=_get)
        econ_rows = fetch_econ_tv(days=ECON_WINDOW_DAYS, _get=_get)

        earn_map: dict[str, dict] = {}
        for ticker, q in quotes.items():
            ts = q.get("earnings_ts") if isinstance(q, dict) else None
            if not isinstance(ts, (int, float)):
                continue
            try:
                edt = datetime.fromtimestamp(ts, tz=timezone.utc).date()
            except Exception:
                continue
            d = (edt - session_date).days
            earn_map[ticker] = {"ts": ts, "days": d if d >= 0 else None}

        catalysts = build_catalysts(econ_rows, memory_rows, earn_map, csv_mirror, session_date)

        symbols = [q.get("tv_symbol") for q in quotes.values() if isinstance(q, dict)]
        news = fetch_news([s for s in symbols if s], _get=_get)

        cache["context_fetched_at"] = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        cache["brief"] = brief
        cache["catalysts"] = catalysts
        cache["news"] = news
        cache["desk_private"] = desk_private
    else:
        brief = cache["brief"]
        catalysts = cache["catalysts"]
        news = cache["news"]
        desk_private = cache["desk_private"]

    # ── once-daily bars rebuild ──────────────────────────────────────────
    bars_payload = None
    if cache.get("bars_built_date") != session_date.isoformat():
        bars_payload, new_avg_move = build_bars(pinned, session_date, _get=_get)
        cache["bars_built_date"] = bars_payload["built"]
        # Merge (not replace): a ticker whose fetch failed THIS rebuild keeps
        # its last-known reading rather than losing it to one bad cycle.
        merged_avg_move = {**cache.get("avg_move", {}), **new_avg_move}
        cache["avg_move"] = merged_avg_move
        for ticker, f in facts.items():
            if ticker in new_avg_move:
                f["avg_move"] = new_avg_move[ticker]

    save_context_cache(cache)

    fields: dict = {}
    if brief is not None:
        fields["brief"] = brief
    if catalysts:
        fields["catalysts"] = catalysts
    if news is not None:
        fields["news"] = news
    if facts:
        fields["facts"] = facts
    if desk_private is not None:
        fields["desk_private"] = desk_private
    if isinstance(cache.get("context_fetched_at"), str):
        fields["context_updated_at"] = cache["context_fetched_at"]

    return fields, bars_payload
