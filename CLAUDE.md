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
- **Ad-hoc bar history rides TradingView's chart websocket from the browser**
  (`tvwsFetchBars`, same protocol as the vault's `scripts/fetch_tv.py`). It
  is an unofficial endpoint: every use must fail soft to "quotes and
  fundamentals still work", and nothing scheduled may depend on it.
- **The heatmap's S&P 500 and Nasdaq 100 universes come from the scanner's
  `symbolset` filter live** (`SYML:SP;SPX`, `SYML:NASDAQ;NDX`) — no baked
  constituent list to go stale. It refreshes only while visible and states
  the 15-minute delay in its footer.
- **Position Guard was removed 2026-08-19 at Zach's direction.** The
  `desk_private` blob still arrives in `data.json` and the page ignores it.
  Do not resurrect the panel without his explicit ask; the vault's
  trade-stops engine and the Morning Brief guard section are unaffected.

## Decision history
Lives in the ClaudeVault repo under `market-data/flow-desk/`.
