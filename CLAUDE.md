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
- **FEATURE FREEZE IN EFFECT (Zach's ruling, 2026-08-22) — see
  `docs/OPEN_ITEMS.md`'s "Getting to a real 'done'" section.** Eight review
  rounds have not closed the nine-section review with zero open findings;
  every feature added mid-stabilization (gamma levels, between rounds 7 and
  8) reopened fresh review surface area and reset progress. **Do not add new
  features to this repo** until `docs/OPEN_ITEMS.md`'s "Open" section is
  empty, or Zach explicitly lifts the freeze in so many words. Bug fixes
  from the review rounds are the only work permitted.
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

## Guardrails added 2026-08-22, round-9 fix pass (24 findings, all 9 sections)

Round 9 of the nine-section review confirmed 24 findings (see
`docs/OPEN_ITEMS.md` for the full list and scores) — the first round run
under the feature freeze (see "Getting to a real done" in that same doc).
This pass fixed all 24 the same day. The non-obvious decisions:

- **The 1H/4H live-quote-artifact filter now detects by SIGNATURE (zero
  range, zero volume), never by a fixed-hour grid modulus.** A real
  08:30-anchored hourly bar lands at :30 past every hour in UTC epoch
  seconds, DST or not — `t%3600===1800`, never 0 — so the old
  `t%3600!==0` check deleted the genuine most-recently-completed candle on
  most symbols, not Yahoo's actual live-quote artifact.
- **The daily/weekly synthetic-candle dimming now checks
  `!STAGE.syntheticReal`, not just `STAGE.synthetic`.** A genuinely
  complete, scanner-sourced afterhours close is a real reading, not a
  fabricated bracket, and drawing it translucent contradicted the
  crosshair's own "fabricated" definition a few lines below.
- **A new `STAGE.weekRealDays` (from `intervalDataFor`) counts real prior
  daily rows already folded into the current 1W bar**, so the pre-market
  and CLOSE-ONLY captions can say "this week already has N real trading
  days in it" instead of claiming the whole week has no data, the way the
  1D version of the same caption correctly does for a single day.
- **`seriesFull`'s trailing-window append now calls `candleClose()`**, the
  same session-aware function the candle and the drawn MA lines both use —
  it used to append raw `q.px` unconditionally, which is yesterday's price
  during pre-market, silently distorting the "% vs it" legend's own rolling
  average by one sample and disagreeing with the chart's own MA lines.
- **`robustClampMag` no longer clamps an outlier whose own immediate
  neighbor is also well above the ordinary spread.** Magnitude alone can't
  tell a lone data glitch (a real spinoff-quarter margin distortion) apart
  from genuine sustained compounding growth (a real earnings explosion) —
  both are "one point far above the median." A glitch is isolated; a real
  trend's neighbor is elevated too.
- **`#chartread` never leaves its original DOM position again.** Round 8's
  own fix moved it into whichever `.gwrap` grid was tapped via
  `insertAdjacentElement`, which incidentally planted it as a descendant of
  `#stagetabbody` — so the next tab switch's `body.innerHTML=...` destroyed
  the node permanently, killing tap-to-read for the rest of the session. A
  `.floating` class now repositions it with `position:absolute` computed
  from the tapped chart's bounding box against `#s-stage`, never touching
  where the node actually lives in the tree.
- **A curated peer set's PARTIAL result now caches separately from its
  COMPLETE one** (`PEERS_LAST` vs. `PEERS_CACHE`). Caching only a complete
  answer keeps a transient scanner outage retryable, but it also meant
  `peerStat`'s fallback (the only path the Fundamentals grid uses) saw
  nothing and showed zero peer context for a name like V, whose one stale
  ticker pin (NASDAQ:FISV instead of NYSE:FI) will never resolve — while
  vs-Peers, holding the same resolved result directly, correctly ranked it.
- **A released catalyst is backfilled forward, not re-derived backward.**
  `fetch_econ_tv` requests `from=now`, so a print that released an hour ago
  is simply absent from the next refetch and `build_catalysts` has no
  memory of what it built last cycle. `_merge_catalysts_forward`
  (fetcher/context.py) carries a previous-cycle row forward while it's
  still inside its own release grace period — computed by
  `_catalyst_still_fresh`, a direct Python port of the frontend's
  `catDone`/`countdown` logic, so the two can never disagree about when a
  row goes from "released" to "cleared."
- **`fetch_econ_tv` looks back 26 hours now, not from=now.** TV only ever
  sets a non-null `actual` on a row whose release time has passed — which a
  from=now-forward-only request can never receive by construction, making
  `DATA_CONTRACT.md`'s "actual fills in once the print lands" promise
  permanently unreachable regardless of anything downstream.
  `build_catalysts`'s own window filter (bounded to `session_date` onward)
  still drops anything from a prior calendar day, so the wider fetch window
  only ever adds today's already-released rows with their real `actual`.
- **Conviction's header counts now disclose their own scope.** bulls/bears/
  firing describe the WHOLE scored watchlist, computed before the
  score-floor cut is applied to what the table actually shows — the header
  now also prints the shown board's own bull/bear split in parentheses
  whenever the cut trims anything, with the two scopes spelled out in the
  tooltip.
- **`adhocFillAvgMove` now matches the fetcher's exact window (20 closes,
  19 changes)**, not 21 closes/20 changes — a one-day-wider window for the
  identical "usual move" figure the HOT badge reads meant a desk-pinned
  ticker (server-computed) and a searched/custom one (this client fallback)
  could disagree about the SAME ticker.
- **Gamma coverage is disclosed as a percentage of total gamma open
  interest, not a strike count.** `total_strikes` isn't on the payload
  (only `total_gamma_oi` is), so "top 4 of N strikes" isn't literally
  available; the caption instead sums the shown levels' own published
  `pct` values against 100% and says how much of the total they cover.
- **The heatmap's three hatch states (`nodata`/`prev1d`/`capfall`) are
  mutually exclusive by precedence now, `nodata` always winning.** A tile
  with no reading for the period AND a stale 1D print used to carry both
  classes, and CSS cascade order let the less severe one's pattern silently
  overwrite the more severe one's.
- **`heatFetchNow` short-circuits before the request, not just before
  branching on the response**, when the Desk universe has no tickers at
  all (every pinned name hidden, or none added) — otherwise a self-caused
  empty watchlist landed on the identical "scanner unreachable" message a
  real HTTP failure produces, blaming TradingView for a state the reader
  caused.
- **Sortable column headers are real tab stops now** (`tabindex="0"`,
  `role="columnheader"`, `aria-sort`, Enter/Space activation) on the shared
  `table()` helper used by every board — Conviction, Swing, Biggest Orders,
  ETF flows, and sector rotation all inherit the fix from one place.

## Guardrails added 2026-08-22, round-10 fix pass (23 findings, all 9 sections)

Round 10 of the nine-section review confirmed 23 findings (see
`docs/OPEN_ITEMS.md` for the full list, scores, and per-finding write-up);
this pass fixed all 23 the same day. The non-obvious decisions from this
pass:

- **The live-poke path now recomputes the SAME extended/fabricated state
  `stageRender` computes at full-render time, on every 30-second poll, in
  both the 1D and 1W branches.** Before this, `stageRender` alone set
  `bar.color`/`bar.wickColor` to a 50%-alpha hex for a dimmed candle and
  `STAGE.syntheticReal` for the "CLOSE ONLY" caption — both froze at
  whatever the last full render computed, so a dimmed candle reverted to
  full opacity 30 seconds later and a real scanner-published open/high/low
  kept reading "CLOSE ONLY" for the rest of the session on a tab left open
  since pre-market. `stageLivePoke` now recomputes `ext` and sets
  `color`/`wickColor`/volume alpha on every `candle.update()` call, and
  flips `STAGE.syntheticReal=true` the moment real `live.o`/`live.h`/
  `live.l` are confirmed, mirroring `stageDailyData`'s own test.
- **The 1W live poke now folds `live.h`/`live.l` into its ratcheted
  high/low, matching what the 1D branch already did.** The weekly branch
  only compared the stored high/low against the new close, silently
  understating the real intraday range whenever a fresh high/low printed
  without moving the close past the prior extreme.
- **A new `taAmvForInterval(amv)` helper extends the existing avg_move-based
  tolerance scaling from 1D-only to every interval**, so `taContainTol` and
  `taFitLine`'s `touchTol`/`hugTol` no longer fall back to flat
  intraday-sized tolerances on 1W — a weekly bar's naturally wider range
  was blowing through those tolerances on every fit attempt, silently
  starving volatile names of any weekly trend line.
- **A new shared `TA_SR_WIDE_BAND` constant (0.02) is now read by both the
  S/R chart-draw block and the caption's wide-band text**, so a cluster
  between the draw block's old 2% threshold and the caption's old 0.4%
  threshold can no longer get a caption describing a two-sided range the
  chart drew as one dashed line. Same "one function/constant, every
  surface" convention as `taSrSide`/`taTrendFlipped` from round 7.
- **A new `TA_FLAG_POLE_LOOKBACK` constant (20 bars) anchors the flag/pole
  percentage to the channel's own start**, not to `win[0]` (the edge of
  whatever range button happens to be active) — before this, clicking 1M
  vs. 1Y re-sliced `win` from scratch and reported a different "run into a
  tight channel" percentage for the identical underlying pattern.
- **`wlRemove(sym)` now always strips a custom entry AND separately hides a
  pinned one**, rather than running only one branch. When `RAIL_GROUPS`
  grows to pin a symbol a browser had already custom-added (the WTI case,
  pinned 2026-08-15), that browser's stale `desk.wl.custom` entry rendered
  a duplicate ghost row whose × button did nothing — `renderWL()`'s
  `custom` list is now filtered to exclude anything `railHasSym` before the
  render list and count are built.
- **Annual financials bar charts get the same `robustClampMag` outlier
  clamp the quarterly charts already had**, folded into the same
  `clampedAny` disclosure flag — LITE's and NBIS's real annual EPS/FCF
  charts were rendering as one bar and near-invisible slivers with no clamp
  and no caption note.
- **`metricValue()`'s PEG derivation now fires on `v==null || v<=0`, not
  just `v==null`.** A company with a real vendor-reported negative PEG (an
  ordinary case: a profitable company whose trailing EPS growth went
  negative) was never given the page's own derived-PEG fallback, and
  `metricReason`'s blanket negative-value check ran before the
  derived-PEG-specific reason could fire for that same case.
- **The heatmap footer now surfaces the previously-unused `staleRead`
  variable as a STALE badge**, and `nCapFall` is recomputed from the
  post-cap `rows` — a scanner outage after first load kept repainting the
  last good tiles with no on-screen sign the scanner had stopped
  responding, and the cap-fallback count could include a row the tile-count
  cap had already sliced off.
- **`peerStat(sym, key, peersOverride)` takes the SAME 2-point/high-spread
  "no usable median" guard `oneMetricChartHTML` already computes**, via a
  new optional `peersOverride` parameter instead of re-reading the
  module-global `PEERS_CACHE` — the rank badge's better/worse color used to
  paint a directional verdict off a median the adjacent caption explicitly
  called unusable (MRVL's PEG chart, a ~100x KLAC/SKHY spread).
- **`_peersByIndustry`'s `finish()` now tracks a null-cap candidate as
  `capUnknown`, distinct from a genuinely out-of-band peer.** `inBand()`
  returns `null` for an unresolved cap and `false` only for two known,
  mismatched sizes — the `wide` array's old `inBand(c.cap)===false` check
  let a null-cap candidate (a foreign issuer or thin OTC name the scanner
  hasn't backfilled) through completely unflagged.
- **`renderPeersTab`'s timeout no longer kills the underlying peer-scan
  promise's callback.** The old `if(timedOut) return;` early-return
  permanently locked the tab on "the peer scan did not answer" even when
  the real two-POST scan (a banded query, then an unbanded retry) finished
  successfully moments later in the background — removed, along with the
  now-unused `timedOut` variable, so a late success still repaints.
- **`_dedup_econ` now merges `forecast`/`prior`/`unit`/`scale`/`period`/
  `agency` onto a surviving CSV row instead of discarding the conflicting
  TradingView row's data outright**, via a new `_ECON_MERGE_FIELDS` tuple —
  every HIGH-importance CSV-sourced row (PCE, Jobs Report, PPI, CPI, Retail
  Sales, FOMC, Fed Chair presser) was live-showing `forecast:null`/
  `prior:null` because the CSV feed itself never carries those numbers and
  the dedup step threw away the TV row that did. A new `_ECON_ALIASES` list
  and `_merge_econ_aliases()` function handle the 5 known title mismatches
  between the two feeds (CPI↔Inflation Rate, Jobs Report↔Non Farm
  Payrolls/Unemployment Rate, FOMC↔Fed Interest Rate Decision, PCE↔PCE
  Price Index); `catMetaLine` still prints "no forecast published for this
  reading" for any HIGH-importance row still missing both after the merge.
- **`build_catalysts`'s earn_map loop now drops a same-day, same-ticker
  memory row and folds its title into the earnings row as a
  parenthetical**, instead of emitting both — MU's Q4 earnings was printing
  twice in the catalysts panel for the same day with no dedup by
  (ticker, date) across the two row kinds.
- **The Swing board's chase chip now derives "since flagged" from a new
  cross-day-persistent `history["swing_first_seen"]` map**, distinct from
  Conviction's original daily-reset `today_sessions`-based
  `first_board_swing` stamping, which Swing had been incorrectly sharing.
  Conviction genuinely resets daily and keeps its original logic unchanged;
  Swing's board persists for weeks to months, so re-baselining
  `spot_at_alert` to that morning's spot on every new trading day defeated
  the chip's entire purpose for a name that had sat on the board, unbroken,
  for 15 sessions. `chaseChipHTML(c, px, board)` gained a `board` parameter
  so the tooltip wording matches which board it's on ("first flagged" for
  Swing, "first hit the board today" for Conviction) — same "one function,
  every surface" convention as `taSrSide`/`taTrendFlipped`/`fedLegPct`.
- **The Biggest Orders delta badge moved to its own `.deltabadge` class**,
  off the shared `"nm tn"` class sector-table company names also carry — the
  mobile media query's `td .nm{display:none}` rule (meant only for those
  names) was hiding the one figure that separates a hedge from a
  directional bet, even though the badge lives in the Side cell the query
  never hides.
- **Every flow-board `tr.rw` row now carries `role="button" tabindex="0"`**
  (Conviction, Swing, Big Orders, and the sector table) — the column
  headers got exactly this fix in round 9, but the rows themselves had no
  attribute for the existing `[data-sym][role="button"]` keydown handler to
  match, so Tab could reach a sortable header but never the row beneath it.
  No handler change was needed; the existing delegate covers the rows
  automatically once the attribute is present.
- **`score_framework`'s Filters 4 and 5 now read UNKNOWN, not a guessed
  PASS/FAIL, past a plausibility ceiling on the FILTER'S OWN OUTPUT
  magnitude** — `FRAMEWORK_OPMARGIN_MAX_PLAUSIBLE_BPS` (2000, a 20
  percentage-point YoY swing) and `FRAMEWORK_FCF_GROWTH_MAX_PLAUSIBLE` (3.0,
  a 300% TTM swing). MU's live sidecar was driving a silent "+5705 bps
  PASS" and "+1291% FCF growth," both far more likely a quarter-alignment
  or duplicate-row artifact than a real reading — the same class of data
  quality problem the Financials chart already guards against with
  `robustClampMag` on the identical arrays, with no equivalent gate on the
  one surface making an investment-grade PASS/FAIL claim from that data. A
  tight reconciliation band (trailing-4-quarter revenue vs. the prior
  annual figure) was considered and rejected: a genuinely fast-growing
  company diverges from a year-old annual figure for real reasons
  mid-fiscal-year, and a tight band would misfire on real hypergrowth into
  false UNKNOWNs — bounding the filter's own computed magnitude instead
  avoids that failure mode.
- **`staleWindowActive()` now also covers `afterhours` up to 15:20 CT.**
  The gate covered `open` (08:30-15:00 CT) and `premarket` from 08:15, but
  nothing covered 15:00-15:20 CT — 20 minutes the page's own tooltips
  repeatedly promise are covered ("outside 8:00-15:20 CT the last publish
  stands"). A fetcher stall at 15:05 drew no STALE badge on any flow board
  for the final 15 minutes of the loop's documented window, the exact
  stretch a trader watches most closely. The 08:00-08:15 front-edge gap is
  a deliberate buffer for the loop's first daily cycle to actually publish
  before the badge starts checking — left unchanged; only the back-edge gap
  was a real bug.
- **`stageFrameworkHTML` now calls `fundBuiltStaleDays(FUND_CACHE[sym])`
  and shows the same STALE badge convention the Fundamentals grid already
  carries for the identical `fund` object.** 3 of the 5 framework filters
  (revenue growth, opmargin expansion, FCF growth — not just the 2
  originally suspected) read from that sidecar with no staleness signal on
  the framework panel at all, so a stockanalysis.com outage kept printing a
  confident verdict off a days-old filing with nothing on screen saying so.

## Guardrails added 2026-08-22, round-11 fix pass (25 findings, all 9 sections)

Round 11 of the nine-section review confirmed 25 findings (see
`docs/OPEN_ITEMS.md` for the full list, scores, and per-finding write-up);
this pass fixed all 25 the same day. The non-obvious decisions from this
pass:

- **A new shared `weekKeyOf(d)` function (hoisted out of `intervalDataFor`'s
  own local copy) is now the ONE place that computes "the Monday of a bar's
  UTC week."** The ad-hoc 1W branch's `wSynth` flag was inverted (`<=`
  instead of `>`) — during ordinary market hours the condition was always
  false, so a searched/off-desk ticker's weekly chart froze at its last
  settled close and never disclosed it. A bare flip to `>` (mirroring the
  1D check) was considered and rejected: the ad-hoc 1W branch never appends
  a new row the way 1D does, so a bare "today after last stored day" would
  also fire across a full week boundary and let `stageLivePoke`'s patch
  overwrite an already-settled PRIOR week's OHLC with today's live price.
  The fix needs a week-boundary comparison specifically, which is why the
  helper had to be shared rather than reused as a private closure.
- **The ad-hoc weekly branch now computes `weekRealDays`/`premarketBar` the
  same way `intervalDataFor` already does for pinned names**, so a searched
  ticker's weekly caption can say "this week already has N real trading
  days in it" instead of always printing a false "CLOSE ONLY" once the
  `wSynth` fix above let `STAGE.synthetic` go true for an off-desk name.
- **`taShapeLabel`'s "ascending/descending channel" branch now has THREE
  outcomes, not two.** `conv` was already computed as converging/diverging/
  parallel, but the label/detail assignment only ever checked
  `conv==="converging"` — diverging silently fell into the same text as
  parallel, captioning a visibly widening channel "roughly parallel"
  (verified live on DIA). New labels ("broadening ascending/descending
  channel") mirror the existing "broadening formation" case for the
  opposite-slope pattern.
- **`adhocEnsureFacts`'s permanent cache now self-invalidates once its own
  cached earnings countdown has gone negative**, re-fetching rather than
  freezing forever — a searched ticker's countdown correctly disappeared
  when it hit zero (per `earnDaysNow`'s own `>=0` guard) but then NEVER
  came back, even months later when the next real earnings date was days
  out, because nothing ever re-fetched a symbol once it was in the map.
- **`_tsVariants` strips a leading `$` before building search variants.**
  "$MU" — how traders paste a ticker from Twitter/StockTwits — read as
  "nothing matched, not a real listed ticker" to TradingView's substring
  matcher, the same class of fix already applied to company-suffix
  stopwords for the identical underlying reason.
- **Boot-time warm-up of the custom watchlist's daily bars switched from a
  sequential `.reduce` chain to a parallel `Promise.all`**, matching the
  facts warm-up immediately above it — a browser with N custom tickers left
  later entries with no hot badge or 52-week bar for N-1 sequential
  stockanalysis.com round-trips.
- **A new `pegGrowthPctFor(fund)` helper factors the growth-rate
  computation out of `derivedPeg`, so `metricValue` can gate a
  VENDOR-supplied PEG against the same implausibility ceiling
  (`DERIVED_PEG_MAX_GROWTH_PCT`, 500%) `derivedPeg`'s own fallback already
  gets.** BE's vendor PEG (0.0178, rendering as a green "bargain" pill) is
  built from the identical near-zero-denominator EPS base — a $0.0047
  prior-year TTM figure, a rounding error from zero — that would make
  `derivedPeg` itself reject the reading; gating only the derived fallback
  left the vendor's own equally-unreliable number through with no caveat.
- **`periodsPerYear`'s exactly-2-distinct-years fallback now has a floor
  (fewer than 8 total labels returns null) and its tally tie-break now
  prefers the LARGER quarter-count, not the smaller one.** `Object.keys` on
  numeric-string keys iterates ascending, and the old strict `>` comparison
  let a 1-vs-1 tally tie (e.g. a 3-quarter year vs. a 2-quarter year)
  resolve to the smaller value — corrupting the YoY window and TTM EPS/PEG
  math downstream, not just a label. The floor is scoped to the two-year
  fallback path only (`!full.length`) — a 3+-year series with one clean
  middle year is already unambiguous regardless of its total label count
  and must not be nulled out by it.
- **`robustClampMag` now isolation-tests EVERY value the ceiling would
  actually clip, not just the single globally-largest pooled value.** With
  revenue+ni+fcf sharing one pooled magnitude, an isolated spike in one
  series could set a ceiling that also clipped a different series' point
  that was never itself checked against its own neighbors — latent on
  today's data (the value that gets clipped happens to also be a genuine
  outlier) but a real, reachable path once a smaller-scale series' own
  ordinary values exceed a structurally-larger series' outlier-driven
  ceiling.
- **The Sector Heatmap's isolate-empty branch now blanks `#heatfoot`
  before returning**, instead of leaving the previous cycle's "N names ·
  Sector only" text standing under a message that says zero names are
  usable — the footer-rebuild code lower in the function never runs on
  this early-return path.
- **`prev1d` and `capfall` are two INDEPENDENT hatch facts a tile can carry
  at once now, via a combined `.hm-tile.prev1d.capfall` CSS rule stacking
  both background-image layers** — the single-class rules' cascade let
  whichever class came second silently overwrite the first's pattern, even
  though both facts (no pre-market print yet, AND no dollar-volume reading
  today) can genuinely be true for the same tile. `nodata` still wins
  outright over either, unchanged from round 9.
- **A sector block under 16px tall now gets a real, if invisible, click/tab
  target** (a 1px-tall strip carrying the sector name in its title/
  aria-label) instead of no header at all — before this, a block too short
  to visually carry a label also could not be isolated by any means, since
  isolation only works by clicking a header.
- **The heatmap's tile-count-cap note now names whichever dimension is
  actually the smaller of `wrapW`/`wrapH`**, since `maxTiles` is driven by
  AREA — a wide-but-short window (1600x600 in expanded mode) hits the cap
  from its height, and the old fixed "widen the window" wording told the
  reader to change the dimension that would not help.
- **The indexed-revenue-growth chart's `skipped` disclosure array is now
  read in BOTH render branches, not just the `lines.length<2` one** — once
  2+ series cleared the 5-quarter minimum, a dropped name (including the
  focused symbol itself) simply vanished from the chart with zero
  explanation, even though the disclosure text already existed and was
  simply never appended to the surviving chart's own caption.
- **The vs-Peers PEG chart's shared `.note` clip-mark sentence is now
  patched in after the async fund load, not just computed once
  synchronously before `FUND_CACHE` resolves** — if PEG's own async-patched
  chart was the only one that ended up clipped, the page-wide sentence
  explaining what a clip mark means never got written (each bar's own hover
  tooltip still discloses it independently either way).
- **`peerStat`'s better/worse verdict now has a THIRD, neutral state for an
  exact tie with the peer median** (`better: null`), read by both
  `peerAnnotate` and the vs-Peers rank badge — strict inequalities both
  ways previously folded a genuine tie into "worse," asserting a false
  verdict for a company tied with the field.
- **`_ECON_ALIASES` now carries ORDERED (include-all, exclude-any) match
  attempts per event, not a single loose substring pattern.**
  TradingView's econ feed carries four distinct Inflation Rate rows on the
  same date/slot (headline YoY, headline MoM, Core YoY, Core MoM); a bare
  `inflation rate` match with no Core exclusion or YoY preference took
  whichever came first in the feed's own row order, which live data showed
  could silently merge Core MoM's numbers under the CPI anchor. The second
  attempt (Core excluded, no YoY requirement) is a deliberate fallback so a
  feed that only publishes MoM for a release still merges something.
- **`nextWeekdayName`/`prevWeekdayName` now walk real calendar days via
  `isTradingDay`**, not a bare Monday-Friday weekday-index table — a
  half-day (a real trading day, just an early close) let the walk land on
  a genuine holiday as "the next session" with nothing checking that day
  against `MARKET_HOLIDAYS`.
- **`_build_opex_rows` sets `anchor:True` for the monthly/quarterly
  branches, not just LOW-importance weekly rows.** The frontend's own
  title-regex curation (`catIsAnchorByName`) already treated these rows as
  anchors, but `catMetaLine`'s badge reads the `anchor` field directly —
  which the fetcher set `False` unconditionally for every market_calendar
  row — so the badge never fired for a row the curation logic had already
  decided was an anchor.
- **Conviction's `#convstat` header build now runs BEFORE its own
  `arr.length===0` early return**, matching the order Swing and Big Orders
  already use — a total CBOE chain outage blanked Conviction's age/stale
  stamp entirely while the other two boards kept showing "as of ..." in
  the identical empty state.
- **`table()` gained an `opts.liveKeys`/`opts.freeze` mechanism so a
  live-poll redraw can reuse the last REAL sort's row order (by ticker
  identity) instead of re-sorting on a value that ticks every 30 seconds.**
  Conviction's RVOL column is the one sort key that updates between
  data.json fetches (`c.rvol_shown`, refreshed from the live price poll);
  resorting on every poll moved rows out from under the reader's cursor
  purely because the number they were watching changed. An explicit header
  click never sets `freeze`, so a real user re-sort still resorts for real.
- **The Biggest Orders/Conviction "counts ≠ $" mismatch pill now reuses
  `tip-flowpct`'s own scope-difference language** instead of asserting only
  a price-weighting explanation — `cp_ratio` is accumulated over every
  strike in the 0-7 DTE bucket while Flow %'s premium is accumulated only
  inside the near-money band, two different POPULATIONS of contracts, not
  just two weightings of the same ones.
- **`score_framework` now returns a `filter_flags` dict distinguishing a
  PERMANENT implausibility-ceiling rejection (Filter 4/5 only) from a
  genuine "still gathering data" gap** — both used to collapse into the
  same `null`/"building…" word, telling the reader a flagged reading might
  arrive next week when it structurally cannot (the underlying financials
  are what's wrong, not the elapsed time). `stageFrameworkHTML` renders
  "DATA FLAGGED" for a flagged key instead, with its own explanatory
  tooltip; the passed/failed/unknown counting a flagged filter still
  correctly behaves as unknown for is unchanged.
- **`cache["fed_odds"]` is only overwritten when the fresh hourly fetch
  actually returns a dict**, mirroring avg_move's own merge-not-replace
  pattern just above this block in the same function — `fetch_fed_odds`
  returns `None` on any ordinary transient condition (an HTTP error, thin
  volume, a bad book-sum read), and the old unconditional overwrite wiped a
  genuinely good prior-hour reading for the rest of the hourly gate. The
  compound failure case (this AND `brief.fed_hike` both empty that day) now
  also gets a visible "No Fed-odds reading this cycle" note instead of the
  card silently vanishing.
- **`gammaStaleDays()` now computes "today" via `ctDateKey`, the same CT
  calendar-day convention every other day-based staleness check on the
  page already follows**, instead of `new Date().toISOString()`'s UTC day
  — between roughly 19:00 and 00:00-06:00 CT the UTC date has already
  rolled to tomorrow while it is still today in CT, producing an
  off-by-one-day STALE count in the evening.

## Guardrails added 2026-08-23, round-12 fix pass (21 findings, all 9 sections)

Round 12 of the nine-section review confirmed 21 findings (see
`docs/OPEN_ITEMS.md` for the full list, scores, and per-finding write-up);
this pass fixed all 21 the same day. The non-obvious decisions from this
pass:

- **`stageNextEarnHTML` now derives its displayed day-count from
  `fund.next_earnings.date` via `fedDaysToMeeting`, the same vendor the
  button's own tooltip/popover print** — it used to compute the count from
  `earnDaysNow(factsOf(sym))` (TradingView) while printing a
  stockanalysis.com date in the same UI element, live-verified disagreeing
  by up to 7 days (MU) and showing a countdown next to a date 18 days in
  the past (TSEM). This is the exact class of bug the Fundamentals grid's
  "Next earnings" cell already fixed, applied to the one remaining call
  site that still had it.
- **The 1D-only `STAGE.premarketBar` session-transition clear now runs
  before BOTH the 1W and 1D live-poke branches**, not just ahead of 1D's
  own block — a tab opened straight to the 1W view during pre-market and
  never switched to 1D had no path to ever clear the flag once the session
  left pre-market, since the clearing check lived inside the `iv==="1D"`
  gated block.
- **The 1W live-poke's pre-market branch now builds its update purely from
  `preMarketBar(wlive, prevWeekClose)`, never folding `live.h`/`live.l`
  into the ratcheted weekly high/low or flipping `syntheticReal`** — those
  fields still describe YESTERDAY's regular session during pre-market (the
  same fact the 1D branch's own `STAGE.premarketBar` gate already
  respects), so folding them into the FORMING week's range silently pulled
  a prior day's reading into the new week and desynced the candle's
  dimmed/real visual state from its own "· pre-market" caption.
- **`STAGE.vZoom` resets to 1 on every interval/window-button click**, not
  just on a symbol change (`stageShow`) or an explicit double-click on the
  axis — a wheel-zoom stretch from a previous view otherwise persisted
  onto a chart the user never touched, re-applied by
  `stageApplyVZoom`/`autoscaleInfoProvider`.
- **A new `TA_REALISTIC_MAX_BARS` map caps `taMinWinForTrend()`'s scaled
  minimum at the actual max bar count the browser can ever hold for 15m
  (130) and 1H (150)** — uncapped, 15m needed 1040 bars against a 140-bar
  fetcher ceiling and 1H needed 260 against a 160-bar frontend slice, both
  permanently "too short" on every ticker forever, with the caption's own
  "try a longer window" escape hatch gated to `iv==="1D"` and therefore
  never reachable from either interval. 4H clears its own scaled minimum
  comfortably and needs no cap.
- **`containLeg` (trend-line containment) now reads CLOSES for 1W as well
  as 1D, not just 1D** — a weekly bar's high/low wick spans five trading
  days of intrabar extremes, so wick-based containment could silently kill
  a genuine, tradeable weekly support/resistance line the moment any ONE
  day that week poked through, even while every weekly close respected it.
  Widening `containTol` (already interval-scaled via `taAmvForInterval`
  since round 10) doesn't fix this — a wick still encodes intrabar
  extremes a close-based check would never see, so the leg selection
  itself had to change, not the tolerance.
- **`taSrBadgePick`'s "nearest level" distance and the S/R axis-badge
  collision test both now measure against a wide band's actual drawn
  EDGE (`l.hi`/`l.lo`), never the cluster's arithmetic mean (`l.price`)**
  — a wide band draws and labels only its near edge, so an MA line sitting
  exactly on that edge while the mean read 3%+ away reported "no
  collision" and stacked the S/R badge directly on the MA's. Fixed at both
  fit time (`taSrBadgePick`, the wideBand render branch) and every live
  poke (`stageTAPoke`'s recolor loop), so a fit-time and a live-poke
  collision decision can never disagree.
- **`LEV_NAME_RE`'s short-index alternatives now allow an optional
  attached number instead of ending flush against a trailing `\b`**
  (`short\s+s&p\s*\d*`, not `short\s+s&p\b`) — ProShares glues the index
  number directly onto the name with no separator ("Short S&P500", "Short
  Dow30", "Short MidCap400"), landing the required word boundary between
  two word characters where none exists, so the alternative never matched
  at all. The multiplier alternatives now also accept a decimal
  (`\d+(\.\d+)?x`, replacing the fixed `2x|3x` set) for real
  fractional-multiple single-stock ETFs (GraniteShares' 1.75x TSLR/CONL).
- **A new `robustClampHasUncorrectedGlitch` detector runs alongside
  `robustClampMag` wherever the latter returns null**, adding a caption
  note for the specific case where an isolated glitch WAS recognized but
  couldn't be clamped because a different value in the same over-threshold
  set is a genuine trend — the uniform single-ceiling clamp this chart kit
  supports cannot clip just the glitch without also flattening the real
  trend value above the same ceiling. A true per-point clip was considered
  and rejected: modeling it against SNDK's live data barely changed its
  bar heights, since SNDK's real EPS genuinely spans 200x+ — the
  actionable fix is disclosure, not chasing a cosmetic reshuffle.
- **The Margins/YoY/EPS chart's `SM.W` now derives from the same `hostW`
  measurement the money chart's `BIG.W` already uses**, sized per the
  actual column count CSS auto-fit will produce, instead of a flat
  hardcoded 340 — at a narrow desktop width where `.gwrap` collapses to
  one ~548px column, each 340-viewBox SVG rendered at 1.61x its authored
  scale while the money chart right above it rendered correctly at the
  same width.
- **`fund.currency` is never left `null` in the published payload
  anymore.** It's only ever SET by the Yahoo leg, gated behind a
  once-per-run crumb handshake — a crumb failure used to blank currency
  for the ENTIRE tracked universe at once, not just one ticker, and the
  page then printed a false "may not report in dollars" hedge for an
  ordinary US company. `build_fund_sidecar` now falls back to a small,
  explicit `KNOWN_NON_USD_CURRENCY` table (SKHY/TSM, the only two
  currently-pinned non-USD reporters) and defaults every other pinned
  ticker to `"USD"` — deliberately NOT a heuristic guess based on exchange
  or any other signal, since none reliable enough exists in this pipeline.
- **The sector heatmap's `isFund` (used for sector bucketing and the "(a
  fund: ...)" tooltip wording) now reads `d[11]` ("type," already fetched
  into `HEAT_COLS` and never used) instead of being inferred from a
  missing market-cap reading.** `byVol` (fires for ANY row missing a cap
  THIS CYCLE, real stock or fund) and "is this actually a fund" are two
  different facts that were conflated — a real equity's transient
  missing-cap read got bucketed into "Funds & wrappers" with a tooltip
  asserting outright what the company IS, not a statement about today's
  data. A `byVol`-but-not-fund row now gets honest "no market cap reading
  today" wording instead.
- **A bare heatmap tile (no visible ticker label) now requires two taps to
  navigate: the first identifies (shows the tooltip via `data-bare`/
  `data-tapped`), the second opens the chart** — a touch user has no
  hover, so a tap on an unlabeled tile used to navigate straight to a full
  chart with zero on-screen identification first; the tile's own click
  handler called `stopPropagation()` before the document-level
  click-tooltip fallback (mobile browsers' tap-triggered click event) ever
  got a chance to fire. Desktop mouse users are unaffected in practice —
  they already saw the hover tooltip before clicking at all.
- **`pegGrowthPctFor` now gates on whether the PRIOR-YEAR EPS BASE itself
  is implausibly tiny (`DERIVED_PEG_MIN_PRIOR_EPS`, 5 cents/share),
  replacing round 11's percentage-only growth ceiling.** A fixed
  percentage ceiling can't distinguish a real V-shaped cyclical earnings
  recovery from a near-zero-denominator rounding artifact — both produce
  "one extreme percentage from one small base." MU's live sidecar has a
  genuine, non-degenerate $5.5538 prior-year base growing to $44.1733 (a
  real 695% AI-supercycle move) that round 11's 500% ceiling flagged
  identically to BE's actual $0.0047-base artifact. Gating on the base's
  own magnitude instead lets MU's real reading through while still
  catching BE's.
- **Sector rotation's fallback dot (price relative strength vs SPY, used
  only when `flow_1w` is null) now renders as a hollow ring
  (`.iodot.pu`/`.pd`), never the solid flow-colored fill**, with its own
  tooltip and panel-caption wording — the dot's tooltip and the panel's
  caption both used to unconditionally call it "the sign of the $1w flow
  beside it" even when the $1w column read "—" right next to it, since
  price-relative-strength is a genuinely different fact from money
  direction.
- **The news ticker's change-detection key now hashes every item's
  identity (`url@ts`), not just the newest headline plus a count** — a
  dominant top story holding slot 1 across several polls while headlines
  in slots 2-20 rotated out for newer ones (same count) went completely
  undetected, freezing the marquee on stale content with nothing on
  screen saying anything was withheld.
- **`renderPriceBanner`'s dead-feed threshold dropped from 2 consecutive
  misses to 1** — `.rl.clock` (the only OTHER carrier of a poll-failure
  warning) is `display:none` at 640px, so on a phone the full-width banner
  was the sole visible warning, and it waited a full extra ~30s poll past
  the first failure while desktop saw the identical single failure
  immediately via the clock-row hint. Both surfaces now agree regardless
  of viewport.
- **`boardCutNoteHTML`'s "every tracked name clears the bar" wording now
  also requires `lowFiring===0`, not just `strong===total`** — a
  live-reachable shape (every non-firing name clearing 60+ while at least
  one firing name, like AVGO or MU, stays sub-60) let the sentence assert
  in one breath that those names are "below the line" AND that "every
  tracked name clears the bar."
- **Conviction's `rowHTMLConv` now calls `dispQuote(liveBySym(c.ticker))`
  directly instead of pre-substituting `{}` when the lookup fails** —
  `dispQuote`'s own `if(!q) return {...tag:null...}` guard exists
  specifically to produce a neutral untagged state for a missing quote,
  but an empty object is truthy, so the pre-substitution defeated the
  guard and fell into the premarket branch, rendering a false "PREV"
  badge and its misleading tooltip for what was actually a failed lookup.
  Every other call site in the file, including Swing's own row builder,
  already called `dispQuote` directly with no fallback.
- **The Swing board's `trend` field is a genuine tri-state now
  (`"UP"`/`"DOWN"`/`"MIXED"`/`null`), not a two-state collapsed onto
  `"MIXED"`.** A ticker with no SMA20/SMA50 from the scanner at all
  (thinly-traded new leveraged ETFs like MUU/RAM, the fetcher's own
  documented gap) used to read identically to a genuine split-above-one-
  average/below-the-other reading, and `swing_score` awarded the same +7
  points for both — `trend == "MIXED"` already excludes `None` with no
  further scoring change needed, and the frontend already renders a null
  trend as "—".
- **The 5-metric framework verdict gained a `"_CAPPED"` suffix, distinct
  from `"_BUILDING"`, for when EVERY unresolved filter was permanently
  rejected by an implausibility ceiling rather than genuinely still
  gathering data.** `_framework_verdict` now takes a `flagged` count
  (`len(filter_flags)`) and only keeps `"_BUILDING"`'s "could still move"
  promise when at least one unresolved filter is genuinely pending — a
  ticker whose only unresolved filters are BOTH ceiling-rejected (MU's own
  real opmargin/FCF swings) got the same "(building)" wording and note as
  one genuinely accumulating weekly consensus history, promising a
  resolution that structurally cannot happen since the underlying
  financials are what's wrong, not the elapsed time.

## Decision history
Lives in the ClaudeVault repo under `market-data/flow-desk/`.
