"""Flow Desk — context layer: vault brief/catalysts/news/facts + daily bars
+ per-symbol fundamentals sidecars.

Free-data only, Python stdlib only (urllib/json/csv/datetime/zoneinfo/math/
os/re/http.cookiejar). Every network call is fail-soft — one bad leg logs a
single warn line and returns None/[]/{} depending on its shape; nothing here
ever raises out to build_snapshot.run_cycle. See
/home/user/flow-desk/DATA_CONTRACT.md for the authoritative shape of every
field this module produces (the data.json keys: brief, catalysts, news,
facts, desk_private, context_updated_at; and the sidecar files bars.json
and fund/{SYM}.json).

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
- TradingView scanner fundamentals (added 2026-08-15, Task 3): pe/peg/
  net_margin/gross_margin/op_margin/fcf_margin/debt_eq/roe/ps/pb/ev_ebitda/
  yld/target/rec_mark — all 14 verified live on NASDAQ:NVDA the same day
  (see build_snapshot.py's TV_COLUMNS). Forward P/E was probed under both
  `price_earnings_forward_fy` and `price_earnings_fy`; both returned null.
- stockanalysis.com (added 2026-08-15, Task 4) — a named alternate in
  DATA_SOURCES.md, tried first for per-symbol fundamentals. No documented
  public API; every page's server-rendered data is available at
  `<route>/__data.json` (SvelteKit's own built-in data-loading endpoint),
  devalue-encoded — see _devalue_resolve's docstring for the format and
  fetch_sa_statistics/fetch_sa_quarterly for the two routes used. Confirmed
  live 2026-08-15 for NVDA/MRVL/AXTI: short % of float, forward P/E, next
  earnings date + before/after-market text, and up to ~20 quarters of
  reported (not derived) revenue + diluted EPS.
- Yahoo quoteSummary (added 2026-08-15, Task 4) — needs a cookie + crumb now,
  not a bare request; confirmed live 2026-08-15 to work fully keyless (GET
  fc.yahoo.com for a cookie — a 404 there is normal, the cookie still lands
  via Set-Cookie on the error response — then GET
  query1.finance.yahoo.com/v1/test/getcrumb on the same cookie jar for a
  crumb token). One quoteSummary call per symbol
  (modules=defaultKeyStatistics,earningsHistory,earnings,calendarEvents)
  supplies short % of float / forward P/E as a fallback, plus historical
  earnings surprise (actual vs estimate-at-report-time) and next-quarter
  analyst estimates that stockanalysis.com's free pages do not carry at
  all. See the "Per-symbol fundamentals sidecars" section below
  build_bars for the full design writeup, including what was probed and
  NOT found (historical revenue estimates).

────────────────────────────────────────────────────────────────────────────
TESTABILITY SEAM
────────────────────────────────────────────────────────────────────────────
Every function that hits the network takes an optional `_get` parameter: a
callable `(url, headers) -> bytes`. Production code never passes it (the
real `_default_get` is used); tests inject a fake to keep the whole suite off
the network. Nothing here ever calls `_default_get` directly except
`_http_get`'s own default. The Yahoo fundamentals leg (fetch_yahoo_crumb /
fetch_yahoo_fundamentals) uses the SAME `_get(url, headers) -> bytes` seam
for testability, even though its real default (`_default_yahoo_get`) is
stateful (a persistent cookiejar-backed opener, needed for the crumb
handshake) rather than the plain one-shot `_default_get` every other fetch
in this module uses.

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
  "bars_sig": "v3-2y-vol",                         // build_bars's BARS_BUILD_SIG as of
                                                    // that last build (added 2026-08-15,
                                                    // Task 2 wave 3) — a mismatch forces
                                                    // a same-day rebuild even when
                                                    // bars_built_date already matches, so
                                                    // a mid-day code deploy that changes
                                                    // bars.json's shape doesn't keep
                                                    // serving the old shape until midnight
  "avg_move": {"MU": 3.45, ...},                   // carried forward on cycles that
                                                    // don't rebuild bars
  "brief": {...} | null,                           // last-fetched values, carried
  "catalysts": [...],                              // forward on cycles that don't
  "news": {...} | null,                            // refetch, so data.json's fields
  "desk_private": {...} | null                     // don't flicker in/out hourly
}
Fail-soft: a missing/corrupt file reads as "never fetched, never built" —
worst case one extra fetch that cycle, never a crash. `bars_built_date` AND
`bars_sig` together also gate the fund/{SYM}.json sidecar rebuild (added
2026-08-15, Task 4) — SAME keys, SAME condition, no separate cache field:
both are once-a-day, Yahoo/stockanalysis.com-heavy builds, and the task's own
instruction was to gate them together.
"""
from __future__ import annotations

import csv
import http.cookiejar
import io
import json
import os
import re
import time
import urllib.error
import urllib.parse
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
NEWS_PER_TICKER_CAP = 3        # Zach, 2026-08-15: "big 4 dominating headlines
                                # ... want to see other names mentioned as
                                # well if in the news". A live pull the same
                                # day put 20 items total across just 3 tickers
                                # (NVDA 6 + AMZN 5 + GOOGL 3 = 14/20). Caps how
                                # many of the final NEWS_CAP items any one
                                # ticker's tag can hold — see
                                # _apply_news_ticker_cap. Mega-caps can still
                                # win MOST slots via backfill; this only
                                # guarantees room for others, not parity.
BARS_MAX = 504                 # cap on daily bars kept per ticker (2y of daily
                                # sessions, bumped from 252/1y 2026-08-15 so
                                # the frontend has enough history for a full
                                # trailing SMA200 line — see build_bars)
BARS_SLEEP_SEC = 0.25          # between per-symbol Yahoo calls
AVG_MOVE_WINDOW = 20            # "last 20 closes" -> 19 day-over-day changes
AVG_MOVE_BASIS = 252            # avg_move's own closes pool stays pinned at
                                # ~1y even though BARS_MAX (bars.json's stored
                                # history) is now 2y — decoupled on purpose so
                                # BARS_MAX can't silently widen this
                                # arithmetic's basis. AVG_MOVE_WINDOW (20)
                                # sits well inside either value; this is a
                                # defensive, redundant slice, not a change in
                                # what avg_move measures (see build_bars).
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


def _str_or_none(v):
    """Non-empty trimmed string, else None. Used for the catalyst unit/scale/
    period/agency labels, where "" and None must both mean "no label" so the
    page's meta line can test one condition."""
    if not isinstance(v, str):
        return None
    s = v.strip()
    return s or None


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

    UNITS (2026-08-17): the feed carries `unit` ("%" / "$", 68 of 224 rows in
    the live probe), `scale` ("K"/"M"/"B"/"T", 20 rows), `period` ("Jul") and
    `source` (the publishing agency, e.g. "Census Bureau") alongside the bare
    forecast/previous NUMBERS — and every one of those was being dropped on
    the floor. That is why the desk rendered "fc 1.35 · prior 1.427" for
    Housing Starts (millions of homes) and "prior -911" for the payroll
    revision (thousands of jobs): unitless numbers a reader cannot use.
    `forecast`/`previous`/`actual` are ALREADY scaled to match `scale` (the
    unscaled figures ride along as forecastRaw/previousRaw/actualRaw —
    previousRaw 1427000 vs previous 1.427 with scale "M"), so the renderer
    appends the suffix and never rescales. All four fields are optional and
    fail soft to None; the page's meta line degrades to the bare number.
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
            "unit": _str_or_none(r.get("unit")),
            "scale": _str_or_none(r.get("scale")),
            "period": _str_or_none(r.get("period")),
            "agency": _str_or_none(r.get("source")),
        })
    return out


def _rotation_banner(items: list[dict]) -> bool:
    hits = 0
    for it in items:
        title = (it.get("title") or "").lower()
        if any(kw in title for kw in ROTATION_KEYWORDS):
            hits += 1
    return hits >= 2


def _apply_news_ticker_cap(pooled: list[dict], total_cap: int, per_ticker_cap: int) -> list[dict]:
    """pooled: newest-first pooled news dicts (each carrying a "ticker" key —
    an item's only/primary tag, see fetch_news — and a "_sort" sortable
    timestamp) -> up to `total_cap` of them, newest first, with no more than
    `per_ticker_cap` counted against any single ticker (Zach, 2026-08-15:
    NEWS_PER_TICKER_CAP's docstring has the live numbers this was built to fix).

    Single forward pass over `pooled` (already newest-first): an item is
    admitted while its ticker is still under the per-ticker cap; once a
    ticker hits the cap, its further items are set aside rather than dropped
    outright. If the admitted items alone don't fill `total_cap` (not enough
    OTHER tickers in the pool that cycle), the remaining room is backfilled
    from the set-asides, newest first — so a mega-cap ticker can still fill
    most or all of a quiet day's board (this cap GUARANTEES room for other
    names, it does not force parity — see the module-level ruling note).

    The result is re-sorted newest-first overall before returning: since a
    capped-out ticker's older items are only ever admitted during the
    backfill pass (appended at the end), leaving the two passes' concatenation
    unsorted could interleave an older backfilled item ahead of a newer one
    from a different ticker that was admitted during the first pass.
    """
    selected: list[dict] = []
    setaside: list[dict] = []
    per_ticker: dict[str, int] = {}
    for item in pooled:
        ticker = item.get("ticker")
        count = per_ticker.get(ticker, 0)
        if count < per_ticker_cap:
            selected.append(item)
            per_ticker[ticker] = count + 1
        else:
            setaside.append(item)
    if len(selected) < total_cap:
        selected.extend(setaside[: total_cap - len(selected)])
    final = selected[:total_cap]
    final.sort(key=lambda x: x["_sort"], reverse=True)
    return final


def fetch_news(symbols: list[str], _get: Optional[Callable] = None) -> Optional[dict]:
    """TradingView per-symbol news -> {"items": [...], "rotation_banner": bool}.

    symbols: exchange-prefixed tv_symbol strings (e.g. "NASDAQ:MU"), matching
    the news endpoint's own filter parameter and the ticker/quote shape the
    rest of this codebase already uses. Collection is pooled across every
    symbol exactly as before; assembling the FINAL list then applies two
    caps together: NEWS_CAP items TOTAL (unchanged, not per ticker) and
    NEWS_PER_TICKER_CAP per ticker (added 2026-08-15 — see
    _apply_news_ticker_cap), newest first throughout. None if nothing at all
    came back for any symbol (fail-soft; a single symbol's failure just
    contributes nothing, it never aborts the others).
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
    final = _apply_news_ticker_cap(pooled, NEWS_CAP, NEWS_PER_TICKER_CAP)
    capped = [{"ticker": x["ticker"], "title": x["title"], "ts": x["ts"], "url": x["url"]}
              for x in final]
    return {"items": capped, "rotation_banner": _rotation_banner(capped)}


# ── Facts (rides the existing per-cycle scanner call — no gate) ─────────────

def fetch_earnings_days(tv_rows: dict[str, dict], session_date: date) -> dict[str, dict]:
    """Build the `facts` map from the extended TV scanner quotes.

    tv_rows: {ticker: quote}, as returned by build_snapshot's
    build_universe()/_resolve_core_tv() — this build extends build_snapshot's
    TV_COLUMNS with price_52_week_high/low, beta_1_year,
    average_volume_10d_calc and RSI (market_cap_basic and
    earnings_release_next_date were already fetched), so every quote dict
    already carries hi52/lo52/beta/avol/rsi/market_cap/earnings_ts. The
    2026-08-15 fundamentals sync (Task 3) further extends TV_COLUMNS with 14
    scanner fundamentals (pe/peg/net_margin/gross_margin/op_margin/
    fcf_margin/debt_eq/roe/ps/pb/ev_ebitda/yld/target/rec_mark), all
    verified live on NASDAQ:NVDA the same day — see build_snapshot.py's
    TV_COLUMNS comment. Forward P/E is NOT among them (TV returned null
    under both candidate column names); it is sourced in fund/{SYM}.json
    instead (Task 4) as `pe_forward`.

    avg_move is NOT set here (always None) — the orchestrator (build_context)
    merges it in afterward from the once-daily bars cache; this function has
    no access to bars history and shouldn't guess.

    short_pct is ALWAYS None — see the module docstring's live-probe note.
    (fund/{SYM}.json's `short_pct_float`, added 2026-08-15, is a DIFFERENT
    field on a DIFFERENT file, sourced from stockanalysis.com/Yahoo rather
    than this scanner — see build_fund_sidecar below. `facts.short_pct`
    itself is untouched and stays permanently None.)
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
            "pe": q.get("pe"),
            "peg": q.get("peg"),
            "net_margin": q.get("net_margin"),
            "gross_margin": q.get("gross_margin"),
            "op_margin": q.get("op_margin"),
            "fcf_margin": q.get("fcf_margin"),
            "debt_eq": q.get("debt_eq"),
            "roe": q.get("roe"),
            "ps": q.get("ps"),
            "pb": q.get("pb"),
            "ev_ebitda": q.get("ev_ebitda"),
            "yld": q.get("yld"),
            "target": q.get("target"),
            "rec_mark": q.get("rec_mark"),
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


# ── Bars (Yahoo daily OHLC, at most once per day) ───────────────────────────

BARS_VERSION = 3   # bars.json schema version — see build_bars's docstring
BARS_BUILD_SIG = "v3-2y-vol-tape"  # bumped whenever build_bars's OUTPUT SHAPE
                                # changes (not on an ordinary daily rebuild).
                                # build_context's once-a-day gate keys off
                                # BOTH bars_built_date AND this signature, so
                                # a code deploy that changes the shape forces
                                # an immediate rebuild even on a day
                                # bars_built_date already matches — otherwise
                                # a cached v2 bars.json from earlier the same
                                # day would keep publishing, unchanged, until
                                # midnight. See build_context.


def _extract_yahoo_ohlcv(obj) -> Optional[list[list]]:
    """v8 chart API response -> [[open, high, low, close, volume], ...] rows,
    one per available bar, in the API's own (oldest-first) order.

    A bar missing ANY of open/high/low/close is dropped ENTIRELY rather than
    partially filled — same "never zero-filled, never guessed" convention
    the old close-only extraction used, just applied per-row instead of
    per-ticker. Yahoo's quote block carries four parallel OHLC arrays plus a
    fifth `volume` array (indices line up positionally with the response's
    `timestamp` array); a short or missing OHLC array here means the shape
    is unusable and yields None, same as any other malformed response.

    Volume (added 2026-08-15, Task 2) is handled separately from the OHLC
    legs on purpose: None != 0 everywhere in this codebase, and a day with a
    perfectly good OHLC bar but a missing/null volume reading must not be
    zero-filled (that would misrepresent "no trading" as a fact rather than
    an unknown) — so an otherwise-valid bar keeps `v: None` in that case, and
    only a genuinely missing/non-list `volume` array (the whole ticker's
    volume leg failed) leaves every row's 5th element None. The OHLC drop
    rule is unaffected by volume either way — a row's fate is decided by its
    four price legs alone.
    """
    try:
        result = obj["chart"]["result"][0]
        q = result["indicators"]["quote"][0]
        opens, highs, lows, closes = q["open"], q["high"], q["low"], q["close"]
    except Exception:
        return None
    if not all(isinstance(x, list) for x in (opens, highs, lows, closes)):
        return None
    volumes = q.get("volume")
    if not isinstance(volumes, list):
        volumes = []
    n = min(len(opens), len(highs), len(lows), len(closes))
    out: list[list] = []
    for i in range(n):
        row = (opens[i], highs[i], lows[i], closes[i])
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in row):
            continue
        vol_raw = volumes[i] if i < len(volumes) else None
        vol = int(vol_raw) if isinstance(vol_raw, (int, float)) and not isinstance(vol_raw, bool) else None
        out.append([float(v) for v in row] + [vol])
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


# ── Tape symbols (added 2026-08-17) ─────────────────────────────────────────
#
# The page's index/macro strip (index.html MAIN_TAPE + MACRO_TAPE) showed
# SPY/DIA/IWM/VIX/US10Y/crude/DXY as read-only tiles, because bars.json only
# ever carried the 62 PINNED equity tickers — so clicking one had nothing to
# chart. These seven ride along on the same once-daily Yahoo bars build.
#
# The keys are DESK keys, not Yahoo symbols, and the split matters in one
# place specifically: **crude's desk key is "CRUDE", never "WTI".** "WTI" is
# already taken by W&T Offshore, the oil-producer EQUITY in the rail (see the
# wlnote in index.html and the exclusion note in build_snapshot.py). Keying
# crude as "WTI" here would silently overwrite W&T Offshore's bars with the
# crude future's and put an $82 oil chart behind a $3 microcap — the exact
# ticker collision the exclusion note exists to prevent. index.html's
# MACRO_TAPE keeps displaying the tile as "WTI · CRUDE"; only the bars key
# and the chart lookup use "CRUDE".
#
# Yahoo symbols verified live 2026-08-17 (all seven return a usable 2y daily
# series). ^VIX / ^TNX / DX-Y.NYB report volume 0 on every bar — that is real,
# not missing data (an index has no share volume), and the page hides its
# volume pane rather than drawing a flat zero line.
TAPE_BARS = {
    "SPY": "SPY",
    "DIA": "DIA",
    "IWM": "IWM",
    "VIX": "^VIX",
    "US10Y": "^TNX",
    "CRUDE": "CL=F",
    "DXY": "DX-Y.NYB",
}

# ── Short-series retry (added 2026-08-17) ───────────────────────────────────
#
# Yahoo intermittently serves a TRUNCATED daily series: HTTP 200, well-formed
# JSON, every OHLC leg present — just 17 rows instead of ~502. Measured on
# ^TNX (the 10-year yield, added with TAPE_BARS): six identical back-to-back
# requests returned 17, 502, 17, 17, 502, 502. It is not the range (1y/2y/5y
# all do it), not the User-Agent (a browser UA does it too), and not a young
# listing — it is a bad shard or cache node answering some fraction of
# requests, and a plain retry gets a good one.
#
# This mattered because nothing downstream could tell the difference: 17 bars
# draw a chart with no 50-day and no 200-day average, and the tile would have
# opened looking merely boring rather than broken. So a series that comes back
# too short to carry the 200-day average is REFETCHED (up to
# BARS_SHORT_RETRIES times) and the LONGEST response wins.
#
# Genuinely short listings exist (SKHY, DRAM, and other recent IPOs), so this
# can never drop a symbol — it retries, keeps the best series it saw, and warns
# once if the result is still short. No sleep between attempts: the failure is
# per-request, not rate-based, and inserting one would slow the daily build and
# the test suite for nothing.
BARS_SHORT_WARN = 220
BARS_SHORT_RETRIES = 2


def build_bars(universe: list[str], session_date: date,
                _get: Optional[Callable] = None,
                aliases: Optional[dict] = None) -> tuple[dict, dict[str, float]]:
    """Yahoo v8 chart API per symbol -> (bars_payload, avg_move_map).

    bars_payload matches bars.json's v3 shape exactly: {"built": <session_date
    ISO>, "v": 3, "bars": {ticker: [[o,h,l,c,v], ...]}} — up to BARS_MAX rows,
    oldest first, o/h/l/c rounded 2dp, v an int or None (see
    _extract_yahoo_ohlcv). avg_move_map ({ticker: float}) is a SEPARATE
    return value for facts.*.avg_move (computed from closes only, same
    arithmetic as before v2/v3) — it is not part of bars.json.

    v3 (added 2026-08-15, Task 2): range bumped from 1y to 2y (so the
    frontend has enough trailing history to plot a full SMA200 line, not
    just ~50 days of it) and a 5th `volume` element added to every row (for
    a finviz-style volume pane) — BARS_MAX raised from 252 to 504 to match.
    The same Yahoo v8 chart call already returns open/high/low/volume arrays
    alongside close in indicators.quote[0] — no new source, just reading
    more of what was already there and asking for a longer window. Consumers
    must accept v1 (bare number arrays, no "v" key), v2 (`[o,h,l,c]` quads,
    "v": 2), and this v3 shape (`[o,h,l,c,v]` quints, "v": 3) — see
    DATA_CONTRACT.md.

    avg_move's own closes pool is explicitly re-sliced to AVG_MOVE_BASIS (252)
    out of the (now up to 504-row) fetched series before being handed to
    _avg_move, so doubling BARS_MAX's stored history does not change this
    arithmetic's basis (see AVG_MOVE_BASIS's comment) — _avg_move's own
    20-day window sits well inside either slice, so this is a defensive,
    provably-inert guard against a future refactor accidentally coupling the
    two, not a behavior change from before this date.

    `aliases` (added 2026-08-17, for TAPE_BARS) maps a DESK key in `universe`
    to the Yahoo symbol to fetch it under, for the handful of symbols whose
    desk key is not a valid Yahoo ticker (VIX -> ^VIX, CRUDE -> CL=F, …).
    Absent from the map means the two are identical, which is every equity.
    The OUTPUT is always keyed by the desk key, never the Yahoo symbol, so
    the page looks up bars under the same string it shows.

    0.25s sleep between calls (skips the sleep before the first). A symbol
    that fails to fetch, or returns an unusable shape, is simply absent from
    both outputs — fail-soft, never zero-filled. A single bar missing any of
    its four OHLC values is dropped rather than partially filled (see
    _extract_yahoo_ohlcv); a bar with valid OHLC but no volume reading keeps
    the bar with v: None rather than 0.
    """
    bars: dict[str, list[list]] = {}
    avg_move: dict[str, float] = {}
    for i, sym in enumerate(universe):
        if i > 0:
            time.sleep(BARS_SLEEP_SEC)
        fetch_sym = (aliases or {}).get(sym, sym)
        url = YAHOO_CHART_URL.format(sym=urllib.parse.quote(fetch_sym, safe="")) + "?range=2y&interval=1d"
        headers = {"User-Agent": UA}
        # Best series across the initial call plus up to BARS_SHORT_RETRIES
        # refetches, taken only while the series is too short to be plausible
        # (see the BARS_SHORT_WARN note above). A fetch error on a RETRY keeps
        # whatever the earlier attempt returned; an error on the FIRST attempt
        # skips the symbol exactly as before.
        quints = None
        for attempt in range(1 + BARS_SHORT_RETRIES):
            try:
                obj = json.loads(_http_get(url, headers, _get=_get))
            except Exception as e:
                if attempt == 0:
                    log(f"skip {sym}: bars fetch failed ({type(e).__name__})")
                    break
                log(f"WARN {sym}: short-series refetch failed ({type(e).__name__}), keeping best so far")
                break
            got = _extract_yahoo_ohlcv(obj)
            if got and (quints is None or len(got) > len(quints)):
                quints = got
            if quints is not None and len(quints) >= BARS_SHORT_WARN:
                break
            if attempt < BARS_SHORT_RETRIES:
                log(f"{sym}: {len(got) if got else 0} bars — refetching (truncated-series retry)")
        if not quints:
            log(f"skip {sym}: no usable OHLC series")
            continue
        quints = quints[-BARS_MAX:]
        if len(quints) < BARS_SHORT_WARN:
            log(f"WARN {sym} ({fetch_sym}): still only {len(quints)} bars after "
                f"{BARS_SHORT_RETRIES} refetches — the 50/200-day averages will not draw. "
                f"Expected for a young listing; investigate for anything older.")
        bars[sym] = [[round(row[0], 2), round(row[1], 2), round(row[2], 2), round(row[3], 2), row[4]]
                     for row in quints]
        closes_for_avg_move = [row[3] for row in quints[-AVG_MOVE_BASIS:]]
        mv = _avg_move(closes_for_avg_move)
        if mv is not None:
            avg_move[sym] = mv
    payload = {"built": session_date.isoformat(), "v": BARS_VERSION, "bars": bars}
    return payload, avg_move


# ── Per-symbol fundamentals sidecars (fund/{SYM}.json, added 2026-08-15) ────
#
# Goal: short % of float, forward P/E, earnings surprise history, next
# earnings estimates, and a quarterly/annual revenue+EPS series — none of
# which the TV scanner carries (Task 3's fundamentals sync confirmed forward
# P/E null; short interest was already confirmed permanently null in this
# module's docstring). Sourced from stockanalysis.com first (a named
# alternate in the vault's DATA_SOURCES.md routing table), Yahoo second.
#
# stockanalysis.com has NO documented public REST API for this data. It is a
# SvelteKit app: every route's server-rendered data is available at
# <route>/__data.json, encoded as a flat "devalue" array (index 0 is the
# root; every object/array VALUE is itself an index into the same array,
# not an inline literal — see _devalue_resolve). This is SvelteKit's own
# built-in data-loading endpoint, not a bespoke stockanalysis.com API, so it
# is considerably more stable than scraping rendered HTML, but it is still
# an internal endpoint, not a published contract — hence per-field fail-soft
# throughout, same as every other fetch in this file.
#
# Two stockanalysis.com routes are used per symbol (no single route carries
# both halves of what's needed):
#   /stocks/{sym}/statistics/__data.json          -> short % of float,
#       forward P/E, next earnings date + before/after-market text (all
#       under root.shortSelling / root.ratios / root.dates, each a list of
#       {"id", "value", "hover"} rows — keyed by "id", not position, so a
#       column reorder on their end can't silently misalign a value).
#   /stocks/{sym}/financials/income-statement/__data.json?p=quarterly
#       -> up to 20 quarters of REPORTED (not derived) revenue + diluted EPS
#       under root.financialData, keyed arrays (datekey/fiscalYear/
#       fiscalQuarter/revenue/epsdil) aligned by position; the leading
#       "TTM" column is a trailing-twelve-months figure, not a completed
#       quarter, and is dropped. ANNUAL figures are then SUMMED from these
#       same quarterly rows (only for fiscal years with all 4 quarters
#       present) rather than fetched separately — this is a disclosed
#       DERIVED aggregate, not the company's own separately-filed annual
#       diluted EPS (which can differ slightly for weighted-share-count
#       reasons); see DATA_CONTRACT.md. Fetching a 4th route just for real
#       annual figures would push every symbol from 3 requests to 4, and the
#       daily runtime budget (60ish symbols, well under 3 minutes) was
#       measured against 3.
#
# Yahoo covers what stockanalysis.com's pages don't have at all: historical
# earnings SURPRISE (actual vs the estimate that existed at report time,
# plus a session read off the report timestamp) and next-quarter analyst
# estimates. quoteSummary needs a cookie + crumb now (a bare API key/token
# is not how this endpoint gates access) — confirmed live 2026-08-15 to work
# completely keyless: GET fc.yahoo.com (best-effort, sets a cookie; a 404
# here is normal and harmless — the cookie lands via Set-Cookie on the error
# response itself), then GET query1.finance.yahoo.com/v1/test/getcrumb
# (same cookie jar) for a crumb token, then ONE quoteSummary call per symbol
# with modules=defaultKeyStatistics,earningsHistory,earnings,calendarEvents
# and that crumb on the query string. The crumb/cookie dance happens ONCE
# per whole build (fetch_yahoo_crumb), not once per symbol — only the final
# quoteSummary GET repeats per ticker.
#
# Revenue ESTIMATES (as opposed to revenue ACTUALS) at historical report
# time were probed and NOT found on either source for past quarters:
# stockanalysis.com's /forecast/ page only carries the CURRENT consensus
# (today's estimate for a past quarter has already been revised to match
# the reported actual, which is not the same thing as "what analysts
# expected before the print"), and Yahoo's earningsTrend module only
# returns forward-looking periods (0q/+1q/0y/+1y) on this account, no
# historical -1q..-4q rows. `rev_est` / `rev_surprise_pct` on past quarters
# are therefore ALWAYS null — a fourth vendor was deliberately not added for
# it, same posture as facts.short_pct. `next_earnings.rev_est` (a FORWARD
# estimate) IS available, from Yahoo's calendarEvents module.
#
# Budget (Task 4): 3 stockanalysis.com requests/symbol + 1 Yahoo request/
# symbol (the crumb dance is a one-time, whole-run cost) at FUND_SLEEP_SEC
# between every request, logged as a one-line timing summary at the end of
# build_fund_universe.

SA_BASE = "https://stockanalysis.com/stocks/{sym}"
SA_STATISTICS_PATH = "/statistics/__data.json"
SA_FINANCIALS_Q_PATH = "/financials/income-statement/__data.json?p=quarterly"

YAHOO_FC_URL = "https://fc.yahoo.com"
YAHOO_CRUMB_URL = "https://query1.finance.yahoo.com/v1/test/getcrumb"
YAHOO_QUOTESUMMARY_URL = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{sym}"
YAHOO_QS_MODULES = "defaultKeyStatistics,earningsHistory,earnings,calendarEvents"

FUND_SLEEP_SEC = 0.3
FUND_MAX_QUARTERLY = 12
FUND_MAX_ANNUAL = 6
FUND_MAX_EARNINGS = 12

_DEVALUE_SPECIAL = {-1: None, -2: float("nan"), -3: float("inf"), -4: float("-inf"), -5: -0.0}
_PCT_RE = re.compile(r"-?\d+(?:\.\d+)?")
_FISCAL_Q_RE = re.compile(r"^(\d)Q(\d{4})$")
# Revenue backfill (added 2026-08-15, wave 3, Task C): Yahoo's earnings row
# period ("Q1 2027", from _fmt_fiscal_period) vs stockanalysis.com's
# quarterly period ("Q1 27", from _build_quarterly_series) — same quarter
# number, year mod 100. See _backfill_earnings_revenue.
_EARNINGS_PERIOD_RE = re.compile(r"^Q(\d)\s+(\d{4})$")
_QUARTERLY_PERIOD_RE = re.compile(r"^Q(\d)\s+(\d{2})$")

_yahoo_opener = None   # lazily-created module-level urllib opener; see _default_yahoo_get


def _devalue_resolve(data: list, idx: int, memo: Optional[dict] = None):
    """Resolve one SvelteKit `__data.json` devalue-encoded value tree.

    `data` is the flat array from one response node's "data" field. Index 0
    is always the root. Every dict/list VALUE in that array is itself an
    integer index into the same array (devalue's reference scheme — this is
    what lets one repeated string be shared by many fields without
    duplicating it inline); this function walks those references and
    returns a plain nested dict/list/primitive tree. Negative indices are
    devalue's special sentinels (-1 undefined -> None is the only one ever
    observed in this site's payloads; the rest are handled for completeness).
    Memoized per top-level call to survive any shared-reference cycles.
    Generic to devalue's format — nothing here is stockanalysis-specific.
    """
    if memo is None:
        memo = {}
    if idx < 0:
        return _DEVALUE_SPECIAL.get(idx, None)
    if idx in memo:
        return memo[idx]
    raw = data[idx]
    if isinstance(raw, dict):
        out: dict = {}
        memo[idx] = out
        for k, v in raw.items():
            out[k] = _devalue_resolve(data, v, memo) if isinstance(v, int) else v
        return out
    if isinstance(raw, list):
        out_list: list = []
        memo[idx] = out_list
        for v in raw:
            out_list.append(_devalue_resolve(data, v, memo) if isinstance(v, int) else v)
        return out_list
    return raw


def _fetch_sa_page(sym: str, path: str, _get: Optional[Callable] = None) -> Optional[dict]:
    """GET one stockanalysis.com SvelteKit page's `__data.json` -> resolved
    root dict. None on: network error, bad JSON, no usable "data" node, or a
    non-dict root — fail-soft, same convention as every fetch in this file.
    """
    url = SA_BASE.format(sym=sym.lower()) + path
    headers = {"User-Agent": BROWSER_UA, "Accept": "*/*"}
    try:
        raw = _http_get(url, headers, _get=_get)
        obj = json.loads(raw)
    except Exception as e:
        log(f"WARN stockanalysis fetch failed for {sym} ({path}): {type(e).__name__}")
        return None
    nodes = obj.get("nodes") if isinstance(obj, dict) else None
    if not isinstance(nodes, list) or not nodes:
        return None
    last = nodes[-1]
    if not isinstance(last, dict) or last.get("type") != "data":
        return None
    node_data = last.get("data")
    if not isinstance(node_data, list) or not node_data:
        return None
    try:
        root = _devalue_resolve(node_data, 0)
    except Exception as e:
        log(f"WARN stockanalysis devalue decode failed for {sym} ({path}): {type(e).__name__}")
        return None
    return root if isinstance(root, dict) else None


def _parse_pct(s) -> Optional[float]:
    """"1.259%" -> 1.259. None on anything unparsable — never a guess."""
    if not isinstance(s, str):
        return None
    m = _PCT_RE.search(s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _parse_plain_number(s) -> Optional[float]:
    """"22.589" / "$22.59" / "-" / "N/A" -> float or None."""
    if not isinstance(s, str):
        return None
    cleaned = s.replace(",", "").replace("$", "").strip()
    if cleaned in ("", "-", "N/A", "n/a", "--"):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _sa_stat_row(rows, row_id: str) -> Optional[dict]:
    if not isinstance(rows, list):
        return None
    for r in rows:
        if isinstance(r, dict) and r.get("id") == row_id:
            return r
    return None


def fetch_sa_statistics(sym: str, _get: Optional[Callable] = None) -> dict:
    """stockanalysis.com's /statistics/ page -> short % of float, forward
    P/E, and the next-earnings date + before/after-market read.

    Returns {"short_pct_float", "pe_forward", "next_earnings_date",
    "next_earnings_session"} — every key independently None on a missing
    row (per-field fail-soft); a page-level fetch failure yields all-None
    rather than raising.
    """
    out = {"short_pct_float": None, "pe_forward": None,
           "next_earnings_date": None, "next_earnings_session": None}
    root = _fetch_sa_page(sym, SA_STATISTICS_PATH, _get=_get)
    if not isinstance(root, dict):
        return out

    short_sel = root.get("shortSelling") or {}
    row = _sa_stat_row(short_sel.get("data"), "shortFloat")
    if row:
        out["short_pct_float"] = _parse_pct(row.get("hover") or row.get("value"))

    ratios = root.get("ratios") or {}
    row = _sa_stat_row(ratios.get("data"), "peForward")
    if row:
        out["pe_forward"] = _parse_plain_number(row.get("hover") or row.get("value"))

    dates = root.get("dates") or {}
    row = _sa_stat_row(dates.get("data"), "earningsdate")
    if row and isinstance(row.get("value"), str):
        try:
            out["next_earnings_date"] = datetime.strptime(row["value"], "%b %d, %Y").date().isoformat()
        except ValueError:
            pass
    text = (dates.get("text") or "").lower()
    if "after market" in text or "after-market" in text or "after the market clos" in text:
        out["next_earnings_session"] = "AMC"
    elif "before market" in text or "before-market" in text or "before the market" in text:
        out["next_earnings_session"] = "BMO"
    return out


def fetch_sa_quarterly(sym: str, _get: Optional[Callable] = None) -> Optional[list[dict]]:
    """stockanalysis.com's quarterly income-statement page -> per-quarter
    rows, NEWEST FIRST (the site's own order): {"date", "fiscal_year",
    "fiscal_quarter", "revenue", "eps"}. The leading "TTM" column (a
    trailing-twelve-months figure, not a completed quarter) is dropped.
    None if the page fetch failed or the shape was unusable.
    """
    root = _fetch_sa_page(sym, SA_FINANCIALS_Q_PATH, _get=_get)
    if not isinstance(root, dict):
        return None
    fd = root.get("financialData")
    if not isinstance(fd, dict):
        return None
    datekeys, fys, fqs = fd.get("datekey"), fd.get("fiscalYear"), fd.get("fiscalQuarter")
    revs, epss = fd.get("revenue"), fd.get("epsdil")
    if not all(isinstance(x, list) for x in (datekeys, fys, fqs, revs, epss)):
        return None
    n = min(len(datekeys), len(fys), len(fqs), len(revs), len(epss))
    rows = []
    for i in range(n):
        if datekeys[i] == "TTM":
            continue
        rows.append({
            "date": datekeys[i] if isinstance(datekeys[i], str) else None,
            "fiscal_year": fys[i] if isinstance(fys[i], str) else None,
            "fiscal_quarter": fqs[i] if isinstance(fqs[i], str) else None,
            "revenue": revs[i] if isinstance(revs[i], (int, float)) and not isinstance(revs[i], bool) else None,
            "eps": epss[i] if isinstance(epss[i], (int, float)) and not isinstance(epss[i], bool) else None,
        })
    return rows or None


def _build_quarterly_series(rows: list[dict]) -> dict:
    """`rows` (newest-first, as stockanalysis.com returns them) -> the
    quarterly.{periods,revenue,eps} series, OLDEST FIRST (same charting
    convention as bars.json), capped at FUND_MAX_QUARTERLY quarters.
    """
    capped = list(reversed(rows[:FUND_MAX_QUARTERLY]))
    periods, revenue, eps = [], [], []
    for r in capped:
        fy, fq = r.get("fiscal_year"), r.get("fiscal_quarter")
        yy = fy[-2:] if isinstance(fy, str) and len(fy) >= 2 else None
        periods.append(f"{fq} {yy}" if fq and yy else None)
        revenue.append(r.get("revenue"))
        eps.append(r.get("eps"))
    return {"periods": periods, "revenue": revenue, "eps": eps}


def _build_annual_series(rows: list[dict]) -> dict:
    """Sum COMPLETE fiscal years (all 4 quarters present) out of the SAME
    quarterly rows stockanalysis.com already returned — a DERIVED aggregate,
    not the company's own separately-filed annual diluted EPS (which can
    differ slightly for weighted-share-count reasons across the year; see
    DATA_CONTRACT.md). No extra network request. Oldest first, capped at
    FUND_MAX_ANNUAL years. A year missing any quarter's revenue/eps yields
    None for that year rather than summing a partial (never a silent
    undercount presented as a full year).
    """
    by_year: dict[str, list[dict]] = {}
    for r in rows:
        fy = r.get("fiscal_year")
        if isinstance(fy, str):
            by_year.setdefault(fy, []).append(r)
    complete_years = sorted(y for y, qs in by_year.items() if len(qs) == 4)
    complete_years = complete_years[-FUND_MAX_ANNUAL:]
    periods, revenue, eps = [], [], []
    for y in complete_years:
        qs = by_year[y]
        revs = [q["revenue"] for q in qs if isinstance(q.get("revenue"), (int, float))]
        epss = [q["eps"] for q in qs if isinstance(q.get("eps"), (int, float))]
        periods.append(f"FY{y[-2:]}")
        revenue.append(round(sum(revs), 2) if len(revs) == 4 else None)
        eps.append(round(sum(epss), 5) if len(epss) == 4 else None)
    return {"periods": periods, "revenue": revenue, "eps": eps}


def _default_yahoo_get(url: str, headers: dict) -> bytes:
    """Real Yahoo transport: a lazily-created, process-lifetime urllib
    opener with its own cookiejar, so the cookie fc.yahoo.com sets survives
    into the getcrumb call and every quoteSummary call that follows within
    the same run — the crumb dance is a stateful cookie handshake, unlike
    every other fetch in this module, hence its own opener rather than
    reusing `_default_get`.
    """
    global _yahoo_opener
    if _yahoo_opener is None:
        _yahoo_opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    req = urllib.request.Request(url, headers=headers)
    with _yahoo_opener.open(req, timeout=TIMEOUT) as resp:
        return resp.read()


def _yahoo_get(url: str, _get: Optional[Callable] = None) -> bytes:
    getter = _get or _default_yahoo_get
    return getter(url, {"User-Agent": BROWSER_UA})


def fetch_yahoo_crumb(_get: Optional[Callable] = None) -> Optional[str]:
    """One-time-per-run cookie warm-up + crumb fetch. None on failure (the
    whole Yahoo leg is then skipped for every symbol this cycle — fail-soft,
    never blocks the stockanalysis.com legs).

    fc.yahoo.com routinely 404s ("Not Found on Accelerator", confirmed live
    2026-08-15) — that is expected and harmless; the cookie lands via
    Set-Cookie on the error response itself, so the exception is swallowed
    deliberately and the crumb call proceeds on the same cookie jar.
    """
    try:
        _yahoo_get(YAHOO_FC_URL, _get=_get)
    except Exception:
        pass
    try:
        raw = _yahoo_get(YAHOO_CRUMB_URL, _get=_get)
        crumb = raw.decode("utf-8").strip()
        return crumb or None
    except Exception as e:
        log(f"WARN yahoo crumb fetch failed: {type(e).__name__}")
        return None


def _yahoo_num(v) -> Optional[float]:
    """Yahoo's {"raw": x, "fmt": "..."} convention -> float, or None."""
    if isinstance(v, dict):
        raw = v.get("raw")
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            return float(raw)
    return None


def _yahoo_num_str(v) -> Optional[float]:
    """Some Yahoo fields (surprisePct) are plain numeric strings, not the
    {"raw","fmt"} dict shape -> float, or None."""
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    return None


def _fmt_fiscal_period(fq) -> Optional[str]:
    """"1Q2027" -> "Q1 2027". None if it doesn't match that shape."""
    if not isinstance(fq, str):
        return None
    m = _FISCAL_Q_RE.match(fq)
    return f"Q{m.group(1)} {m.group(2)}" if m else None


def fetch_yahoo_fundamentals(sym: str, crumb: str, _get: Optional[Callable] = None) -> dict:
    """One Yahoo quoteSummary call (defaultKeyStatistics + earningsHistory +
    earnings + calendarEvents) -> {"short_pct_float", "pe_forward",
    "earnings": [...], "next_earnings": {...} | None}.

    `earnings` is built from earnings.earningsChart.quarterly (actual/
    estimate/surprise/session — a strict superset of the separate
    earningsHistory module for the same quarters, so that module is
    requested but not separately parsed) matched against
    earnings.financialsChart.quarterly (actual revenue) by Yahoo's own
    shared "date" label (e.g. "2Q2025") — both charts use the same key, so
    no timestamp-matching heuristics are needed. Yahoo returns at most ~4
    historical quarters here; `rev_est`/`rev_surprise_pct` are always None
    (no historical estimate-at-time source was found — see the module
    header). `next_earnings` comes from calendarEvents.earnings (date,
    eps_est, rev_est); it carries no intraday time, so `session` is left
    None here for the caller to fill in from a same-ticker TV timestamp if
    one is available (see build_fund_sidecar).

    Whole-dict-empty on a fetch/parse failure; every field independently
    None/[]/absent on a narrower miss (per-field fail-soft throughout).
    """
    empty = {"short_pct_float": None, "pe_forward": None, "earnings": [], "next_earnings": None}
    url = (YAHOO_QUOTESUMMARY_URL.format(sym=sym)
           + f"?modules={YAHOO_QS_MODULES}&crumb={urllib.parse.quote(crumb)}")
    try:
        raw = _yahoo_get(url, _get=_get)
        obj = json.loads(raw)
        result = obj["quoteSummary"]["result"][0]
    except Exception as e:
        log(f"WARN yahoo quoteSummary fetch failed for {sym}: {type(e).__name__}")
        return empty
    if not isinstance(result, dict):
        return empty

    out = dict(empty)
    dks = result.get("defaultKeyStatistics") or {}
    short_frac = _yahoo_num(dks.get("shortPercentOfFloat"))
    out["short_pct_float"] = round(short_frac * 100, 3) if short_frac is not None else None
    out["pe_forward"] = _yahoo_num(dks.get("forwardPE"))

    earnings_mod = result.get("earnings") or {}
    echart = ((earnings_mod.get("earningsChart") or {}).get("quarterly")) or []
    fchart = ((earnings_mod.get("financialsChart") or {}).get("quarterly")) or []
    rev_by_caldate = {r.get("date"): _yahoo_num(r.get("revenue"))
                      for r in fchart if isinstance(r, dict)}

    rows = []
    for r in echart:
        if not isinstance(r, dict):
            continue
        pe_raw = r.get("periodEndDate")
        pe_ts = pe_raw.get("raw") if isinstance(pe_raw, dict) else None
        if not isinstance(pe_ts, (int, float)):
            continue
        rd_raw = r.get("reportedDate")
        rd_ts = rd_raw.get("raw") if isinstance(rd_raw, dict) else None
        surprise = _yahoo_num_str(r.get("surprisePct"))
        rows.append({
            "period": _fmt_fiscal_period(r.get("fiscalQuarter")),
            "date": datetime.fromtimestamp(pe_ts, tz=timezone.utc).date().isoformat(),
            "report_date": (datetime.fromtimestamp(rd_ts, tz=timezone.utc).date().isoformat()
                            if isinstance(rd_ts, (int, float)) else None),
            "session": _earnings_session(rd_ts) if isinstance(rd_ts, (int, float)) else None,
            "eps": _yahoo_num(r.get("actual")),
            "eps_est": _yahoo_num(r.get("estimate")),
            "eps_surprise_pct": round(surprise, 2) if surprise is not None else None,
            "rev": rev_by_caldate.get(r.get("date")),
            "rev_est": None,
            "rev_surprise_pct": None,
        })
    rows.sort(key=lambda r: r["date"])
    out["earnings"] = rows[-FUND_MAX_EARNINGS:]

    cal = (result.get("calendarEvents") or {}).get("earnings") or {}
    ed = cal.get("earningsDate")
    next_ts = None
    if isinstance(ed, list) and ed and isinstance(ed[0], dict):
        next_ts = ed[0].get("raw")
    if isinstance(next_ts, (int, float)):
        out["next_earnings"] = {
            "date": datetime.fromtimestamp(next_ts, tz=timezone.utc).date().isoformat(),
            "session": None,   # filled in by the caller from TV's earnings_ts, if any
            "eps_est": _yahoo_num(cal.get("earningsAverage")),
            "rev_est": _yahoo_num(cal.get("revenueAverage")),
        }
    return out


def _backfill_earnings_revenue(earnings: list[dict], quarterly: dict) -> None:
    """Mutates `earnings` IN PLACE: any row whose `rev` is still None (Yahoo's
    financialsChart had no matching-quarter row — e.g. AXTI's oldest row,
    2026-08-15 live) gets backfilled from the SAME symbol's already-fetched
    stockanalysis.com `quarterly` series, matched by quarter number + fiscal
    year mod 100 (Yahoo's "Q1 2027" vs stockanalysis's "Q1 27" — same quarter,
    same "27").

    Only `rev` is ever filled — `rev_est`/`rev_surprise_pct` are NEVER
    invented here (stockanalysis.com's quarterly series carries reported
    revenue only, no historical estimate, so there is nothing honest to fill
    them with; see DATA_CONTRACT.md's note on why those two stay permanently
    null). Fail-soft throughout: no quarterly series, an unparseable period
    label on either side, or simply no matching quarter, and the row's `rev`
    is left exactly as it was (None) — never guessed, never zero-filled.
    """
    periods = quarterly.get("periods") if isinstance(quarterly, dict) else None
    revenues = quarterly.get("revenue") if isinstance(quarterly, dict) else None
    if not isinstance(periods, list) or not isinstance(revenues, list):
        return
    by_quarter_year: dict[tuple[int, int], float] = {}
    for period, rev in zip(periods, revenues):
        m = _QUARTERLY_PERIOD_RE.match(period) if isinstance(period, str) else None
        if not m or not isinstance(rev, (int, float)) or isinstance(rev, bool):
            continue
        by_quarter_year[(int(m.group(1)), int(m.group(2)))] = rev

    for row in earnings:
        if not isinstance(row, dict) or row.get("rev") is not None:
            continue
        m = _EARNINGS_PERIOD_RE.match(row.get("period")) if isinstance(row.get("period"), str) else None
        if not m:
            continue
        key = (int(m.group(1)), int(m.group(2)) % 100)
        if key in by_quarter_year:
            row["rev"] = by_quarter_year[key]


def build_fund_sidecar(sym: str, session_date: date, crumb: Optional[str],
                        earn_ts, _get: Optional[Callable] = None) -> dict:
    """One ticker's fund/{SYM}.json payload (see DATA_CONTRACT.md for the
    full shape). Every leg below is independently fail-soft: a leg that
    errors contributes null/[]/default fields and never raises, never
    blocks the other leg, never blocks the next symbol.

    earn_ts: this ticker's TV earnings_release_next_date (unix seconds, from
    build_snapshot's quotes), used ONLY to derive next_earnings.session via
    the same premarket/afterhours heuristic build_catalysts uses elsewhere
    — Yahoo's calendarEvents carries no intraday time, and stockanalysis.com
    supplies its own session read separately (see fetch_sa_statistics).

    Revenue backfill (added 2026-08-15, wave 3): a Yahoo earnings row whose
    `rev` came back None (no financialsChart match for that quarter) is
    backfilled, in place, from this same call's `quarterly` series — see
    _backfill_earnings_revenue. Runs unconditionally at the end so it applies
    whether or not the Yahoo leg above ran at all (an empty `earnings` list
    is simply a no-op for the backfill, same fail-soft posture as everything
    else in this function).
    """
    payload = {
        "built": session_date.isoformat(), "sym": sym,
        "short_pct_float": None, "pe_forward": None,
        "earnings": [], "next_earnings": None,
        "quarterly": {"periods": [], "revenue": [], "eps": []},
        "annual": {"periods": [], "revenue": [], "eps": []},
    }

    sa_stats = fetch_sa_statistics(sym, _get=_get)
    payload["short_pct_float"] = sa_stats["short_pct_float"]
    payload["pe_forward"] = sa_stats["pe_forward"]
    sa_next_earnings = None
    if sa_stats["next_earnings_date"] is not None:
        sa_next_earnings = {
            "date": sa_stats["next_earnings_date"],
            "session": sa_stats["next_earnings_session"],
            "eps_est": None, "rev_est": None,
        }

    time.sleep(FUND_SLEEP_SEC)
    quarterly_rows = fetch_sa_quarterly(sym, _get=_get)
    if quarterly_rows:
        payload["quarterly"] = _build_quarterly_series(quarterly_rows)
        payload["annual"] = _build_annual_series(quarterly_rows)

    payload["next_earnings"] = sa_next_earnings   # best guess so far; Yahoo may improve it below

    if crumb:
        time.sleep(FUND_SLEEP_SEC)
        yq = fetch_yahoo_fundamentals(sym, crumb, _get=_get)
        if payload["short_pct_float"] is None:
            payload["short_pct_float"] = yq["short_pct_float"]
        if payload["pe_forward"] is None:
            payload["pe_forward"] = yq["pe_forward"]
        if yq["earnings"]:
            payload["earnings"] = yq["earnings"]
        if yq["next_earnings"] is not None:
            ne = dict(yq["next_earnings"])
            if ne.get("session") is None:
                if isinstance(earn_ts, (int, float)):
                    ne["session"] = _earnings_session(earn_ts)
                elif sa_next_earnings is not None:
                    ne["session"] = sa_next_earnings.get("session")
            payload["next_earnings"] = ne

    _backfill_earnings_revenue(payload["earnings"], payload["quarterly"])
    return payload


def build_fund_universe(universe: list[str], session_date: date,
                         earn_ts_map: Optional[dict] = None,
                         _get: Optional[Callable] = None) -> dict[str, dict]:
    """Build fund/{SYM}.json payloads for the whole tracked universe (called
    once per day by build_context, on the SAME gate as the bars rebuild).

    Fail-soft per symbol: one symbol's total failure (an uncaught exception
    anywhere in build_fund_sidecar) is logged and skipped, never blocks the
    rest of the universe. Logs one timing summary line at the end (Task 4's
    runtime-budget note: ~60 symbols x up to 4 requests/symbol including the
    one-time crumb dance, ~0.3s sleep between each, should stay well under
    the daily gate's 3-minute budget).
    """
    earn_ts_map = earn_ts_map or {}
    crumb = fetch_yahoo_crumb(_get=_get)
    if crumb is None:
        log("WARN fund sidecars: yahoo crumb unavailable this cycle — "
            "short_pct_float/pe_forward/earnings fall back to stockanalysis.com only")

    out: dict[str, dict] = {}
    t0 = time.monotonic()
    for i, sym in enumerate(universe):
        if i > 0:
            time.sleep(FUND_SLEEP_SEC)
        try:
            out[sym] = build_fund_sidecar(sym, session_date, crumb, earn_ts_map.get(sym), _get=_get)
        except Exception as e:
            log(f"skip {sym}: fund sidecar build failed ({type(e).__name__})")
    elapsed = time.monotonic() - t0
    log(f"fund sidecars: built {len(out)}/{len(universe)} symbols in {elapsed:.1f}s")
    return out


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
        "bars_sig": raw.get("bars_sig") if isinstance(raw.get("bars_sig"), str) else None,
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
                   ) -> tuple[dict, Optional[dict], Optional[dict]]:
    """Run the whole context layer for one build_snapshot.run_cycle call.

    Returns (fields, bars_payload, fund_payload):
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
      fund_payload — {ticker: fund/{SYM}.json body} when the fund sidecars
                     were (re)built this cycle (added 2026-08-15, Task 4),
                     else None. Built on the SAME gate as bars_payload — see
                     below. The caller writes one file per ticker to
                     OUT_DIR/fund/{ticker}.json, same tmp-then-replace
                     pattern.

    quotes  — {ticker: quote} from build_snapshot.build_universe(), with this
              build's extended TV_COLUMNS (hi52/lo52/beta/avol/rsi/
              earnings_ts/market_cap/tv_symbol already present per quote).
    pinned  — build_snapshot.PINNED (the bars universe, also the fund
              sidecar universe — TRACK_ONLY names are tracked here same as
              everything else; only the CBOE chain fetch skips them).
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

    # ── once-daily bars rebuild (+ fund sidecars, same gate — Task 4) ────
    # Gated on BOTH the date AND the build signature (added 2026-08-15,
    # Task 2 wave 3): a sig mismatch forces a rebuild even when today's date
    # already matches, so a code deploy that changes bars.json's shape mid-day
    # (e.g. this same date's v2 -> v3 upgrade) doesn't keep serving whatever
    # was already cached under today's date until midnight.
    bars_payload = None
    fund_payload = None
    if (cache.get("bars_built_date") != session_date.isoformat()
            or cache.get("bars_sig") != BARS_BUILD_SIG):
        # Tape symbols ride along on the same build (see TAPE_BARS). They are
        # appended, not merged into `pinned`, so nothing downstream of `pinned`
        # (facts, fund sidecars, the boards, the flow universe) sees them — an
        # index has no options chain and no fundamentals, and only bars.json
        # should learn about it. Any desk key already in `pinned` is skipped
        # rather than fetched twice.
        bars_universe = pinned + [k for k in TAPE_BARS if k not in pinned]
        bars_payload, new_avg_move = build_bars(bars_universe, session_date,
                                                _get=_get, aliases=TAPE_BARS)
        cache["bars_built_date"] = bars_payload["built"]
        cache["bars_sig"] = BARS_BUILD_SIG
        # Merge (not replace): a ticker whose fetch failed THIS rebuild keeps
        # its last-known reading rather than losing it to one bad cycle.
        merged_avg_move = {**cache.get("avg_move", {}), **new_avg_move}
        cache["avg_move"] = merged_avg_move
        for ticker, f in facts.items():
            if ticker in new_avg_move:
                f["avg_move"] = new_avg_move[ticker]

        earn_ts_map = {t: (q.get("earnings_ts") if isinstance(q, dict) else None)
                       for t, q in quotes.items()}
        fund_payload = build_fund_universe(pinned, session_date, earn_ts_map=earn_ts_map, _get=_get)

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

    return fields, bars_payload, fund_payload
