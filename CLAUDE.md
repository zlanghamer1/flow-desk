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
  symbol the desk polls, and cross-correlating 30 scanner samples against a
  real-time feed puts the lag at 16 minutes on SPY, MU, CRWD and NVDA alike
  (2026-08-19; MU's mean absolute error runs 3.85 at lag 0, 0.37 at lag 15,
  0.64 at lag 20 — a clean minimum, not a coincidence). `rtc` is NOT fresher
  than `close`; both land on the same 16-minute shift. The 30-second poll is
  how often the page RE-READS a delayed print, not how fresh the print is.
  The page said "live" for weeks before this was measured. If a keyless real-time source is ever found, that is a separate
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

## Guardrails added by the second review round (same day)
- **A responsive rule that rescues the narrow case gets checked at the wide
  one.** The tape's 4x2 grid started at 1160px, so the index labels were
  clipped at every desktop width from 1240 to 1920 while the phone showed
  them in full. The rail wrapped at 900px and forced a horizontal page scroll
  from 901 to 1060. Measure every width, not the two you designed for.
- **A header carrying live text holds a fixed height.** `.stagehead .ohlc`
  reserves 15px (30px at <=640px) whether or not the crosshair is over a bar.
  Without it the line wrapped and unwrapped as the cursor moved and the whole
  chart jittered.
- **Two numbers describing the same thing on one screen must agree.** The
  Conviction footer counted score-60+ names and firing names together and
  called the sum "score 60+", contradicting the Morning Brief tile. Different
  counting rules get their own sentence.
- **A feed that fails keeps its slot.** A macro tile with no quote renders an
  em-dash and "no quote"; sector rotation, ETF flows, tagged headlines and
  the ticker each print a one-line reason instead of hiding. `hidden` is for
  a payload the desk never carries, not for one that came back empty.
- **A grade says how many inputs it had.** `macro_backdrop.py` attempts seven
  readings and ships the ones that resolve, so the panel prints a chip for
  each missing reading and "graded on 4 of 7". `BACKDROP_ALL` in index.html
  is that list; keep it in step with the components in macro_backdrop.py.
- **Contrast is picked, not assumed.** `heatTextColor` falls back to pure
  black or white whenever both themed inks land under 4.5:1, choosing the
  side on the pure contrasts. Tile ink bottomed out at 3.77:1 before this.
- **A tile too small to label is too small to be a keyboard stop.** Heatmap
  tiles under 24px in either dimension keep their click and their tooltip but
  leave the tab order and the a11y tree.
- **A clamp above the tallest bar is not a clamp.** `peerBarsSVG` nulls it
  and the caption prints the real ratio, so a genuinely 24:1 spread reads as
  data rather than a rendering fault.
- **A formatter must keep its own chart's values apart.** `peerFmtFor` adds
  decimals until no two distinct values print the same label — PEG showed MU
  0.026 and SKHY 0.034 as "0.03" under a caption ranking one above the other.
- **One chart can hold two data vintages.** Desk names come from the morning
  snapshot, searched peers from the scanner seconds ago. `vintageNote` says
  which rows are which.

## Guardrails added by the 2026-08-20 review round

- **A view that changes symbol clears its data first.** `stageShow` empties
  `STAGE.rows`, `dates`, `times` and the marker maps before it repaints, so a
  header can never sit over the previous name's bar. Any panel that paints
  from cached arrays and refills them asynchronously owes the same reset.
- **Pre-market, the regular-session columns are yesterday's.** `rtc`, `open`,
  `high`, `low` and `change` all still describe the previous session before
  the bell. Only `premarket_close` and `premarket_change` describe the new
  day. A name with no pre-market print carries a PREV tag, drops out of the
  hot test, and sorts to the bottom of a list headed by today's move.
- **A 200 that updated nothing is a failed request.** The scanner answers 200
  with an empty `data` array under rate limiting. Both polls count that as a
  miss rather than stamping a fresh timestamp over frozen prices.
- **Every feed needs its own staleness signal.** The page banner watches the
  equity poll only; the macro tape keeps its own miss count and prints FROZEN
  on its tiles. A second feed is a second thing that can die quietly.
- **A verdict computed from price is recomputed when price moves.** Trend-line
  status, distance and side are re-derived on every caption draw, and the drawn
  lines are recoloured to match. A conclusion cached at open is a conclusion
  about a market that has moved.
- **A claim about a stretch of bars is checked against those bars.** "Price has
  stayed above it since" counts the closes after the break, and says what it
  counted, rather than testing the last one and generalising.
- **A flag that marks fabricated data must be read.** `syntheticReal` existed
  for three rounds before anything consumed it. A bracketed today candle now
  prints CLOSE ONLY.
- **The market calendar is not a weekday test.** `isTradingDay` consults the
  holiday and half-day tables, preferring bars.json v4's session list where it
  is published. A green OPEN lamp on Thanksgiving is worse than no lamp.
- **A countdown is aged against the snapshot it came from.** `earnDaysNow`
  subtracts the sessions elapsed since `session_date`; a countdown measured
  live carries `earn_live` and is left alone.
- **One rule, one helper, every surface.** The $100K flow-% floor lived inline
  in the board and was missing from the chart tab. Any rule stated in a
  tooltip has to be enforced everywhere the number appears.
- **A resample buckets by session, never by counting bars.** `slot4H` keys on
  pre-market / 08:30-12:30 / 12:30-15:00 / post, so the opening auction is
  never folded into a pre-market bucket and dimmed.
- **An async render captures the state it was called for.** The heatmap
  captures its universe and drops if the map has moved on; in-flight callers
  share one promise instead of being told the scanner is unreachable.
- **A clamp anchored on "the second largest" needs three values.** With two,
  the second largest is the smaller one — a 106:1 gap drew as 1.6:1.
- **A hover target has to be hittable.** Chart values live on full-height
  bands per period, not on 2.6-pixel circles: a circle is not a touch target.
- **A network failure is never cached as a fact about the world.** A failed
  peer scan says the scan did not answer, and is not written to the cache.

## Guardrails added 2026-08-21 (5-metric framework, Auto-TA, mobile watchlist)

- **The 5-metric scoring framework never uses ClaudeVault's per-ticker
  analysis numbers.** `market-data/results/desk_universe_framework_analysis_
  2026-08-21.md` and `watchlist_framework_analysis_2026-08-21.md` misidentify
  at least two tickers (NBIS as "NBT Bancorp / Specialty Biotech" — it is
  Nebius Group, an AI infrastructure company; CORZ as "Corzine / Specialized
  Mining" — it is Core Scientific) and score filters inconsistently against
  their own stated thresholds. They read as generated illustrative content,
  not a verified pull. Only the METHODOLOGY from
  `financial_metrics_backtest_extended_2026-08-21.md` is implemented, in
  `fetcher/context.py`'s `score_framework` — every number comes from a live
  vendor at fetch time, or the filter reads null. Never hardcode a specific
  ticker's verdict from either analysis file.
- **A filter with no data is null, never a guessed pass or fail — and the
  verdict says so.** Two of the five filters (forward EPS revision, analyst
  velocity) need 3-6 months of accumulated weekly consensus history that
  does not exist on a fresh deployment. The verdict reads `"BUILDING"`
  (`FRAMEWORK_MIN_EVALUATED` = 3) rather than a confident tier computed from
  a minority of the five.
- **The weekly consensus snapshot lives on the `data` branch
  (`consensus_history.json`), never in `fetcher/.context_cache.json`.** The
  job-local cache is gitignored and does not survive a redispatch or a new
  day's job (each re-clones `data` fresh — see DEPLOY.md); this needs to
  survive months of those. Same publish mechanism as `history.json`, same
  `write_history` guard against phantom weekend snapshots.
- **The framework verdict is display-only and never feeds a board score.**
  `facts.<TICKER>.framework` rides the same "reference data" posture as
  `facts.op_margin`/`facts.short_pct` — it does not touch
  `conviction_score`/`swing_score`, per the framework doc's own explicit
  instruction not to feed it into scoring without separate testing.
- **`facts.eps_ntm`/`.rev_ntm`'s TV scanner column names were live-verified,
  not assumed.** `eps_growth_next_5y` and `revenue_growth_next_year` both
  return null (not real columns);
  `earnings_per_share_forecast_next_fy`/`revenue_forecast_next_fy` are real —
  confirmed by the FY/FQ ratio landing near 4x, the shape a genuine annual
  vs. quarterly consensus pair should have. Deliberately the ANNUAL estimate
  for both the 6-month and 3-month lookback filters, never the quarterly
  one — the quarterly estimate rolls over to a new quarter every time one
  reports, which would compare two different quarters under one "velocity"
  label.
- **EMA and RSI overlays were removed from the chart** (Zach's call). The
  Fundamentals grid still shows a daily RSI(14) snapshot from the scanner —
  a different, unrelated reading; do not conflate the two when touching
  either.
- **A two-line shape label is read off the SAME fitted geometry, never a
  separate pattern detector.** `taShapeLabel` classifies slope and
  convergence from the resistance/support pair `taFitLine` already
  produced. Its flag-pole threshold (`TA_FLAG_MIN_BARS`) is a first-pass
  heuristic, unlike the ported `TA_TOUCH_TOL`/`TA_CONTAIN_TOL`-class
  constants above, which carry live-measurement comments — treat it with the
  same scrutiny before trusting its exact numbers.
- **S/R line color and the caption's position word are computed by ONE
  function (`taSrSide`), never two.** A level can never be drawn red on the
  chart while the sentence under it says "under" — the class of bug several
  earlier rounds' guardrails exist to prevent.
- **The mobile watchlist order was reversed.** The 2026-08-18 ruling put the
  Morning Brief verdict first on a phone; Zach's follow-up puts the
  watchlist first instead (`.wl{order:1}`), and defaults it EXPANDED rather
  than collapsed behind a tap — "toward the top for easier functionality"
  meant visible, not just first in the DOM. If a future ruling reverses this
  again, update the dated CSS comment in the `@media (max-width:900px)`
  block, not just the `order` values.

## Guardrails added 2026-08-21, second round (unusual options activity, Bollinger Bands)

- **`opt_rvol`'s baseline must never include today's own reading.**
  `compute_opt_rvol` is called with `vol_history.get(ticker, [])` snapshotted
  BEFORE today's `sum_vol_0_7` is appended — appending first would let a
  genuine outlier dilute the very average it's being measured against.
  `UOA_HOT_MULT` (3.0) and `ACTIVITY_FLAT_PCT` (0.3) are first-pass
  heuristics, not backtested, same disclosure class as the shape-detector's
  flag-pole threshold above.
- **HEDGING is a heuristic label with one honest use, not a catch-all.** It
  fires ONLY for put-heavy flow while the stock is not falling — the one
  signature free, sampled, aggregated CBOE data can support (see
  `options_activity_tag`'s docstring). A put-heavy day where the stock IS
  falling is BEARISH. Call-heavy flow disagreeing with price reads MIXED,
  never a mirrored "hedging" claim — this data cannot distinguish a bought
  call from a written one (covered-call income vs. a directional bet), so
  don't add that mirror later without a real basis for it.
- **`opt_rvol`/`activity_tag`/`unusual_activity` are display-only**, same
  posture as `flow_pct` and the aggressor tilt — they must never be wired
  into `conviction_score`/`swing_score` without the same backtesting rigor
  this file demands everywhere else scoring is discussed.
- **Bollinger Bands are computed on the FULL price series (`rows`), not the
  trend/S-R fitters' windowed `win`.** Matches the always-on SMA20/50/200
  lines' behavior (and the old EMA's, before it was removed) — a band that
  changes shape when you switch from 1M to 1Y would contradict what a trader
  expects from Bollinger Bands specifically.
- **The on-chart bands and the rail-wide `bollingerOf(sym)` scanner are two
  separate call sites, not one shared function** — the chart overlay reads
  `STAGE.rows` (the open chart's data), the rail scanner reads `barsOf(sym)`/
  `ADHOC_BARS` (works for any rail ticker without opening its chart, mirror
  of how `hotOf`/`statsOf` already work). Both share the same underlying
  `rollMA`/`rollStd` math and the same `BB_PERIOD`/`BB_MULT` constants — if
  either ever needs to change, change it once for both, or the chart and the
  rail panel will disagree about the same ticker.
- **A Bollinger cross reads "volatility," never "bullish" or "bearish."**
  `renderBBCrosses` deliberately colors both "above upper" and "below lower"
  the same (`--bb` purple) — a band cross can mean continuation or reversion
  depending on the reader's own view, and painting one direction green and
  the other red would claim a directional verdict this indicator does not
  support. Don't add that coloring later without a real basis for it.
- **The Band crosses panel hides entirely when nothing has crossed**, unlike
  the MOVERS panel above it which always shows and says "none yet." A cross
  is a genuinely occasional event; an empty box every single day would be
  clutter MOVERS' near-daily "something is hot" reading isn't. This is a
  deliberate asymmetry with MOVERS, not an inconsistency to "fix."
- **This is the first client-side alerting/notification mechanism in this
  codebase.** No browser Notification API, no permission flow, no
  persistence — it is a stateless, recomputed-every-poll panel, the same
  posture as the existing MOVERS box. Before adding push notifications or
  any persisted alert state later, read this note: that would be new
  architecture, not an extension of what exists.

## Decision history
Lives in the ClaudeVault repo under `market-data/flow-desk/`.
