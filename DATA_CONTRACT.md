# data.json / history.json / bars.json / fund/{SYM}.json contract (authoritative — builders #1 and #2 both obey this)

The fetcher writes `data.json` and `history.json` to the `data` branch, plus
two sidecars built at most once per day: `bars.json` (daily OHLC per pinned
ticker) and `fund/{SYM}.json` (per-symbol fundamentals). The frontend reads
`data.json` (and, if it renders bars/fundamentals, the sidecars) — history is
internal to the fetcher. All numbers are plain JSON numbers; missing/unknown
values are `null` (never a string sentinel). All strings are already plain
(frontend still escapes on render).

## data.json

```json
{
  "generated_at": "2026-07-16T21:40:05Z",      // UTC ISO8601, when this cycle finished
  "generated_at_ct": "2026-07-16 16:40 CT",     // human string, Central
  "session_date": "2026-07-16",                  // trading date this data belongs to
  "market_state": "closed",                      // "open" | "premarket" | "afterhours" | "closed"
  "universe": {
    "watched": 35,         // size of the curated pinned list (no market screen)
    "candidates": 35,      // of those, how many resolved a live quote
    "with_options": 35,    // of those, how many had a usable CBOE chain
    "pinned": 35           // len(PINNED) — watchlist + sector ETFs
  },
  "stats": {                 // header tiles (computed across BOTH boards' members, deduped by ticker)
    "bullish_flow": 12,
    "bearish_flow": 9,
    "firing": 3,
    "high_conviction": 14    // conviction-board members with score >= 60 (swing-only tickers are not counted)
  },
  "etf_flows": {             // semi ETF share-flow context card (added 2026-07-19); null if the fetch failed and no history exists
    "as_of_session": "2026-07-18",   // session the shares-outstanding snapshot belongs to
    "flow_session": "2026-07-17",    // the session the DOLLARS in flow_1d actually moved (max of the
                                     // per-fund flow_session values below; null when every fund is
                                     // collecting). The card's honest date label: over a weekend or a
                                     // Monday snapshot this can lag as_of_session by several sessions,
                                     // and the UI must label the money with THIS date, never "yesterday".
                                     // (Documented 2026-08-18; the fetcher has published it since the
                                     // lag-correction fix — this entry catches the contract up.)
    "funds": [                        // fixed order: SMH, SOXX, SOXL, SOXS, DRAM; a fund with no data this cycle is omitted
      {
        "ticker": "SMH",
        "flow_1d": -123456789.0,      // (shares outstanding this session - previous session) x NAV, signed $;
                                      // null until 2 sessions of SO history exist ("collecting"), and also
                                      // null when split_suppressed is true (see below)
        "flow_session": "2026-07-17", // session this fund's flow_1d dollars moved (documented 2026-08-18)
        "baseline_session": "2026-07-17",  // session the SO baseline came from; null when flow_1d is null
        "streak": 3,                  // consecutive sessions (incl. latest) of same-sign daily flow; null when flow_1d is null
                                      // split days contribute a 0 delta, so they break a streak rather than extend it
        "flow_1m": -4800472730.0,     // trailing 1-month net flow $, straight from TV fund_flows.1M; null if TV omits it
        "aum": 71093689042.6,         // fund AUM $ (TV); null if TV omits it
        "so": 120391874,              // shares outstanding this session
        "nav": 568.67,                // NAV per share (TV); the $ multiplier for flow_1d
        "split_suppressed": false     // true when this session's SO change looks like a SPLIT, not creations
                                      // (added 2026-07-28). SO and NAV moving by reciprocal factors at a listed
                                      // split ratio (within 8%) is a split: the share count changed and NO money
                                      // moved. Read naively a 1-for-10 reverse split — routine for SOXL/SOXS —
                                      // prints an outflow of ~90% of the fund's AUM, the same fabricated number
                                      // class as the CRWD 4-for-1 fake -74.9%. When a NAV is missing the split
                                      // cannot be confirmed, so a split-shaped SO ratio still suppresses.
                                      // flow_1d goes null (NOT 0 — a flat day was not observed); the site
                                      // renders "split — n/a".
      }
    ]
  },
  "big_orders": [ <BigOrder>, ... ],          // biggest-orders board (added 2026-07-31); cross-ticker,
                                              // sorted premium desc, at most BIG_ORDERS_CAP rows and at
                                              // most BIG_ORDERS_PER_TICKER rows per ticker.
                                              // Empty array (never null) when nothing clears the floor.
  "big_orders_capped": [                      // per-ticker cap disclosure; [] when the cap bound nothing.
    {"ticker": "QQQ", "shown": 3, "earned": 5}  // "earned" = rows this ticker held in the UNCAPPED top
                                              // BIG_ORDERS_CAP on dollars alone; "shown" = rows published.
                                              // Sorted by earned desc. The frontend MUST render this —
                                              // a bounded board that doesn't say what it dropped reads
                                              // as "this is everything".
  ],
  "conviction": [ <ConvictionCard>, ... ],   // 0-7 DTE board, sorted score desc
  "swing": [ <SwingCard>, ... ],              // 14d-6mo board, sorted score desc
  "notes": {
    "flow_proxy": "Net flow = call premium traded minus put premium traded (volume x last x 100). Free data can't see buy/sell side — this is premium changing hands, not directional order flow.",
    "delay": "Options data is 15-minute delayed (CBOE free feed). Stock prices update live every 30s (TradingView Cboe One).",
    "tilt": "…methodology one-liner for the aggressor tilt (see build_snapshot.py header)…",
    "flow_pct": "…methodology one-liner for the premium-weighted put/call split…",
    "oi_confirm": "…methodology one-liner for OI-confirm…",
    "etf_flows": "…methodology one-liner for the semi ETF flows card…",
    "big_orders": "…methodology one-liner for the biggest-orders board…"
  },
  "brief": { "...": "...", "stale": false },   // OPTIONAL — see note below
  "catalysts": [ <Catalyst>, ... ],             // OPTIONAL — see note below
  "news": { "items": [ <NewsItem>, ... ], "rotation_banner": false },  // OPTIONAL
  "facts": { "MU": { "hi52": null, "...": "..." } },  // OPTIONAL
  "desk_private": { "v": 1 },                    // OPTIONAL, opaque — see note below
  "fed_odds": { "hike_pct": 28.4, "...": "..." },  // OPTIONAL — see note below
  "context_updated_at": "2026-08-15T14:32:00Z"   // OPTIONAL — see note below
}
```

> **All seven keys above are OPTIONAL and were added in the context-layer build
> (2026-08; `fed_odds` 2026-08-18).** Absent on old snapshots and the site renders nothing for a
> missing key — the same "old readers keep working" rule every prior addition
> in this file follows. Each is OMITTED entirely (not present as a key) when
> its own build produced nothing that cycle, never present with a `null`/`{}`
> placeholder — a caller checks `"brief" in data`, not `data["brief"] is not
> None`, except `desk_private` which is a true nullable passthrough (see below).
>
> **`brief`** — a verbatim passthrough of the vault's
> `market-data/data/brief_summary.json` (ClaudeVault repo, fetched read-only
> over the GitHub raw-content API), with exactly one field the loop adds
> itself: `"stale"` (bool) — true when the brief's own `date` field is older
> than the last completed trading day, computed the same way
> `build_snapshot.py` computes `session_date`. Every other key inside `brief`
> is whatever `brief_summary.json` contains that cycle, unmodified — this
> contract does not pin its inner shape, because the loop never inspects it
> beyond the one `date` field needed for `stale`. Fetched on the hourly gate
> (see `fetcher/.context_cache.json` below), not every cycle.
>
> **`fed_odds`** (added 2026-08-18, Zach's ask) — Polymarket's market-priced
> chance that the Fed RAISES rates at the next FOMC meeting. The loop fetches
> this itself on the hourly context gate (it is NOT a vault passthrough), so it
> refreshes intraday rather than once a day like `brief`. Absent entirely when
> nothing trustworthy resolved. Shape:
>
> ```json
> {
>   "as_of": "2026-08-18T12:34:24Z",   // UTC, when the loop read the book
>   "source": "Polymarket",
>   "event_title": "Fed Decision in September?",
>   "url": "https://polymarket.com/event/fed-decision-in-september-762",
>   "meeting_date": "2026-09-16",      // the FOMC decision this book settles on
>   "days_to_meeting": 29,
>   "hike_pct": 28.4,                  // chance of ANY increase, normalised (see below)
>   "hold_pct": 70.5,
>   "cut_pct": 1.1,                    // hike + hold + cut == 100
>   "hike_pct_raw": 28.85,             // the same sum BEFORE normalising
>   "book_sum_pct": 101.45,            // what every leg's Yes price summed to
>   "legs": [ {"label": "25 bps increase", "pct": 28.5}, ... ],
>   "volume_usd": 36569390.0,          // the event's traded volume, for the thin-book guard
>   "liquidity_usd": 3873767.0,
>   "chg_1d_pp": 5.0,                  // change in hike_pct_raw, in percentage POINTS
>   "chg_1w_pp": -11.2,                //   over 1 day / 7 days / 30 days.
>   "chg_1m_pp": -7.2,                 //   null when the history does not reach back that far
>   "year_hike_pct": 48.5,             // "any hike this calendar year" — context only, may be null
>   "grade": "HOSTILE",                // "HOSTILE" | "NEUTRAL" | "SUPPORTIVE"
>   "alarm": false                     // true when the page should shout (see thresholds)
> }
> ```
>
> **`hike_pct` is the SUM of every increase leg** (25 bps + 50+ bps), not the
> headline 25 bps leg: the question is whether the Fed raises, and any increase
> answers it. Same for `cut_pct`. The legs are then divided by `book_sum_pct` so
> the three numbers add to 100 on the page — the raw legs sum slightly over
> because each carries its own bid/ask spread.
>
> **`grade` and `alarm` are computed in the fetcher, never on the page**, so the
> desk and the Morning Brief can never disagree about what counts as loud.
> `grade` is HOSTILE when `hike_pct >= 25` or `chg_1d_pp >= 10` (a sharp
> one-day repricing is itself the news, even from a low base), SUPPORTIVE when
> `cut_pct >= 50`, else NEUTRAL. `alarm` is true when `hike_pct >= 40` (near a
> coin flip) or `chg_1d_pp >= 10`. **These thresholds are duplicated from
> ClaudeVault's `market-data/morning-report/macro_backdrop.py` (`FED_HIKE_*`) on
> purpose — two repos, two CI runs, one methodology. Move a number in one and
> you must move it in the other in the same change** (same class of sync
> obligation as `index.html`'s TIPS text vs `build_snapshot.py`'s scoring).
>
> **Guards — the key is OMITTED rather than guessed** when: the fed-rates shelf
> has no live "Fed Decision in <month>" event; the nearest such event traded
> under $250k (too thin to mean anything); the legs sum outside 80-120% (the
> book is being read wrong, and a wrong read must fail rather than print a
> confident number); or either endpoint is down. A delta is `null` rather than
> partial when the price history does not reach its window — "no data" is not a
> smaller move. **Never render an absent `hike_pct` as 0%**: a 0% chance of a
> hike is a real and dramatic claim, and "we could not read the book" is not it.
>
> The Morning Brief also carries its own once-a-day copy of the same reading at
> `brief.fed_hike` (written by the vault's `desk_summary.py`, same shape minus
> `event_title`/`volume_usd`/`liquidity_usd`/`book_sum_pct`/`hike_pct_raw`). The
> page prefers top-level `fed_odds` and falls back to `brief.fed_hike`, so the
> card still appears when the loop's own fetch failed or when no
> `VAULT_READ_TOKEN` is configured — see `normalizeFedOdds()` in `index.html`.
>
> **`catalysts`** — a merged, date-sorted list of upcoming market events: TV's
> economic calendar (next 28 days), the vault's hand-kept
> `market-data/data/econ_calendar.csv` (WINS on same-day+similar-title
> conflicts — it is Zach's verified source, not TV's raw feed), one row per
> pinned ticker's next known earnings date, the vault's
> `market-data/data/memory_events.csv` rows, and locally-computed options-
> expiration (OpEx) rows (third-Friday-of-month = MEDIUM "Monthly options
> expiration", other Fridays = LOW "Weekly options expiration", quarter-end =
> MEDIUM). **Anchors are the one exception to the 28-day window**: the next
> FOMC rate decision and the next CPI print are always included even when they
> fall past the 28-day horizon, and so is each pinned name's next earnings
> date — all three marked `"anchor": true` — because a name popping up on a
> board with an earnings date 40 days out is exactly when Zach wants the
> catalyst visible, not dropped for being outside an arbitrary window.
>
> > **Importance floor:** TradingView econ rows below MEDIUM are dropped at
> fetch — the raw feed carries hundreds of LOW auction/release rows per month
> and the rail is curated by design. `"LOW"` therefore appears only on
> market-calendar rows (weekly OpEx) or rows the hand-kept CSV mirror
> deliberately carries.

### Catalyst
> ```json
> {
>   "date": "2026-09-16",            // YYYY-MM-DD
>   "time_ct": "13:00",               // HH:MM 24h, America/Chicago; best-effort —
>                                     // null when the source gives no time (e.g. some
>                                     // memory_events.csv rows)
>   "title": "FOMC Rate Decision + Summary of Economic Projections (dot plot)",
>   "importance": "HIGH",             // "HIGH" | "MEDIUM" | "LOW"
>   "kind": "econ",                   // "econ" | "earnings" | "memory" | "market"
>   "ticker": null,                   // set for "earnings" rows and memory rows whose
>                                     // scope looks like a US ticker; else null
>   "session": null,                  // "premarket" | "afterhours" | null — only ever
>                                     // populated on "earnings" rows, only when
>                                     // derivable from TV's earnings timestamp
>   "forecast": null,                 // econ rows only (TV/csv "forecast"); else null
>   "prior": null,                    // econ rows only (TV/csv "previous"); else null
>   "actual": null,                   // econ rows only, filled in once the print
>                                     // lands; else null
>   "anchor": false,                  // true = kept past the 28-day window (see above)
>   "source": "tv_calendar",          // "econ_calendar" | "tv_calendar" | "tv_earnings"
>                                     // | "memory_events" | "market_calendar".
>                                     // INTERNAL provenance — the page does NOT
>                                     // render this (it used to, as "via
>                                     // tv_calendar" on every row); keep it for
>                                     // debugging.
>   "unit": null,                     // OPTIONAL, tv_calendar rows only: "%" | "$" | null
>   "scale": "M",                     // OPTIONAL, tv_calendar rows only: "K"|"M"|"B"|"T"|null
>   "period": "Jul",                  // OPTIONAL, tv_calendar rows only: the reporting
>                                     // period the figure covers ("Jul", "Q2")
>   "agency": "Census Bureau"         // OPTIONAL, tv_calendar rows only: the publishing
>                                     // body TV names for the release
> }
> ```
>
> **Units on `forecast`/`prior`/`actual` (added 2026-08-17).** Those three are
> bare numbers, and until this date the page printed them bare — "fc 1.35 ·
> prior 1.427" for Housing Starts (millions of homes), "prior -911" for the
> payroll revision (thousands of jobs). `unit` and `scale` are what make them
> readable and both come straight from the TV feed. **The figures are ALREADY
> scaled to match `scale`** (the feed's own `previousRaw` is 1427000 where
> `previous` is 1.427 at scale "M"), so a consumer appends the suffix and must
> never rescale. All four fields are optional: absent or null means "no label",
> and a row with no unit and no scale is correct to print bare — an ISM
> reading of 55.6 is an index level, not a quantity. Rows from the other four
> sources do not carry them at all.
>
> **`news`** — up to 20 items total (not per ticker) across the pinned
> universe, newest first, pulled from TradingView's per-symbol news endpoint.
> Within that total, no single ticker's tag can hold more than
> `NEWS_PER_TICKER_CAP` (3) slots unless a backfill pass needs the extra room
> to reach 20 (Zach's ruling, 2026-08-15: mega-caps may still appear most
> often, but other tagged names are now guaranteed a seat instead of being
> crowded out entirely). `rotation_banner` is true when at least 2 of the
> scanned titles carry rotation/derisking language — the identical keyword
> list the morning brief's headline scan uses
> (`market-data/morning-report/sections/headlines.py`, `ROTATION_KEYWORDS`),
> copied into `fetcher/context.py` with a comment naming that source so the
> two lists can't silently drift apart. Display only.
>
> ### NewsItem
> ```json
> {"ticker": "MU", "title": "...", "ts": "2026-08-15T14:02:00Z", "url": "https://..."}
> ```
>
> **`facts`** — per pinned ticker, one row of reference numbers riding along
> on the scanner batch-quote call `build_universe()` already makes every
> cycle (no separate fetch, no gate). A ticker absent from `quotes` that
> cycle (self-healing exchange probe found nothing) is simply absent from
> `facts` too.
>
> ### Facts entry
> ```json
> {
>   "hi52": 1255.0,          // TV price_52_week_high; null if TV omits it
>   "lo52": 113.46,          // TV price_52_week_low; null if TV omits it
>   "cap": 1097386086649.25, // TV market_cap_basic; null if TV omits it
>   "beta": 3.0174081,       // TV beta_1_year; null if TV omits it
>   "avol": 34379166.7,      // TV average_volume_10d_calc; null if TV omits it
>   "short_pct": null,       // ALWAYS null. Live-probed 2026-08 across every pinned
>                            // name: short_percent_float, short_interest_percent,
>                            // short_interest, shares_short, short_percent_of_float,
>                            // shares_short_prior_month, days_to_cover_short — every
>                            // candidate column returned null for every ticker (the
>                            // scanner accepts unknown column names silently rather
>                            // than erroring, so a typo can't be told apart from a
>                            // real-but-empty field; several tickers were cross-
>                            // checked to rule that out). TradingView's free scanner
>                            // does not carry short interest at all — DATA_SOURCES.md
>                            // already routes that need to Yahoo quoteSummary
>                            // (`sharesShort`/`shortPercentOfFloat`), a second vendor
>                            // this build deliberately did not wire in. The key stays
>                            // present so the frontend has a stable field to check
>                            // for rather than a key that might appear later; never
>                            // rendered as 0.
>   "earn_days": 45,         // calendar days, session_date -> TV earnings_release_next_date;
>                            // null if TV has no date on file, or the date is in the past
>   "rsi": 56.3,             // TV RSI; null if TV omits it
>   "avg_move": 3.45,        // mean(|daily % change|) over the last 20 closes in
>                            // bars.json, 2dp. Populated only after bars.json has
>                            // built at least once for this ticker; recomputed once
>                            // per day alongside the bars rebuild (see bars.json
>                            // below) and carried forward on the other ~50 cycles/day
>                            // via fetcher/.context_cache.json — a deliberately
>                            // day-stale reading, not a live one.
>   // ── Fundamentals (added 2026-08-15, Task 3) — all 14 verified live on
>   // NASDAQ:NVDA the same day, rides the SAME scanner batch-quote call as
>   // everything else above (no separate fetch, no gate). null if TV omits it
>   // for a given ticker, exactly like every other field here — never 0.
>   "pe": 34.483,            // TV price_earnings_ttm (trailing P/E)
>   "peg": 0.313,            // TV price_earnings_growth_ttm
>   "net_margin": 62.97,     // TV net_margin_ttm, percent (62.97 == 62.97%)
>   "gross_margin": 74.15,   // TV gross_margin_ttm, percent
>   "op_margin": 64.02,      // TV operating_margin_ttm, percent
>   "fcf_margin": 46.97,     // TV free_cash_flow_margin_ttm, percent
>   "debt_eq": 0.0656,       // TV debt_to_equity
>   "roe": 114.29,           // TV return_on_equity, percent
>   "ps": 25.56,             // TV price_sales_ratio
>   "pb": 34.79,             // TV price_book_ratio
>   "ev_ebitda": 32.51,      // TV enterprise_value_ebitda_ttm
>   "yld": 0.124,            // TV dividends_yield_current, percent (0.124 == 0.124%)
>   "target": 314.29,        // TV price_target_average (analyst 12-mo price target, $)
>   "rec_mark": 1.115        // TV recommendation_mark, 1.0 (strong buy) .. 5.0 (sell)
> }
> ```
>
> **Forward P/E is NOT in `facts`.** TradingView's scanner was probed live
> 2026-08-15 under both `price_earnings_forward_fy` and `price_earnings_fy`
> and BOTH returned null for every ticker tried — this scanner simply does
> not carry a forward multiple. Forward P/E is instead `pe_forward` in
> `fund/{SYM}.json` (see below), sourced from stockanalysis.com/Yahoo.
> **`desk_private`** — omitted, same as the other five keys, whenever the
> vault fetch has nothing to report (no token, 404, bad JSON); present as
> `{"v": 1, ...}` — an encrypted blob passed through **verbatim** from the
> vault's `market-data/data/desk_private.enc.json` — whenever the fetch
> succeeds. The loop republishes the parsed JSON byte-for-byte; it never
> decrypts, inspects, or validates the payload's contents — only Zach's own
> client-side key can read it.
>
> **`context_updated_at`** — UTC ISO8601, the last time the hourly-gated
> vault/econ/news fetch actually ran — **not** this cycle's `generated_at`.
> `facts` (ungated) is always as fresh as the current cycle; `bars.json`
> carries its own `built` date; this timestamp is `brief`/`catalysts`/`news`/
> `desk_private`'s freshness signal, since those four can be up to ~55 minutes
> older than the snapshot they're riding in.

## bars.json (published beside data.json on the `data` branch)

A sidecar file for the pinned universe's daily OHLC history, written in the
same publish step `loop.py` already uses for data.json/history.json —
`loop.py`'s `git add -A` over `OUT_DIR` picks up any new file there, so
shipping this required no `loop.py` change. Built **at most once per calendar
day** (see `fetcher/.context_cache.json` below): it is daily-bar history, so
refetching it every ~7-minute cycle would be pure waste against Yahoo for no
benefit.

**v3 (2026-08-15, Task 2, wave 3):** rows are now `[open, high, low, close,
volume]` quints, the fetch window doubled from 1y to 2y, and the file carries
a `"v": 3` marker. Source is unchanged — the SAME Yahoo v8 chart call this
file always used already returns `open`/`high`/`low`/`close`/`volume`
parallel arrays in `indicators.quote[0]`; earlier versions just read less of
it. **Any consumer of this file must accept ALL THREE shapes**: v1 (no `"v"`
key, `bars` values are plain close-only number arrays), v2 (`"v": 2`, `bars`
values are `[o,h,l,c]` quad arrays), and v3 (`"v": 3`, `bars` values are
`[o,h,l,c,v]` quint arrays) — the same "old readers keep working" rule every
other addition in this file follows. A reader that only wants the close can
take `row[3]` in v2 or v3, or `row` itself in v1 — that index didn't move
when volume was appended after it.

```json
{
  "built": "2026-08-15",
  "v": 3,
  "bars": {
    "MU": [[112.80, 114.10, 112.50, 113.46, 24581900], "...", [968.00, 975.20, 965.10, 971.66, 5124300]]
  }
}
```

**Tape symbols (2026-08-17).** Beyond the pinned universe, `bars` also carries
seven keys for the page's index/macro strip so its tiles can open a chart:
`SPY`, `DIA`, `IWM`, `VIX`, `US10Y`, `CRUDE`, `DXY` (`QQQ` was already pinned).
They are `context.TAPE_BARS`, fetched from Yahoo under the symbols that source
needs (`^VIX`, `^TNX`, `CL=F`, `DX-Y.NYB`) but **keyed by the desk key**, which
is the string `index.html` looks them up under.

> **Crude's key is `CRUDE`, never `WTI`.** `WTI` is W&T Offshore, an
> oil-producer equity that is in the rail. Keying crude as `WTI` would overwrite
> that stock's bars with the crude future's and open an ~$82 oil chart from a
> tile the rail uses for a small-cap stock. The tape still *displays* the tile
> as "WTI · CRUDE"; only the bars key and chart lookup differ.

These seven appear in `bars.json` ONLY. They are deliberately absent from
`facts`, from `fund/{SYM}.json` and from every board — an index has no options
chain, no market cap and no margins — so a consumer must treat "has bars, has
no facts" as a normal, expected combination and not render an empty
fundamentals table for it.

- `built` — session date (`YYYY-MM-DD`) this file was last (re)built.
- `v` — schema version, `3` as of 2026-08-15. Absent entirely on pre-2026-08-15
  snapshots (v1), or `2` on snapshots written between the OHLC upgrade and the
  volume/2y upgrade earlier the same day — check for the key's VALUE, not
  just its presence, to tell all three apart.
- `bars` — per pinned ticker (`build_snapshot.PINNED`, TRACK_ONLY names
  included — bars/facts/fund track the full universe regardless of chain
  eligibility), up to 504 daily (2 years' worth of) `[open, high, low, close,
  volume]` rows, **oldest first**, o/h/l/c rounded 2dp. Source: Yahoo's v8
  chart API
  (`query1.finance.yahoo.com/v8/finance/chart/<SYM>?range=2y&interval=1d`,
  bumped from `range=1y` 2026-08-15 so the frontend has enough trailing
  history to plot a full SMA200 line rather than just a partial one). A
  ticker whose fetch failed is simply absent from `bars` — fail-soft, never
  zero-filled or backfilled from a stale value. A single bar missing ANY of
  its four OHLC legs is dropped entirely (not partially filled) — same
  "never fabricate" rule applied per-row instead of just per-ticker; this
  drop decision never depends on volume. `volume` (the 5th element) is an
  int when Yahoo has a reading for that day, or `null` — NEVER `0` — when it
  doesn't (None != 0 throughout this codebase; a null-volume bar still keeps
  its OHLC and should simply be skipped in a volume pane, not read as "no
  shares traded").

- `split_fixed` — **present only when a repair fired** (added 2026-08-18):
  `{ticker: factor}` for every symbol whose pre-split history Yahoo served on
  the wrong scale and the fetcher rescaled. Yahoo returned SOXS with every bar
  before 2026-05-26 priced exactly 15x too high (1159.50 against 77.30 from
  both Polygon and TradingView), which drew three months of real trading as a
  flat line along the bottom of a $31–$1,660 axis. `context._repair_split_breaks`
  finds a bar that OPENS a factor of 2.5+ away from the previous CLOSE — the
  signature of a split, since a real crash gaps small and moves intraday —
  divides the earlier bars' prices by that factor and multiplies their volumes
  by it. The published factor is what was applied (15.0 for SOXS; the repaired
  series then matches Polygon bar for bar). The key exists so the page can SAY
  a history was rescaled instead of silently redrawing it — index.html renders
  it as a "split-rescaled 15×" chip on the chart. A consumer that ignores the
  key still gets correct bars; it just can't tell Zach why they changed.
  `bars_intraday.json` runs the same repair (its 60-minute series spans three
  months, long enough to hold a split) but publishes no such key — an intraday
  chart is too short a window to be worth annotating.

`facts.*.avg_move` (see above) is derived from this same fetch — mean of
`abs(daily % change)` over each ticker's last 20 CLOSES (the 4th element of
each row in v2/v3) — but that reading is published in `data.json`'s `facts`,
not duplicated here. Doubling this file's stored history to 2 years does NOT
widen avg_move's own basis: the fetcher re-slices to its last 252 rows
(`AVG_MOVE_BASIS`, decoupled from this file's `BARS_MAX`) before taking the
trailing-20-closes window, so this reading is unaffected by the 2026-08-15
range change.

## bars_intraday.json (added 2026-08-18 — published beside bars.json on the `data` branch)

Intraday OHLCV for the same universe bars.json covers (pinned + tape symbols,
keyed by desk key via the same alias map). Shape:

```jsonc
{
  "built": "2026-08-18T13:05:00Z",   // UTC build time (not a session date —
                                      // this file rebuilds intra-day)
  "v": 1,
  "i15": { "MU": [[t, o, h, l, c, v], ...], ... },  // 15-minute bars, ~5 trading days
  "i60": { "MU": [[t, o, h, l, c, v], ...], ... }   // 60-minute bars, ~3 months
}
```

- Rows are `[epoch_seconds, open, high, low, close, volume]` — one element
  longer than bars.json's quints, with the timestamp FIRST. Intraday charts
  cannot reconstruct bar times the way the daily chart reconstructs weekday
  dates, so a bar with no usable timestamp is dropped at extraction rather
  than kept.
- Same per-row fail-soft rules as bars.json otherwise: a bar missing any OHLC
  leg is dropped whole; a bar with good OHLC but no volume reading keeps
  `v: null` (never zero-filled). A symbol/interval whose fetch failed is
  simply absent.
- Unlike bars.json, TODAY'S IN-PROGRESS bars are INCLUDED — freshness is the
  point of these views, and the page draws the series as-is (no synthetic
  live candle is appended).
- EXTENDED-HOURS bars are included too (`includePrePost=true`, added
  2026-08-18 — the 15m view was blind to premarket without it). The page
  renders pre/post-market candles dimmed; consumers can classify a bar by its
  CT clock time (regular session = 08:30–15:00 CT).
- Rebuilt on its own **~25-minute gate** (`INTRA_STALE_SEC`,
  `intraday_built_at` in `fetcher/.context_cache.json`), not the once-daily
  bars gate. Source is the same Yahoo v8 chart call with
  `interval=15m&range=5d` and `interval=60m&range=3mo`. Caps: 140 rows per
  symbol for i15, 320 for i60 (`INTRA_MAX`).
- The page derives the **4H** view by resampling i60 in 4-bar chunks within
  each CT session day, and the **1W** view by resampling bars.json's daily
  quints — neither is stored here.
- A build where EVERY fetch failed returns nothing and the previous published
  file stands (never overwrite good data with an empty shell).

## fund/{SYM}.json (added 2026-08-15, Task 4 — one file per tracked ticker,
published beside data.json on the `data` branch)

Per-symbol fundamentals: short % of float, forward P/E, earnings surprise
history, next-earnings estimates, and a quarterly/annual revenue+EPS series
— none of which the TV scanner carries (`facts.short_pct` is permanently
null; forward P/E was confirmed null in `facts` too — see above). Written in
the SAME publish step `loop.py` already uses for bars.json — `loop.py`'s
`git add -A` over `OUT_DIR` picks up the new `fund/` directory with no
`loop.py` change. Built **at most once per calendar day, on the SAME gate as
bars.json** (`fetcher/.context_cache.json`'s `bars_built_date` AND
`bars_sig` together — see that file's shape below) — one file per name in
`build_snapshot.PINNED` (TRACK_ONLY names included; this sidecar tracks the
full universe same as bars.json, regardless of CBOE chain eligibility).

`earnings[].rev` backfill (added 2026-08-15, wave 3): a row whose `rev` came
back null from Yahoo (no `financialsChart` match for that quarter — e.g.
AXTI's oldest row, live-confirmed 2026-08-15) is backfilled from this same
symbol's `quarterly` series below by matching period labels (quarter number +
fiscal year mod 100); only `rev` is ever filled this way, never `rev_est` or
`rev_surprise_pct`.

```jsonc
{
  "built": "2026-08-15",
  "sym": "NVDA",
  "short_pct_float": 1.259,          // % of float sold short, or null
  "pe_forward": 22.589,              // forward P/E, or null
  "earnings": [                      // up to 12 rows, newest LAST, oldest first
    {
      "period": "Q1 2027",           // "Q{n} {fiscal year}"
      "date": "2026-04-30",          // fiscal quarter END date (not report date)
      "report_date": "2026-05-28",   // date the results were actually announced
                                      // (Yahoo reportedDate) — the page anchors
                                      // chart E-badges here so they sit on the
                                      // earnings gap; null if Yahoo omits it,
                                      // in which case the page falls back to
                                      // `date`
      "session": "afterhours",       // "premarket" | "afterhours" | null — read
                                      // off the ACTUAL report timestamp, same
                                      // heuristic context._earnings_session uses
                                      // for catalysts; null if unclassifiable
      "eps": 1.87, "eps_est": 1.77191, "eps_surprise_pct": 5.54,
      "rev": 81615000000.0,          // actual reported revenue
      "rev_est": null,               // ALWAYS null — see note below
      "rev_surprise_pct": null       // ALWAYS null — see note below
    }
  ],
  "next_earnings": {                 // null if no confirmed next date anywhere
    "date": "2026-08-26",
    "session": "AMC",                // "AMC" | "BMO" | null (before/after market)
    "eps_est": 2.083, "rev_est": 91846098240.0
  },
  "quarterly": {                     // up to 12 quarters, OLDEST FIRST
    "periods": ["Q2 24", "...", "Q1 27"],   // "Q{n} {2-digit fiscal year}"
    "revenue": [26044000000.0, "...", 81615000000.0],   // reported, not estimated
    "eps": [0.2895, "...", 2.39]             // reported diluted EPS
  },
  "annual": {                        // up to 6 years, OLDEST FIRST — DERIVED, see note
    "periods": ["FY23", "...", "FY26"],
    "revenue": [26974000000.0, "...", 215938000000.0],
    "eps": [0.83, "...", 5.84]
  }
}
```

- `short_pct_float` / `pe_forward` — sourced from stockanalysis.com's
  `/stocks/{sym}/statistics/` page first (short % of float: `shortSelling`
  row `id="shortFloat"`; forward P/E: `ratios` row `id="peForward"`), Yahoo
  quoteSummary `defaultKeyStatistics` (`shortPercentOfFloat`, `forwardPE`)
  as a fallback whenever the stockanalysis.com leg came back null. Both
  independently null if BOTH legs fail for that field.
- `earnings` — sourced from Yahoo quoteSummary's `earnings.earningsChart.
  quarterly` (actual/estimate/surprise% + report timestamp, up to ~4
  quarters — Yahoo's own limit on this module) matched against `earnings.
  financialsChart.quarterly` (actual revenue) by Yahoo's shared calendar-
  quarter label. **`rev_est` and `rev_surprise_pct` are ALWAYS null** —
  probed and NOT found on either source: stockanalysis.com's `/forecast/`
  page only carries TODAY'S consensus (a past quarter's estimate has
  already been revised to match the actual, which is not "what analysts
  expected before the print"), and Yahoo's `earningsTrend` module only
  returned forward-looking periods (`0q`/`+1q`/`0y`/`+1y`) on the account
  this was built against, no historical `-1q..-4q` rows. A fourth vendor
  was deliberately not added for it — same posture as `facts.short_pct`.
- `next_earnings` — date/eps_est/rev_est from Yahoo's `calendarEvents.
  earnings` module (a genuine FORWARD estimate, unlike the historical
  `rev_est` above). `session` is read off stockanalysis.com's own
  before/after-market text when Yahoo's copy is null (Yahoo's calendarEvents
  carries no intraday time at all) or, if a same-ticker TV
  `earnings_release_next_date` timestamp is available, that timestamp takes
  priority (same premarket/afterhours heuristic `catalysts` uses).
- `quarterly` / `eps` — up to 12 quarters of REPORTED (not derived) revenue
  and diluted EPS from stockanalysis.com's `/stocks/{sym}/financials/
  income-statement/?p=quarterly` page (`financialData.revenue` /
  `financialData.epsdil`), oldest first. The leading `"TTM"` column
  (trailing-twelve-months, not a completed quarter) is dropped.
- `annual` — **a DERIVED aggregate, not a separately-fetched or separately-
  reported figure.** Summed from the SAME quarterly rows above, only for
  fiscal years where all 4 quarters are present (a partial year yields no
  row rather than an undercount presented as a full year). This is NOT
  necessarily identical to the company's own separately-filed annual
  diluted EPS, which can differ slightly for weighted-average-share-count
  reasons across the year — e.g. NVDA FY2026: summed-from-quarters gives
  5.84, the company's own filed annual diluted EPS is 4.90. Revenue sums
  match closely since revenue isn't share-count-sensitive. Fetching a
  separate stockanalysis.com annual route instead would have made this
  exact (like `quarterly` is) but pushed every symbol from 3 requests to 4
  against the runtime budget below — a deliberate tradeoff, not an oversight.
- A ticker whose stockanalysis.com legs both fail keeps whatever Yahoo
  supplied (or null); a ticker whose Yahoo leg fails (including "no crumb
  this cycle") keeps whatever stockanalysis.com supplied for
  `short_pct_float`/`pe_forward`/`next_earnings`, with `earnings` empty and
  `rev_est`/`rev_surprise_pct` null throughout — per-field fail-soft, same
  as every other part of this build. NEVER fabricated: a field either came
  from a live source or it is null.
- **Runtime budget:** 3 stockanalysis.com requests/symbol (statistics +
  quarterly financials) + 1 Yahoo quoteSummary request/symbol, at a 0.3s
  sleep between every request. The Yahoo cookie+crumb handshake
  (`fc.yahoo.com` then `query1.finance.yahoo.com/v1/test/getcrumb`) is a
  ONE-TIME cost for the whole run, not per symbol. Measured live 2026-08-15
  for 3 symbols: ~7s total including the crumb dance, extrapolating to
  roughly 2-2.5 minutes for the full ~62-name tracked universe — inside the
  daily gate's budget.

> **Note on `etf_flows`:** this is a once-per-session CONTEXT signal, not a
> scoring input — it never touches the conviction/swing scores. Daily flow is
> estimated from the day-over-day change in the fund's shares outstanding
> (ETFs create/destroy shares as money enters/leaves), so it reads "previous
> session's money movement," unlike the 7-minute options boards. SOXX is
> fetched for this card only — it is NOT part of the PINNED options universe.
> The frontend must render nothing (no card) when `etf_flows` is null/absent
> or `funds` is empty, so old snapshots keep working.

> **Note on `big_orders` — it is a DAY TOTAL PER CONTRACT, not a single order.**
> Each row is one options contract's whole session: `volume x last x 100`, the
> same premium convention as `net_flow` and `flow_pct`. The free CBOE feed
> publishes per-contract aggregates, not a trade-level tape, so an individual
> block or sweep is **not observable here** and the field names deliberately
> avoid implying one (`premium`, `volume` — never "order size"). Commercial
> "big order" feeds rank single prints; ranking day totals is the closest
> honest thing free data supports, and the site must keep saying so.
> Two filters are load-bearing:
> - **Near-money only** (`MONEYNESS_BAND`, ±20% of spot) — the same reason
>   `flow_pct` carries it. Premium is intrinsic + extrinsic, so a deep-ITM
>   strike costs nearly what it is already worth; a handful of those carry
>   enormous dollars while betting on nothing (they are a way of holding the
>   stock) and would permanently own the top of an unfiltered leaderboard.
>   Unfiltered, LLY's 2026-07-27 chain put seven ~35%-ITM strikes at 79% of all
>   call premium. **Do not widen this band to "show more names".**
> - **A premium floor** (`BIG_ORDERS_MIN_PREMIUM`) so a quiet session publishes
>   a short board rather than noise. A ticker with no spot is skipped entirely
>   (fails closed — without spot, a stock-replacement strike is
>   indistinguishable from a bet).
>
> DTE spans `0..BIG_ORDERS_DTE_HI` (183) on purpose: the two scoring boards
> bucket 0-7 and 14-183, and this board must NOT inherit their 8-13 day blind
> spot. Per-ticker shortlists are capped at `BIG_ORDERS_CAP` before the
> cross-ticker merge — equal to the published row count, so the merge the cap is
> applied to is exact. Display only: no row here moves any score.
>
> **`BIG_ORDERS_PER_TICKER` (3) caps rows per ticker, and the cap is DISCLOSED,
> not silent (Zach's call 2026-07-31).** The first live cycle put 0-DTE QQQ
> calls in 5 of 12 rows at adjacent strikes ($683-$687, same expiry) — an honest
> ranking that crowded five other names off the board to say one thing five
> times. Rows a capped ticker gives up go to the next-loudest OTHER contract, so
> the board stays `BIG_ORDERS_CAP` long. `big_orders_capped` reports what the cap
> cost, measured against the UNCAPPED top-`BIG_ORDERS_CAP` (not the ticker's
> whole shortlist — a 13th-place row was never going to show, so counting it
> would overstate the loss).

### BigOrder
```json
{
  "ticker": "AMZN",
  "tv_symbol": "NASDAQ:AMZN",       // exchange-prefixed, same as the cards
  "side": "CALL",                   // "CALL" | "PUT"
  "strike": 250.0,
  "expiry": "2026-08-21",
  "dte": 21,                        // calendar days from session_date
  "last": 23.0,                     // last traded price of the contract
  "volume": 54529,                  // contracts traded today (session total)
  "open_interest": 41200,
  "delta": 0.55,                    // null if CBOE omits it
  "iv": 0.31,                       // decimal (0.31 = 31%); null if CBOE omits it
  "premium": 125416670.0,           // volume x last x 100 — the ranking key.
                                    // A SESSION TOTAL, not one order (see note above).
  "occ": "AMZN260821C00250000"
}
```

> **Note on `notes`:** the frontend does NOT render `notes.*` — it ships its
> own tooltip copy (the `TIPS` object in `index.html`). The `notes` strings
> here and the `TIPS` text describe the same methodology and must be kept in
> sync whenever scoring or weights change.

### ConvictionCard
```json
{
  "ticker": "MU",
  "tv_symbol": "NASDAQ:MU",        // exchange-prefixed, for the browser's live TV poll
  "direction": "BULL",             // "BULL" | "BEAR"  (sign of 0-7DTE net flow)
  "firing": true,                  // score>=80 OR flow accel vs prior cycle
  "score": 87,                     // 0-100 int
  "spot": 858.35,                  // underlying price at fetch (CBOE current_price)
  "spot_at_alert": 851.10,         // spot when first appeared on this board today (from history); null if new-this-cycle
  "net_flow": 4250000.0,           // signed $, 0-7 DTE (call prem - put prem)
  "cp_ratio": 2.35,                // call vol / put vol, 0-7 DTE; null if no put vol
  "flow_pct": 73.0,                // premium-weighted put/call split, 0-7 DTE: the DOMINANT
                                   // side's share of NEAR-MONEY premium traded (strikes within
                                   // MONEYNESS_BAND = ±20% of spot), 50.0-100.0, 1dp.
                                   // Pairs with flow_side. Both null if no near-money premium
                                   // traded, or if spot is unknown (fails closed — with no spot
                                   // a stock-replacement strike is indistinguishable from a bet).
                                   // cp_ratio counts contracts, flow_pct counts dollars —
                                   // they diverge when one side's options are far pricier.
                                   // NEAR-MONEY SINCE 2026-07-28: premium is intrinsic +
                                   // extrinsic value, so weighting the whole bucket let deep-ITM
                                   // stock-replacement paper dominate (LLY 2026-07-27: seven
                                   // Jul-31 strikes ~35% below a ~$1,205 spot, ~101% of price
                                   // intrinsic, were 79% of all call premium and produced a bogus
                                   // "84% CALL"). Band-only reads 60.1%; an independent
                                   // ">=90% intrinsic" filter reads 60.4%. NOTE net_flow above
                                   // is still whole-bucket and carries the same distortion — it
                                   // is a scoring input, so changing it is a separate decision.
                                   // Display only; not a scoring input.
  "flow_side": "PUT",              // "CALL" | "PUT" — which side flow_pct refers to; ties
                                   // (exactly 50/50) resolve to "PUT". null if no near-money
                                   // premium, or if spot is unknown.
  "flow_pct_basis": 1834000.0,     // $ of near-money premium (both sides) behind flow_pct — the
                                   // denominator, exposed so the UI can suppress a percentage
                                   // computed on trivia ("95% CALL" of $6K is noise, not signal;
                                   // the display floor mirrors BIG_ORDERS_MIN_PREMIUM = $100K).
                                   // null exactly when flow_pct is null. Display only; not a
                                   // scoring input. (Added 2026-08-18.)
  "rvol": 1.04,                    // relative_volume_10d_calc from TV
  "change_pct": -0.66,             // TV change (day % )
  "tilt": 0.64,                    // aggressor tilt, -1..+1: day-accumulated sampled buy/sell
                                   // classification of traded contracts vs their bid/ask
                                   // (+1 = all classified premium leaned bullish); null until
                                   // anything classifies ("sampling"). Both DTE buckets.
  "tilt_prem": 1250000.0,          // $ premium classified into the tilt today (both sides summed)
  "popular_contract": {            // max-premium contract within +/-20% moneyness, 0-7 DTE; null if none
    "side": "CALL",                // "CALL" | "PUT"
    "strike": 860.0,
    "expiry": "2026-07-17",
    "dte": 1,
    "last": 12.40,
    "delta": 0.52,
    "iv": 0.98,                    // decimal (0.98 = 98%)
    "volume": 8200,
    "open_interest": 4100,
    "occ": "MU260717C00860000"
  }
}
```

### SwingCard
```json
{
  "ticker": "MU",
  "tv_symbol": "NASDAQ:MU",
  "direction": "BULL",
  "score": 72,                     // 0-100 int (swing-weighted; see scoring doc in build_snapshot.py)
  "spot": 858.35,
  "spot_at_alert": 851.10,         // null if new
  "persist": 4,                    // n out of 5 sessions same-direction net flow (from history)
  "persist_max": 5,
  "flow_5d": 18500000.0,           // signed $, sum of last up-to-5 sessions' net flow
  "flow_5d_pct": 62.0,             // flow_5d as % of gross premium (calls+puts) over the same sessions; signed, -100..+100; null if no gross history
  "oi_build": 12000,               // day-over-day sum-OI delta in the flow direction (contracts); null if <2 days history
  "oi_confirm": "OPENING",         // "OPENING" | "CLOSING" | "CHURN" | null — did yesterday's
                                   // swing-bucket (14-183d) volume become held OI (+/-25% of
                                   // yesterday's side volume)? null if <2 days of side data or
                                   // yesterday's side volume < 500
  "oi_confirm_frac": 0.41,         // (OI_today - OI_yest) / vol_yest on yesterday's direction side; null when oi_confirm is null
  "oi_confirm_side": "CALL",       // which side was checked (yesterday's direction); null when oi_confirm is null
  "trend": "UP",                   // "UP" | "DOWN" | "MIXED"  (spot vs SMA20/SMA50)
  "iv_rank": 63,                   // 0-100 percentile once >=20 sessions; else null
  "iv30": 0.98,                    // decimal; always present as fallback display
  "iv_collecting": true,           // true while <20 sessions of iv history (show "collecting history")
  "cp_skew": 1.85,                 // call prem / put prem, 14d-6mo; null if no put prem
  "earnings_in_window": true,      // TV earnings date falls inside suggested-contract expiry
  "earnings_days": 12,             // days to earnings; null if none/out of window
  "suggested_contract": {          // highest-premium 0.30-0.60 |delta|, 14d-6mo; null if none
    "side": "CALL",
    "strike": 900.0,
    "expiry": "2026-09-18",
    "dte": 64,
    "delta": 0.42,
    "iv": 0.95,
    "volume": 3100,
    "open_interest": 8800,
    "occ": "MU260918C00900000",
    "entry": 34.50,                // = last
    "stop": 24.15,                 // entry * 0.70  (-30%)
    "target": 70.73,               // entry * 2.05  (+105%)
    "rr": 3.5                      // fixed 3.5
  }
}
```

## history.json (fetcher-internal)
```json
{
  "sessions": {
    "2026-07-16": {
      "MU": {
        "net_flow_0_7": 4250000.0,   // signed
        "sum_oi_0_7": 210000,        // aggregate OI in the flow direction (contracts)
        "gross_prem_0_7": 10600000.0, // calls+puts premium, 0-7 DTE (denominator for flow_5d_pct)
        "nm_call_prem_0_7": 2832000.0,// NEAR-MONEY call premium, 0-7 DTE (added 2026-07-28)
        "nm_put_prem_0_7": 1882000.0, // NEAR-MONEY put premium, 0-7 DTE
                                      // These are the two inputs FLOW % is computed from. Archived
                                      // because the accuracy backtest found history stored only
                                      // net_flow and gross premium, so no historical FLOW % could be
                                      // reconstructed and its predictive value was untestable. Absent
                                      // on sessions written before 2026-07-28 — readers must treat a
                                      // missing key as unknown, never as zero.
        "iv30": 0.98,
        "direction": "BULL",
        "tilt_bull_prem": 2100000.0, // day-accumulated classified bullish premium (calls bought + puts sold)
        "tilt_bear_prem": 850000.0,  // day-accumulated classified bearish premium (calls sold + puts bought)
        "swing_vol_c": 41000,        // swing-bucket (14-183d) call volume   — OI-confirm inputs
        "swing_vol_p": 28000,        // swing-bucket put volume
        "swing_oi_c": 910000,        // swing-bucket call OI
        "swing_oi_p": 640000,        // swing-bucket put OI
        "first_board_conviction": {"time": "2026-07-16T14:32:00Z", "spot": 851.10},
        "first_board_swing": {"time": "2026-07-16T14:32:00Z", "spot": 851.10}
      }
    }
  },
  "iv_history": { "MU": [0.91, 0.88, 0.98, ...] },  // per-name daily iv30, most-recent last, for IV rank
  "etf_so": {                                        // semi ETF shares-outstanding snapshots (etf_flows inputs)
    "SMH": { "2026-07-17": {"so": 120391874, "nav": 568.67}, ... }
  },
  "big_orders": {                                    // published biggest-orders board, one entry per session
    "2026-07-31": {
      "rows": [ <BigOrder>, ... ],                   // same shape as data.json's, minus tv_symbol
      "capped": [ {"ticker": "QQQ", "shown": 3, "earned": 5} ]  // the cap disclosure, archived with it
    }
  }
}
```
Keep max 60 sessions; prune older. `iv_history` keeps max 60 values/name.
`etf_so` keeps max 60 sessions/fund; like the rest of history it is only
written when the market is not closed (forced weekend runs must not create
phantom flow sessions).

`big_orders` keeps max 60 sessions and is **archived deliberately, not
incidentally**: FLOW % shipped display-only with nothing stored but aggregates,
and when its accuracy was finally questioned not one historical day could be
reconstructed (see `market-data/results/flow_accuracy_2026-07.md`). Storing the
board makes "did the loudest contract of the day lead price?" answerable after
~30 sessions instead of unanswerable forever. Later cycles in a session
OVERWRITE that session's row — the day total is cumulative, so the last cycle
of the day is the complete one.
On each cycle: reload history, update today's row (net_flow, sum_oi, iv30, direction,
swing side vol/OI; tilt_*_prem ACCUMULATE across the day's cycles rather than being
overwritten), set first_board_* only if not already set today, recompute
persist/flow_5d/flow_5d_pct/oi_build/oi_confirm/iv_rank.

`fetcher/.prev_cycle.json` (job-local, gitignored, NOT part of the data branch):
`{"session": "2026-07-18", "flows": {ticker: net_flow}, "vols": {ticker: {occ: cum_volume}}}`.
flows drives the firing accel check; vols is the per-contract baseline for the
aggressor-tilt volume deltas (same session only — after a workflow restart the
first cycle contributes no tilt, by design). Legacy flat {ticker: net_flow}
files are still readable.

`fetcher/.context_cache.json` (job-local, gitignored, NOT part of the data
branch — same pattern as `.prev_cycle.json` above, deliberately kept as a
SEPARATE file so the context layer's read/write lifecycle inside one
`run_cycle` can never clobber build_snapshot's own prev-cycle write, or vice
versa):
```json
{
  "context_fetched_at": "2026-08-15T14:32:00Z",
  "bars_built_date": "2026-08-15",
  "bars_sig": "v3-2y-vol",
  "avg_move": {"MU": 3.45},
  "brief": {"...": "..."},
  "fed_odds": {"...": "..."},
  "catalysts": [ "..." ],
  "news": {"items": [], "rotation_banner": false},
  "desk_private": null
}
```
Drives two independent gates: the vault/econ/news fetch runs only when
`context_fetched_at` is missing or >55 minutes stale; the Yahoo bars fetch
runs when EITHER `bars_built_date` differs from today's session date OR
`bars_sig` differs from `context.BARS_BUILD_SIG` (added 2026-08-15, wave 3).
The signature half exists so a same-day code deploy that changes
`bars.json`'s shape (e.g. the v2 -> v3 volume/2y upgrade) forces an immediate
rebuild instead of matching on date alone and serving the OLD shape,
unchanged, until midnight. `brief`/`catalysts`/`news`/`desk_private`/`fed_odds` hold the
LAST successfully fetched values (not just gate metadata) so data.json's
fields keep publishing on the ~50 cycles/day that skip the hourly fetch,
instead of flickering in and out every hour; `avg_move` does the same job for
`facts.*.avg_move` across the cycles that skip the daily bars rebuild.
Fail-soft: a missing or corrupt file reads as "never fetched, never built,
never signed" — worst case one extra fetch/rebuild that cycle, never a crash.

## Symbol hygiene (fetcher)
Skip TV tickers containing `/`, `.`, `-` (preferred shares, warrants, units).
Root for OCC = the plain ticker (strip exchange prefix). Skip CBOE 404s.

## TRACK_ONLY (added 2026-08-15)
`build_snapshot.TRACK_ONLY` (`SKHX`, `NRGU`, `OILU`, `STLL`, `AAOG`) names are
full members of `PINNED` — they get quotes, `facts`, `bars.json` rows, and
`fund/{SYM}.json` sidecars exactly like every other pinned name — but
`select_candidates()` deliberately excludes them from CBOE chain fetches, so
they can never appear on the `conviction` or `swing` boards. See
`fetcher/build_snapshot.py`'s WATCHLIST comments for why each one is here
(a confirmed ghost/thin chain or a confirmed 403 with no listed options at
all, live-verified 2026-08-15).
