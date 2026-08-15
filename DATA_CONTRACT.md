# data.json / history.json / bars.json contract (authoritative — builders #1 and #2 both obey this)

The fetcher writes `data.json` and `history.json` to the `data` branch. The
frontend reads `data.json` only (history is internal to the fetcher). All
numbers are plain JSON numbers; missing/unknown values are `null` (never a
string sentinel). All strings are already plain (frontend still escapes on render).

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
    "funds": [                        // fixed order: SMH, SOXX, SOXL, SOXS, DRAM; a fund with no data this cycle is omitted
      {
        "ticker": "SMH",
        "flow_1d": -123456789.0,      // (shares outstanding this session - previous session) x NAV, signed $;
                                      // null until 2 sessions of SO history exist ("collecting"), and also
                                      // null when split_suppressed is true (see below)
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
  "context_updated_at": "2026-08-15T14:32:00Z"   // OPTIONAL — see note below
}
```

> **All six keys above are OPTIONAL and were added in the context-layer build
> (2026-08).** Absent on old snapshots and the site renders nothing for a
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
>   "source": "tv_calendar"           // "econ_calendar" | "tv_calendar" | "tv_earnings"
>                                     // | "memory_events" | "market_calendar"
> }
> ```
>
> **`news`** — up to 20 items total (not per ticker) across the pinned
> universe, newest first, pulled from TradingView's per-symbol news endpoint.
> `rotation_banner` is true when at least 2 of the scanned titles carry
> rotation/derisking language — the identical keyword list the morning brief's
> headline scan uses (`market-data/morning-report/sections/headlines.py`,
> `ROTATION_KEYWORDS`), copied into `fetcher/context.py` with a comment naming
> that source so the two lists can't silently drift apart. Display only.
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
>   "avg_move": 3.45         // mean(|daily % change|) over the last 20 closes in
>                            // bars.json, 2dp. Populated only after bars.json has
>                            // built at least once for this ticker; recomputed once
>                            // per day alongside the bars rebuild (see bars.json
>                            // below) and carried forward on the other ~50 cycles/day
>                            // via fetcher/.context_cache.json — a deliberately
>                            // day-stale reading, not a live one.
> }
> ```
>
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

A sidecar file for the pinned universe's daily close history, written in the
same publish step `loop.py` already uses for data.json/history.json —
`loop.py`'s `git add -A` over `OUT_DIR` picks up any new file there, so
shipping this required no `loop.py` change. Built **at most once per calendar
day** (see `fetcher/.context_cache.json` below): it is daily-bar history, so
refetching it every ~7-minute cycle would be pure waste against Yahoo for no
benefit.

```json
{
  "built": "2026-08-15",
  "bars": {
    "MU": [113.46, 114.02, "...", 971.66]
  }
}
```

- `built` — session date (`YYYY-MM-DD`) this file was last (re)built.
- `bars` — per pinned ticker (`build_snapshot.PINNED`), up to 252 daily
  closes, **oldest first**, rounded 2dp. Source: Yahoo's v8 chart API
  (`query1.finance.yahoo.com/v8/finance/chart/<SYM>?range=1y&interval=1d`). A
  ticker whose fetch failed is simply absent from `bars` — fail-soft, never
  zero-filled or backfilled from a stale value.

`facts.*.avg_move` (see above) is derived from this same fetch — mean of
`abs(daily % change)` over each ticker's last 20 closes — but that reading is
published in `data.json`'s `facts`, not duplicated here.

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
  "avg_move": {"MU": 3.45},
  "brief": {"...": "..."},
  "catalysts": [ "..." ],
  "news": {"items": [], "rotation_banner": false},
  "desk_private": null
}
```
Drives two independent gates: the vault/econ/news fetch runs only when
`context_fetched_at` is missing or >55 minutes stale; the Yahoo bars fetch
runs only when `bars_built_date` differs from today's session date.
`brief`/`catalysts`/`news`/`desk_private` hold the LAST successfully fetched
values (not just gate metadata) so data.json's fields keep publishing on the
~50 cycles/day that skip the hourly fetch, instead of flickering in and out
every hour; `avg_move` does the same job for `facts.*.avg_move` across the
cycles that skip the daily bars rebuild. Fail-soft: a missing or corrupt file
reads as "never fetched, never built" — worst case one extra fetch that
cycle, never a crash.

## Symbol hygiene (fetcher)
Skip TV tickers containing `/`, `.`, `-` (preferred shares, warrants, units).
Root for OCC = the plain ticker (strip exchange prefix). Skip CBOE 404s.
