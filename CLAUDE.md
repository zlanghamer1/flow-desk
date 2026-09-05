# CLAUDE.md — direction for Claude sessions working on flow-desk

## What this is
Flow Desk is a personal options-flow dashboard: a static GitHub Pages site
(`index.html`) plus a GitHub Actions loop (`fetcher/`) that pulls free CBOE +
TradingView data, scores it onto two boards, and publishes `data.json` +
`history.json` to the `data` branch, which the site reads live.

It is a personal research tool, not a product. The paid-site question is
closed — see "Settled questions" below.

## Read these first
- **DATA_CONTRACT.md** — authoritative for the `data.json` / `history.json`
  shape. Change a field here first, then match the code and the site.
- **README.md** — the canonical user-facing, plain-English truth. Keep its voice.
- **DEPLOY.md** — ops only (deploy method, loop lifecycle, what starts the day).
- **docs/DATA_LICENSING.md** — authoritative for which external hosts the desk
  may call. Adding a host means adding a row in the same change.
- **docs/OPEN_ITEMS.md** — open findings, review scores, per-round tables.
- **docs/GUARDRAIL-HISTORY.md** — the *why* behind every rule here: the live
  measurements, the bugs each guard was written against, the fixes past passes
  rejected and why. Read it before re-litigating any decision below.

## Model-role convention for work on this repo
- **Fable** — architect; rules on scope and gives final approval.
- **Opus** — directs traffic; synthesizes reviews into build specs.
- **Sonnet** — builds (writes the code and docs).
- **Haiku** — mechanical grunt work.

---

# Standing bans

Never do these. Each one has a live incident or a measurement behind it in
`docs/GUARDRAIL-HISTORY.md`.

1. **Never push the `data` branch by hand.** The loop force-pushes it every
   cycle; your push will be clobbered or will fight the loop.
2. **Never flip Settings → Pages to "GitHub Actions" mode.** Branch mode from
   `gh-pages` is intentional (DEPLOY.md).
3. **Never call TradingView's chart websocket from the site.**
   `data.tradingview.com` enforces an exact-host `Origin` allowlist; `Origin`
   is a forbidden header name, so page JavaScript cannot set it. A python
   probe "proving" it works is sending websocket-client's own allowlisted
   default. The scanner host is different and reflects any Origin, which is
   why quotes, search and fundamentals work from the browser.
4. **Never remove the split repair in `fetcher/context.py`, and never trust
   Yahoo's split events to replace it.** Yahoo served SOXS's history 15x too
   high and its own declared splits match neither the break's date nor its
   factor. The threshold is set from the live universe; loosening it would
   rewrite a real gap into a fake split. `fetcher/test_split_repair.py` pins
   both directions.
5. **Never remove `build_snapshot.run_cycle`'s `write_history = market_state
   != "closed"` guard.** Forced off-hours runs may refresh `data.json` but must
   never create weekend or holiday history sessions.
6. **Never re-add the excluded tickers** — BESIY, IFNNY, SPX, VIX, SPMO —
   without reading the exclusion note in `fetcher/build_snapshot.py`. NRGU and
   WTI were reinstated 2026-08-15; NRGU is TRACK_ONLY, and WTI is W&T Offshore
   equity, not crude.
7. **Never remove the in-chart TradingView attribution logo
   (`layout.attributionLogo`) or the footer credit.** Both are Apache-2.0
   license conditions of the vendored Lightweight Charts v5.2.1 build.
   `pages.yml` ships `vendor/` with `index.html`; never publish one without
   the other.
8. **Never call stock prices live.** They are 15-minute delayed. The scanner
   reports `update_mode: "delayed_streaming_900"`, and cross-correlation puts
   the real lag at 16 minutes on SPY, MU, CRWD and NVDA alike. `rtc` is not
   fresher than `close`. The 30-second poll is how often the page re-reads a
   delayed print, not how fresh the print is. If a keyless real-time source is
   ever found, relabeling is a separate change with its own measurement.
9. **Never skip, disable, or quarantine a test to get CI green**, and never
   push an empty commit or close-and-reopen a PR to kick CI.
10. **Never let a display-only field feed a score.** `flow_pct`, the aggressor
    tilt, `opt_rvol`, `activity_tag`, `unusual_activity`, `facts.*.framework`,
    `facts.op_margin` and `facts.short_pct` are reference data. Wiring any of
    them into `conviction_score` / `swing_score` needs its own backtest first.
11. **Never widen the server universe from the page.** Custom watchlist adds
    and hidden pinned names live in `localStorage` (`desk.wl.custom`,
    `desk.wl.hidden`), per browser, disclosed in the UI. Boards, `bars.json`,
    `facts` and `fund/` sidecars follow `build_snapshot.PINNED` only.
12. **Never weaken a disclosure without a verified fact to replace it.**
    Replacing a stated caveat with a false certainty is worse than the caveat.
13. **Never invent an entity name, contact, or governing law** to make
    `legal.html`'s bracketed placeholders look finished. They are Zach's to
    fill and an attorney's to approve.
14. **Never name a person in user-facing copy.** Rendered pages state the
    rule, not who made it ("the 2026-08-26 declutter rule", not "Zach's
    ruling"). Code comments, this file, and README decision notes keep
    attribution.
15. **Never let a page smoke test reach the network** to make it pass. It
    blocks every external host by design; a failure there is a real fail-soft
    bug in the page.

---

# Cross-cutting rules

Every review round re-taught these. They are the general form of roughly 250
individual findings.

## Truthfulness of what's on screen
- **One function, every surface.** A fact computed in two places will
  eventually disagree in public. Existing single-source functions: `taSrSide`
  (S/R color and position word), `taTrendFlipped` (trend-line role),
  `fedLegPct` (Fed-odds rounding), `vpWords` (volume-profile wording),
  `flowCpMismatchHTML`, `sessionsBehind`, `earnCountdownDays`, `newsForSym`,
  `ntDuration`, `newsIssuerNoteHTML`, `chaseChipHTML`. Add to this list rather
  than re-deriving a rule inline.
- **Two numbers describing the same thing on one screen must agree.** If two
  counting rules differ, each gets its own sentence naming its own scope.
- **A missing reading is never an inflow, a zero, a pass, or a green pill.**
  It is null, it renders neutral and dimmed, it sorts to the bottom, and the
  UI says which reading is missing.
- **A feed that fails keeps its slot.** Print a one-line reason. `hidden` is
  for a payload the desk never carries, never for one that came back empty.
  The one deliberate exception is the Band-crosses panel, which hides when
  nothing crossed; that asymmetry with MOVERS is intentional.
- **A grade says how many inputs it had.** `macro_backdrop.py` attempts seven
  readings and ships what resolves, so the panel prints a chip per missing
  reading and "graded on N of 7". Keep `BACKDROP_ALL` in step with it.
- **A claim about a stretch of bars is checked against those bars.** Count the
  closes; do not test the last one and generalize.
- **A flag that marks fabricated data must be read by something.**
- **A network failure is never cached as a fact about the world.** A failed
  scan says the scan did not answer, and is not written to the cache. Track
  "attempted and failed" separately from "never attempted"
  (`ADHOC_FACTS_FAILED`, `FUND_CACHE_FAILED`).
- **A 200 that updated nothing is a failed request.** The scanner answers 200
  with an empty `data` array under rate limiting; count that as a miss rather
  than stamping a fresh timestamp over frozen prices.
- **Every feed needs its own staleness signal.** The page banner watches the
  equity poll only. A second feed is a second thing that can die quietly.
- **Every board prints its own "as of" unconditionally**, and builds that
  stamp before any empty-state early return.

## Live data and sessions
- **A verdict computed from price is recomputed when price moves.** Trend
  status, distance, side, drawn line colors, axis-badge collisions and the
  volume-profile wording all re-derive on every poll. A conclusion cached at
  open is a conclusion about a market that has moved.
- **Indicators compute on settled bars; the live bar is excluded from the
  math, not just the display.** Bollinger, volume profile, and the trend/S-R
  fit window (`nFit`) all slice off the live-appended candle. Slice once —
  double-slicing drops a real settled bar.
- **Pre-market, the regular-session columns are yesterday's.** `rtc`, `open`,
  `high`, `low`, `change` and `volume` all still describe the previous
  session. Only `premarket_close` / `premarket_change` describe the new day. A
  name with no pre-market print carries PREV, drops out of the hot test, and
  sorts below names with a live move.
- **A synthetic "today" candle checks the calendar AND the clock.** Require
  `isTradingDay(now)` and `ctMinutesOfDay(now) >= 3*60`. Before 3:00 CT the
  quote is still the prior day's close.
- **The market calendar is not a weekday test.** `isTradingDay` consults the
  holiday and half-day tables. A green OPEN lamp on Thanksgiving is worse than
  no lamp.
- **Day-based staleness uses the CT calendar day (`ctDateKey`), never UTC.**
  Between ~19:00 and 06:00 CT the UTC date has already rolled.
- **A resample buckets by session, never by counting bars**, and keys on the
  CT session date, never a UTC day key.
- **A view that changes symbol clears its data first.** `stageShow` empties
  rows, dates, times and every marker map before it repaints, so a header can
  never sit over the previous name's bar.
- **An async render captures the state it was called for.** Guard on
  (symbol, interval, prefs) being unchanged, share one in-flight promise, and
  make retries one-shot per key so a failure can never loop.
- **A cached session-derived flag tracks the session, not the moment it was
  set.** Clear it when the session leaves that state, on every interval branch.

## Rendering and geometry
- **Chart geometry is authored for the width it renders at.** SVG text scales
  with the viewBox, so a fixed font-size lands anywhere from 5px to 16px.
  Measure real host widths; re-render the open tab on a width-class change.
  `.gchart` caps at 420px and `.gfull` at 1000px — clamp computed widths to
  the authored ceiling.
- **A responsive rule that rescues the narrow case gets checked at the wide
  one**, and vice versa. Measure every width, not the two you designed for.
- **A header carrying live text holds a fixed height**, or it wraps and
  unwraps as the cursor moves and the chart jitters.
- **A clamp above the tallest bar is not a clamp**, and one anchored on "the
  second largest" needs three values.
- **An outlier clamp (`robustClampMag`) isolation-tests every value it would
  clip**, using each point's own neighbors, not just the globally largest. A lone glitch is
  isolated; a real trend's neighbor is elevated too. Where a single ceiling
  cannot clip the glitch without flattening a real trend, disclose instead of
  clamping, and name which chart.
- **A formatter keeps its own chart's values apart** — add decimals until no
  two distinct values print the same label.
- **Every formatter prints U+2212, never ASCII "-", and guards signed zero.**
  `(-0.3).toFixed(0)` is `"-0"`, which reads as flat beside a red FAIL badge.
  `fm1`/`sign1` (1-decimal, 0.05 threshold), `fm2`/`sign2` (2-decimal, 0.005)
  and `fwSignedFixed` carry the epsilon guard; keep the precisions distinct
  rather than merging them. The minus-sign bug has been caught in six separate
  formatters — `numStr`, `fmtAxisPct`, `fmtAxisNum`, `peerFmtFor`,
  `fwSignedFixed` and the loss-P/E tooltip.
- **Keyboard focus and open tooltips survive an `innerHTML` rebuild.**
  Capture a stable attribute key before the rewrite and restore after —
  `table()`, `renderWL`, `renderTape`, `renderHeatBar` and `heatRender` all do.
  A DOM mutation alone does not re-fire `mouseover`.
- **Rewrite a live text node only when its text actually changed**, tracking
  the source string, never reading innerHTML back.

## Interaction and accessibility
- **Every interactive row carries `data-sym`, `role="button"` and
  `tabindex="0"`.** The keydown delegate only activates elements with all
  three; mouse-clickable but Tab-invisible is the recurring failure.
- **A hover target has to be hittable.** Use full-height bands per period, not
  2.6-pixel circles.
- **A tile too small to label is too small to be a keyboard stop.** Under 24px
  in either dimension it keeps its click and tooltip but leaves the tab order
  and the a11y tree.
- **Contrast is picked, not assumed.** `heatTextColor` falls back to pure
  black or white whenever both themed inks land under 4.5:1.
- **Hue is never the only signal.** Direction also carries a +/− glyph, and it
  leads the label so trailing-ellipsis truncation can never eat it.
- **Type floor is 10px, 10.5px for anything labeling data.** No word sits
  under 9.5px. Named exceptions are icon glyphs only: the brand sub-mark
  (9px), ◆ news separators and ▼ sort arrows and expander carets (8px),
  ▼ section carets (9px).
- **A radio group and a multi-select group get different indicators.**
  Interval and Range are radios (filled pressed style); Overlays is
  `.seg.tog` and draws a square that fills when on.
- **Tooltip underlines rest on `--tipline`** (~40% alpha) inside table cells,
  quick reads, footnotes and key/value rows, showing on row hover or focus.
  Headers, chips and rail labels keep the permanent underline so the
  affordance stays learnable.
- **Grid items need `min-width:0`.** The default `auto` lets a nowrap child
  widen a phone column past the viewport.
- **Wide content scrolls inside its own container**; the page body never
  scrolls sideways. Verify at 1440px and 390px.
- **Only static methodology prose may collapse behind a button.** Every
  dynamic disclosure stays printed unconditionally: as-of stamps, STALE
  badges, failure reasons, clamp / cap / coverage notes, currency caveats. The
  price-honesty disclosures (STALE, CLOSE ONLY, pre-market, fabricated-candle
  captions) live in the chart header and never move into a collapsed block.
- **NO EXPLANATION TEXT ON THE PAGE (Zach's ruling, 2026-09-05).** Do not
  write prose that explains what a panel is, how to read it, what a number
  means, what the desk does or does not endorse, or where the data came from.
  He asked for this after the Forecast chart shipped under a five-line
  figcaption explaining that the fan was not a prediction. A chart that needs a
  paragraph is a chart that has not been drawn well enough.
  - **A tooltip is not a hiding place.** The first pass at this rule moved the
    prose into `data-tip`; Zach's follow-up closed that door — "on mobile when
    clicking a technical indicator button the explanation text will pop up,
    remove this. I don't want it either in mobile or on the web." The page's
    tooltip opens on hover AND on tap, so a tooltip is on-screen text with an
    extra step. Explanation is DELETED, not relocated.
  - **`TIPS` is an empty lookup and stays that way.** It held 43 entries of
    methodology and is now `new Proxy({}, {get:()=>""})` so every call site
    resolves to "" and `showTip` no-ops. `fetcher/test_tips_sync.py` fails if
    anyone refills it. Same for `METRIC_MARKET_NOTE`.
  - **A control does not explain itself.** A button may carry a short
    affordance line saying what the click does ("Click to hide it from the
    rail."). It may not carry methodology, scope, or what the feature is for.
  - **A dynamic disclosure is not an explanation and still stays printed** —
    the rule above is unchanged. STALE badges, as-of stamps, failure reasons,
    clamp/cap/coverage notes and "no analyst covers this name" all state a
    fact about the reading on screen right now. Write them as the bare fact
    ("8 of 57 not bucketed by the feed"), never as a paragraph about it.
  - **The test:** would the sentence read the same for every symbol on every
    day? Then it is explanation — delete it. Does it change with the data?
    Then it is a disclosure — keep it, and cut it to the fact.
  - **Emptying `TIPS` is not the whole sweep.** Most explanation on this page
    is not in `TIPS` at all — it is inline, written straight into the markup
    as `data-tip="'+esc("...")+'"`. The first pass gutted the lookup and
    declared the job done; five explainers were still shipping on the Forecast
    and Options-flow tabs a session later (the median caveat, the bucket
    shortfall, the delta/decay lecture, two liquidity lectures). Grep
    `data-tip="[^"]{40,}` and `data-tip="'+esc(` before claiming the page is
    clean, and check the rendered DOM per tab rather than the source alone.

## Tests and process
- **A test that mirrors buggy logic keeps passing against a copy of the bug.**
  When you fix the code, fix the test's mirror in the same change. This has
  bitten `test_big_orders.py`, `test_framework_score.py`, `test_context.py`.
- **Verify before claiming done.** Run `pytest fetcher` and `pytest tests`,
  and render the page in headless Chromium at 1440px and 390px checking for
  page errors and sideways scroll. Point `PW_CHROMIUM` at a preinstalled
  browser (`/opt/pw-browsers/chromium`) rather than downloading one.
- **When adding a state to a function, check every return path**, not just the
  one the feature was written against. An early return is how `_CAPPED` missed
  25 names for two weeks.
- **Read the rendered string, not just the payload.** Three correct payload
  codes collapsed into one misleading word at the render layer and looked fine
  under inspection of `data.json`.
- **A feature added mid-review-round reopens review surface area.** Time
  feature work accordingly.

---

# Cross-file pairs that must move together

Change one, change the other in the same commit.

| Pair | Files | Pinned by |
|---|---|---|
| Scoring weights ↔ methodology text | `fetcher/build_snapshot.py` ↔ `index.html`'s `TIPS` | `fetcher/test_tips_sync.py` |
| Fed-hike grading thresholds | `fetcher/context.py` (`FED_HIKE_*`, `POLY_*`) ↔ ClaudeVault `market-data/morning-report/macro_backdrop.py` (`FED_HIKE_*`) | — (two repos, two CI runs, one methodology) |
| Holiday + half-day tables | `fetcher/market_guard.py` ↔ `fetcher/build_snapshot.py` ↔ `index.html` | `fetcher/test_sync_constants.py` |
| TRACK_ONLY names | `fetcher` `TRACK_ONLY` ↔ frontend `TRACK_ONLY_SYMS` | `fetcher/test_sync_constants.py` |
| Board score floor | Morning Brief `high_conviction` ↔ `BOARD_SCORE_FLOOR` | `fetcher/test_sync_constants.py` |
| Root HTML pages | all three lists in `pages.yml` (`paths:`, `git checkout main --`, `git add`) | `fetcher/test_pages_ship.py` |
| Color tokens | `index.html` ↔ `legal.html` | — |
| Bollinger math | on-chart overlay (`STAGE.rows`) ↔ rail scanner (`bollingerOf`) — two call sites, one `BB_PERIOD`/`BB_MULT`/`rollMA`/`rollStd` | — |

The `grade` / `alarm` fields are computed in the fetcher, never re-derived in
JavaScript. Same for `f.alarm`'s banner threshold.

---

# Subsystem rules

## Chart stage
- Intervals: 1D, 1W, 15m, 1H, 4H. Only 1D computes the day-denominated
  20/50/200 MAs, so **the MA button is disabled off 1D with a stated reason**.
  Do not invent per-interval MAs — a "20-day line" on an hourly axis is a
  different indicator.
- **1H keeps its 160-bar cap** (TA thresholds are calibrated to it) and
  discloses it with a chip when more bars are on file, naming that 4H reads
  the same file uncapped.
- Intraday live-quote artifacts are detected **by signature (zero range, zero
  volume), never by a fixed-hour grid modulus** — real hourly bars land at :30
  past the hour in UTC epoch seconds. For a series with no volume anywhere
  (VIX, US10Y, DXY), a flat trailing row is dropped only when it also sits off
  that series' own dominant timestamp remainder, computed per series.
- `resample4H` tracks the last real hourly bar merged into each bucket
  (`row[6]`) separately from the bucket's open time (`row[0]`), so the
  freshness chip reports real freshness.
- The weekly view's "closed" wording comes from `isLastTradingDayOfWeek()`,
  never today's own session state.
- The forming week's "yesterday" is `STAGE.weekPrevClose`, never
  `STAGE.rows[wn-2]` — weekly rows are one per week.
- Right-side spacing is `pad(nShown) = max(5, ceil(nShown*0.07))` on all five
  interval paths, unconditional.
- Vertical drag-to-pan rides the same `autoscaleInfoProvider` as wheel zoom
  (`STAGE.vPan`, applied after the stretch/floor math). Recompute
  `coordinateToPrice` fresh at both start and current Y on every move; a
  cached start price creates a feedback loop. Exclude the price axis and the
  bottom time strip; take `setPointerCapture`; never `preventDefault`.
- A log-scale floor is `pr.minValue/2`, never 0 or an epsilon —
  `log10(price+1e-4)` gives a 0-to-1 span as much room as four decades.
- `STAGE.vZoom` and `STAGE.vPan` reset at exactly three sites: axis
  double-click, the interval/window click handler, and `stageShow`.
- **A bare `stageRender()` skips `stageKeepView` and resets zoom and pan.**
  Route every re-render that should preserve the view through
  `stageKeepView`, the wrapper the TA toggles already use.
- **The boot-race rebuild is provably one-shot**, keyed `STAGE.bootRebuilt =
  sym+"|"+iv`, covering 1D and 1W and accepting ad-hoc bars
  (`ADHOC_BARS[sym].D`) as well as `quadsRaw`, cleared in `stageShow` and on
  every interval/window click. A `!STAGE.synthetic` test alone is not
  single-shot: on a non-trading day, or on the ad-hoc 1W path that keeps
  `synthetic` false by design, it refits from scratch on every 30-second poll
  forever. `STAGE.vpIntraKey` follows the same one-shot pattern.
- **The daily-bars cache keys on a CT calendar day (`BARS_FETCHED_KEY`), not a
  millisecond TTL** — `bars.json` changes once a day. That key drives both
  `ensureBars()`'s memoization and a `tick()`-driven re-fetch, so a tab left
  open across midnight picks up the new day untouched.
- **The six technicals buttons (MA, trend, S/R, BB, VP, GEX) carry no
  `data-tip`.** Every fact those tooltips held is printed where the overlay
  lands: the MA disabled reason in the chart-notes legend, "S/R is hidden while
  the volume profile is on" in the auto-TA caption, and each overlay's failure
  reason in the quick read's "nothing to draw for …" clause. Do not re-add
  without a fresh ask. `TIPS.ta_sr`, `ta_ma`, `ta_vp`, `ta_gex` and the
  deleted `taTrendTip()` note are kept as the canonical wording store with no
  consumer; if any renders again, restore the threshold substitution with it.
  `TIPS.ta_bb` still has two live consumers — leave it wired.
- The quick read under the chart is computed only from price vs its own 50-day
  and 200-day averages, with a ±0.3% dead zone. Display-only, never scored.
  Its Bollinger clause is 1D-only and neutral-colored. It names any toggled-on
  overlay that produced nothing to draw.
- `taDefaults()` is `{trend:false, sr:false, bb:true, vp:false, ma:false,
  gex:false}`, stored under `desk.stage.ta2`.

## Auto-TA
Display-only. It draws lines; it never scores, signals, or feeds an engine.
The geometry is a port of the vault's `scripts/trendline_break_scan.py`
constants (`TA_PIVOT_K`, `TA_MIN_SPAN`, `TA_TOUCH_TOL`, `TA_CONTAIN_TOL`).

- **Bar-count and tolerance thresholds scale per interval**, capped by
  `TA_REALISTIC_MAX_BARS` at the real maximum bars the browser can hold for
  that interval. Uncapped, 15m and 1H read "too short" forever.
  `taBarScale`, `taFreshBars`, `taMinSpanScaled`, `taMinWinForTrend`,
  `taAmvForInterval`, `taShapeMinMove`, `taBreakConfFor`, `taRetestNear`,
  `taMaxExt`. `TA_SHAPE_CONVERGE` stays unscaled — it is a dimensionless
  ratio, not a percent of price.
- **A trend line's role flips on BREAKOUT and EXTENDED, never on RETEST or
  FAILED.** `taTrendFlipped(status)` is the single source for the fit-time
  color, the live recolor, and the caption's color and name.
- `TA_FLAG_MIN_BARS` and `TA_FLAG_POLE_LOOKBACK` are first-pass heuristics,
  unlike the ported `TA_TOUCH_TOL` / `TA_CONTAIN_TOL` constants, which carry
  live-measurement comments. Give the heuristics the same scrutiny before
  trusting their exact numbers.
- Containment reads **closes on 1D and 1W**, wicks only intraday. A weekly
  wick spans five days of extremes and would kill a line every close respects.
- A shape label is read off the same fitted geometry `taFitLine` produced,
  never a separate pattern detector. The ascending/descending channel branch
  has three outcomes: converging, diverging, parallel.
- The flag/pole percentage anchors to `TA_FLAG_POLE_LOOKBACK`, never `win[0]`,
  so the range button cannot change the reported pattern.
- **A FAILED line never displaces a currently-valid candidate**, whatever its
  touch count. It still wins as the sole candidate.
- A FAILED verdict distinguishes a settled reversal from a live one
  (`fit.failedLive`). When the settled close cannot be read, default to
  live — never claim a settled reversal you cannot prove.
- **`TA_SR_MAX_DIST` stays flat at 20% by ruling.** An S/R level is a measured
  shelf; a trend line's value is a projection. The %-distance caption keeps a
  far level honest.
- S/R distance, inclusion and axis-badge collision all measure from the
  cluster's **drawn near edge** (`hi`/`lo`), never its arithmetic mean.
  `TA_SR_WIDE_BAND` (0.02) is shared by the draw block and the caption.
- A fit that hits its hug or containment ceiling says so (`fit.atCeiling`).
  Disclosure, not re-tuning: the ceilings came from live measurement.
- **One badge per price.** MAs, the one badged S/R level, the VP POC line and
  the GEX peak all check `taSrBadgePick` / `gexBadgeCollides`, at fit time and
  on every poke. The collision test is gated on `prefs.ma` — a badge
  suppressed by an invisible line would be wrong.

## Volume profile
- **Honest vocabulary only.** "volume profile", "most-traded price" (POC),
  "value area", "high-volume shelf". Never "institutional", "smart money",
  "buy zone", "sell zone".
- **Neutral coloring only** — `--ink3` / `--acc` / `--bb`, never `--up` /
  `--dn`. Colors re-resolve from `cssVar()` inside `draw()` every frame so a
  theme flip repaints with no separate hook.
- Frozen for the session: bins, POC and value area compute once per
  `stageTA()` pass on settled bars. Only the **words** re-derive on a poke,
  via `vpWords`. The POC axis badge's collision test does re-run every poke.
- **VP and S/R never stack.** S/R draws only when `prefs.sr && !vpOn`; when
  both are on, `summary.srHiddenByVp` names why, and the S/R button's tooltip
  says so before the click. Gamma lines are unaffected.
- Histogram bars anchor to `timeToCoordinate(lastBarTime)` re-read every
  frame, never `paneW - barW`. When the last bar is panned out of range the
  bars are withheld; the price-anchored bands still draw.
- Three distinct missing-data reasons, never a blank chart: no volume on the
  feed, too few bars carrying volume, window too short. **The 60% coverage
  fraction is daily/weekly only** — intraday zero-volume bars are ordinary
  extended-hours bars, not missing data, and the fraction test silently
  vetoed every intraday profile until this was fixed.
- Intraday-precision decomposition (1D, tracked names only) uses a day's own
  15m or 1H bars, never mixing the two within a session, and only when summed
  intraday volume falls within `VP_INTRA_SANITY_LO`/`HI` (0.5x–2.0x) of that
  day's daily bar. Outside the band, keep the plain daily smear for that day.
  Disclose the count and precision only when at least one session got it.
- In-bar volume labels are size-gated: bin height ≥11px in media coordinates
  and bar length clearing measured text width plus 6px.
- Teardown (`stageTAClear`) drops `vpPrim`, `vpData` and `vpLines` alongside
  `srLines` and `gammaLines`.
- `VP_BINS` (40, halved to 24 under 640px) and `VP_VALUE_AREA` (0.70) are
  first-pass constants, not backtested.

## Bollinger bands and alerts
- **A cross reads "volatility", never "bullish" or "bearish."** Above-upper
  and below-lower are the same `--bb` purple. Do not color one green and one
  red.
- Lower-band rows lead the panel and carry **weight, never a green ink**. The
  ask was to be alerted on the condition, not for the page to call it a buy.
- Three wordings for three facts: "at/below lower band" (current price),
  "touched lower band today (back inside)" (day low reached it), "above
  upper". `lowNear` (`BB_LOWER_NEAR_PCT`, 1% above the band) is an approach
  alert, worded distinctly from a touch.
- The day-low leg reads `q.l` only outside pre-market; before the bell that
  column is yesterday's low.
- One ticker per row, ticker in band color, reason in plain ink, each row a
  `data-sym` target with the full sentence as the row's own `data-tip`. The
  reason ellipsizes rather than wrapping. "+N more" is a plain status line,
  not a clickable-looking row.
- The panel hides entirely when nothing crossed or touched — the deliberate
  asymmetry with MOVERS.
- This is the page's only client-side alerting mechanism: stateless,
  recomputed every poll, no Notification API, no permission flow, no
  persistence. Adding push notifications would be new architecture.

## GEX / gamma
- Off by default (`gex`), gated inside `stageGamma` / `stageGammaLegend`.
  Failure reasons (`GAMMA_REASON`) print when it is on.
- Coverage is disclosed as a percentage of total gamma open interest, not a
  strike count — `total_strikes` is not on the payload.
- `gamma_history.json` accumulates daily snapshots on the `data` branch for a
  future GEX + volume-profile backtest. The page never reads it. Write is
  gated on the same `write_history` flag; a same-day re-run overwrites that
  session; only a real dict gets a row; **a ticker whose cycle spot is null or
  non-positive is skipped**, never written as an unevaluable row. Retention
  `MAX_GAMMA_HISTORY_SESSIONS` (250).

## Financials and vs-Peers
- **One company, one bar.** TradingView lists a foreign issuer's ordinary line
  and its ADR separately with the same fundamentals. Dedupe by
  `issuerKey(description)`, primary US listings only, and let `_tickerRank`
  replace an accepted line with a better-ranked one.
- **A peer must be comparable in size.** Rank by closeness in market cap,
  preferring inside `PEER_CAP_BAND` (5x either way). When nothing is in band
  the set still fills and the note names what sits outside it. `inBand`
  returns `null` for an unknown cap and `false` only for two known mismatched
  sizes; a null-cap candidate is tracked as `capUnknown`, never as
  out-of-band.
- **The peer median excludes the focused company**, in the dashed line and the
  caption. An exact tie renders neutral (`better: null`), never "worse".
- `PEER_GROUPS` curated overrides win over the industry scan. Current
  overrides: CRWD, V, TSEM, LITE, MRVL, AEHR, MU. **Curation is the only
  mechanism available** — see "Settled questions".
- **An exchange:ticker pin is a live fact.** `PEER_GROUPS.V`'s Fiserv pin has
  flipped twice; re-probe it live when a curated peer reads "did not resolve"
  for days, and never trust a dated comment over a fresh probe.
- A partial peer result caches separately (`PEERS_LAST`) from a complete one
  (`PEERS_CACHE`), so a transient outage stays retryable while
  `peerStat`'s fallback still has something to rank.
- `peerStat` takes the resolved peer list as `peersOverride` rather than
  re-reading the module global, and carries the same "no usable median" guard
  the chart computes.
- `periodsPerYear` returning null is honored by every real-math caller:
  `ttmEpsOf` returns null, `pegGrowthPctFor` returns "unresolved cadence", and
  `renderGrowth` suppresses the YoY chart. Never fall back to `|| 4`.
- PEG's derived fallback and a **vendor-supplied PEG** both gate on
  `DERIVED_PEG_MIN_PRIOR_EPS` (5 cents) — the prior-year base's own magnitude,
  not a percentage ceiling, which cannot tell a real cyclical recovery from a
  near-zero-denominator artifact.
- A YoY point is nulled, with a caption note, when its denominator is
  discontinuous (`yoyDenomDiscontinuous`, walking outward past nulls) or is
  half of a detected duplicated vendor row (`dupIdx`). A duplicate is
  revenue **and** EPS matching at the same index.
- `renderGrowth` flags byte-identical back-to-back quarters as a probable
  duplicated vendor row rather than dropping either.
- One chart can hold two data vintages: desk names from the morning snapshot,
  searched peers from the scanner seconds ago. `vintageNote` says which rows
  are which, on the vs-Peers tab **and** the Fundamentals grid badge tooltip.
- Only PEG needs `FUND_CACHE`. Patch its chart node in place via `outerHTML`
  (`oneMetricChartHTML`); never re-render the whole section, which discards
  open tap-to-read state.
- The zero-metric fallback still renders an empty `.gwrap` so a late PEG chart
  has somewhere to insert.
- `fund.currency` is never null in the published payload. It is set only by
  the Yahoo leg behind a once-per-run crumb handshake, so a crumb failure
  blanked the whole universe; `build_fund_sidecar` falls back to
  `KNOWN_NON_USD_CURRENCY` (SKHY, TSM) and defaults other pinned tickers to
  `"USD"`. Never a heuristic guess from exchange.
- A searched ticker's currency is defaulted `"USD"` client-side and **says it
  was not checked**. See "Settled questions" before trying to fix this.
- Visible caveats never collapse: the sidecar STALE badge, non-USD and
  unverified-currency warnings, dropped annual years, the semiannual-filer
  reason, clamp / anomaly / duplicated-row disclosures, the peers source line,
  vintage note, and the ✳ / ? / clip legends.

## 5-metric framework
- Display-only. `facts.<TICKER>.framework` never touches a board score.
- **Never hardcode a ticker's verdict.** Only the *methodology* from
  `financial_metrics_backtest_extended_2026-08-21.md` is implemented, in
  `score_framework`; every number comes from a live vendor at fetch time or
  reads null. The per-ticker analysis files misidentify tickers (NBIS, CORZ)
  and score inconsistently against their own thresholds.
- **A filter with no data is null, never a guessed pass or fail**, and the
  verdict says which. Suffixes carry three distinct states: `_BUILDING` (at
  least one unresolved filter is genuinely pending), `_CAPPED` (every
  unresolved filter was permanently ceiling-rejected), and plain `BUILDING`
  (fewer than `FRAMEWORK_MIN_EVALUATED` = 3 resolved). **Never lower
  `FRAMEWORK_MIN_EVALUATED` or guess an unresolved filter.**
- **A fund reads `NOT_APPLICABLE`**, gated on TradingView's own `type` column
  and only `FRAMEWORK_NO_FINANCIALS_TYPES = ("fund",)`. `dr` (TSM, SKHY) are
  depositary receipts of real operating companies with real financials. A null
  or unrecognized type falls through to the ordinary path. Never infer fund
  status from an absent market cap or sidecar. The panel renders one sentence
  and **no filter rows and no progress strip** for a fund.
- **A tier verdict carries no "(building)" suffix at render.** The tier prints
  as the result it is; a qualifier line states the true fact ("3 of 3
  measurable filters passed · 2 unlock later"). The payload's `_BUILDING`
  suffix is unchanged — the fetcher's distinction was always right; the
  rendering was what lied. `(capped)` does print, because there the ceiling is
  the honest thing to name.
- **All five filters carry an implausibility ceiling**, and past it the filter
  reads UNKNOWN with `filter_flags[...] = "implausible_swing"` (rendered as
  DATA FLAGGED, distinct from "still gathering data"):
  `FRAMEWORK_EPS_REVISION_MAX_PLAUSIBLE` (3.0, filters 1/3),
  `FRAMEWORK_REV_GROWTH_MAX_PLAUSIBLE` (3.0),
  `FRAMEWORK_OPMARGIN_MAX_PLAUSIBLE_BPS` (2000),
  `FRAMEWORK_FCF_GROWTH_MAX_PLAUSIBLE` (3.0). Bounding the filter's own output
  magnitude was chosen over a revenue reconciliation band, which would misfire
  on real hypergrowth.
- **Both legs of a ratio come from the same vendor.** Filter 3 pairs Yahoo's
  `eps_trend.current` with its own `d90`, never with TradingView's
  `facts.eps_ntm`. That cross-vendor pairing is what produced MU's fake
  "+246% revenue growth". A test pins it.
- Sign flips (profit-to-loss consensus) are real and read as downgrades
  correctly; they are not anomalies.
- `_ratio_matches_split` guards both consensus-EPS filters against an
  unadjusted split between weekly snapshots, reusing the vetted
  `SPLIT_RATIOS` / `SPLIT_SNAP_TOL` / `SPLIT_BREAK_MIN` constants.
- `consensus_history.json` lives on the `data` branch, never in the gitignored
  `fetcher/.context_cache.json`, and shares `write_history`'s guard.
- Filter 4/5 use the **annual** consensus estimate for both lookbacks, never
  the quarterly one, which rolls over every report.
- `metrics.ttm_fcf_positive` is published because filter 5 ANDs in
  `ttm_fcf_now > 0` — invisible from the two growth percentages alone.
- The five-segment `.fwstrip` is `aria-hidden` and built from the same
  per-filter states as the rows. A building segment carries an `--ink3` inset
  ring; flat `--edge` on `--srf2` measured 1.13:1.
- The BUY/ADD/HOLD/AVOID vocabulary is deliberately unchanged, flagged for a
  future attorney conversation.

## Flow boards
- **Biggest Orders ranks on `vs_normal`, never raw premium** — `premium /
  normal_prem`, where `normal_prem` averages the ticker's near-money 0-7 DTE
  premium over its prior `BIG_ORDERS_BASELINE_SESSIONS` (20) sessions. On raw
  dollars the index ETFs own the board by size alone. Today's row is excluded
  from its own baseline. A ticker with too little history gets `vs_normal:
  null`, sorts after every ranked row on raw premium, and prints "no baseline"
  with its session count. `rank_big_orders` is the one function that stamps and
  orders the pool; the page's default sort is the same key so fetcher and page
  cannot disagree.
- Gross premium is **not a directional claim** (2026-08-24 ruling). The Orders
  quick read counts calls and puts neutrally — no lean word, no lean color.
- `big_orders_capped`'s "earned" counts a ticker's rows across the whole pool.
  The disclosure gate is `shown == BIG_ORDERS_PER_TICKER AND earned > shown`;
  a ticker that never ranked on at all is an ordinary miss on dollars.
- MOSTLY INTRINSIC computes against the snapshot's own `o.spot`, never a live
  poll, or the badge flickers on timing alone.
- `contractLine` caps displayed IV at `IV_DISPLAY_CAP_PCT` (300%) with a
  dashed tooltipped placeholder — live examples ran 500-850%, all 0DTE
  deep-ITM artifacts.
- The $100K flow-% floor is enforced by `flowPctHTML` / `flowCpMismatchHTML`
  everywhere the number appears, board row and detail panel alike.
- The counts-vs-dollars mismatch pill states the **scope** difference:
  `cp_ratio` accumulates over every strike in the 0-7 DTE bucket, Flow %'s
  premium only inside the near-money band. Two populations, not two
  weightings.
- `universe.candidates` means every quote-resolved pinned name, TRACK_ONLY
  included; `universe.chain_eligible` carries the TRACK_ONLY-excluded count.
  Compare `with_options` against `chain_eligible`. Coverage disclosure has a
  third neutral clause for quote-only-by-design names.
- Empty-state wording checks `candidates === 0` **before** `with_options === 0`
  — a quote-vendor outage makes both zero with no chain ever attempted, so
  blaming the chain vendor would be wrong. `boardCutEmptyHTML` applies the same
  coverage check to the scored-but-all-below-floor case.
- Header counts disclose their own scope. bulls/bears/firing describe the whole
  scored watchlist, computed before the score floor cut; the shown board's own
  split prints in parentheses when the cut trims anything. `boardCutNoteHTML`'s
  "every tracked name clears the bar" requires `lowFiring === 0` too.
- Board quick reads restate the header counts from the same variables in the
  same render, so the sentence and the chips cannot disagree. Swing counts
  `cut.rows` and says "today's options money", never "multi-week".
- Swing's `trend` is a genuine tri-state (`UP`/`DOWN`/`MIXED`/null); a name
  with no SMA from the scanner reads null, not MIXED, and scores nothing.
- Swing's chase chip reads the cross-day-persistent `history["swing_first_seen"]`
  map, which tracks `last_seen` per entry and is deleted only after a full
  missed session — never on a single missed cycle. Conviction keeps its own
  daily-reset `today_sessions` stamping. `chaseChipHTML` takes a `board`
  parameter so the wording matches.
- `dispQuote` is always called directly with the live-quote lookup, never with
  a `{}` fallback — an empty object is truthy and defeats its own null guard.
  Its PRE branch gates on `prepx` alone; a null `prech` renders a price with no
  percentage, never yesterday's change beside this morning's price.
- Direction pills are outline. **FIRING and NEW are the only filled badges on a
  board.**
- Live price sits on its own line in the Name cell (`.livepx`, its own class —
  sharing `.nm` let a mobile rule hide it). The delta badge has `.deltabadge`
  for the same reason. VOL > OI lives in the Side cell, which mobile never
  hides.
- `table()` provides tab-stop headers (`tabindex`, `role="columnheader"`,
  `aria-sort`, Enter/Space), focus and hover restore across redraws, a
  `liveKeys`/`freeze` mechanism so a live poll reuses the last real sort order
  by ticker identity, and a `foot.html` that accepts a function evaluated per
  draw. An explicit header click never sets `freeze`. Never attach content to
  `table()`'s own element with `insertAdjacentHTML` — the first sort destroys
  it; use the foot mechanism.
- ETF rows carry the same row triad as every other board, plus a per-fund
  "Nd behind" badge from each fund's own `flow_session` via `sessionsBehind` —
  the published aggregate is the freshest fund's, so a single stalled fund is
  invisible from the header alone.

## Watchlist rail
- Sort is one native `<select>` (`#wlsel`) rendering into `#wlsortbox`, a
  **sibling** of `#wl` — `#wl` is rewritten every 30 seconds and a native
  select whose element is replaced closes under the reader's thumb. The
  explanation for the current sort prints on one line beneath it.
- `wlSort` persists to `desk.wl.sort`, read at boot through the
  `WL_SORT_VALUES` allow-list, falling back to "groups".
- Every sort comparator sinks a `liveStale(sym)` row to the bottom and guards
  the both-null NaN case.
- `volNow` mirrors `dispQuote`'s session awareness: the scanner's plain
  `volume` is the regular session's running total, so pre-market reads the
  premarket column, and returns **null** when no premarket print exists.
- `wlCustom()` / `wlHidden()` hold an in-memory mirror (`WL_MEM`); writes go
  to memory first so a browser where `setItem` throws still registers adds for
  the session, and `WL_MEM.saveFailed` surfaces a one-line warning.
- `wlRemove` always strips a custom entry and separately hides a pinned one;
  `renderWL` filters `railHasSym` out of the custom list so a newly-pinned
  name cannot render a ghost row with a dead ×.
- `wlIoApply` (bulk paste) enriches every new symbol exactly as `wlAdd` does
  (`adhocEnsureFacts` + `adhocEnsureDaily`), merges against a **fresh**
  `wlCustom()` read inside its `.then` so a mid-flight add or removal is not
  reverted, strips a leading `$`, counts only genuinely new names, and
  disables Apply while in flight.
- Boot warm-up of custom names' daily bars runs in parallel, not sequentially.
- `adhocEnsureFacts`'s permanent cache self-invalidates once its cached
  earnings countdown goes negative.
- `adhocFillAvgMove` is called from both the daily and facts success paths —
  whichever settles second does the write, since only it sees both pieces —
  and matches the fetcher's exact window (20 closes, 19 changes).
- `adhocEnsureDaily` fetches
  `https://stockanalysis.com/api/symbol/s/{sym}/history?range=5Y`, plain GET,
  **no custom headers** (any one forces a preflight). Rows arrive newest
  first — reverse them. `range=2Y` silently returns one year with HTTP 200;
  only 3M/6M/YTD/1Y/5Y/10Y are honored.
- `_tsVariants` strips a leading `$` before building search variants.
- `isLeveraged()` / `LEV_NAME_RE` must not match real companies. Three false
  positives have shipped: Build-A-Bear (bare `bear`), Ultra Clean Holdings
  (bare `ultra`), and a plural boundary bite. `bear` and `ultra` require an
  attached digit or an index/asset name; multiples accept decimals
  (`\d+(\.\d+)?x`) for real fractional single-stock ETFs. ProShares' plain
  inverse funds (SH, PSQ, DOG, MYY) are named "Short S&P500" with the number
  glued on, so the short-index alternatives allow an optional attached number.
- MOVERS and the shopping list carry their own `liveStale` STALE tags, gate
  and count "+N more" off the array the visible list is sliced from, disclose
  the 3-name cap, and print "new low" rather than a clamped 0%.
- A `NEWS` mark means a headline inside `NEWS_FRESH_MS` (24h) for that name,
  on the ticker line, never the name line.

## Sector heatmap
- The S&P 500 and Nasdaq 100 universes come from the scanner's `symbolset`
  filter live (`SYML:SP;SPX`, `SYML:NASDAQ;NDX`) — no baked constituent list.
  It refreshes only while visible and states the 15-minute delay.
- `HEAT.data`, `HEAT.inflight`, `HEAT.lastFetch` and `HEAT.lastFetchFailed`
  are all keyed **per universe**. The refetch gate reads the current
  universe's `lastAttempt` (stamped on every try), never the success-only
  timestamp, and backs off 30s → 60s → … → 5min while failing.
- `isFund` reads TradingView's `type` column (`d[11]`), never an absent market
  cap. "no cap reading this cycle" and "is a fund" are two different facts;
  the "(a fund: …)" tooltip requires `isFund && byVol`.
- The 1D reading is session-aware: pre-market swaps to the live premarket
  print (PRE) or keeps the prior day's figure tagged PREV; after the bell it
  swaps to `postmarket_change` (POST).
- The three hatch states are `nodata` (always wins), then `prev1d` and
  `capfall`, which are independent facts and stack via a combined CSS rule.
  Use `background-color` longhand inline — the `background` shorthand resets
  `background-image` and silently defeats the hatch.
- Non-Desk universes **exclude** a `byVol` row from the sized set entirely.
  `byVol` overwrites `cap` with dollar volume upstream, 500-1000x smaller;
  Desk avoids the problem by using dollar volume uniformly.
- `heatDeskTickers()` filters by `wlHidden()`.
- `heatFetchNow` short-circuits before the request when the Desk universe has
  no tickers, rather than blaming the scanner for a self-caused empty state.
- `heatClampFrom` uses an interpolated percentile (index `(n-1)*0.90`) —
  `floor(n*0.90)` is the maximum index for n of 8-10 and rendered every
  ordinary Desk tile near-neutral.
- DOM emission re-sorts by (y, x) after squarify so tab order follows the
  layout. `_wrapFocusKey` restores a focused tile by `data-sym`, not just a
  sector header.
- A sector block under 16px tall still gets a 1px click/tab target carrying
  its name, or it cannot be isolated at all.
- `heatMeasureHead()` and `heatMeasureFoot()` publish real measured heights
  (`--heathead-h`, `--heatfoot-h`) on **every** render exit path, failure
  branches included. Never a hardcoded offset: `.rail` flex-wraps below
  1080px. Expanded mode's floor is a flat `min-height:240px` —
  `min(420px, calc(…))` against an identical `height` is a no-op.
- The tile-cap note names whichever of width or height is actually the
  smaller, and on a phone points at the Desk universe or a desktop rather
  than telling the reader to widen the window.
- The cap diffs the sector set before and after slicing and names any sector
  that vanished entirely.
- A `prefers-color-scheme` change listener clears `_heatRGB` and re-renders,
  guarded on no explicit `desk.theme`.
- The isolate-empty branch blanks `#heatfoot` before returning.

## Macro tape, catalysts, news
- The macro tape keeps its own miss count and prints FROZEN on its tiles.
  `renderTape()` runs on the same 1-second clock timer as the market lamp so
  its PRE/AFT tags cannot lag the lamp by 30 seconds. Every tile carries a
  normal-case tooltip, not only the no-quote branch.
- `staleWindowActive()` covers `premarket` from 08:15, `open`, and
  `afterhours` to `ctSessionCloseMinute()+20` — half-day aware, never a fixed
  15:20. The 08:00-08:15 front gap is a deliberate buffer.
- `fetch_econ_tv` looks back 26 hours. TV only sets a non-null `actual` on a
  row whose release has passed, which a `from=now` request can never receive.
- `_merge_catalysts_forward` carries a previous-cycle row forward while it is
  inside its release grace period. `_catalyst_still_fresh` is a direct port of
  the frontend's `catDone` / `countdown` logic, and requires the release to
  have **happened** (`0 <= delta < 6h`; no-time rows same-day only).
- `catDone()` never short-circuits on a populated `actual` — that buried every
  just-released HIGH print behind weeks of future events the instant it
  printed.
- `_dedup_econ` merges `_ECON_MERGE_FIELDS` onto a surviving CSV row rather
  than discarding the TV row that carries them; every HIGH-importance CSV row
  ships `forecast:null`/`prior:null` on its own. `_ECON_ALIASES` handles known
  title mismatches with **ordered (include-all, exclude-any) attempts** — TV
  carries four Inflation Rate rows per date and a loose substring took
  whichever came first. `_merge_econ_aliases` removes the matched TV row from
  `out` afterward, matched by (date, title), never object identity. It does not
  skip a CSV anchor that carries its own prior.
- The earnings loop drops a same-day same-ticker memory row and folds its
  title in as a parenthetical, rather than emitting both.
- `catPassesCurated`'s memory branch gates on `importance` unless the row
  matches a desk ticker — most memory events carry `ticker:null` by design.
  There is no bare `/options expiration/` catch-all; the
  monthly/quarterly/quad/triple regex covers it. `_build_opex_rows` sets
  `anchor:True` for monthly and quarterly branches. `catMetaLine` reads
  `c.anchor || catIsAnchorByName(c)`.
- Cleared catalysts group last.
- `nextWeekdayName` / `prevWeekdayName` walk real calendar days via
  `isTradingDay`. `marketClosedWording`'s 00:00-03:00 CT branch returns the
  literal "today".
- **`newsForSym(sym, data)` is the one function every per-name news surface
  calls** — header reel, focus bar, rail panel, rail-row mark. It reads
  `news.by_ticker[sym]` first, then reel items tagged either way, deduped and
  newest first. Raw `news.items` carry `ticker` (singular); `tickers` exists
  only after `dedupeNews`, and filtering raw items on it matched nothing for
  every name.
- `news.by_ticker` gives every pinned name its own newest headlines from the
  same hourly per-symbol pulls — zero extra requests. A symbol that returned
  nothing has no key, never an empty list. Custom names can never be in it:
  `news-mediator.tradingview.com` sends no CORS header, so the reel says
  "headlines cover desk names only".
- `NEWS_CAP` is 24 and `NEWS_PER_TICKER_CAP` is 2, deliberately favoring
  breadth over depth per name. Two historical-scenario tests pin the
  algorithm at the older caps via `monkeypatch`, while the cap-size tests read
  the constants — change a cap and check both kinds.
- **`ntDuration(n)` is the one pace function for both reels** — 8s per
  headline, 55-200s bounds. Change the pace only there, and only on a fresh
  ask.
- **Both reels roll on every motion setting and are never manually
  scrollable.** This is a deliberate `prefers-reduced-motion` override for
  these two elements only; every other animation still honors the setting.
  Hover pauses a reel. The loop-seamlessly duplicate copy always renders,
  since nothing can reach it by scrolling any more. Do not copy this override
  elsewhere.
- `tickNewsStat()` rewrites only the `#newsstat` badge on the standalone
  30-second timer. Never call `renderNews()` there — it throws away keyboard
  focus on a headline link.
- The news change key hashes every item's identity (`url@ts`), not the newest
  headline plus a count.
- `newsIssuerNoteHTML(tickers, title)` is the one issuer-linkage disclosure,
  called by both the panel and the marquee: analyst headlines tagged to
  wrapper tickers get "(about the fund's issuing bank, not its market)". The
  payload has no relation field, so it is a disclosure gated on all-wrapper
  tickers plus a rating-note title shape, never a drop.
- `renderPriceBanner`'s dead-feed threshold is 1 miss — `.rl.clock` is hidden
  at 640px, so on a phone the banner is the only warning.
- `renderBrief`'s backdrop block gates on `brief.backdrop`, not
  `readings.length`, so a 0-of-7 failure prints seven "no data" chips instead
  of a bold grade with no visible basis.

## Fed-hike odds
- The market-priced chance of a hike at the next meeting (Polymarket,
  keyless). It grades the macro backdrop and words the verdict; **it never
  moves the verdict score.**
- `normalizeFedOdds` computes `hikePct` (via `fedLegPct`, largest-remainder so
  the three legs sum to 100), one `loud` boolean (`alarm===true ||
  grade==="HOSTILE"`), and `stale` (from `asOf` age against
  `FED_ODDS_STALE_MS`, 3 hours). Every surface reads those, never its own
  derivation: the rail chip, the card headline and numeral, the banner.
- `fedAlarmHTML` has three "why" phrasings and reads the upstream `f.alarm`
  rather than re-deriving the 40% threshold. The banner fires at the 25%
  HOSTILE floor, so a 32%-no-jump reading says "elevated enough to flag, short
  of a coin flip".
- The countdown has an explicit `dLeft < 0` branch, reachable in combination
  with a long fetcher outage.
- `cache["fed_odds"]` is overwritten only when the fresh fetch returns a dict
  — `fetch_fed_odds` returns `None` on any transient condition. The compound
  failure case prints "No Fed-odds reading this cycle" rather than vanishing.

## Forecast tab
- **One vendor per panel.** Every figure comes from the same TradingView
  scanner row (`target*`, `rec_*`). Yahoo's `recommendationTrend` and
  `financialData` targets were rejected: their counts and means disagree with
  TV's and with Yahoo's own analyst count, so mixing them would put two
  contradictory numbers on one panel.
- **`rec_mark` runs 1..3, NOT 1..5** (corrected 2026-09-05). 1 = every analyst
  a strong buy, 2 = neutral, 3 = every analyst a strong sell. The market's
  worst consensus is 2.7143 and nothing can exceed 3. The gauge maps it
  `(v-1)/2*180`. Drawing it on a 1..5 arc — which shipped for two days — put a
  dead-neutral 2.00 on "Buy" and made the Sell half unreachable, so every name
  read more bullish than it was.
- **There are FIVE rating buckets and all five must be requested.** TV's own
  column names understate two of them: `recommendation_buy` weighs 1.0 (a
  STRONG buy) and `recommendation_sell` 3.0 (a STRONG sell), with
  `recommendation_over` (1.5) and `recommendation_under` (2.5) carrying the
  plain ones. Label them accordingly or the bars contradict the needle. With
  all five they sum to `rec_total` exactly; a shortfall is a real vendor gap,
  and **is still never closed by rescaling the bars.**
- **No consensus word is printed** — but the old reason for it was wrong, so do
  not repeat it. It claimed the mark "is not a plain average of its own
  buckets" and that a mapped label contradicted TradingView. Both were
  artefacts of the 1..5 error and the mislabelled buckets. The mark IS a plain
  weighted average: AAOI's 4 buy / 1 over / 3 hold = (4+1.5+6)/8 = 1.4375, its
  published mark exactly, landing by the Buy anchor, which is TradingView's own
  label. The word is omitted because Zach asked for a gauge and a number and
  has not asked for one. That is a display choice, not a data limit.
- **Before writing "the vendor does not publish X", check.** Fetch
  `https://scanner.tradingview.com/america/metainfo` (keyless) and grep its
  3,777-field list. Three separate forecast bugs in one week were all the same
  shape — the request narrower than the feed — and twice the page printed its
  own gap as the vendor's defect.
- When the live price sits outside the published target range, the broken
  bound becomes the price and is labeled "price", not "low"/"high". The
  diamond is the live price; the accent tick is the average.
- A median more than 5% from the mean gets its own sentence naming which way
  the outliers pull.

## Layout and shell
- `.shell` has no max-width; side columns keep fixed widths so reclaimed width
  goes to the middle column.
- `.stagebar .seg` wraps (`flex-wrap:wrap; max-width:100%`) — at 390px the
  labeled overlay group ran 26px past the screen and `.seg{overflow:hidden}`
  cut GEX off with no scroll path.
- On phones the boards' last cell keeps a 26ch floor (34ch for desktop Swing)
  and the board scrolls inside `.xwrap`. An overflowing table hands a wrapping
  cell its minimum width.
- Chips never break mid-chip or across lines (`.chasef`, `.pill`, `.bc`).
- Below 900px the search button says "Search", never ⌘K / Ctrl K.
- `.grow` (and the header headline reel inside it) is `display:none` under
  900px; the focus bar carries the newest headline there instead.
- `ageWordsHTML` appends "· N min ago" to every as-of chip. `stampMs` parses
  both stamp shapes (ISO, and the loop's "YYYY-MM-DD HH:MM CT"); it is silent
  past 24h and reads "just now" for a stamp up to 15 minutes ahead. Known and
  accepted: the CT parse takes Chicago's offset from now, so a stamp read
  across a DST switch is off by an hour that night.
- Shading is surfaces only, never text. Every gradient runs between the
  palette's own `--srf2`/`--srf`, a hairline `--hilite`, or an existing
  low-alpha tint. No measured text contrast moves.
- The brand is an inline SVG candle mark plus the wordmark. The favicon is the
  same mark on `#0C0E11`, and `legal.html` uses the identical one. Change one,
  change all three.
- Loading states: `stageMsg` appends a `.busybar` for in-progress strings;
  boards boot with shimmer rows. Both stop under `prefers-reduced-motion`.
- The honesty box is a three-column grid (Freshness / Sources / Limits) at
  11.5px, every sentence verbatim, with the attribution line as its own credit
  row.
- A focused ticker's tape tile, rail row and board rows all carry `.foc`.
- `expHTML` / `EXP_OPEN` holds open state in a JS object, deliberately not
  `localStorage`: boards rewrite innerHTML every 30 seconds, but a fresh load
  starting decluttered is the feature. Its click delegate runs in capture
  phase with `stopPropagation`. Its only remaining consumer is the chart-notes
  toggle; every "what this means" button was removed 2026-09-03. `finMethod`
  is still built as the canonical wording store but no longer rendered.
- The `#chartread` tap-to-read node never leaves its original DOM position.
  A `.floating` class repositions it with `position:absolute` computed from
  the tapped chart's box; moving the node itself put it inside
  `#stagetabbody`, which the next tab switch destroyed permanently.
- Head metadata is product copy: description, Open Graph, Twitter card, theme
  colors, canonical URL. Keep the "15-minute delayed" and "research, not
  advice" claims when editing them.
- The page scrollbar is thin and themed via standard properties only.
- The visible-range chip reads "+N% in view" with a tooltip: first to last
  candle on screen, following zoom and pan.

## Fetcher and publishing
- **The refresh loop cannot start earlier than 8:00am CT.**
  `market_guard.should_publish()`'s extended window opens at 8:00 sharp; a
  cron firing earlier exits immediately doing nothing. The backup crons target
  8:03am CT, past that floor and off the top-of-hour mark GitHub delays.
- **The self-redispatch chain is not a daily starter.** `loop.py` exits at the
  15:20 CT window close, so any run starting after ~09:50 CT never reaches
  `MAX_RUN_SEC` and never prints `REDISPATCH`. Every session's first run is a
  cron firing or a dispatch.
- **GitHub's `schedule` event is the measured failure point** — firings 2.6-5h
  late, and two crons still unfired at 11:38am CT on 2026-09-03. Eight `:03`
  crons across 13:00-20:00 UTC give coverage, not punctuality; the real fix is
  an external pinger POSTing `refresh-loop.yml/dispatches`, blocked on a token
  scoped to this repo. Steps in DEPLOY.md.
- **Diagnose any "nothing updated" report by reading `origin/data`'s last
  commit timestamp first.** The desk's Morning Brief tile is `data.json.brief`,
  not the Morning Brief workflow's output, so a loop that never ran freezes the
  brief, both boards, catalysts, news, Fed odds and the framework together —
  while the Morning Brief email is fine. One command separates the two systems.
- The fetcher is holiday-aware in `market_guard.py` (`MARKET_HOLIDAYS`,
  `MARKET_HALF_DAYS`), and `build_snapshot.py`'s `market_state` block calls
  those helpers rather than reimplementing the calendar. A half day shrinks the
  close to noon CT while preserving each window's post-close buffer, computed
  as an offset from 15:00.
- `compute_opt_rvol` takes its baseline snapshotted **before** today's
  `sum_vol_0_7` is appended — appending first would let a genuine outlier
  dilute the average it is measured against. `rank_big_orders` excludes
  today's row from its own baseline for the same reason.
  `UOA_HOT_MULT` (3.0) and `ACTIVITY_FLAT_PCT` (0.3) are first-pass
  heuristics.
- **HEDGING fires only for put-heavy flow while the stock is not falling** —
  the one signature free, sampled, aggregated CBOE data supports. Put-heavy
  while falling is BEARISH. Call-heavy disagreeing with price is MIXED, never a
  mirrored "hedging" claim: this data cannot tell a bought call from a written
  one.
- `fund.next_earnings.session` is normalized to the documented "AMC"/"BMO" enum
  at publication. `_earnings_session()`'s own "premarket"/"afterhours"
  vocabulary is correct for the two other fields it feeds; map only at that one
  call site. The frontend accepts the legacy spelling too.
- `load_gamma_history` / `load_consensus_history` share a known fail-soft
  weakness on purpose: a transient read error returns an empty structure and
  the next save overwrites the remote file. Hardening either means hardening
  both in one change.
- CI runs `pytest fetcher` and `pytest tests` on every PR with a read-only
  token and pinned versions.

---

# Settled questions — do not re-investigate

Each was probed live and answered. Re-deriving any of them from memory has
already wasted a session. `docs/GUARDRAIL-HISTORY.md` carries the probe
transcripts.

1. **The TradingView chart websocket cannot be reached from the browser.**
   Measured with byte-identical handshakes differing only in `Origin`.
2. **`fundamental_currency_code` does not answer the reporting-currency
   question.** It returns `"USD"` for NYSE:TM, NYSE:TSM and NASDAQ:SKHY — the
   ADR listing's converted currency, the opposite of the signal needed. Wiring
   it would replace a disclosed caveat with a false certainty.
3. **`eps_growth_next_5y` and `revenue_growth_next_year` are not real scanner
   columns** — both return null. The real ones are
   `earnings_per_share_forecast_next_fy` and `revenue_forecast_next_fy`,
   confirmed by the FY/FQ ratio landing near 4x, the shape a genuine annual
   vs quarterly consensus pair should have. `facts.eps_ntm` / `.rev_ntm` use
   the **annual** estimate deliberately, for both the 6-month and 3-month
   lookback filters; the quarterly estimate rolls over every time a quarter
   reports, which would compare two different quarters under one "velocity"
   label.
4. **No scanner column exposes a per-period end date for the ad-hoc quarterly
   arrays.** Eight candidate names all returned `{"d":[null]}` —
   indistinguishable from a deliberately fake column name, because the scanner
   has no error signal separating "not a real column" from "no data".
   `_adhocQuarterLabels`'s 3-month subtraction stands.
5. **Framework filter 1 (26-week EPS revision) has no free source.** Yahoo
   publishes nothing older than 90 days; Zacks and Seeking Alpha stop there
   too; 180-day revision history is a premium I/B/E/S-class product. Filter 3
   *is* answerable, from Yahoo's `earningsTrend` 90-day leg.
6. **"Direct competitor" cannot be derived from this vendor's data for an
   arbitrary ticker.** `sub_industry` returns null for every symbol probed;
   `industry` is coarse enough that TradingView itself files AEHR beside PLUG
   and LG Display while filing AEHR's real competitors COHU and FORM under a
   different bucket. The curated-override-then-scan design is correct for that
   constraint; `PEER_GROUPS` grows by the same pattern whenever a mismatch is
   flagged. There is no drop-in algorithmic fix.
7. **The nine-section review cycle is CLOSED** (2026-08-27). Every section
   scored 87-100 anchored against the 80 finish line. **Do not launch round 20
   without a fresh ask.** Recorded caveat: 12 verify agents died on the org
   usage limit, so 11 findings across vs-Peers, panels, flow boards and data
   honesty were never adversarially verified; those four sections' 100s mean
   "no verified findings". The unverified list is preserved in
   `docs/OPEN_ITEMS.md`.
   If a round ever is authorized: the score is **anchored, not
   reviewer-opined** — 100 − 25/blocker − 10/major − 3/minor over
   adversarially confirmed findings, floored at 0
   (`docs/review/nine-section-review.js`). Never revert to a reviewer-assigned
   impression; a fresh harsh reviewer with a finding budget calibrates to its
   own dig depth, which is a moving goalpost by construction.
8. **The feature freeze is LIFTED** (2026-08-26). Its lesson stands as
   judgement, not law: a feature added mid-round reopens review surface area.
9. **The paid-site question is closed by ruling** (2026-09-03): "too much is
   involved to make it a paid site. Just make it professional-looking for me."
   The roadmap in `docs/MONETIZATION.md` is a record, not a plan. Do not
   re-pitch it, and do not re-open the data-vendor question from memory —
   every market-data row in `docs/DATA_LICENSING.md` is Blocked for a paid
   product, resolvable only by a signed agreement, never by wording. The
   2026-06-14 "don't re-pitch paid feeds" ruling still governs the personal
   tool.
10. **Position Guard was removed** (2026-08-19). The `desk_private` blob still
   arrives in `data.json` and the page ignores it. Do not resurrect the panel
   without an explicit ask; the vault's trade-stops engine and the Morning
   Brief guard section are unaffected.
11. **Framework "building" verdicts are correct, not a symptom.** Filters 1 and
    3 read null until roughly late November 2026 and February 2027 by
    construction. Of the names reading plain BUILDING, most are ETFs and
    wrappers with no company financials at all. Nothing here is broken.
12. **Three settled non-bugs, working as designed, each already disclosing its
    own caveat** (2026-08-24 architect ruling): the chart attribution size, the
    net-flow vs Flow % scope mismatch, and Biggest Orders' gross-premium
    ranking.
13. **EMA and RSI overlays were removed from the chart.** The Fundamentals grid
    still shows a daily RSI(14) snapshot from the scanner — a different,
    unrelated reading. Do not conflate them.

---

## Decision history
Lives in the ClaudeVault repo under `market-data/flow-desk/`.
Guardrail rationale and per-round narration: `docs/GUARDRAIL-HISTORY.md`.
