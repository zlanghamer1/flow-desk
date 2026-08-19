# CLAUDE.md — direction for Claude sessions working on flow-desk

## What this is
Flow Desk is a personal options-flow dashboard: a static GitHub Pages site
(`index.html`) plus a GitHub Actions loop (`fetcher/`) that pulls free CBOE +
TradingView data, scores it onto two boards, and publishes `data.json` +
`history.json` to the `data` branch, which the site reads live.

## Doc authority (read before changing behavior)
- **DATA_CONTRACT.md** — authoritative for the `data.json` / `history.json`
  shape. Change a field here first, then match the code and the site.
- **README.md** — the canonical user-facing, plain-English truth. Keep its voice.
- **DEPLOY.md** — ops only (deploy method, loop lifecycle).

## Model-role convention for work on this repo
- **Fable** — architect; rules on scope and gives final approval.
- **Opus** — directs traffic; synthesizes reviews into build specs.
- **Sonnet** — builds (writes the code and docs).
- **Haiku** — mechanical grunt work.

## Hard guardrails
- **Never** push the `data` branch by hand — the loop force-pushes it every
  cycle; a manual push will be clobbered or will fight the loop.
- **Never** flip Settings → Pages to "GitHub Actions" mode. Branch mode from
  `gh-pages` is intentional (see DEPLOY.md).
- **Never** re-add the deliberately-excluded tickers — BESIY, IFNNY, SPX,
  VIX, SPMO — without first reading the exclusion note in
  `fetcher/build_snapshot.py`. (NRGU and WTI were reinstated 2026-08-15 by
  Zach's full TV-list ruling — NRGU is TRACK_ONLY, and WTI is W&T Offshore
  equity, not crude; both cases are documented in that same note.)
- Keep `index.html`'s `TIPS` text in sync with `build_snapshot.py` scoring
  whenever weights change — the two describe the same methodology and must not
  drift.
- **Same rule ACROSS REPOS for the Fed-hike odds (added 2026-08-18):** the
  grading thresholds live in both `fetcher/context.py` (`FED_HIKE_*`,
  `POLY_*`) and ClaudeVault's `market-data/morning-report/macro_backdrop.py`
  (`FED_HIKE_*`). Two repos, two CI runs, one methodology — move a number in
  one and move it in the other in the same change, or the desk and the Morning
  Brief will disagree about what counts as a loud day. The `grade`/`alarm`
  fields are computed in the fetcher, never in the page; don't re-derive
  thresholds in JavaScript.
- **Don't remove the split repair in `fetcher/context.py`, and don't trust
  Yahoo's split events to replace it.** Yahoo served SOXS's pre-2026-05-26
  history 15x too high and its own declared splits (1:20 on 2026-03-05, 1:10
  on 2026-07-15) match neither that break's date nor its factor. The repair is
  data-driven (a bar that OPENS 2.5x+ from the previous close) and its
  threshold is set from the live universe: the only other outsized overnight
  gaps in 69 tickers are NBIS/BE/APLD at ~0.65, all real news. Loosening the
  threshold would rewrite a real gap into a fake split. `fetcher/test_split_repair.py`
  pins both directions.
- Forced test runs off-hours are fine for `data.json`, but must **not** create
  weekend/closed history sessions. `build_snapshot.run_cycle` guards this
  (`write_history = market_state != "closed"`) — do not remove that guard.

## Guardrails added with the 2026-08-19 trading-platform redesign
- **The chart engine is vendored TradingView Lightweight Charts, pinned at
  v5.2.1** (`vendor/lightweight-charts.standalone.production.js`,
  Apache-2.0). The in-chart attribution logo (`layout.attributionLogo`) and
  the footer credit are license conditions — never remove either. `pages.yml`
  ships `vendor/` together with `index.html`; never publish one without the
  other.
- **Auto-TA is display-only.** The trend-line geometry is a port of the
  vault's `scripts/trendline_break_scan.py` constants (`TA_PIVOT_K`,
  `TA_MIN_SPAN`, `TA_TOUCH_TOL`, `TA_CONTAIN_TOL`). It draws lines; it never
  scores, signals, or feeds an engine. Keep it that way.
- **The page never widens the server universe.** Custom watchlist adds and
  hidden pinned names live in `localStorage` (`desk.wl.custom`,
  `desk.wl.hidden`), per browser, disclosed in the UI. Boards, `bars.json`,
  `facts`, and `fund/` sidecars follow `build_snapshot.PINNED` only.
- **TradingView's chart WEBSOCKET can never be called from this site — do not
  try it again.** `data.tradingview.com` enforces an exact-host allowlist on
  the `Origin` header. Measured 2026-08-19 with byte-identical handshakes
  differing only in Origin: `https://www.tradingview.com`,
  `https://s.tradingview.com` and `https://data.tradingview.com` get `101
  Switching Protocols`; `https://zlanghamer1.github.io`, `https://example.com`
  and no-Origin get `403 Forbidden` from `Server: tv`. `Origin` is a forbidden
  header name, so page JavaScript cannot set it and the `WebSocket`
  constructor takes no header options. A python probe "proving" it works is
  almost certainly sending websocket-client's default
  `Origin: https://data.tradingview.com` — an allowlisted value. The scanner
  host is different: it reflects any Origin, which is why quotes, search and
  fundamentals work from the browser.
- **Ad-hoc bar history comes from stockanalysis.com** (`adhocEnsureDaily`):
  `https://stockanalysis.com/api/symbol/s/{sym}/history?range=5Y`, plain GET,
  `access-control-allow-origin: *`, keyless. Send NO custom headers (any one
  forces a preflight). Rows arrive NEWEST FIRST — reverse them. `range=2Y`
  silently returns one year with HTTP 200; only 3M/6M/YTD/1Y/5Y/10Y are
  honored. No browser-readable intraday source exists for off-desk names, so
  15m/1H/4H stay a tracked-names feature and the stage says so.
- **The heatmap's S&P 500 and Nasdaq 100 universes come from the scanner's
  `symbolset` filter live** (`SYML:SP;SPX`, `SYML:NASDAQ;NDX`) — no baked
  constituent list to go stale. It refreshes only while visible and states
  the 15-minute delay in its footer.
- **Position Guard was removed 2026-08-19 at Zach's direction.** The
  `desk_private` blob still arrives in `data.json` and the page ignores it.
  Do not resurrect the panel without his explicit ask; the vault's
  trade-stops engine and the Morning Brief guard section are unaffected.

## Guardrails added by the 2026-08-19 review round
- **STOCK PRICES ARE 15-MINUTE DELAYED. Never call them live.** The scanner
  reports `update_mode: "delayed_streaming_900"` — 900 seconds — for every
  symbol the desk polls, and a same-instant comparison against a real-time
  feed measured 11-15 minutes of lag on SPY, MU, CRWD and NVDA (2026-08-19).
  The 30-second poll is how often the page RE-READS a delayed print, not how
  fresh the print is. The page said "live" for weeks before this was
  measured. If a keyless real-time source is ever found, that is a separate
  change with its own measurement — do not relabel on a hunch.
- **A source line names what actually supplied the data.** `stageSourceLine`
  reads the real state — `barsRaw`, `ADHOC_BARS`, `INTRA_CACHE`,
  `fund.source` — never "does an object exist". Branching on truthiness told
  43 of 50 tracked names they were "outside the desk universe".
- **The price layer must survive a data.json outage.** `refreshLiveUI` is two
  halves: prices always render, boards need the snapshot. A frozen price next
  to a ticking clock is the failure the "prices as of" stamp exists to catch.
- **Chart geometry is authored for the width it renders at.** SVG text scales
  with the viewBox, so a fixed font-size lands anywhere from 5px to 16px.
  `renderGrowth` picks its viewBox from `window.innerWidth`, `axisChartSVG`
  measures its own left gutter from the widest formatted tick, and a
  width-class change re-renders the open tab.
- **One company, one bar.** TradingView lists a foreign issuer's ordinary
  line and its ADR as separate tickers with the same fundamentals. Peer sets
  dedupe by `issuerKey(description)` and take primary US listings only.
- **A peer must be comparable in size.** Peers rank by closeness in market
  cap, preferring inside `PEER_CAP_BAND` (5x either way). When nothing is in
  band the set still fills and the note names what sits outside it.
- **The "peer median" excludes the focused company**, in the dashed line and
  in the caption. Including it put the reference through the subject's own
  bar.
- **A missing reading is never an inflow, a zero, or a green pill.** Sector
  rows with nothing published render a neutral dot, a dimmed row, and sort to
  the bottom in either direction.
- **Every board prints its own "as of" unconditionally.** The stale badge is
  gated to 08:15-15:00 CT, so gating the stamp on it left the data undated
  exactly when it was oldest.

## Decision history
Lives in the ClaudeVault repo under `market-data/flow-desk/`.
