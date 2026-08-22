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

## Guardrails added 2026-08-21, round-6 fix pass (26 findings, all 9 sections)

Round 6 of the nine-section review confirmed 26 findings (see
`docs/OPEN_ITEMS.md`'s history for the full list); this pass fixed all 26.
The non-obvious decisions from that pass:

- **A cached session-derived flag has to track the session, not just the
  moment it was set.** `STAGE.premarketBar` was set once at full render and
  never revisited — `stageLivePoke` now flips it off the moment
  `priceSessionNow()` leaves premarket, which also fixes the "pre-market"
  caption that read the same flag. The daily bars cache got the same
  treatment: `BARS_FETCHED_KEY` (a CT calendar-day string, not a millisecond
  TTL — `bars.json` only changes once a day) drives both `ensureBars()`'s
  memoization and a `tick()`-driven re-fetch, so a tab left open across
  midnight picks up the new day without the user touching anything.
- **A log-scale axis floor of exactly 0 is not "safe" — it's a squashing
  bug.** `log10(price+1e-4)` gives the 0-to-1 span as much room as four full
  decades above 1, so `autoscaleInfoProvider`'s floor is `pr.minValue/2`
  when `STAGE.log` is true, never a hardcoded epsilon or 0. Linear scale
  keeps the old 0 floor — the squashing problem is log-specific.
- **S/R price lines carry their own level object now**
  (`STAGE.srLines = [{level, line}, ...]`, not bare price-line handles), so
  `stageTAPoke()` can re-derive each line's color from `taSrSide` on every
  poll, the same live re-grade the caption already got. `taShapeLabel`'s
  pattern-name guard now excludes `BREAKOUT` and `EXTENDED`, not just
  `FAILED` — a status frozen at fit time is not the same claim as "this
  pattern's boundary still holds" — and `stageTAPoke` blanks `summary.shape`
  the moment either line's live regrade stops holding.
- **Two matched "attempted and failed" trackers, same shape, same reason:**
  `ADHOC_FACTS_FAILED` (peers, `adhocEnsureFacts`) and `FUND_CACHE_FAILED`
  (financials/peers, `ensureFund`) both distinguish "this fetch genuinely
  failed" from "never attempted" — the two read identically before, so a
  transient scanner or sidecar hiccup looked exactly like "still loading"
  forever. Cleared on any attempt that resolves, success or a genuine empty
  answer; never cleared on a thrown HTTP status or a rejected fetch.
- **`axisChartSVG` clamps both directions now** (`opts.clamp` for the
  ceiling, `opts.clampLo` for the floor), with a matching `↓` clip arrow next
  to the existing `↑`. `robustClampMag()` picks the clamp magnitude from the
  MEDIAN magnitude of the series (robust to the one runaway period), floored
  so an ordinary wide-swinging name never gets clipped. Bars get the same
  edge-pin-and-arrow treatment lines already had — a value outside the
  domain used to just draw past the plot into the axis padding.
- **One `loud` boolean for the Fed-hike card, computed once in
  `normalizeFedOdds`** (`alarm===true || grade==="HOSTILE"`), used by the
  rail chip's `bad` class, `fedAlarmHTML`'s banner gate, and
  `fedOddsHTML`'s card/numeral classes alike. Three separate call sites each
  deriving their own version of "is this loud" is exactly how the header
  chip, the banner and the numeral ended up disagreeing about one reading.
- **`big_orders_capped`'s "earned" now counts a ticker's rows across the
  WHOLE pool**, not a naive top-`BIG_ORDERS_CAP` slice by raw premium — the
  greedy per-ticker-capped merge backfills past that slice whenever an
  earlier ticker gets skipped for hitting its quota, so a ticker with zero
  rows in the naive slice could still lose a row to the cap and never appear
  in the disclosure. The gate is `shown==BIG_ORDERS_PER_TICKER AND
  earned>shown` — a ticker that simply never ranked onto the board at all
  (shown 0) is an ordinary miss on dollars, not a per-ticker cap to confess;
  `fetcher/test_big_orders.py`'s `_merge()` mirror was carrying the old,
  buggy logic and had to be fixed in step, or the test would keep passing
  against a copy of the bug instead of the fetcher's real code.
- **`liveStale(sym)`/the rail's STALE convention now covers three more
  surfaces**: the main tape (SPY/QQQ/DIA/IWM, via a small inline `frozen`
  check in `mainTileHTML` mirroring `macroTileHTML`'s existing FROZEN
  badge), the open chart's header price (`stageHeaderHTML`), and the
  fundamentals grid's Fwd P/E / Next earnings cells (`fundBuiltStaleDays()`,
  a DAY-based comparison of `fund.built` against `data.session_date` —
  deliberately not a reuse of `isStaleFlow`/`isStaleContext`, which compare
  a millisecond timestamp against `Date.now()` and are gated to trading
  hours, the wrong shape for a once-a-day sidecar build date).
- **The heatmap's 1D reading is now session-aware.** `HEAT_COLS` carries
  `premarket_change`/`postmarket_change`; pre-market, a tile's `chg["1D"]`
  swaps to the live pre-market print when one exists (tagged `PRE`) or keeps
  the prior day's figure explicitly tagged `PREV` (a new `.hm-tile.prev1d`
  hatch, vertical stripes to stay visually distinct from `.nodata`'s
  diagonal one) — mirroring the rail's own PRE/PREV convention, which the
  map had no equivalent of before. Separately, the no-data hatch itself was
  dead: the tile's inline style used the `background` shorthand, which resets
  `background-image` to `none` and silently defeated the `.nodata` CSS —
  fixed by switching the inline style to `background-color` (longhand).
- **`isLeveraged()`'s bare `bear` match needed the same digit guard `bull`
  already had** (`bear\s*\d`, not a bare `\bbear\b`) — Build-A-Bear
  Workshop (BBW) is a real toy retailer, not a leveraged wrapper.
- **`catIsAnchorByName`'s options-expiration exception is monthly/quarterly
  only now** — the separate bare `/options expiration/` catch-all matched
  `fetcher/context.py`'s literal "Weekly options expiration" (LOW
  importance) exactly as it matched the monthly/quarterly titles, so every
  weekly OpEx row bypassed the curation floor. Removed outright; the
  monthly/quarterly/quad/triple regex above it already covers both titles
  this exception exists for.

## Guardrails added 2026-08-22, round-7 fix pass (27 findings, all 9 sections)

Round 7 of the nine-section review confirmed 27 findings against the new
80-point bar (see `docs/OPEN_ITEMS.md` for the full list, scores, and the
methodology note on catching a schema-valid-but-empty review result); this
pass fixed all 27 the same day. Round 8, an independent re-review against
the fixed page, has not yet run — see `docs/OPEN_ITEMS.md`'s Open section.
The non-obvious decisions from this pass:

- **A trend line's role FLIPS on BREAKOUT and EXTENDED, never on RETEST or
  FAILED — one function, three call sites.** `taTrendFlipped(status)` is now
  the single source for the fit-time series color, `stageTAPoke`'s live
  recolor, and the caption's color/name in `stageTALegend`. Before this, all
  three independently checked `status==="BREAKOUT"` only, so an EXTENDED
  line (a confirmed, matured break — reachable only once price ran >12%
  past the line or the break is >12 sessions old, never a false positive)
  stayed drawn in its pre-break color while its own caption said the move
  was already made. Mirrors `taSrSide`'s existing one-function pattern for
  the horizontal S/R lines.
- **The on-chart Bollinger Bands now use completed closes only, same
  convention as the rail's `bollingerOf(sym)`.** `stageTA`'s BB block used
  to run over `STAGE.rows`, which includes the live-appended "today" candle
  — baked in once at full render and never recomputed, so it was
  simultaneously live-contaminated (disagreeing with `bollingerOf` for the
  same ticker at the same instant) and frozen (the code's own comment
  claimed "computed on settled bars," which was true of `.side` but not of
  the band's dollar levels themselves). Slicing off the live bar when
  `STAGE.synthetic` is true fixes both findings in the same change — the
  comment is now actually true, so no live recompute in `stageTAPoke` was
  needed.
- **The drawn SMA20/50/200 lines now recompute their own last point on every
  live poke**, inside `stageTAPoke`, from `STAGE.rows` (which `stageLivePoke`
  has already patched with the live close by the time TA poke runs). Before
  this, the lines only got new data from a full `stageRender`, while the
  adjacent legend text recomputed fresh every poll from `statsOf` — so the
  stated "+Y% vs it" and the true visual gap to the line could name two
  different values for any name that moved since the last full render.
- **The single S/R axis price badge is re-picked on every live poke, not
  just recolored.** `taSrBadgePick(lvls, lastPx)` — one function for fit
  time and every poke — returns which level is nearest price and which
  moving averages it would collide with; `STAGE.srLines` entries now carry
  `levelIdx`/`edge` so a wide band's near edge can be re-derived as price
  crosses the cluster, not just recolored. Previously `nearestIdx` was
  computed once at the fit and never revisited, so the badge could keep
  sitting on a level that used to be nearest and no longer is.
- **`wlIoApply` (bulk watchlist paste) now enriches every newly-listed
  symbol the same way `wlAdd` (single search-add) always has** —
  `adhocEnsureFacts`/`adhocEnsureDaily` for each entry in the resolved
  `list`, right after `adhocRegister`. The bulk path never called either,
  so a pasted ticker showed price and name only: no 52-week bar, no
  earnings countdown, and no way to ever trigger the hot badge or reach
  MOVERS, until the page was reloaded or the chart opened individually.
- **`adhocFillAvgMove(sym)` is now called from BOTH `adhocEnsureDaily` and
  `adhocEnsureFacts`'s success paths**, not just the daily path. The two
  fetches are deliberately still unchained and racing (wlAdd/wlIoApply fire
  them together), but before this only `adhocEnsureDaily`'s own callback
  attempted the avg_move write, gated on an ambient "does `ADHOC_FACTS[sym]`
  already exist" check rather than a real dependency — so if the plain GET
  to stockanalysis.com won the race, the write was silently skipped forever
  (`ADHOC_BARS[sym].D` already existed, so no later call ever retried).
  Whichever fetch settles SECOND now does the write, since only it can see
  both pieces.
- **`renderGrowth` now flags byte-identical revenue/EPS across back-to-back
  quarters as a probable duplicated vendor row**, alongside the existing
  missing-data/outlier checks — never silently dropped, since the desk
  cannot know which of two identical readings (if either) is the real one.
  CBRS's live sidecar carries exactly this (Q1/Q2 23 both 4,332,000 revenue
  and -0.907903 EPS to six decimals).
- **The shared tap-to-read chart readout (`#chartread`) now moves itself
  to sit under whichever chart was tapped**, via `insertAdjacentElement` on
  click, instead of staying fixed at the bottom of the whole tab. It is
  still the one aria-live node; only its DOM position changes per tap. Any
  chart wrapped in `.gchart` (Financials AND vs Peers both use it) benefits.
- **`.hm-tile b`/`span` get nowrap/ellipsis plus `max-width:100%`** — matching
  every other truncatable label in the file. Column-direction
  `align-items:center` does not stretch these children, so without an
  explicit width neither overflow rule had anything to fire against, and a
  5-letter ticker at the minimum label-showing tile size could clip to a
  DIFFERENT real, currently-listed symbol with no ellipsis to say it was cut.
- **`heatDeskTickers()` now filters by `wlHidden()`**, the same way the rail
  itself does. Hiding a pinned name pushes it onto `desk.wl.hidden` without
  touching `RAIL_GROUPS`, so the "Desk" heatmap kept rendering a hidden
  name's tile at full size and color with no note that it wasn't on the
  visible watchlist.
- **A `matchMedia('(prefers-color-scheme: light)')` change listener now
  clears `_heatRGB` and re-renders the heatmap**, guarded on no explicit
  `desk.theme` being stored (an explicit in-app choice already pins
  `dataset.theme` regardless of the OS). Before this, `_heatRGB` only
  invalidated on the explicit theme-button click, so a tab left open across
  an OS-scheduled light/dark switch kept mixing the old theme's `--up`/`--dn`
  hex with the new theme's neutral midpoint.
- **`peerStat(sym, key, peersOverride)` takes an optional resolved peer list
  now**, and `renderPeersInto`'s per-metric-chart loop passes `res.peers`
  instead of letting the function re-read the module-global `PEERS_CACHE`.
  `peersFor` only WRITES that cache when every curated peer resolves, so a
  curated set that only partially resolved on a given cycle drew a full
  chart from the `res` already in hand while every caption underneath it,
  reading the still-empty cache, said "too few peers to rank." Callers with
  no `res` in scope (`peerAnnotate`, from the Fundamentals grid) still fall
  back to the cache.
- **`inBand(c)` in `_peersByIndustry` returns `null` for "unknown" now,
  never `false`** — `false` is reserved for two KNOWN sizes that are
  genuinely more than 5× apart. With `myCap` null (common for a foreign
  issuer or thin OTC name the scanner hasn't backfilled), every candidate
  used to read `inBand()===false`, so the footer named every peer as
  size-mismatched with a specific, false numeric claim instead of saying
  the real reason: SYM's own cap is unknown.
- **The indexed-revenue-growth chart now appends a one-line reason** naming
  which peers lacked enough quarterly history, instead of disappearing with
  zero explanation whenever fewer than 2 series clear the 5-quarter minimum
  — the file's own "a failed feed keeps its slot" rule, which this was the
  one remaining exception to.
- **`fedAlarmHTML` now has three "why" phrasings, not two**, and reads the
  upstream `f.alarm` boolean rather than re-deriving the 40% ALARM threshold
  in JS (this file's own standing rule). The banner fires at the fetcher's
  25%-grade HOSTILE floor, well below the 40%/10pp ALARM thresholds
  README.md documented for it, so a 32%-with-no-jump reading used to print
  "near a coin flip" — now it prints "elevated enough to flag, short of a
  coin flip" unless `f.alarm` is actually true. README.md's own paragraph is
  corrected to match.
- **`catPassesCurated`'s memory-kind branch no longer requires a desk-ticker
  match on its own** — a desk-ticker memory row still passes unconditionally
  (unchanged), but everything else now gates on `importance` the same way
  the econ branch already does. Most memory events carry `ticker:null` BY
  DESIGN (non-US-ticker companies, index-wide events), so the ticker
  requirement had dropped 21 of 22 memory catalysts from the default
  curated view with no on-screen note that anything was dropped.
- **The news ticker's marquee track drops its duplicate copy under reduced
  motion.** The duplicate exists to loop the animation seamlessly and is
  `aria-hidden`, but reduced motion disables the animation and switches to
  manual horizontal scroll — so the hidden-from-screen-readers copy was
  still fully visible to scrolling, printing every headline twice
  back-to-back for the one audience the duplicate was never meant to reach.
- **The Biggest Orders "MOSTLY INTRINSIC" badge now computes intrinsic value
  against the fetcher snapshot's OWN spot (`o.spot`), not a live poll.**
  Crossing a live price against the contract's frozen ~7-minute-old "last"
  premium let the badge flicker on and off every 30 seconds purely from
  live/stale timing, with no actual change in the contract's real extrinsic
  value.
- **`contractLine` now caps displayed IV at `IV_DISPLAY_CAP_PCT` (300%)** and
  shows a dashed, tooltipped placeholder above it instead of the raw number
  — live examples were XLF 847%, AAOI 757%, XLV 559%, CORZ 511%, all 0DTE
  deep-ITM pricing artifacts (delta≈±1.0), not real implied vol. The
  function no longer wraps its whole return in one `esc()` call, since the
  capped-IV branch needs to return real markup (a tooltip span); every other
  piece was already safe to leave un-escaped a second time (expiry is
  pre-escaped, everything else is numeric/enum).
- **The Swing board now renders the same live price/±change block
  Conviction already builds**, from the identical `dispQuote(liveBySym(...))`
  call already in scope — it just never got rendered. SwingCard carries no
  `change_pct` snapshot fallback the way ConvictionCard does, so this one
  reads live-or-nothing rather than falling back to a stale snapshot figure.
- **DATA_CONTRACT.md's `etf_flows` note is corrected**, not the code: the
  code's always-show-a-reason behavior was already right (matches the "a
  feed that fails keeps its slot" convention every other panel follows) —
  the doc just never got updated when that behavior was written.
- **"Short % float" gets the same `fundStaleSub` staleness badge Fwd P/E and
  Next earnings already carry**, gated on `shortFromFund` (true only when
  the value actually came from the sidecar `fund` object, never from
  `facts.short_pct`, which the fetcher always sets null). `stageSourceLine`'s
  STALE tooltip is also corrected to name all three sidecar-sourced fields
  it warns about, not just two of the three it had just claimed came from
  that sidecar in the same sentence.
- **`_ratio_matches_split(ratio)` guards both consensus-EPS filters
  (forward EPS revision, analyst velocity) against an unadjusted split
  between two weekly snapshots.** Reuses the existing `SPLIT_RATIOS` /
  `SPLIT_SNAP_TOL` / `SPLIT_BREAK_MIN` constants already vetted for price-bar
  split repair (`_repair_split_breaks`) rather than inventing a new
  threshold or a new vendor field — `consensus_history.json`'s weekly
  `eps_ntm` snapshots carry no split adjustment of their own and there are
  no bars to repair at that layer, so this checks the ratio itself: a jump
  landing on a clean split factor (2, 3, 4, 5, 10, ...) AND outside the
  2.5x "ordinary move" band reads UNKNOWN instead of a real revision. Not
  yet observed live (only one week of consensus history exists), but the
  misfiring path was already live.
- **`_framework_verdict` now appends a `_BUILDING` suffix to a tier reached
  with fewer than all 5 filters resolved** (e.g. `ADD_BUILDING`), which the
  frontend's `stageFrameworkHTML` strips back off to get the base tier's
  label/color and adds a "(building)" qualifier instead. Before this,
  `passed=3` with 2 filters still UNKNOWN rendered byte-identical to
  `passed=3` with those same 2 filters genuinely FAILED — "ADD" either way,
  collapsing "clean record, still gathering data" into "mixed record,
  already failing." `fetcher/test_framework_score.py`'s verdict-tier
  parametrization had a `(3, 3, "ADD")` case that was pinning the OLD,
  ambiguous behavior; updated in step, same as round 6's `test_big_orders.py`
  fix — a test that mirrors buggy logic keeps passing against a copy of the
  bug instead of the fetcher's real code.

## Guardrails added 2026-08-22, round-8 fix pass (26 findings, all 9 sections)

Round 8 of the nine-section review confirmed 26 findings (see
`docs/OPEN_ITEMS.md` for the full list, scores, and a second occurrence of
the "schema pass is not a content pass" methodology note — this round's
Chart Stage reviewer returned the same placeholder-garbage failure round 7's
Auto-TA reviewer did); this pass fixed all 26 the same day. The non-obvious
decisions from this pass:

- **A synthetic "today" candle now checks `isTradingDay()`, not just
  premarket-vs-not.** `stageDailyData`'s two live-append branches and
  `seriesQuads`' weekly resample all built a full fabricated candle from a
  stale weekend/holiday scanner quote, tagged `syntheticReal=true` so none
  of the existing fabrication disclosures fired — exactly the class of bug
  the fetcher's `write_history` guard exists to prevent server-side, with
  no client-side counterpart until now. One underlying bug, confirmed
  independently by both the Chart Stage and Data honesty reviewers.
- **A new `isLastTradingDayOfWeek()` helper decides the weekly view's
  "closed" wording, not today's own intraday session state.** The 1W
  view's current (partial) candle used to read "closed" any weekday
  afternoon after the regular session ended, even on a Tuesday — asserting
  the week's bar was settled three days early.
- **Auto-TA's bar-count thresholds are now interval-scaled.**
  `TA_FRESH_BARS`/`TA_MIN_SPAN`/`TA_MIN_WIN_FOR_TREND` were tuned for daily
  bars; a new `TA_BARS_PER_DAY` map and
  `taBarScale()`/`taFreshBars()`/`taMinSpanScaled()`/`taMinWinForTrend()`
  convert them per active interval, so 1D and 1W no longer disagree about
  what "fresh" or "long enough" means for the same calendar stretch (live
  example: XLB).
- **S/R level captions state a %-distance now, reusing `taSrSide`'s own
  side determination rather than re-deriving it.** `TA_SR_MAX_DIST` permits
  a level up to 20% from spot; before this, a 19.3%-away band (AMAT) printed
  with the identical wording as a 1%-away one.
- **`liveStale(sym)` now gates the rail's own summary boxes, not just its
  individual rows.** MOVERS and the shopping list rendered `hotOf()`/
  `statsOf()` figures with no staleness check of their own, so a frozen
  quote could sit at the top of MOVERS with nothing marking it frozen —
  both boxes now append the same STALE tag the rows already carry.
- **`LEV_NAME_RE` now matches "short" + a major index name.** ProShares'
  plain (non-leveraged) inverse funds — SH, PSQ, DOG, MYY — are named
  "Short S&P500"/"Short QQQ"/etc., none of which contain "inverse", "ultra",
  or a leverage multiple, so they slipped past the shopping list's own
  advertised exclusion.
- **The shopping list now discloses its own 3-name cap**, mirroring MOVERS'
  existing "+N more — sort by hot" pattern with its own "+N more — sort by
  range" note. Before this, a broad day could push real candidates off the
  list with nothing on screen saying more existed.
- **The money and EPS financials charts get the same `robustClampMag`
  outlier clamp margins/YoY already had.** The clamp shipped in round 6 for
  two of the four chart types was never extended to the other two — live on
  LITE's EPS array and NBIS's FCF — so a single anomalous quarter could
  visually flatten the rest of either chart. `clampedAny`'s declaration
  moved earlier in `renderGrowth` so the money chart's clamp can flip it
  before margins/YoY get their turn; the shared caption note now says "one
  or more charts" instead of naming only margins/growth.
- **`.gwrap .chartread{grid-column:1/-1}` makes the tap-to-read readout
  span the grid row it lands in.** `#chartread` moves itself into whichever
  chart's `.gwrap` via `insertAdjacentElement`, but had no `grid-column` of
  its own, so it took only one 300px track at desktop widths instead of
  spanning the row.
- **The "vendor duplicated this row" caveat now requires revenue AND EPS to
  both match at the same index**, not EPS alone. ONTO's real, distinct
  Q2/Q3 24 quarters happened to round EPS to the same figure while revenue
  genuinely differed, and the EPS-only check flagged that as a duplicate.
- **The heatmap tooltip's market-cap fallback now says so explicitly**
  ("market cap (no dollar-volume reading today)") instead of keeping the
  "traded per day" wording that belongs only to the dollar-volume figure it
  replaced.
- **The heatmap's tile-count cap now diffs the sector set before and after
  slicing**, and names any sector that vanished entirely in the footer note.
  The cap previously ran before sector grouping, so a small-cap-heavy sector
  (Utilities, Real Estate) could sort entirely below the cutoff with only a
  generic "N smaller names left off" count — no sector-level disclosure.
- **`postmarket_change` (`d[13]`) is finally read.** Fetched into
  `HEAT_COLS` in the same round `premarket_change` was, for the identical
  reason, but nothing consumed it — after the bell a tile kept showing the
  regular-session close-to-close move with no equivalent to the rail's own
  AFT tag. After-hours, a tile's 1D reading now swaps to the live
  postmarket print (tagged POST), mirroring the existing PRE/PREV
  convention.
- **The indexed-revenue-growth note now names which peers, if any, are
  live-scanner lines rather than daily-sidecar ones.** The `sources` object
  distinguishing them was already computed; the printed note stayed generic
  regardless of what actually got used, so a chart mixing a once-daily
  sidecar line with a seconds-old scanner line said nothing about which was
  which.
- **`_tickerRank()` is wired into `ingest()`'s collision branch now**,
  tracked via a new `seenIssuerAt` map from issuer key to `cands[]` index so
  a better-ranked line (a plain ticker over a `.`-suffixed dual listing) can
  replace an already-accepted one for the same issuer. It existed since an
  earlier round and was never called — the `/`-suffix half of its job was
  already redundant with an existing filter, but the `.`-suffix half had no
  coverage at all.
- **`renderPeersInto`'s post-fund-load step patches only PEG's chart node in
  place now, via `outerHTML`, instead of a full recursive re-render.** PEG
  is the one PEER_METRICS entry that needs `FUND_CACHE` (via `derivedPeg`);
  every other metric already renders its final value on first paint. The
  old code recursed into `renderPeersInto` a second time regardless of that,
  tearing down and rebuilding the whole section — every metric, the key,
  the source note — a second time just to refresh PEG, discarding any
  tap-to-read state a trader had open on some unrelated chart. The per-
  metric chart builder is now `oneMetricChartHTML()`, callable standalone;
  the recursive call and the now-unused `isRedraw` parameter are gone.
- **`fedLegPct()` is the one function computing the Fed-odds card's
  largest-remainder rounding, used by `normalizeFedOdds`'s new `hikePct`
  field, the card headline, the rail chip, and the FED HIKE RISK banner
  alike.** The headline used to round independently with plain
  `toFixed(0)` while the legend used largest-remainder rounding so its
  three legs sum to 100 — the two could print different whole-percent
  figures for the identical reading. Same "one function, every surface"
  convention as `taSrSide`/`taTrendFlipped`/the `loud` boolean above.
- **`renderTape()` now runs on the same 1-second clock-driven timer as the
  market-state lamp.** The lamp got a 1-second repaint in round 7; the
  tape's own PRE/AFT tags were left on the 30-second data-poll cadence, so
  the lamp could flip to OPEN or AFTER HOURS up to 30 seconds before the
  tiles beneath it agreed. `renderTape()` is a pure render off already-
  cached data with no network call, so this is free.
- **A new `tickNewsStat()` rewrites just the `#newsstat` staleness badge on
  the existing 30-second standalone timer**, the same timer `renderCats()`
  already uses to recompute ITS staleness badge regardless of whether
  `fetchData()` got a new payload. News had no equivalent — its badge only
  updated from inside `renderNews()`'s call in the data-fetch success path,
  which never fires during a total outage, so the badge froze at whatever
  age it last saw instead of escalating to STALE. A full `renderNews()` on
  this timer was rejected on purpose (it throws away keyboard focus on a
  headline link, per the standing comment above `tickNewsStamps()`) —
  `tickNewsStat()` only ever touches the one badge span.
- **`BigOrder` rows now publish `spot`** (`build_snapshot.py`'s
  `big_candidates.append()`), added to `DATA_CONTRACT.md`'s schema. The
  frontend's `o.spot`-based MOSTLY INTRINSIC detection (added in round 7 to
  fix the badge's live-price flicker) had no field to read — verified
  against the live `origin/data:data.json` payload showing `'spot' in o`
  false for every row — so the badge's real detection path was dead code
  since the day it shipped.
- **Conviction/Swing's live price block is `.livepx` now, not `.nm`.** Both
  boards' live price/%-change span shared the `.nm` class with sector-table
  company names, so the mobile media query's `td .nm{display:none}` rule
  (meant only for those names) silently hid the live price on a phone too.
- **The 'VOL > OI' badge moved from the Open Interest cell to the Side
  cell** in the Biggest Orders table. It was glued inside the OI `<td>`,
  which the mobile media query hides outright to fit the table — the Side
  cell (column 2) is never hidden at mobile and already carries the
  contract's other badges (delta, MOSTLY INTRINSIC).

## Decision history
Lives in the ClaudeVault repo under `market-data/flow-desk/`.
