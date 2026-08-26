# Flow Desk — what is still open

Written 2026-08-20, at the end of the review rounds. Everything in the
"Shipped" list below is done, verified and merged. Everything under "Open" is
work a later session can pick up. Nothing here blocks using the page.

---

## Getting to a real "done" (Zach's ruling, 2026-08-22)

Eight review rounds in, no round has cleared 80 across all nine sections at
once, and the confirmed-finding count has held flat at 26-27 per round for
three rounds running rather than dropping toward zero. Diagnosis and the
approved fix, in full:

1. **Feature work is frozen until this closes out.** The gamma-levels
   feature landed between rounds 7 and 8 and was itself a fresh source of
   round-8 findings — every feature added mid-stabilization reopens surface
   area for the next round to find, so fixing and building at the same time
   never converges. No new features land in this repo until every section
   clears the bar below, or Zach explicitly lifts the freeze.
2. **The grading tool itself had a reliability bug, now fixed.** Two
   separate rounds (7's Auto-TA, 8's Chart Stage) returned schema-valid
   placeholder garbage (`section:"test"`, a finding titled `"t"`) that
   looked like a real score until caught by hand. `docs/review/nine-
   section-review.js` now runs each section's review through the same
   content-sanity retry check (`looksLikePlaceholder`, up to 4 attempts)
   that a one-off script used to catch this manually — a broken run can no
   longer silently pass as a real score.
3. **Rounds keep running back-to-back** until the finish line below is met.
4. **The finish line changed.** "All nine sections clear 80 in the same
   single pass" chases a number the review script's own header says is not
   comparable round to round (a harsher re-read of an improved page can
   score lower with nothing having regressed). The bar is now: **zero
   unresolved confirmed findings in the "Open" section below.** Every
   confirmed finding from a round gets fixed and moved to "Shipped" the same
   day it's found, same as every round so far — the difference is the stop
   condition is "nothing left in Open," not a specific number on a specific
   day. Numeric scores are still recorded per round for trend-reading (is
   severity shifting from blocker to minor?) but are not themselves the
   pass/fail test.

---

## Scoped freeze lift, 2026-08-24 (volume profile)

Zach lifted the feature freeze explicitly for one feature only ("Lift the
freeze for the volume profile", 2026-08-24) — this does not close out the
freeze itself; see "Getting to a real done" above, whose Open-section
stop condition still applies to everything else in this repo. Shipped the
same day: a volume-profile chart overlay (VP toggle, `vpProfile`/
`vpBuildPrimitive` in `index.html`), right-side chart spacing on every
interval (`stageApplyWindow`), and the VP-suppresses-S/R declutter rule.
Full detail and the non-obvious decisions: CLAUDE.md's "Guardrails added
2026-08-24 (volume profile, Zach's freeze lift)" section.

---

## Scoped freeze lift, 2026-08-24 (gamma snapshots)

Zach lifted the feature freeze explicitly for one feature only ("Lift the
freeze for gamma snapshots", 2026-08-24) — this does not close out the
freeze itself; see "Getting to a real done" above, whose Open-section stop
condition still applies to everything else in this repo. Shipped the same
day: `gamma_history.json`, a new daily-snapshot file on the `data` branch
accumulating each ticker's `facts.<TICKER>.gamma` object plus that cycle's
spot (`build_snapshot.apply_gamma_history_cycle`/`load_gamma_history`/
`save_gamma_history`), gated on the same `write_history` flag as
history.json, purely to make a future combined GEX + volume-profile
backtest possible. Fetcher-only — `index.html` is untouched, the page never
reads this file. Full detail: CLAUDE.md's "Guardrails added 2026-08-24,
gamma snapshots, Zach's freeze lift" section.

---

## Closed by ruling, 2026-08-24

Zach directed a freeze close-out pass over this file's Open section; the
architect (Fable) ruled on these three, previously "deferred by judgement,"
items directly rather than assigning them as code work — none of the three
is a bug:

- **Chart attribution link under the 24px touch minimum.** TradingView's
  vendored Lightweight Charts library injects and sizes the in-chart
  attribution logo itself, and the logo is a license condition (see
  CLAUDE.md's 2026-08-19 vendoring guardrail) — restyling it is not this
  repo's call to make.
- **Net flow/BULL-BEAR counts every strike; Flow % counts only the
  near-money band.** Both figures already disclose the scope difference on
  every surface that shows them (row tooltips and the shared
  `flowCpMismatchHTML` mismatch pill). Narrowing `net_flow` to match Flow %'s
  band would discard a real fact — whole-chain premium — purely to make two
  numbers agree; the fetcher's job is to publish what's true, not to make
  two different questions share one answer.
- **Biggest Orders ranks gross premium, so a deep-ITM contract can lead.**
  Gross premium is the honest answer to "what traded"; ranking on extrinsic
  value instead would answer a different question. The MOSTLY INTRINSIC
  badge already flags the caveat rows rather than re-ranking them out of
  sight.

---

## Freeze lifted and review cycle resumed, 2026-08-26 (Zach's ruling)

Zach: **"Unfreeze & merge. Continue sonnet agents review to 80+ score on
all."** Three effects, all applied 2026-08-26:

1. **The feature freeze is lifted in so many words.** The two remaining
   Open items (A: ad-hoc currency signal, B: ad-hoc quarter cadence) stay
   open below as genuine vendor-data gaps — they no longer gate anything.
2. **The 2026-08-26 declutter branch merged to main** (full-width desktop,
   BB-only chart defaults, quick-read recaps, collapsible explainers — see
   CLAUDE.md's 2026-08-26 guardrails section).
3. **The automated nine-section review cycle resumed**, run with
   Sonnet-model reviewer/verifier agents, with a NEW finish line replacing
   the 2026-08-22 zero-open-findings condition: **every one of the nine
   sections scores 80+ in a single round.** Confirmed findings still get
   fixed the same day they're found, every round, as before.

---

## Round 17 — 2026-08-26, first Sonnet-agent round after the unfreeze (24 confirmed, all fixed same day)

Run via `docs/review/nine-section-review.js` (39 agents: 9 Sonnet reviewers
at high effort with the placeholder-garbage retry — it fired three times
this round and caught all three — plus one Sonnet adversarial verifier per
finding). Scores, per the standing caveat that they are not comparable
round to round:

| Section | Score | Confirmed |
|---|---|---|
| Chart Stage | 76 | 3 (1 blocker) |
| Auto-TA | 55 | 3 |
| Left watchlist rail | 70 | 4 |
| Financials | 68 | 3 (1 blocker) |
| Sector Heatmap | 78 | 3 |
| vs Peers | **80** | 1 |
| Right rail panels | 74 | 2 |
| Flow boards | 79 | 2 |
| Data Honesty | 70 | 3 (1 blocker) |

Eight of nine below the 80 bar; 24 confirmed findings, 4 refuted by the
adversarial pass. Five of the 24 were regressions from the same-day
declutter redesign (the stale quick-read on an empty chart, its focus
drop, the swing recap's scope and "multi-week" wording, the sector-dots
expander dying on sort, the money chart stretching past its viewBox once
the shell cap came off) — the freeze's own lesson, accepted knowingly
under the unfreeze ruling. The standouts among the rest: V's Fiserv peer
pin dead on the scanner (re-verified live, FISV again — the pin has now
flipped twice); the FOMC/CPI catalyst duplicates live in production
(root-caused to `_merge_econ_aliases`'s skip guard, NOT the reviewer's
proposed `_catalyst_still_fresh` cause — the verifier's correction was
right, and the latent future-date backfill bug got fixed alongside);
`TA_BREAK_CONF` never volatility-scaled (an ordinary AAOG wiggle graded
as a confirmed BREAKOUT); and `isLeveraged()`'s bare "ultra" false-tagging
Ultra Clean Holdings — the third real-company false positive from that
regex. All 24 fixed the same day (fetcher: 2 fixes + 2 new tests, 333
passing; the rest frontend). One finding closed by documented ruling
rather than code: TA_SR_MAX_DIST's flat 20% vs the scaled trend-line
distance is a deliberate design difference (a level is a measured shelf;
a trend line is a projection) — now stated at the constant and in
TIPS.ta_sr. Non-obvious decisions: CLAUDE.md's round-17 section.

---

## Open — in the order they are worth doing

### 1. Automated review cycle RESUMED 2026-08-26 (paused 2026-08-23 → Fable architect pass → resumed at Zach's explicit ask)

The round-16 fix pass closed all 25 confirmed findings the same day they were
found (see that section below). Per Zach's instruction, the automated
round-fix-launch cycle stopped there rather than launching round 17.

A Fable-model architect pass then read CLAUDE.md, `docs/OPEN_ITEMS.md`
(including this section's own deferred-by-judgement list) and DATA_CONTRACT.md
in full, then the entire fetcher and the entire `index.html`, looking
specifically for what a fixed nine-section rubric structurally misses:
whole-pipeline calendar correctness, frontend assumptions cross-checked
against what the fetcher actually publishes (not what a comment claims), and
doc/payload drift. It found 14 items (one blocker) across two fetcher-only
findings groups and three frontend/cross-file groups. **All 14 were fixed the
same day** in the Sonnet follow-up pass — see "Shipped 2026-08-23, Fable
architect pass" below for the full writeup. Three new test files
(`test_market_guard.py`, plus additions to `test_flow_pct.py` and
`test_context.py`, plus `test_sync_constants.py`) bring the fetcher suite to
314 passing tests.

The automated round-N review cycle stayed paused from 2026-08-23 until
Zach's explicit ask on 2026-08-26 ("Continue sonnet agents review to 80+
score on all") — see "Freeze lifted and review cycle resumed" above. Rounds
run `docs/review/nine-section-review.js` with Sonnet agents and continue
until all nine sections clear 80 in one round; per-round results are
recorded below as before.

### 2. Deferred by judgement, not by omission — both re-measured 2026-08-24, both still stand

Both items below were investigated LIVE against `scanner.tradingview.com`
during the 2026-08-24 freeze close-out pass (Zach's instruction: "address
what is left in Open so the freeze can close"), not re-argued from memory.
Both probes came back negative — see the exact requests/responses in each
item. No code changed for either.

- **The ad-hoc/scanner Financials fallback (`adhocEnsureFundamentals`)
  hardcodes `currency: "USD"` for every off-desk (non-pinned) ticker.** Round
  13 added this deliberately, replacing a `null` currency that wrongly
  flagged the far more common case (an ordinary US company reached via
  search) as "may not report in dollars." Round 14 confirmed the flip side:
  a genuine foreign issuer reached via search (an ADR like Toyota/TM) now
  gets a false "filed in US dollars" claim instead. Round 15 added a scoped
  on-screen caveat ("Reporting currency was not checked for this searched
  ticker...") for this specific path instead of a silent "Statements are
  filed in US dollars" claim — a mitigation, not a fix.
  **2026-08-24 measurement:** probed whether TradingView's scanner exposes a
  `fundamental_currency_code` column that would give a real per-ticker
  signal. It exists and returns non-null ISO codes, but the codes are
  wrong for exactly the two cases that matter — it returns `"USD"` for
  `NYSE:TM` (Toyota; real reporting currency is JPY) and `"USD"` for
  `NYSE:TSM` and `NASDAQ:SKHY` (both documented in `context.py`'s
  `KNOWN_NON_USD_CURRENCY` as TWD/KRW respectively). Live request/response:
  `POST https://scanner.tradingview.com/america/scan` with
  `{"symbols":{"tickers":["NASDAQ:AAPL","NYSE:TM","NYSE:TSM"]},
  "columns":["fundamental_currency_code","currency","description"]}` →
  `{"data":[{"s":"NASDAQ:AAPL","d":["USD","USD","Apple Inc."]},
  {"s":"NYSE:TM","d":["USD","USD","Toyota Motor Corp. Sponsored ADR"]},
  {"s":"NYSE:TSM","d":["USD","USD","Taiwan Semiconductor Manufacturing
  Co., Ltd. Sponsored ADR"]}]}`; `NASDAQ:SKHY` alone returned the same
  `["USD","USD","SK hynix Inc. Sponsored ADR"]`. The column appears to
  report the ADR listing's own converted/normalized currency, not the
  underlying issuer's financial-statement currency — the one fact this
  fix needs. Wiring a column that confidently claims USD for the two known
  non-USD probe cases would REMOVE the round-15 caveat and replace it with
  a false "checked, and it's dollars" claim, a regression CLAUDE.md's
  "never weaken a disclosure" rule forbids. Left open; would reopen only if
  a different, unprobed column is found that returns JPY/TWD/KRW correctly
  for these three names.
- **The ad-hoc/scanner Financials fallback's quarter labels
  (`_adhocQuarterLabels`) assume a strict 3-month cadence**, mechanically
  subtracting 3 calendar months per column from a single known end-date
  scalar — there is no equivalent to the sidecar path's `periodsPerYear`
  cadence check, because TradingView's scanner columns for this path don't
  expose each individual period's own end date to validate against.
  **2026-08-24 measurement:** probed for a per-period end-date/cadence
  column on the same endpoint, against `NASDAQ:AAPL`. Tried
  `report_period_h`, `fiscal_period_end_fq_h`, `earnings_release_date_h`,
  `earnings_release_next_date_fq_h`, `fiscal_period_fq_h`,
  `period_end_date_fq_h`, `report_date_fq_h`, `fiscal_period_end_ttm_h` — all
  eight returned `{"d":[null]}`, byte-identical in shape to a deliberately
  fake column name probed for comparison (`totally_fake_column_xyz` also
  returned `{"d":[null]}`). The scanner gives no way to tell "this column
  doesn't exist" from "this column exists and has no data" — either way,
  there is no per-period date signal to validate cadence against for this
  path. `fiscal_period_end_fq` (no `_h` suffix, already read as `endEp`)
  remains the only date field, one scalar for the newest period only, which
  is exactly what the existing code already uses. No new column to wire;
  left open per the round-14 writeup's own reasoning, now backed by a
  measurement instead of an assumption.
- **The chart's own attribution link** is 35x11 on a phone, under the 24px
  touch minimum. Lightweight Charts injects and sizes it; restyling a vendor's
  attribution is not ours to do. **Closed by ruling, 2026-08-24** — moved to
  Shipped below; not a code fix, a scope call.
- **Net flow and the BULL/BEAR pill count every strike; Flow % counts only
  strikes within 20% of spot.** **Closed by ruling, 2026-08-24** — moved to
  Shipped below.
- **The biggest-orders board ranks gross premium**, so deep in-the-money
  paper can lead on money already in the strike. **Closed by ruling,
  2026-08-24** — moved to Shipped below.

### Freeze status, 2026-08-24 — SUPERSEDED 2026-08-26 (Zach lifted the freeze outright; see "Freeze lifted and review cycle resumed" above)

The freeze's own stop condition ("Getting to a real done" above) is **zero
unresolved confirmed findings in this Open section.** As of this pass, Open
holds exactly the two items above (A: currency signal, B: quarter cadence),
both re-measured live this session and both still genuinely blocked on a
vendor data gap, not on unstarted work — every other item that was ever
in this section (three ruling-closed items, plus everything the round-N
and Fable-architect passes found) is Shipped. The freeze does not lift on
this pass: it lifts the moment either A or B gets a real signal (a
different scanner/vendor column that returns correct non-USD currencies
for TM/TSM/SKHY, or a real per-period date field for the quarterly
arrays), or Zach rules the two remaining items closed the same way he
closed C/D/E above. Nothing else is blocking "done."

---

## Shipped 2026-08-23, Fable architect pass (14 findings, all fixed)

A Fable-model architect pass — the follow-up to pausing the automated
round-N review cycle after round 16 — read the full guardrail history first,
then did an independent, cross-file pass over the whole fetcher and the
whole `index.html`, deliberately looking for what sixteen rounds of a
per-section rubric structurally miss. It found 14 items (1 blocker, 2 major,
11 minor/hardening) and none of the four already-documented deferred-by-
judgement items were re-flagged. All 14 were fixed the same day. Summary:

- **Fetcher calendar correctness (1 blocker):** the fetcher had ZERO market-
  holiday awareness anywhere — `market_guard.py`'s `_in_window` and
  `build_snapshot.py`'s own `market_state` block were pure weekday+clock
  tests. On a weekday market holiday (Labor Day 2026-09-07 was 15 days from
  this pass), the backup cron would have started the loop, `market_state`
  would have read `"open"`, and `write_history=True` would have fabricated a
  full phantom session into `history.json`, `iv_history`, `vol_history`,
  `swing_first_seen`, `etf_so` and `big_orders` from stale weekend/holiday
  vendor data — exactly the corruption the `write_history` guard exists to
  prevent, defeated for every weekday holiday. Fixed by adding
  `MARKET_HOLIDAYS`/`MARKET_HALF_DAYS` tables to `market_guard.py`, mirrored
  EXACTLY from `index.html`'s own tables (`is_market_holiday`/
  `is_market_half_day` reject a holiday outright; a half day shrinks the
  session close to noon CT with each window's own post-close buffer
  preserved). `build_snapshot.py`'s `market_state` block now calls these
  helpers directly. New `test_market_guard.py` (5 tests) pins the behavior
  at the day-boundary edges.
- **Frontend/fetcher/contract drift (5 findings, 1 major):** `universe.candidates`
  excluded the five TRACK_ONLY names (quote-only by design, never
  chain-fetched), contradicting DATA_CONTRACT.md's own definition — as a
  direct result, the flow boards' coverage footer printed a FALSE
  vendor-failure claim ("5 of your 62 watched names resolved no live quote
  this cycle") on every single healthy cycle. Fixed contract-first: `candidates`
  now means every quote-resolved name (TRACK_ONLY included, matching
  `len(quotes)`); a new `chain_eligible` field carries the old (TRACK_ONLY-
  excluded) count for the chain-coverage comparison; `boardEmptyHTML`/
  `boardCutEmptyHTML`/`boardCoverageHTML` all updated, with a fallback to
  `candidates` for a payload published before `chain_eligible` existed.
  Also fixed: `fund.next_earnings.session` was published in three different
  vocabularies (AMC/BMO from stockanalysis, premarket/afterhours from a
  TV-timestamp path, tested for pre/post by the chart header — a dead
  branch); the fetcher now normalizes the TV-timestamp path's spelling to
  the documented AMC/BMO enum, and the frontend accepts the legacy spelling
  for already-published sidecars. The published `notes.delay` string still
  claimed stock prices "update live," contradicting the site's loudest
  guardrail — corrected to match DATA_CONTRACT.md's own text. DATA_CONTRACT.md
  contradicted itself on how `big_orders_capped.earned` is measured (one
  paragraph described the pre-round-6 naive-slice measurement, a different
  paragraph the current whole-pool one) — the stale paragraph rewritten to
  match the code. `etf_flows`' split-day payload published `streak: 0` and a
  dated `baseline_session` when `flow_1d` was null, violating the contract's
  own "both null when flow_1d is null" rule — fixed, with a new assertion in
  `test_flow_pct.py`'s existing split test.
- **Fetcher state integrity (1 major):** Swing's cross-day `swing_first_seen`
  memory (the round-10 "since flagged" fix) was erased by ANY single-cycle
  chain hiccup — the cleanup loop deleted an entry the instant a ticker was
  absent from one cycle's board, even a transient CBOE timeout, silently
  re-baselining the chase chip at that moment's spot instead of the name's
  real first-flagged spot from weeks earlier. Fixed with a `last_seen`
  timestamp per entry: an entry now survives any absence within the same
  trading session and is only deleted once its `last_seen` falls behind the
  prior published session (absent for a full session, not one ~7-minute
  cycle).
- **Frontend correctness (4 findings, all minor):** the 1W chart had no
  boot-race rebuild equivalent to 1D's — a weekly chart rendered before the
  first live quote landed never gained its forming-week candle. Fixed by
  extending `stageLivePoke`'s boot-race guard to 1W and adding a per-symbol/
  per-interval one-shot flag (`STAGE.bootRebuilt`) so both the 1D and 1W
  guards are provably single-shot (cleared on symbol change and interval/
  window clicks). The new `fwSignedFixed` framework-filter formatter (added
  in round 16 itself) printed an ASCII hyphen for negatives, breaking the
  page-wide U+2212 convention its own neighbors enforce — fixed, plus the
  `fcf_growth` row's separate formatting. `rowHTMLConv` duplicated
  `flowPctHTML`'s $100K-floor/thin-basis logic inline instead of calling the
  shared helper — refactored to call it (rendered markup unchanged). The
  command palette's ticker hint could print "on the desk · on the desk" for
  a name with no quote yet — fixed.
- **Hardening (3 sync tests, no live bug):** added `test_sync_constants.py`,
  pinning three previously-untested cross-file constant pairs equal: TRACK_ONLY
  (fetcher) vs TRACK_ONLY_SYMS (frontend), the Morning Brief's
  high_conviction threshold vs BOARD_SCORE_FLOOR, and the two holiday tables
  from the calendar fix above — in the same deliberately-dumb regex style as
  the existing `test_tips_sync.py`, so the next drift in any of these three
  pairs fails a test instead of shipping silently.

`node --check` and the full pytest suite (314 passing — 306 + 5 new
market_guard tests + 3 new sync_constants tests) both green.

## Shipped 2026-08-23, round 16 (25 findings confirmed, all fixed) — last automated round before the Fable architect pass

All 9 sections scored below 80 (Chart Stage 70, Auto-TA 73, Left watchlist
rail 83, Financials 68, Sector Heatmap 76, vs Peers 80, Right rail panels 80,
Flow boards 64, Data Honesty 84). Every confirmed finding was fixed the same
day — no fetcher changes this round, all frontend JS. Summary by section:

- **Chart Stage (3 fixed):** the ad-hoc (searched-ticker) daily chart branch
  never got round 14's clock gate (`ctMinutesOfDay(new Date()) >= 3*60`) that
  stops a stale overnight quote from becoming a phantom "today, closed"
  candle before the market opens — added, matching the pinned-symbol branch
  exactly. The one-time "boot race" rebuild in `stageLivePoke` was gated on
  `quadsRaw(STAGE.sym)`, always null for a searched ticker, so a chart could
  freeze at yesterday's close forever if `adhocEnsureDaily` resolved before
  `pollTvPrices` populated `LIVE[sym]` — now also accepts
  `ADHOC_BARS[STAGE.sym] && ADHOC_BARS[STAGE.sym].D`. The 4H "bars through
  HH:MM CT" freshness chip read the bucket's OPEN time (needed for correct
  candle x-position), understating freshness by up to ~4 hours — `resample4H`
  now tracks a separate `row[6]` last-merged-bar time, threaded through as
  `STAGE.lastBarUpdate`, which the chip reads instead.
- **Auto-TA (3 fixed):** the "trend" toggle's tooltip stated a flat 12/40-bar
  rule true only on 1D (off by 4-6x on every other interval) — now built from
  `taFreshBars()`/`taMinWinForTrend()` at render time via a new `taTrendTip()`
  function. The triangle/wedge/flag shape caption's `TA_SHAPE_MIN_MOVE`
  (a flat 2% net-move threshold) was the one threshold in the whole fitter
  never routed through `taAmvForInterval` — added `taShapeMinMove(sym)`,
  scaled the same way `hugTol`/`taContainTol` already are.
  `taLevels`'s S/R inclusion filter measured distance from the cluster's
  arithmetic MEAN while every other part of the feature (the axis badge, the
  wide-band draw block) measures from the near EDGE actually drawn — a level
  whose mean sat just past the 20%-of-price limit while its near edge sat
  well inside it was dropped from the levels array entirely; now measured
  from `min(|hi-last|,|lo-last|)`.
- **Left watchlist rail (2 fixed):** the ticker-search dropdown's session/ext
  chip was appended inline inside `.tsr .ch` (flex:none, no shrink target),
  so it could push the row past the rail's fixed ~220-250px width and hide
  the add/remove button entirely — moved to its own second-line slot
  alongside `.nm`, which already handles overflow. `wlSort` was a plain
  in-memory variable that always booted back to "groups" — now persisted to
  `localStorage` (`desk.wl.sort`) the same way custom adds, hidden pins and
  the mobile collapse flag already are.
- **Financials tab (3 fixed):** `yoyDenomDiscontinuous`'s null-neighbor bailout
  meant it never fired on NBIS's real Q3'23 discontinuity (idx=0, no left
  neighbor, a null right neighbor) — both candidates got filtered to
  `nb.length===0` and the check returned false via its own empty-array
  bailout, letting a fake -98.5% YoY collapse print next to real +350%-to-
  +770% bars. Now walks outward past a null to the next REAL value on each
  side. `fmtAxisNum` never got `fmtAxisPct`'s own minus-sign fix, so a
  negative EPS legend showed a plain ASCII hyphen while the axis tick and
  tooltip for the identical value both used the real minus sign (U+2212) —
  fixed. The duplicate-quarter caption said "revenue and/or EPS" but the
  actual check (since round 8) requires BOTH to match exactly — reworded to
  "revenue AND EPS."
- **Sector Heatmap (3 fixed):** `HEAT.lastFetchFailed` was one shared boolean,
  not keyed per universe like `HEAT.data`/`HEAT.inflight` — a failed fetch on
  one universe (mid-switch) could falsely mark a DIFFERENT universe's fresh,
  successful fetch as stale; now `HEAT.lastFetchFailed[univ]`. The expanded
  map's hardcoded `210px` header-offset constant ignored the top rail's own
  mobile wrapping (`.rail` flex-wraps at <=1080px, is never hidden by any
  heatwide-mode rule) — added `heatMeasureHead()`, mirroring
  `heatMeasureFoot()`'s own real-measurement approach, publishing
  `--heathead-h`. "Energy Minerals" (XOM's real sector) had no
  `HEAT_SEC_SHORT` medium form while every sibling long sector name did —
  added.
- **vs Peers tab (2 fixed):** a curated peer unresolved because the scanner
  POST itself failed was told "usually a company that changed listing" —
  `adhocFactsBatch` now returns whether the REQUEST succeeded (not whether
  every symbol resolved), threaded into `peersFor`'s curated branch as
  `unresolvedScanFailed`, which the disclosure text now reads to give the
  correct two-reason wording (mirroring `_peersByIndustry`'s own
  `scan-failed` wording). Resizing the window while vs Peers was open
  re-entered a full `peersFor()` network fetch for any curated set that
  hadn't fully resolved, even though only the SVG geometry needed to change
  — `renderPeersTab` gained a `widthOnly` parameter that reuses
  `PEERS_CACHE`/`PEERS_LAST` directly via `renderPeersInto` instead.
- **Right rail panels (3 fixed):** the Safe havens table (GLD/TLT/IEF/TIP/BIL)
  had no `data-sym`/`role`/`tabindex` at all, unlike the sector table three
  lines above it — added, matching exactly. Catalyst rows and news rows were
  both mouse-clickable (`[data-sym]`) but keyboard-unreachable (no
  `role="button"`/`tabindex="0"`, so the keydown delegate never matched and
  the row wasn't even a Tab stop) — added to both row templates.
- **Flow boards (4 fixed):** `boardEmptyHTML` checked `with_options===0`
  before `candidates`, so a total TradingView quote-vendor outage (which
  makes `candidates===0` and `with_options===0` follow automatically, with no
  CBOE chain ever attempted) was misdiagnosed as a chain-vendor outage — now
  checks `cand===0` first and names the TradingView quote step specifically.
  `table()`'s periodic full re-render restored keyboard focus (round 15) but
  never a hovered tooltip, so a live/snapshot drift tooltip (e.g.
  Conviction's RVOL cell) held open with the mouse froze on stale numbers
  every 30-second poll — added the same capture/restore pattern `renderTape`
  already uses, keyed on the row/header plus the hovered `[data-tip]`
  element's index within it. The `cut.rows.length===0` "no names score 60+"
  message was a hardcoded "quiet tape" sentence regardless of coverage,
  which could flatly contradict `boardCoverageHTML`'s own partial-outage note
  printed one line below it — new `boardCutEmptyHTML()` routes through the
  same candidates/with_options check `boardEmptyHTML` already does for the
  `arr.length===0` case. The Flow%/C-P mismatch "counts ≠ $" pill existed
  only on the Conviction board row — factored into a shared
  `flowCpMismatchHTML()` and called from both the board row and
  `stageFlowSecHTML`'s Options flow detail panel (same "one function, every
  surface" convention as `taSrSide`/`fedLegPct`).
- **Data Honesty (2 fixed):** the watchlist's "volume" sort had zero
  staleness handling — `liveStale()` trips after 75s with no fresh scanner
  read, guarded against in six other places on this page, but not here —
  added the same stale-sinks-to-bottom comparator term the "chg" sort already
  has. None of `FRAMEWORK_FILTER_ROWS`'s five `fmt()` functions guarded
  against JS's signed-zero rounding (`(-0.3).toFixed(0)==="-0"`) the way
  `fm1`/`sign1` elsewhere do — a tiny negative reading (e.g. a -0.3bps YoY
  margin contraction) rendered as a literal "-0 bps" next to a red FAIL
  badge, reading as flat/zero rather than "very slightly negative" — added a
  shared `fwSignedFixed()` helper used by all five rows.

## Shipped 2026-08-23, round 15 (26 findings confirmed, all fixed)

All 9 sections scored below 80 (Chart Stage 64, Auto-TA 70, Left watchlist
rail 66, Financials 47, Sector Heatmap 52, vs Peers 60, Right rail panels 76,
Flow boards 64, Data honesty 76). Every confirmed finding was fixed the same
day. Full per-finding detail lives in the review transcript; summary by
section:

- **Chart Stage (1 fixed):** the weekly chart's premarket live-poke read the
  PRIOR completed week's close (`STAGE.rows[wn-2]`) as "yesterday" on every
  weekday except Monday, corrupting the forming week's open/high/low with a
  stale reference. Fixed by adding `STAGE.weekPrevClose` — the forming week's
  own last REAL daily close, computed once in `intervalDataFor` and threaded
  through `stageViewData`/`stageRender` — and reading it instead of indexing
  into the mutable weekly `STAGE.rows` array. The premarket branch also now
  folds any already-recorded weekly open/high/low into the poke instead of
  overwriting them outright.
- **Auto-TA (3 fixed):** `taFreshBars()` had no ceiling, so 15m/1H's
  interval-scaled minimum bar count could exceed the browser's own max fetch
  window, permanently reading "too short" — added `TA_REALISTIC_MAX_BARS`.
  `TIPS.ta_trend` claimed a flat 1%/1.2% touch/poke tolerance on intraday
  views that the code doesn't actually use (tolerances scale by avg_move on
  every interval) — corrected. The flag/pole lookback anchored to `win[0]`
  (whatever range button happened to be active), reporting a different
  percentage for the same pattern depending on the chart's zoom — anchored to
  a fixed `TA_FLAG_POLE_LOOKBACK` window instead.
- **Left watchlist rail (3 fixed):** `railRowHTML` computed an unused `q`
  variable before calling `dispQuote` — dead code cleanup, no behavior
  change. `earnCountdownDays` never fell through to `earnDaysNow` when the
  fund-cache-derived count had gone negative (a stale cached earnings date),
  now guards on `d>=0`. MOVERS counted stale rows toward its own cap/overflow
  math — split into `hot` (all rows, preserving individual STALE tags) and
  `hotFresh` (used only for the cap/overflow/tab-title numbers).
- **Financials tab (3 fixed):** the YoY chart could silently divide by a
  denominator from a different fiscal regime (a spinoff, a restated prior
  period) with no disclosure — added `yoyDenomDiscontinuous`, an
  isolation-test (same philosophy as `robustClampMag`) that nulls a YoY point
  when its denominator is 8x+ off both neighbors and flags the chart. The
  tap-to-read readout's floating position didn't scope to the tapped chart's
  own column width. The Annual section silently disappeared for any filer
  with a non-4-quarter cadence with no explanation — added a caption note.
- **Sector Heatmap (2 fixed):** a bare tile (`data-bare="1"`) needed its tooltip marked "tapped"
  on first touch so a second tap opens the chart, not the first — the
  mouseover delegate now sets `data-tapped` for exactly this case.
  `nVolMismatch` had a stray post-cap recompute that double-counted rows —
  removed, restoring the single accumulate-once-during-mapping value.
- **vs Peers tab (3 fixed):** a failed peer-facts batch fetch (TradingView
  scanner returned symbols but no matching `factsOf` data for any of them)
  cached as a real, data-free "peer" set forever — added a `batchFailed`
  check forcing `source:"scan-failed"` so it retries. The zero-metric
  fallback replaced the WHOLE section (key, srcLine, curated/scan-source
  note) with one bare sentence and left no `.gwrap` for a later-resolving PEG
  chart to insert into — now preserves `key`/`srcLine` and always renders an
  (initially empty) `.gwrap`. Both `pbColW` (vs Peers) and `SM.W`
  (Financials) clamped their column width to 460px while `.gchart`'s own CSS
  caps `max-width` at 420 — both clamps corrected to 420.
- **Right rail panels (3 fixed):** the Fed-odds card and its rail chip had no
  staleness signal anywhere despite `context.py`'s cache-merge leaving a bad
  fetch's last-good value in place indefinitely — added `fed.stale` (derived
  from `f.asOf` age against a new `FED_ODDS_STALE_MS`, 3 hours) threaded into
  the rail chip's tooltip/text and the card's `.fedsrc` line. The catalysts
  panel could show the same FOMC-day event twice — `_dedup_econ`'s
  substring-based title match missed alias pairs `_merge_econ_aliases`
  itself later matched and copied numbers FROM, without ever removing the
  now-redundant TV row; fixed by removing the matched TV row from `out` after
  the merge, and added a "Fed Chair Press Conference"/"Fed Press Conference"
  alias pair neither mechanism previously caught. The Fed-odds card's
  countdown silently dropped once a meeting date passed instead of saying so
  — added an explicit `dLeft<0` branch (normally unreachable, but reachable
  in combination with the staleness bug above during an extended outage).
- **Flow boards (5 fixed):** sorting ANY board with the keyboard (Enter on a
  sortable `<th>`) destroyed keyboard focus on every redraw, since `table()`'s
  `draw()` fully rewrites `innerHTML` with no focus-preservation of its own —
  the exact bug the watchlist rail's `renderWL` already solved. Applied the
  identical capture/restore pattern (keyed on `data-k` for a header, `data-sym`
  for a row) inside `table()` itself, which also fixes the 30-second live-poll
  redraw dropping focus from a tabbed board row (same root cause, same fix).
  Conviction's RVOL column header tooltip claimed "the column sorts on the
  number you can see," false whenever the freeze mechanism (added round 11)
  is holding the last real sort's order against the ticking live value —
  reworded to describe the freeze accurately. The ETF board's single
  aggregate staleness stamp (`ef.flow_session`, published as the MAX/freshest
  of every fund's own `flow_session`) made one stalled fund invisible while
  its peers kept updating — added a shared `sessionsBehind()` helper used by
  both the header and a new per-fund "Nd behind" badge. ETF rows were the
  only board rows in the file with no `data-sym`/`role="button"` — added,
  matching every other board's row convention exactly.
- **Data honesty (3 fixed):** Filter 5's FAIL badge could show two numbers
  that both look like a PASS (FCF growing faster than revenue) because the
  real rule ANDs in an undisclosed `ttm_fcf_now > 0` condition — the fetcher
  now publishes `metrics.ttm_fcf_positive` and the frontend appends "(TTM FCF
  still negative)" to the row when that's the actual reason for the FAIL;
  `TIPS.framework` and `DATA_CONTRACT.md` corrected to state the real
  two-part rule. Searched (non-pinned) foreign-issuer financials got a flat,
  server-confirmed-looking "Statements are filed in US dollars" claim with no
  caveat that this specific path never actually checked — added a scoped
  caveat for `fund.source==="scanner"` (see the deferred item above for why a
  full fix isn't shipped here). The Fundamentals grid's RSI cell rounded for
  display (`Math.round(f.rsi)`) but its overbought/oversold color used the
  raw unrounded value — a reading in [69.5,70) or (30,30.5] could print "70"/
  "30" uncolored while an exact 70.0/30.0 colored, showing the same visible
  number two different ways; `fundCls("rsi", ...)` now rounds before
  thresholding, same convention as `taSrSide`/`taTrendFlipped`/`fedLegPct`.

## Shipped 2026-08-23, round 14 (21 findings confirmed, 19 fixed, 2 deferred)

Scores before this pass: Chart Stage 38, Auto-TA 78, Left watchlist rail 68,
Financials 64, Sector Heatmap 76, vs Peers 85, Right rail 74, Flow boards 82,
Data honesty 72. Two findings (both Financials, ad-hoc currency and ad-hoc
quarter cadence) are documented as deferred in the "Open" section above
rather than shipped with a partial fix — see that section for why.

**Chart Stage (3 findings)**
- A fabricated, undimmed "today, closed" candle appeared every weekday
  between midnight and 3:00 AM CT — `stageDailyData`'s closed-branch and
  `seriesQuads`' equivalent both checked `isTradingDay(now)` but never the
  CLOCK, so `live` (still yesterday's settled close) got stamped with
  today's date. Added `ctMinutesOfDay(new Date()) >= 3*60` to both gates.
- Clicking the log-scale button silently discarded the chart's zoom/pan on
  every click — wrapped in `stageKeepView`, matching the TA toggle buttons.
- Over a weekend/holiday, `stageLivePoke`'s boot-race guard never saw
  `STAGE.synthetic` go true (correctly, since `stageDailyData` withholds the
  synthetic bar on a non-trading day), so it stayed satisfied forever and
  reset the chart's zoom/pan every 30-second poll. Added `isTradingDay(new
  Date())` to the guard and wrapped its render in `stageKeepView`.

**Auto-TA (3 findings)**
- Rail-wide Bollinger "Band crosses" read `q.px` (yesterday's regular close
  pre-market, per `rtc`'s own documented behavior) instead of a
  session-aware value — the one alert panel built to catch a pre-market band
  cross couldn't see one. Changed to `candleClose(q)`, matching the on-chart
  BB overlay.
- The post-break POST_TOL slack containment check read the raw high/low wick
  (`rows[z][side]`) instead of `containLeg` (closes on 1D/1W) — the
  anchor-to-anchor containment check three lines up already made this switch
  in round 12 for exactly this reason. Fixed the one remaining gate.
- A flipped (broken) trend line lost its "broken" label the moment price
  retested it — the `atLine` override unconditionally replaced `name` with
  no `flipped` check. Preserved the prefix: `name = (flipped?"broken
  ":"")+label+" (at the line)"`.

**Left watchlist rail (3 findings)**
- Rail's per-row earnings countdown used the uncorrected TradingView date,
  disagreeing with the chart header/Fundamentals grid (already fixed in
  round 12) by up to a week for the same ticker. New shared
  `earnCountdownDays(sym, f)` helper prefers `FUND_CACHE[sym].next_earnings.date`
  when already cached, falling back to `earnDaysNow(f)` — wired into the
  rail row and Conviction's "E Nd" pill.
- Custom watchlist add/paste failed completely silent if `localStorage`
  writes fail (blocked storage, strict privacy mode). Added an in-memory
  mirror (`WL_MEM`) so a click registers for the session even when the
  underlying write fails, plus a visible warning when it does.
- Bulk-paste could report the same ticker as both "removed" and "already
  pinned"/"unhidden" in one message — a stale custom entry for a
  rail-promoted ticker satisfied both conditions. Excluded `railHasSym`
  tickers from the `removed` computation.

**Financials (1 of 3 findings fixed; 2 deferred, see Open section)**
- The narrow (<=760px) branch hardcoded `BIG.W`/`SM.W` to 380/340 regardless
  of the real host width, unlike the desktop branch's own measurement — on a
  ~320px phone this rendered 11px axis text under 8px. Now measures `hostW`
  in the narrow branch too, clamped to a phone-appropriate range.

**Sector Heatmap (3 findings)**
- S&P 500/Nasdaq 100 maps mixed dollar-volume into market-cap-sized tiles
  for any row with a transient missing market cap (the exact bug already
  fixed for the Desk map) — a byVol row's `cap` field had already been
  overwritten with a 500-1000x-smaller dollar-volume figure upstream, for
  every universe. Now excluded entirely from the sized set for non-DESK
  universes, with a new footer disclosure count.
- Every heatmap toolbar/sector-header click destroyed keyboard focus (a
  full `innerHTML` rebuild on every render, including the one triggered by
  the just-clicked button). Capture a stable key (`data-hu`/`data-htf`/
  `data-hsec`/id) before rebuild, restore focus to the matching new element
  after — both `renderHeatBar` and `heatRender`'s wrap rebuild.
- Expand mode's height floor was self-defeating: `min-height:min(420px,
  calc(...))` used the SAME calc() as `height`, so it never actually added a
  floor — a phone in landscape collapsed the map to ~135px. Replaced with a
  flat, always-enforced `min-height:240px` (a genuine legibility floor, well
  under the default view's 420px so round 11's original overflow problem
  doesn't return in full).

**vs Peers (3 findings)**
- `peerBarsSVG` used a hardcoded 300px viewBox regardless of the real
  measured column width, unlike the Financials tab's identical chart kit
  (fixed in round 12) — text rendered at up to ~1.4x its authored size. Now
  measures the real `.gwrap` column width the same way `renderGrowth`'s
  `smAvail`/`smCols`/`smColW` already do, and passes it via `opts.W`.
- The 10s peer-scan timeout was shorter than the documented worst-case
  4-sequential-round-trip path for a genuinely searched/off-desk symbol.
  Raised to 20s.
- The ✳ (confirmed 5x+ size mismatch) and ? (unknown size) peer-key marks
  shared one style, reading equally alarming despite meaning different
  things. Gave "?" its own muted `.oob.unk` style.

**Right rail + top rail (2 findings)**
- The tape's 1-second render loop unconditionally rewrote every tile's DOM
  node, silently defeating keyboard focus (Tab+Enter stopped working after
  any ~1s dwell) and freezing an open tooltip on stale text indefinitely
  (mouseover doesn't re-fire on a mutation with no pointer movement).
  `renderTape` now saves/restores focus and re-invokes `showTip` for the
  hovered tile across the rewrite.

**Flow boards (2 findings)**
- Biggest Orders never called `boardCoverageHTML()`, unlike Conviction and
  Swing, despite building `big_orders` from the identical per-ticker
  chain-resolution loop — a partial CBOE outage left the board looking
  normal with no sign some tickers were silently excluded. Wired in.
- Swing's earnings-countdown badge read `c.earnings_days` straight off the
  payload with no elapsed-day correction, unlike Conviction's identical
  badge (`earnDaysNow`). Now ages it the same way:
  `earnDaysNow({earn_days: edRaw})`.

**Data honesty (2 findings)**
- Same root cause as the left-rail earnings-countdown finding — Conviction's
  "E Nd" 0-7 day pill also read the uncorrected TradingView date. Fixed by
  the same `earnCountdownDays` wiring.

Scores before this pass: Chart Stage 60, Auto-TA 58, Left watchlist rail 76,
Financials 74, Sector Heatmap 66, vs Peers 62, Right rail panels 72, Flow
boards 62, Data honesty 74.

**Chart Stage (3 findings)**
- Searched-ticker weekly chart falsely called real Friday data "CLOSE ONLY"
  and dimmed it every weekend/holiday — `wSynth` had no `isTradingDay(today)`
  term, unlike its three sibling code paths. Added the guard.
- `isLastTradingDayOfWeek()` walked into next week on a Sunday (`wd===0`),
  wrongly returning false. Special-cased Sunday to return true immediately,
  mirroring Saturday's existing (accidental) correctness.
- `seriesFull()` duplicated the latest close into the 50-/200-day legend on
  every non-trading day, desyncing it from the chart's own MA line. Gated the
  live-close append on `isTradingDay(new Date())`, matching `stageDailyData`.

**Auto-TA (3 findings)**
- `taMaxDist` read raw daily `avg_move`, never routed through
  `taAmvForInterval` — starved every low-beta weekly-trend name (V, XLU, XLF)
  of any 1W line at all. Fixed.
- `TA_RETEST_NEAR`/`TA_MAX_EXT` were flat 3%/12%, mislabeling ordinary weekly
  pullbacks/continuations on volatile names as FAILED/EXTENDED. New
  `taRetestNear()`/`taMaxExt()` helpers scale both by `taAmvForInterval`,
  read at both fit time (`taFitLine`) and live re-grade (`taRegrade`, via
  `STAGE.sym`).
- `taShapeLabel`'s flag/pole `poleThresh` used raw daily `avg_move` — routed
  through `taAmvForInterval` per the review's own correction (the reachable
  failure is a trading-range/descending-channel mislabel, not an ascending
  one as originally stated).

**Left watchlist rail (3 findings)**
- Band Crosses could alert off a frozen/stale price with no staleness
  disclosure — added a `liveStale(s)` skip inside `renderBBCrosses`'s loop.
- Long searched-ticker company names could swallow the earnings countdown
  inside `.meta`'s own ellipsis with zero sign one existed. Gave the
  countdown its own flex child (`.earnb`), separate from `.meta`.
- "Sort by hot" tie-break returned NaN when both `hotOf()` values were null.
  Added the same explicit both-null guard the "range" comparator already had.

**Financials (3 findings)**
- Pinned ETFs (SMH, QQQ, all eleven sector SPDRs, ~22 tickers) rendered a
  wall of 20 unexplained dashes with data-gap-flavored tooltips instead of
  the one-line fund/wrapper explanation vs-Peers already gives. Added an
  `isFundSym(sym)` short-circuit to `renderFundamentals`.
- Tap-to-read readout always rendered directly over the next chart section's
  title/axis. Re-anchored it to the BOTTOM of the tapped chart itself
  (clamped, measured via `getBoundingClientRect`) instead of the boundary
  just past it.
- Margins/YoY/EPS chart's `SM.W` omitted the `.dsec` padding (32px) `bigW`
  already subtracts, overestimating available width and column count.
  Subtracted the same padding before computing `smCols`/`smColW`.

**Sector Heatmap (3 findings)**
- A 200-with-empty-data scanner response (the documented TradingView
  rate-limit quirk) silently corrupted `HEAT.data[univ]` and defeated the
  STALE badge. `heatFetchNow` now only writes the cache/timestamp when
  `rows.length>0`, matching the equity-poll/macro-tape convention.
- Tooltip's secondary "1D" figure lost its PRE/PREV/POST tag whenever the
  active timeframe wasn't 1D. Added an always-computed `tag1DAlways` word to
  that clause.
- A universe-wide zero-weight cycle (no isolate active) fell through to a
  blank box with no message. Widened the isolate-empty guard to
  `sectors.length===0` regardless of `HEAT.isolate`, with isolate-aware wording.

**vs Peers (2 findings)**
- `metricReason` gated ALL six peer metrics on `FUND_CACHE`, mislabeling a
  permanent vendor gap (AAOI's null EV/EBITDA, whose real -11.31 op margin
  already answers it) as "still loading" forever on a peer's first
  appearance. Scoped the gate to only pe/peg/ev_ebitda's eps-dependent
  branches; gross_margin/op_margin/fcf_margin/ps/pb fall straight through.
- The "?" size-unknown mark had no generic definition for a curated peer
  set (only the industry-scan branch defined it). Added a generic,
  always-checked sentence gated on `Object.keys(capUnk).length>0`, mirroring
  ✳'s existing pattern.

**Right rail panels (4 findings)**
- Top-rail tiles (SPY/QQQ/DIA/IWM, VIX/crude/DXY) could print a red
  "−0.00%" for a flat/negligible move — the exact signed-zero bug `fm1`/
  `sign1` were written to fix elsewhere, never reused here. New `fm2`/
  `sign2` (2-decimal, 0.005 threshold) applied to both tile builders.
- CLOSED lamp's "next session" named tomorrow instead of today for 3 hours
  every trading morning (00:00-03:00 CT) — `nextWeekdayName` can never
  answer "today" by construction. `marketClosedWording`'s early-morning
  branch now returns `"today"` directly instead of walking forward.
- Catalysts meta line dropped forecast/prior silently for real HIGH-importance
  tv_calendar-sourced releases (Michigan Consumer Sentiment Prel, Building
  Permits Prel) — the fallback text only fired for `source==="econ_calendar"`.
  Widened to any HIGH-importance econ row.
- Cleared catalysts rendered ABOVE "This week" — moved the "Cleared" group to
  the end of the `groups` array.

**Flow boards (3 findings)**
- Conviction's RVOL cell was a click dead-zone on nearly every row —
  `rvTip` fired whenever both live and snapshot RVOL existed (almost
  always), and sat on the whole `<td>` rather than a small inner span,
  triggering the click delegate's "inner tooltip blocks row click" rule.
  Gated `rvTip` on an actual >0.1 drift threshold and moved it to an inner
  `<span>`.
- Conviction and Swing boards' live prices could freeze silently with no
  staleness signal, unlike the identical ticker's rail row. Added a
  `liveStale(c.ticker)` check and the same STALE badge to both row builders.
- ETF board's `m1cls` used a two-way ternary treating an exact-zero
  `flow_1m` as bullish green, contradicting `d1cls` two lines up (built from
  `sign()`) and the file's own "zero is never a green pill" rule. Changed to
  `sign(m1)`.

**Data honesty (1 finding)**
- Financials tab falsely claimed "may not report in dollars" for ordinary
  US companies (AAPL, TSLA, or a desk-pinned name whose sidecar 404s one
  cycle) on the scanner-fallback path — `adhocEnsureFundamentals`'s returned
  object had no `currency` field at all. Defaulted it to `"USD"`, mirroring
  `build_fund_sidecar`'s own server-side fallback from round 12.

## Shipped 2026-08-23, round 12 (21 findings confirmed, all fixed)

Round 12 checked the round-11-fixed page. Pre-fix scores:

| Section | R12 |
|---|---|
| Flow boards | 81 |
| Sector Heatmap | 80 |
| Data honesty | 78 |
| vs Peers | 72 |
| Right rail panels | 72 |
| Left watchlist rail | 76 |
| Chart Stage | 64 |
| Auto-TA | 62 |
| Financials | 60 |

**21 findings confirmed** across the 9 sections. No section had zero.

They are ordered by section in review order; within each section, blocker
first, then major, then minor.

#### Chart Stage — 64

- **[blocker] Header earnings countdown mixed two vendors' dates — the
  exact bug the Fundamentals grid already fixed, live right now on
  MU/COHR/V/XOM/TSEM.** `stageNextEarnHTML` computed its displayed
  day-count from `earnDaysNow(factsOf(sym))` (TradingView-sourced) but
  printed `fund.next_earnings.date` (stockanalysis.com-sourced) in the
  same button's own tooltip/popover — MU showed "E 38d" while its own
  tooltip said a date 32 days out, a 6-day self-contradiction in one UI
  element; TSEM showed an 86-day countdown next to a date 18 days in the
  PAST. Fixed by deriving the day-count from `ne.date` itself via
  `fedDaysToMeeting`, matching the Fundamentals grid's own already-fixed
  convention, which also hides a stale past date instead of showing it as
  upcoming.
- **[blocker] 1W live-poke folded yesterday's regular-session high/low
  into the new week's candle with no premarket check**, unlike the 1D
  branch's explicit `STAGE.premarketBar` gate — pre-market, `live.h`/
  `live.l` still describe YESTERDAY's session, so folding them into the
  ratcheted weekly high/low pulled a PRIOR week's reading into the new
  week, while flipping `syntheticReal` desynced the candle's dimmed/real
  visual state from its own "· pre-market" caption. Fixed by moving the
  `premarketBar`-clearing check above BOTH branches (was 1D-only, so
  opening straight to 1W during pre-market never cleared it) and building
  the 1W pre-market update purely from the pre-market bracket, mirroring
  1D's own handling.
- **[minor] Vertical zoom (`STAGE.vZoom`) persisted across interval/
  window-button clicks**, only resetting on symbol change or an explicit
  double-click — a chart the user never zoomed on the new view arrived
  visually compressed or stretched at whatever stretch factor was left
  over from a different view. Fixed by resetting `STAGE.vZoom` in the
  iv/tf button click handler.

#### Auto-TA — 62

- **[major] Trend-line fitting was mathematically impossible on the 15m
  interval for every ticker, permanently** (and the identical structural
  defect also applies to 1H, per this finding's own correction) — the
  scaled 40-day-equivalent minimum window (1040 bars for 15m, 260 for 1H)
  demanded far more bars than the fetcher's own `INTRA_MAX` ceiling (140
  for 15m, a further 160-row slice for 1H) could ever supply, so the
  caption repeated "too short" forever with no path to ever resolve. Fixed
  with a new `TA_REALISTIC_MAX_BARS` cap so 15m/1H get their own honest,
  reachable minimum instead of demanding a bar count no dataset can supply.
- **[minor] Trend-line containment was judged on wicks for 1W (and every
  non-daily interval), but a weekly bar's high/low wick spans five trading
  days of intrabar extremes** — a genuine, tradeable weekly support/
  resistance line could be silently discarded the moment any ONE day that
  week poked through, even while every weekly CLOSE respected it. Widening
  the tolerance wouldn't fix this (a wick still encodes intrabar extremes a
  close-based check would never see), so `containLeg` now also uses closes
  for 1W, matching the existing daily convention.
- **[minor] The S/R axis-badge collision check tested the band's mean
  price, not the edge actually drawn/labeled** — a wide band draws (and
  labels) its near EDGE, never the cluster's arithmetic mean, so an MA
  line sitting exactly on the displayed edge while the mean read 3%+ away
  reported "no collision" and stacked the S/R badge directly on the MA's.
  Fixed by testing collision (and picking the "nearest level" for the
  badge in the first place) against the actual edge price for a wide band,
  at both fit time and every live poke.

#### Left watchlist rail — 76

- **[major] `isLeveraged()` still missed ProShares' plain inverse funds
  (SH, DOG, MYY)** — the regex's short-index alternatives ended with a
  `\b` immediately after the bare index name, but ProShares glues the
  index number directly onto the name with no separator ("Short S&P500",
  "Short Dow30", "Short MidCap400"), so no boundary exists there and the
  alternative never matched. Fixed by allowing an optional attached number
  on each short-index alternative instead of a flush trailing boundary.
- **[major] `LEV_NAME_RE` only matched exact 1x/2x/3x, missing real
  fractional-multiple single-stock ETFs** (GraniteShares' 1.75x TSLR/
  CONL) — real, actively-traded products exactly the shape the shopping-
  list exclusion exists for. Fixed by replacing the fixed `2x|3x` set with
  a general `\d+(\.\d+)?x` pattern.

#### Financials tab — 60

- **[blocker] `robustClampMag` voided the WHOLE clamp when any one
  over-threshold point had an elevated neighbor, so a real ticker's small
  quarters rendered invisible** — SNDK's isolated -13.33 write-down
  quarter sat among real 23.03/43.96 hypergrowth quarters that correctly
  veto a uniform clamp, so the whole clamp canceled and 4 of 12 real
  quarters rendered under 4px tall with zero disclosure anything was even
  considered. Per this finding's own correction, a true per-point clip
  would barely change SNDK's bar heights (its real EPS genuinely spans
  200x+) — the actionable fix is disclosure, not a reshuffle. Fixed with a
  new `robustClampHasUncorrectedGlitch` detector and a caption note for
  exactly this "recognized but uncorrected" case.
- **[major] Margins/YoY/EPS chart viewBox width was a hardcoded 340px**,
  never derived from the actual rendered column width the way the money
  chart's `BIG.W` already is — at a narrow desktop width where `.gwrap`
  collapses to one ~548px column, each 340-viewBox SVG rendered at 1.61x
  its authored scale (an 11px axis tick displaying at ~17.7px) while the
  money chart right above it rendered correctly. Fixed by deriving `SM.W`
  from the same `hostW` measurement `BIG.W` uses, sized per the actual
  column count CSS auto-fit will produce.
- **[minor] `fund.currency` was only ever set by the optional Yahoo leg,
  so a Yahoo outage made a domestic company's Financials tab falsely warn
  it may not report in dollars** — the once-per-run crumb handshake's
  failure blanks currency for the ENTIRE tracked universe at once, not
  just one ticker, and the frontend read a null currency as "possibly
  foreign." Fixed with a small explicit `KNOWN_NON_USD_CURRENCY` table
  (SKHY/TSM, the only two currently-pinned non-USD reporters) and a
  default to `"USD"` for every other pinned ticker when the Yahoo leg
  didn't run or didn't answer.

#### Sector Heatmap — 80

- **[major] A real stock with a missing market-cap reading was asserted
  to be "a fund" in its own tooltip and sector bucket** — `byVol` (fired
  for ANY row missing a cap reading, real stock or fund) was conflated
  with "is this actually a fund," bucketing a real equity's transient
  missing-cap read into "Funds & wrappers" with a tooltip stating "(a
  fund: no market cap)" outright. Fixed by reading `d[11]` ("type,"
  already fetched into `HEAT_COLS` and never used) to determine `isFund`
  separately from the dollar-volume sizing fallback.
- **[minor] Touch users got zero identification before the map navigated
  them to a ticker** — a tile too small to carry a ticker label has no
  touch-hover equivalent of the desktop mouseover tooltip, and the tile's
  own click handler called `stopPropagation()` before the document-level
  click-tooltip fallback ever got a chance to fire. Fixed with a two-tap
  pattern for bare tiles: first tap identifies (shows the tooltip), second
  tap navigates — desktop mouse users are unaffected since they already
  saw the hover tooltip before clicking at all.

#### vs Peers tab — 72

- **[blocker] MU's own PEG was wrongly nulled as "not a real reading"
  during a genuine earnings supercycle.** The round-11 percentage-only
  growth ceiling (500%) couldn't distinguish BE's near-zero-denominator
  rounding artifact ($0.0047 prior-year base) from MU's real, non-
  degenerate $5.5538 prior-year base growing to $44.1733 — a genuine 695%
  AI-driven supercycle move — and flagged both identically. Fixed by
  gating on whether the PRIOR-YEAR BASE ITSELF is implausibly tiny (a new
  `DERIVED_PEG_MIN_PRIOR_EPS`, 5 cents/share) instead of the resulting
  growth percentage, which BE's base fails and MU's clears trivially.

#### Right rail panels + top rail — 72

- **[major] Sector rotation's IN/OUT dot's tooltip and caption falsely
  claimed to be the $1w flow sign when it was actually the price-relative-
  strength fallback** — when `flow_1w` is null, the dot falls back to the
  sign of price performance vs SPY, a DIFFERENT fact from money direction,
  but both the per-dot tooltip and the panel-wide caption unconditionally
  called it "the sign of the $1w flow beside it" even as the $1w column
  read "—" right next to it. Fixed with a hollow-ring dot style and its
  own distinct tooltip/caption wording for the fallback case, never the
  solid flow-colored fill.
- **[minor] The news ticker's change-detection key could miss real
  content changes**, freezing the marquee on stale headlines while
  claiming nothing changed — `NT_KEY` only inspected the newest headline
  and the total count, so headlines rotating in slots 2-20 while the top
  story held slot 1 went undetected. Fixed by hashing every item's
  identity, not just the first.
- **[minor] On phones, a single failed price poll gave zero on-screen
  warning for ~30-60s** — `.rl.clock` (the only other carrier of a
  poll-failure warning) is `display:none` at 640px, so the full-width
  banner (which waited for 2 consecutive misses) was the only visible
  warning on mobile at all, arriving a full poll cycle later than
  desktop's immediate clock-row hint for the identical single failure.
  Fixed by lowering the banner's threshold to 1 miss, so both surfaces
  agree regardless of viewport.

#### Flow boards — 81

- **[major] `boardCutNoteHTML` could assert "every tracked name clears
  the bar" in the same sentence as "N firing below the line."** The
  "every tracked name clears the bar" wording fired whenever
  `cut.strong===cut.total`, with no check on `lowFiring` — a live-
  reachable shape (all non-firing names clearing 60+ while at least one
  firing name, like AVGO or MU, stays sub-60) let the sentence claim in
  one breath that those names are "below the line" and that every name
  clears the bar. Fixed by gating the "clears the bar" wording on
  `lowFiring===0` too, with its own wording for the mixed case.
- **[major] Conviction's own row builder defeated `dispQuote`'s
  null-check, turning a failed live-quote lookup into a false "PREV"
  badge.** `rowHTMLConv` pre-substituted `{}` before calling `dispQuote`,
  so `dispQuote`'s own `if(!q) return {...tag:null...}` guard never fired
  (an empty object is truthy) — execution fell into the premarket branch
  and rendered "This name has not traded pre-market yet" for a symbol
  whose live quote simply failed to look up. Fixed by calling
  `dispQuote(liveBySym(c.ticker))` directly, matching every other call
  site in the file including Swing's own row builder.

#### Data honesty — 78

- **[major] Swing board's "MIXED" trend reading was indistinguishable
  from "no SMA data at all."** A ticker with no SMA20/SMA50 from the
  scanner (thinly-traded new leveraged ETFs like MUU/RAM) fell into the
  same `else: trend = "MIXED"` branch as a genuine split-above-one-
  average/below-the-other reading, and `swing_score` awarded the same +7
  points for both. Fixed by making the missing-data case its own tri-
  state (`trend = None`), reserving "MIXED" for a genuine split reading —
  `swing_score`'s `trend == "MIXED"` check already excludes `None` with no
  further change needed, and the frontend already renders a null trend as
  "—".
- **[major] The 5-metric framework's "(building)" verdict qualifier
  promised resolution to filters that are permanently rejected, not
  pending.** A ticker whose only unresolved filters are BOTH flagged by
  round-11's implausibility ceiling (MU's own real opmargin/FCF swings)
  got the same "(building)" qualifier and "could still move once the
  remaining filter(s) report" note as a ticker genuinely still gathering
  weekly consensus history — a promise the flagged case structurally
  cannot keep, since the underlying financials are what's wrong, not the
  elapsed time. Fixed with a new "_CAPPED" verdict suffix (distinct from
  "_BUILDING") for when every unresolved filter is flagged, plus a
  corrected on-screen note distinguishing the two cases.

---

## Shipped 2026-08-22, round 11 (25 findings confirmed, all fixed)

Round 11 checked the round-10-fixed page. Pre-fix scores:

| Section | R11 |
|---|---|
| Left watchlist rail | 85 |
| Auto-TA | 79 |
| Flow boards | 74 |
| Sector Heatmap | 78 |
| vs Peers | 78 |
| Chart Stage | 76 |
| Data honesty | 71 |
| Right rail panels | 58 |
| Financials | 62 |

**25 findings confirmed** across the 9 sections. Left watchlist rail cleared
80 for the second time (round 9 also cleared it); its 3 confirmed findings
were fixed anyway, per the finish-line ruling — a passing score doesn't
exempt a section from a confirmed finding.

They are ordered by section in review order; within each section, blocker
first, then major, then minor.

#### Chart Stage — 76

- **[blocker] Weekly chart for any searched/off-desk ticker froze at a stale
  close and never disclosed it.** `stageViewData`'s ad-hoc 1W branch built
  `wSynth` from `today > lastStoredDate`, the OPPOSITE of what the analogous,
  correct 1D check tests — during ordinary market hours that condition is
  always false, so `STAGE.synthetic` never went true and the live-patch path
  never ran for an off-desk name. A bare flip to `>` (mirroring 1D) was
  considered and rejected: unlike 1D, the ad-hoc 1W branch never appends a
  new row, so a bare "today is after the last stored date" would also fire
  across a full week boundary (e.g. viewing on the Monday after a holiday)
  and let the live patch overwrite an already-settled PRIOR week's OHLC with
  today's live price. Fixed with a new shared `weekKeyOf(d)` function (hoisted
  out of `intervalDataFor`'s own local copy) and a compound check: `today`
  strictly after the last stored day AND in the SAME calendar week as it.
- **[major] Even after fixing the flag above, the ad-hoc weekly branch would
  have printed a false "CLOSE ONLY" caption.** The ad-hoc branch's return
  object never set `syntheticReal`/`premarketBar`/`weekRealDays`, so once
  `STAGE.synthetic` could go true, the caption's `fabricated` test always
  evaluated true regardless of whether the week's open/high/low were real.
  Fixed by computing `weekRealDays` (real prior daily rows already folded
  into the forming week, via the same `weekKeyOf`) and `premarketBar` in the
  ad-hoc branch, mirroring what `intervalDataFor` already does for pinned
  names; `syntheticReal` starts false and gets set by `stageLivePoke`'s
  existing 1W patch logic once real live O/H/L are confirmed.

#### Auto-TA — 79

- **[major] A visibly widening (diverging) channel was captioned "roughly
  parallel."** `taShapeLabel` computed `conv` as converging/diverging/
  parallel but only ever branched on `conv==="converging"` — diverging fell
  into the same else-branch text as parallel. Verified live on DIA's 6M
  chart. Fixed by giving diverging its own label ("broadening ascending/
  descending channel") and detail text ("the gap widening"), mirroring how
  "broadening formation" already exists for the opposite-slope case.

#### Left watchlist rail — 85

- **[major] A custom/searched ticker's earnings countdown went blank
  forever once its cached date passed, on a tab left open across it.**
  `adhocEnsureFacts`'s permanent in-memory cache (`if(ADHOC_FACTS[sym])
  return...`) never re-fetched once populated, so a countdown that hit zero
  (and correctly disappeared per `earnDaysNow`'s `>=0` guard) never came
  back even three months later when the next real earnings date was days
  out. Fixed by deleting the cache entry and re-fetching whenever the cached
  countdown has actually gone negative.
- **[minor] Searching "$MU" — the ticker convention traders paste from
  Twitter/StockTwits — returned "nothing matched."** TradingView's
  substring matcher can't match a leading `$` against any real name or
  description; `_tsVariants` stripped company-suffix stopwords but never a
  leading `$`. Fixed by stripping it before building search variants.
- **[minor] Boot-time enrichment of the custom watchlist fetched daily bars
  ONE TICKER AT A TIME**, so later entries in a multi-name custom list sat
  without a hot badge or 52-week bar for N sequential stockanalysis.com
  round-trips — the exact race condition `wlAdd`/`wlIoApply` were already
  fixed to avoid for the identical fetch. Fixed by switching the sequential
  `.reduce` chain to a parallel `Promise.all`, matching the facts warm-up
  immediately above it.

#### Financials tab — 62

- **[blocker] BE's PEG rendered as a green 0.02 "bargain" signal — a
  near-zero-denominator artifact, not a real ratio.** BE's prior-year TTM
  EPS base ($0.0047) is a rounding error from zero, producing a 16,166%
  "growth" rate; TradingView's own vendor PEG (0.0178) is built on the
  identical arithmetic and rendered with no caveat. Fixed with a new
  `DERIVED_PEG_MAX_GROWTH_PCT` (500%) ceiling, factored into a shared
  `pegGrowthPctFor(fund)` helper so `metricValue` can gate a VENDOR-supplied
  PEG against the same implausibility check `derivedPeg` already applies to
  its own fallback — a vendor PEG built on an implausible growth rate is
  just as unreliable as a derived one would be.
- **[major] `periodsPerYear` misdetected cadence for any ticker with
  quarterly history confined to exactly two calendar years** — corrupting
  the YoY window and TTM EPS/PEG math, not just a label. With exactly 2
  distinct years, the "drop first/last partial year" fallback empties, and a
  1-vs-1 tally tie (e.g. a 3-quarter year vs. a 2-quarter year) resolved to
  the SMALLER count because `Object.keys` iterates ascending and the old
  strict `>` comparison never let a later, larger key overtake it. Fixed
  with a floor (fewer than 8 total labels in the two-year-fallback path
  returns null, scoped so a 3+-year series with one clean middle year is
  never affected) and a tie-break preferring the larger count (`>=`, not
  `>`) — a partial year undercounts, it never overcounts.
- **[minor] The combined Revenue/NI/FCF clamp could be triggered by one
  series' outlier and silently clip a different series' value that was
  never itself isolation-tested.** `robustClampMag`'s isolated-spike check
  only tested the single globally-largest pooled value's own neighbors, so
  a different series' point exceeding the resulting shared ceiling could be
  clipped without ever having its OWN neighbors checked — latent on today's
  data (a genuine outlier happens to also be the value clipped), but a real,
  reachable path. Fixed by running the isolation test against every value
  that would actually be clipped under the ceiling, not just the largest.

#### Sector Heatmap — 78

- **[major] Isolating a sector that later lost all its rows left the
  footer's stale "N names" count contradicting the on-screen "0 usable"
  message.** The `sectors.length===0` early-return branch called `heatMsg`
  with the recovery message but never reached the footer-rebuild code below
  it, so the footer kept showing the PREVIOUS cycle's count. Fixed by
  blanking `#heatfoot` in that same branch.
- **[minor] Hatch precedence only resolved nodata vs. the other two facts —
  `prev1d` silently swallowed `capfall` when both were true**, even though
  the two are independent facts a tile can genuinely carry at once. Fixed
  with a combined `.hm-tile.prev1d.capfall` CSS rule (both hatch patterns
  layered) and JS that now applies both classes together instead of an
  either/or chain; `nodata` still wins outright over either, unchanged.
- **[minor] A sector block under 16px tall got no header at all and could
  never be isolated** — no label anywhere named which sector its tiles
  belonged to, and isolation only works by clicking a header. Fixed with a
  1px-tall invisible click/tab target carrying the sector name in its
  title/aria-label, so a headerless block stays isolatable even though it
  has no room to visually look like one.
- **[minor] The tile-count-cap message blamed "this width" even when the
  real bottleneck was a short window** — `maxTiles` is driven by AREA
  (`wrapW*wrapH`), so a wide-but-short window (e.g. 1600x600 in expanded
  mode) hits the cap from its height, and "widen the window" told the reader
  to change the dimension that wouldn't help. Fixed by naming whichever
  dimension is actually smaller ("make the window taller/wider").

#### vs Peers tab — 78

- **[major] Indexed revenue-growth chart silently dropped the focus ticker
  (or any peer) from its own comparison once 2+ series succeeded.** The
  `skipped` disclosure array was built unconditionally but only ever READ in
  the `lines.length<2` branch — once 2+ series cleared the bar, a dropped
  name (including the focused symbol itself) simply vanished from the chart
  with no on-screen note. Fixed by appending the same disclosure text inside
  the `lines.length>=2` branch too.
- **[minor] PEG chart's async re-render could add a clip mark the page's
  one clip-disclosure sentence never learned about.** The shared `.note`
  sentence explaining the clip-mark convention was computed once,
  synchronously, before `FUND_CACHE` loaded; if PEG's own async-patched
  chart was the only one that ended up clipped, that sentence never got
  written (each bar's own hover tooltip still discloses it independently).
  Fixed by appending the sentence to the existing `.note` element in place
  when the PEG patch reveals a clip the synchronous pass didn't know about.
- **[minor] `peerStat`'s better/worse coloring misclassified an exact tie
  with the peer median as "worse."** Strict inequalities both ways folded a
  genuine tie (a focused company landing exactly on the peer median — round
  percentages and small curated peer sets make this plausible) into the
  "worse" branch with no neutral state. Fixed by treating `mine.v === med`
  as a third, neutral state (no color class) in both `peerStat` and its two
  consumers (`peerAnnotate`, the vs-Peers rank badge).

#### Right rail panels + top rail — 58

- **[blocker] CPI/PCE anchor rows could silently merge the WRONG
  sub-metric's forecast/prior.** TradingView's econ feed carries FOUR
  distinct Inflation Rate rows on the same date/slot (headline YoY, headline
  MoM, Core YoY, Core MoM); the CSV-side alias's tv-side pattern (`inflation
  rate`) matched all four with no Core exclusion or YoY preference, taking
  whichever came first in the feed's own row order — verified live: that
  order put "Core Inflation Rate MoM" first, so CPI's merged numbers would
  have silently been the wrong sub-metric entirely. Fixed by restructuring
  `_ECON_ALIASES` into ordered (include-all, exclude-any) attempts —
  headline YoY with Core excluded first, any non-Core row as a fallback —
  applied to both CPI and PCE.
- **[major] "Next session" in the closed-market tooltip could name a day
  the market is holiday-closed.** `nextWeekdayName`/`prevWeekdayName` did
  plain Monday-Friday arithmetic with no `MARKET_HOLIDAYS` lookup, unlike
  `isTradingDay` a few lines above them — a Thursday half-day (not a
  holiday) let the walk land on "Friday" without checking that the actual
  next day was Christmas. Fixed by rewriting both to walk real calendar days
  via `isTradingDay` (which already prefers bars.json's published session
  calendar) instead of a bare weekday-index table.
- **[minor] Monthly/quarterly options-expiration rows were filtered as
  curated anchors on the frontend but never got the anchor badge** — the
  fetcher's `_build_opex_rows` set `anchor:False` unconditionally for every
  market_calendar row, so `catMetaLine`'s badge (which reads `c.anchor`
  directly) never fired for a row the curation logic had already decided
  was an anchor. Fixed by setting `anchor:True` for the monthly/quarterly
  branches only; weekly rows are unchanged.

#### Flow boards — 74

- **[major] Conviction board's age/stale stamp disappeared entirely on a
  chain-vendor outage.** The `arr.length===0` early-return branch blanked
  `#convstat`'s innerHTML before returning, unlike Swing and Big Orders,
  which build their stat line BEFORE their own empty checks and so keep
  showing "as of ..." in the identical empty state. Fixed by moving the
  `#convstat` build above Conviction's early return too, and dropping the
  blanking line.
- **[major] Sorting Conviction by RVOL reshuffled rows under the cursor
  every 30 seconds.** RVOL is the one Conviction column whose displayed
  value updates on every 30-second price poll (via `c.rvol_shown`), and
  `refreshLiveUI`'s poll-driven `renderConv` call fully re-sorted on every
  tick — the only sort key where re-sorting moved rows purely because the
  number the reader was watching ticked. Fixed by giving `table()` an
  `opts.liveKeys`/`opts.freeze` mechanism: a live-poll redraw with the
  active sort key in `liveKeys` reuses the last REAL sort's row order (by
  ticker identity) instead of re-sorting, while still rendering each row's
  updated cell value; an explicit header click always resorts for real.
- **[minor] The "counts ≠ $" mismatch pill gave one specific, often-wrong
  reason for why C/P and Flow % disagree.** `cp_ratio` is accumulated over
  EVERY strike in the 0-7 DTE bucket while Flow %'s premium is accumulated
  only inside the near-money ±20% band — two different POPULATIONS of
  contracts, not just two weightings of the same ones — but the pill's
  tooltip asserted only the price-weighting explanation. Fixed by folding
  in the same scope-difference language `tip-flowpct` already carries.

#### Data honesty — 71

- **[blocker] The 5-metric framework labeled a PERMANENT data-quality
  rejection as "still building history," with no way it will ever resolve
  by waiting.** Round 10's new implausibility ceilings on Filters 4/5 read
  as an ordinary `null` — indistinguishable from the two consensus-history
  filters that genuinely will resolve once enough weekly snapshots
  accumulate. Fixed with a new `filter_flags` dict on the framework object
  (`{"opmargin_expansion": "implausible_swing"}`), letting
  `stageFrameworkHTML` render "DATA FLAGGED" instead of "building…" for
  exactly the ceiling-rejected keys, without changing the passed/failed/
  unknown counting a flagged filter still correctly behaves as unknown for.
- **[major] A single transient Polymarket failure wiped the cached
  `fed_odds` reading for the rest of the hour**, silently killing the FED
  HIKE RISK banner whenever `brief.fed_hike` was ALSO unavailable that day
  (no VAULT_READ_TOKEN, or the Morning Brief's own Polymarket reading was
  unusable) — `normalizeFedOdds`'s existing fallback to `brief.fed_hike`
  already covers the ordinary case silently and correctly. Fixed by only
  overwriting `cache["fed_odds"]` when the fresh fetch actually returns a
  dict (keeping the previous cached value otherwise, mirroring avg_move's
  own merge-not-replace pattern), plus a visible "No Fed-odds reading this
  cycle" note in `fedOddsHTML` for the narrower compound-failure case.
- **[minor] The gamma-levels staleness counter used the UTC calendar day
  instead of the site's own CT day**, producing an off-by-one-day STALE
  count roughly 19:00-00:00 CT when the UTC date has already rolled to
  tomorrow. Fixed by switching `gammaStaleDays()` to `ctDateKey`, the same
  CT-day convention every other day-based staleness check on the page
  already follows.

---

## Shipped 2026-08-22, round 10 (23 findings confirmed, all fixed)

Round 10 checked the round-9-fixed page. Pre-fix scores:

| Section | R10 |
|---|---|
| Sector Heatmap | 83 |
| Flow boards | 78 |
| Right rail panels | 63 |
| Left watchlist rail | 62 |
| Auto-TA | 60 |
| Financials | 60 |
| vs Peers | 58 |
| Data honesty | 58 |
| Chart Stage | 34 |

**23 findings confirmed** across the 9 sections — no section had zero. Chart
Stage's pre-fix 34 was its lowest score of any round to date, driven by the
same live-poke/full-render divergence bug recurring in three different
places at once (dimming, `syntheticReal`, and the 1W high/low ratchet);
per-round scores are not a trend line (the review script's own documented
caveat — a harder finding surfaces new surface area every round), but a
Chart Stage regression to 34 after round 9's fixes made it worth naming
plainly rather than folding into the summary below.

They are ordered by section in review order; within each section, blocker
first, then major, then minor.

#### Chart Stage — 34

- **[blocker] The dimmed/fabricated candle body reverts to full opacity on
  the very first live poll, 30 seconds after it was drawn.** `stageRender`
  sets `bar.color`/`bar.wickColor` to a 50%-alpha hex when the last candle is
  extended/fabricated, but `stageLivePoke`'s `candle.update()` calls (both
  1D and 1W branches) always redrew at full opacity and full-alpha volume
  (0.45 instead of 0.2) — the one visual signal that a bar isn't settled
  disappeared 30 seconds after every full render. Fixed by recomputing the
  same `ext` condition inside `stageLivePoke` and conditionally setting
  `color`/`wickColor`/volume alpha on every live poke, mirroring
  `stageRender` exactly.
- **[blocker] `STAGE.syntheticReal` never updates after the first render, so
  a real scanner-published open/high/low gets mislabeled "CLOSE ONLY" for
  the whole regular session.** A tab left open from pre-market through the
  08:30 open kept reading its one pre-market-render `syntheticReal=false`
  forever, since only `stageDailyData`/`stageRender` ever set it. Fixed by
  having `stageLivePoke` set `STAGE.syntheticReal=true` in both the 1W and
  1D branches the moment real `live.o`/`live.h`/`live.l` are confirmed
  present, the same test `stageDailyData` already applies at full-render
  time.
- **[major] The weekly view's live poke never read `live.h`/`live.l`, so the
  current week's high/low could silently understate the real intraday
  range.** The 1D branch already folded `live.h`/`live.l` into its ratcheted
  high/low; the 1W branch only compared the OLD stored high/low against the
  new close. Fixed by folding `live.h`/`live.l` into the 1W branch's
  `whi`/`wlo` computation the same way the daily branch already does.

#### Auto-TA — 60

- **[blocker] Weekly-view trend lines silently never fit for volatile
  names.** `taContainTol`/`taFitLine`'s `touchTol`/`hugTol` only scaled by
  `avg_move` when `STAGE.iv==="1D"` — every other interval, 1W included,
  fell back to the flat intraday-sized tolerances the code and the
  `ta_trend` tooltip both describe as "1% touch / 1.2% poke" figures meant
  for intraday charts, which a weekly bar's naturally wider range blows
  through on every fit attempt. Fixed with a new `taAmvForInterval(amv)`
  helper that scales the daily `avg_move` figure to a weekly-equivalent
  before computing tolerance, extending the existing 1D-only scaling to
  cover 1W as well.
- **[major] S/R caption could quote a price range the chart never drew.**
  The chart's own draw block split a cluster into two edge-lines only above
  a 2% width; the caption's own "wide" check fired at 0.4% and, once wide,
  printed a two-sided range and an edge-based distance — any cluster
  between 0.4% and 2% (a common width) got a caption describing a band the
  chart drew as one dashed line. Fixed with a new shared `TA_SR_WIDE_BAND`
  constant (0.02) used by both the S/R draw block and the caption, so the
  two can never disagree about whether a level counts as a band.
- **[minor] Flag/pole percentage for a triangle-turned-channel was measured
  from the edge of whatever range button happened to be active, not from a
  fixed point in the pattern.** Clicking 1M vs. 1Y re-sliced `win` from
  scratch, so the same underlying chart pattern reported a different
  "run into a tight channel" percentage purely from the range button.
  Fixed with a new `TA_FLAG_POLE_LOOKBACK` constant (20 bars) anchoring the
  pole measurement to the channel's own start, independent of the window.

#### Left watchlist rail — 62

- **[blocker] A custom-added symbol later promoted to a pinned rail ticker
  rendered twice, and its "× remove" button silently stopped working.**
  When `RAIL_GROUPS` grows to pin a symbol a browser had previously
  custom-added (the WTI case, pinned 2026-08-15), that browser's
  `desk.wl.custom` entry never got pruned, so the symbol rendered once under
  "MY ADDS" and once under its real pinned group — and `wlRemove` only ever
  ran one of its two removal branches, so clicking × on the ghost row did
  nothing. Fixed by rewriting `wlRemove(sym)` to always strip a custom entry
  AND separately hide a pinned one (previously only one branch ever ran),
  and by filtering `renderWL()`'s `custom` list to exclude anything now
  `railHasSym` before building `customSyms`/the "N custom" count/the render
  list.
- **[minor] The rail's phone toggle count included a symbol orphaned by the
  same bug** — a direct consequence of the finding above, fixed by the same
  change (the count is a `customSyms.length` derived from the now-pruned
  list).

#### Financials tab — 60

- **[major] Annual financials bar charts had no outlier clamp** — LITE's and
  NBIS's real annual charts rendered as one bar and near-invisible slivers
  with no disclosure, because only the quarterly render loop called
  `robustClampMag`. Fixed by giving each annual-chart metric its own
  `robustClampMag` clamp, folded into the same `clampedAny` flag the
  quarterly block already uses so the caption discloses it.
- **[major] `metricValue()`'s PEG derivation only fired when the vendor
  field was exactly `null`, never when it was a non-positive number** — a
  company with a real vendor PEG that happened to be negative (a
  still-profitable company whose trailing EPS growth went negative) was
  told "TradingView reports no PEG" instead of getting the page's own
  derived-PEG fallback. Fixed by widening the fallback condition to
  `(v==null || v<=0)` for the `peg` key, and moving the derived-PEG reason
  lookup ahead of `metricReason`'s blanket negative-value check for that key
  specifically.

#### Sector Heatmap — 83

- **[major] A scanner outage after first load repainted stale tiles with no
  stale indicator.** `heatFetchNow`'s catch path set `HEAT.lastFetchFailed`
  but never cleared `HEAT.data[univ]`, so every subsequent `tick()`-driven
  repaint kept showing the last good read with no on-screen sign the
  scanner had stopped responding. Fixed by wiring the previously-unused
  `staleRead` variable into the footer as a STALE badge, and recomputing
  `nCapFall` from the post-cap `rows`.
- **[minor] Desk-universe fallback-to-market-cap count could overstate what
  was actually on screen** — `nCapFall` was computed before the tile-count
  cap sliced off the smallest names, so a capFallback row cut by the cap
  still counted toward the footer's "N names had no volume figure" note.
  Fixed in the same change as the finding above.

#### vs Peers tab — 58

- **[blocker] Rank badge's better/worse color used a median the caption
  calls unusable.** `peerStat` computed the badge's color independently of
  `oneMetricChartHTML`'s own 2-point/high-spread "no usable median" guard,
  so a chart whose caption disowned its median (MRVL's PEG chart, a ~100x
  KLAC/SKHY spread) still painted a directional badge sourced from that
  same disowned number. Fixed by giving `peerStat` the identical guard, and
  by passing `oneMetricChartHTML`'s already-resolved peer list into
  `peerStat` via a new optional `peersOverride` parameter instead of
  letting it re-read the module-global `PEERS_CACHE`.
- **[major] A peer with an unresolved market cap was never marked as a size
  outlier.** `inBand()` returns `null` for an unknown cap and `false` only
  for two known, genuinely-mismatched sizes, but `finish()`'s `wide` array
  only checked `inBand(c.cap)===false`, so a null-cap candidate (a foreign
  issuer or thin OTC name the scanner hasn't backfilled) slipped through
  unflagged. Fixed by tracking null-cap candidates separately (`capUnknown`)
  and giving them their own footnote and `?` key marker, distinct from a
  genuinely out-of-band peer.
- **[minor] A slow-but-succeeding peer scan was permanently reported as
  failed for that view.** `renderPeersTab`'s fixed 10-second timeout could
  fire before a legitimate two-POST scan (banded query, then an unbanded
  retry) finished, and the real promise kept running in the background with
  no live callback wired to it — so a late success never repainted the tab.
  Fixed by removing the `if(timedOut) return;` early-return and the
  now-unused `timedOut` variable, keeping the underlying promise wired to a
  live callback (guarded by sequence/tab checks) so a late resolution still
  repaints.

#### Right rail panels + top rail — 63

- **[blocker] The 8 highest-importance economic catalysts never showed
  forecast/prior/actual — live, right now.** Every HIGH-importance
  CSV-sourced row (PCE, Jobs Report, PPI, CPI, Retail Sales, FOMC, Fed Chair
  presser) carried `forecast:null`/`prior:null`, because `_dedup_econ`
  always kept the CSV row and discarded any TradingView row with the same
  date+title outright — even when the TV row carried real forecast/prior
  numbers the CSV feed doesn't supply. Fixed with a new
  `_ECON_MERGE_FIELDS` tuple and a rewritten `_dedup_econ` that merges those
  fields onto the surviving CSV row instead of discarding the conflicting
  row's data, plus a new `_ECON_ALIASES` list and `_merge_econ_aliases()`
  function (CPI↔Inflation Rate, Jobs Report↔Non Farm Payrolls/Unemployment
  Rate, FOMC↔Fed Interest Rate Decision, PCE↔PCE Price Index) wired into
  `build_catalysts`, plus a `catMetaLine` fallback note ("no forecast
  published for this reading") for any HIGH-importance row still missing
  both after the merge.
- **[major] MU's Q4 earnings printed twice in the catalysts panel for the
  same day.** `build_catalysts` extended `memory_rows` and appended the
  `earn_map`-derived earnings row with no cross-kind dedup by
  (ticker, date), and `catPassesCurated` passed both unconditionally. Fixed
  by dropping the memory row when it shares (ticker, date) with an
  earn_map-derived earnings row, folding its extra color into the earnings
  row's title as a parenthetical instead of emitting both.

#### Flow boards — 78

- **[major] Swing board's "since flagged" chase chip re-baselined every
  calendar day, defeating its purpose on a multi-week board.** Swing shared
  Conviction's daily-reset `today_sessions`-based `first_board_swing`
  stamping, so a name sitting on Swing unbroken for 15 sessions and up 22%
  since it first appeared had its `spot_at_alert` silently re-stamped to
  that morning's spot on every new trading day. Fixed with a new
  cross-day-persistent `history["swing_first_seen"]` map in
  `build_snapshot.py`, cleared only when a ticker actually drops off the
  Swing board that cycle — Conviction keeps its original daily-reset logic
  unchanged, since its own board genuinely resets daily.
  `chaseChipHTML(c, px, board)` gained a `board` parameter for board-aware
  tooltip wording ("first flagged" for Swing vs. "first hit the board today"
  for Conviction).
- **[major] Biggest Orders board silently dropped the delta badge on
  mobile** — the one figure separating a hedge from a directional bet. The
  badge shared the `"nm tn"` class with sector-table company names, and the
  mobile media query's `td .nm{display:none}` rule (meant only for those
  names) hid the badge too, even though it lives in the Side cell the query
  never hides. Fixed with a dedicated `.deltabadge` class carrying the same
  muted styling, outside the `.nm` selector's reach.
- **[minor] No flow-board row was reachable or activatable by keyboard**,
  despite the column headers getting exactly this fix in round 9. Every
  `tr.rw` row (Conviction, Swing, Big Orders, and the sector table) carried
  no `role`/`tabindex`, so Tab never reached them and the existing
  `[data-sym][role="button"]` keydown handler never matched. Fixed by
  adding `role="button" tabindex="0"` to all four `tr.rw` builders — the
  existing keydown handler covers them automatically once the attribute is
  present, so no handler change was needed.

#### Data honesty — 58

- **[blocker] The 5-metric framework computed filters from financials that
  don't reconcile with each other, and showed no anomaly flag.** MU's live
  sidecar drove `opmargin_expansion_bps: 5704.9` and `fcf_growth_ttm_pct:
  1291.39%`, both silently PASSing — a >20-percentage-point YoY margin swing
  and a >300% TTM FCF swing are far more likely a quarter-alignment or
  duplicate-row artifact than a real reading, but Filters 4 and 5 had no
  anomaly check the identical arrays already get on the Financials chart.
  A tight reconciliation band (trailing-4-quarter revenue vs. the prior
  annual figure) was considered and rejected — a fast-growing company
  genuinely diverges from a year-old annual figure mid-fiscal-year, and a
  tight band would misfire on real hypergrowth. Fixed with two new ceiling
  constants, `FRAMEWORK_OPMARGIN_MAX_PLAUSIBLE_BPS` (2000) and
  `FRAMEWORK_FCF_GROWTH_MAX_PLAUSIBLE` (3.0), bounding the FILTER'S OWN
  OUTPUT magnitude rather than the input ratio — a swing past either ceiling
  reads UNKNOWN rather than a guessed PASS/FAIL, the same "no trustworthy
  data, no guessed verdict" rule this file applies everywhere else.
- **[major] Flow-board staleness check had a live 35-minute blind spot
  inside the loop's own documented active window.** `staleWindowActive()`
  covered `open` (08:30-15:00 CT) and `premarket` from 08:15, but nothing
  covered 15:00-15:20 CT — 20 minutes the page's own tooltips repeatedly
  promise are covered ("outside 8:00-15:20 CT the last publish stands"). A
  fetcher stall at 15:05 drew no STALE badge on any flow board for the
  final 15 minutes of the loop's documented window. The 08:00-08:15
  front-edge gap is a deliberate buffer for the loop's first daily cycle
  and was left unchanged. Fixed by extending `staleWindowActive()` with an
  `afterhours`-until-15:20-CT branch.
- **[major] The 5-metric framework panel never showed the fund-sidecar
  staleness badge the rest of the Overview tab enforces for the same
  file.** Fwd P/E, Short % float, and Next earnings all gate on
  `fundBuiltStaleDays(fund)` in the Fundamentals grid, but 3 of the 5
  framework filters (revenue growth, opmargin expansion, FCF growth — not
  just the 2 originally suspected) read from that identical `fund` object
  with no staleness signal on the framework panel at all. Fixed by calling
  `fundBuiltStaleDays(FUND_CACHE[sym])` in `stageFrameworkHTML` and
  appending the same STALE badge convention next to the panel's header.

---

## Shipped 2026-08-22, round 9 (24 findings confirmed, all fixed)

Round 9 checked the round-8-fixed page — the first round run under the
feature freeze, with no new feature landing between rounds 8 and 9. Pre-fix
scores:

| Section | R9 |
|---|---|
| Left watchlist rail | 80 |
| Flow boards | 79 |
| Auto-TA | 74 |
| Sector Heatmap | 74 |
| Data honesty | 78 |
| vs Peers | 64 |
| Right rail panels | 60 |
| Financials | 46 |
| Chart Stage | 42 |

**Left watchlist rail cleared 80 for the first time.** Its 2 confirmed
findings were fixed anyway, per the finish-line ruling above (a passing
score doesn't exempt a section from a confirmed finding). Two of Data
honesty's findings landed on the newest code in the repo — gamma levels,
shipped the same day the freeze took effect — which is exactly the pattern
the freeze exists to stop from recurring.

**24 findings confirmed** across the 9 sections. None of the round-8 fixes
broke or regressed; every round-9 finding is new ground the deeper pass
reached.

They are ordered by section in review order; within each section, blocker
first, then major, then minor.

#### Chart Stage — 42

- **[blocker] 1H and 4H charts silently drop the most recent real hourly
  candle on every symbol whose fetch cycle catches it before the next
  live-quote row appends.** `intervalDataFor`'s live-quote-artifact detector
  compared the last bar's timestamp against a fixed hour grid (`t%3600===0`)
  to find Yahoo's off-grid live quote and drop it — but every REAL
  08:30-anchored regular-session hourly bar also lands at :30 past the hour
  (`t%3600===1800`, in UTC epoch seconds, DST or not), so the check deleted
  the genuine latest candle instead. Verified live on MU/CRWD/COHR/V's i60
  series. **Fixed**: detection now uses the live-quote row's own signature
  (zero range, zero volume) instead of a grid modulus.
- **[major] Today's candle stays dimmed at 50% opacity all evening even when
  it is the real, fully-settled closing bar.** The dimming gate checked only
  `STAGE.synthetic`, not `STAGE.syntheticReal` — so a scanner-sourced,
  genuinely complete afterhours close (not a fabricated bracket) drew
  translucent, contradicting the crosshair's own "fabricated" definition a
  few lines below. **Fixed**: gated on `STAGE.synthetic && !STAGE.syntheticReal`.
- **[major] Weekly view's "no session open/high/low yet" and "open is
  yesterday's close" disclosures are false once earlier days in the same
  week have already traded.** Both captions were written as if the visible
  bar held nothing but today's bracket; a 1W chart opened midweek already
  has real Monday/Tuesday sessions baked into the same weekly candle's
  open/high/low. **Fixed**: `intervalDataFor` now counts real prior days in
  the current week (`STAGE.weekRealDays`), and both captions name that count
  when nonzero instead of claiming the week has no real data at all.

#### Automatic Technical Analysis — 74

- **[major] "Closest approach" caption actually reports the WORST touch, not
  the closest.** `fit.worstTouch` tracks the maximum gap among counted
  touches; the caption called it "closest approach," the opposite of what
  it measures. **Fixed**: relabeled "loosest touch."
- **[major] Chart's 50-day/200-day "% vs it" legend uses yesterday's frozen
  price during pre-market, while the candle beside it shows today's real
  gap.** `seriesFull`'s trailing-window append read raw `q.px` (still
  yesterday's price pre-market) instead of the session-aware price
  `candleClose`/`dispQuote` already compute — distorting the rolling
  average by one sample and silently diverging from the chart's own drawn
  MA lines (which use `candleClose`-built rows). **Fixed**: `seriesFull` now
  calls `candleClose()`, the same function the candle itself uses.
- **[minor] Flag/pole reclassification has no cap on how long a "pole" can
  span, so a slow multi-month drift can be mislabeled a sharp flagpole.**
  The bar-count factor in the magnitude threshold was capped at 15, so a
  100+-bar "pole" needed the same magnitude as a 15-bar one. **Fixed**:
  removed the cap; the threshold now scales with the pole's real length.

#### Left watchlist rail — 80

- **[major] MOVERS box fabricates a "names that have printed pre-market"
  count for symbols with no data at all.** `dispQuote(null)` returns
  `prev:false`, the identical shape a genuine pre-market print returns, so a
  symbol the feed hasn't answered for yet was counted as "printed"
  alongside names that actually had. **Fixed**: the count now requires
  `liveBySym(s)!=null` before checking `.prev`.
- **[minor] A leveraged/inverse wrapper's range bar shows a
  reverse-split-distorted position with no caveat on the row itself.** The
  shopping list already excludes these names on the strength of this
  disclosure; any OTHER box showing the same bar (52w sort, groups view)
  gave no hint. **Fixed**: added a "(lev.)" tag and tooltip to
  `rangeBarHTML` whenever `isLeveraged(sym)`.

#### Financials tab — 46

- **[blocker] Tapping a financial chart, then clicking any stage tab,
  permanently destroys the tap-to-read readout for the rest of the
  session.** `#chartread` physically moved itself into whichever `.gwrap`
  grid was tapped via `insertAdjacentElement` — planting it as a descendant
  of `#stagetabbody`, so the next tab switch's `body.innerHTML=...`
  destroyed the actual DOM node. This was a correction of round 8's own
  financials finding #3 fix, which fixed the visual symptom (a cramped
  300px-wide readout) without noticing the reparenting itself was
  destructive. **Fixed**: `#chartread` never leaves its original position as
  a sibling of `#stagetabbody`; a new `.floating` class repositions it with
  `position:absolute`, computed from the tapped chart's own bounding box
  against `#s-stage`.
- **[major] The outlier clamp on the Financials money and EPS charts
  flattens MU's real, current earnings/revenue explosion into a bar
  indistinguishable from a smaller prior quarter.** `robustClampMag` judged
  an outlier purely by magnitude against the series median, which can't
  tell a lone data glitch (NBIS's real spinoff-quarter margin distortion)
  apart from genuine sustained compounding growth (MU's real earnings) —
  both are "one point far above the median." **Fixed**: a candidate outlier
  is no longer clamped when its own immediate neighbor is also well above
  the ordinary spread, since a lone spike's neighbors sit back at normal
  levels and sustained growth's don't.
- **[minor] `numStr`/`pctStr` print a plain ASCII hyphen for negative
  values, breaking the file's own U+2212 minus-sign convention** used
  throughout the Fundamentals grid (P/E, PEG, Fwd P/E, P/S, P/B, EV/EBITDA,
  Debt/Eq, Beta, margins, ROE, dividend yield). **Fixed**: both functions
  now route through the same substitution the axis/hover formatters use.

#### Sector Heatmap — 74

- **[major] Isolating a sector that empties out renders a silent blank
  box.** The toolbar's own "show all sectors" button already names the
  isolated sector and offers the recovery action, but the box itself gave
  no indication anything was wrong. **Fixed**: added an inline message
  inside `#heatwrap` for the same case.
- **[major] "Scanner unreachable" is printed for a self-caused empty Desk
  watchlist, not just a real API failure.** Hiding every pinned name (or
  adding none) makes `heatDeskTickers()` return empty, but the code fired
  the scanner request anyway and blamed TradingView for the resulting empty
  response. **Fixed**: `heatFetchNow` now short-circuits before the request
  when the Desk universe has no tickers, with a distinct message.
- **[major] Desk-universe size fallback can mix market cap into a
  dollar-volume map by 2-3 orders of magnitude, with only a tooltip flagging
  it.** Round 8 added the tooltip; nothing made the distortion glanceable
  without hovering. **Fixed**: a new dotted `.capfall` hatch class, distinct
  from `.nodata`'s diagonal and `.prev1d`'s vertical lines.
- **[minor] `.nodata` hatch can be silently overridden by `.prev1d` hatch on
  the same tile.** Both classes could apply to one tile, and CSS cascade
  order let `.prev1d` win, hiding the stronger "no data" fact. **Fixed**:
  the three hatch states (`nodata`/`prev1d`/`capfall`) are now mutually
  exclusive by precedence, `nodata` always winning.

#### vs PEERS tab — 64

- **[blocker] Fundamentals tab and vs-Peers tab disagree about whether peer
  data exists — live and reproducible on V.** A curated set with one
  unresolved peer (V's own NASDAQ:FISV pin is stale — Fiserv trades NYSE:FI
  now) deliberately never writes `PEERS_CACHE` (kept retryable), so
  `peerStat`'s no-override fallback — the only path the Fundamentals grid
  uses — saw nothing cached and showed zero peer context, while vs-Peers,
  holding the resolved result directly, correctly ranked V against 3 real
  peers one click away. **Fixed**: a new `PEERS_LAST` cache always holds the
  most recent result regardless of completeness; `peerStat` falls back to
  it, while `peersFor`'s own retry-on-incompleteness behavior is unchanged.
- **[minor] The "comparing SYM to its peers…" loading state has no timeout
  and no way to tell a hang from a fetch in progress.** **Fixed**: a 10s
  timeout races the fetch and falls back to the same "scan-failed / reopen
  this tab to retry" message every other peers failure already uses.

#### Right rail panels + top rail — 60

- **[blocker] A released catalyst (econ print or earnings) silently
  disappears from the rail instead of showing "released"/"cleared".**
  `fetch_econ_tv` requests `from=now` forward only, so a print that released
  an hour ago is simply absent from the next hourly refetch, and
  `build_catalysts` has no memory of the previous cycle's rows to backfill
  from — a HIGH-importance print could vanish well before the frontend's
  own 6h grace period would call it "cleared." **Fixed**: a new
  `_merge_catalysts_forward` (fetcher/context.py) backfills any previous
  cycle's row still inside its own grace period (mirrored exactly from the
  frontend's `catDone`/`countdown` logic via `_catalyst_still_fresh`) that
  the fresh fetch no longer carries. 6 new tests cover both helpers.
- **[major] `DATA_CONTRACT.md` promises `actual` is "filled in once the
  print lands"; no code path ever sets it.** TV only reports a non-null
  `actual` once a row has released — and a released row's time is
  necessarily in the past, which a `from=now` request can never receive by
  construction. **Fixed**: `fetch_econ_tv` now looks back 26 hours (bounded
  so it only ever adds today's already-released rows; `build_catalysts`'s
  own window filter still drops anything from a prior calendar day). The
  contract note is also corrected to name the CSV-mirror exception (a
  CSV-sourced anchor carries no numeric fields at all and wins date+title
  conflicts against TV regardless).

#### Flow boards — 79

- **[major] Conviction header's bull/bear/firing counts describe the whole
  watchlist, not the board shown underneath, with no disclosure.** The
  counts were computed from the full scored array before the score-floor
  cut was applied. **Fixed**: the header now also shows the shown-board's
  own bull/bear split in parentheses whenever the cut actually trims
  anything, with a tooltip spelling out both scopes.
- **[minor] Mobile Conviction board loses its contract column entirely;
  Swing keeps the equivalent column at the same breakpoint.** The mobile
  media query hid both RVOL and the loudest-contract column on Conviction,
  while Swing's equivalent rule kept its own last column. **Fixed**: only
  RVOL is hidden now.
- **[minor] Sortable column headers on all four boards are mouse-only.**
  **Fixed**: added `tabindex`, `role="columnheader"`, `aria-sort`, and a
  keydown handler (Enter/Space) to the shared `table()` helper's sort
  headers, mirroring the tab-stop treatment already given to heatmap tiles.

#### Data honesty — 78

- **[major] `avg_move` (the "×usual move" HOT badge input) is computed with
  two different window sizes for desk names vs. custom watchlist names.**
  The fetcher's `_avg_move` uses the last 20 closes (19 changes);
  `adhocFillAvgMove` used 21 closes (20 changes) — a one-day-wider window
  for the identical figure. **Fixed**: `adhocFillAvgMove` now matches the
  fetcher's window exactly.
- **[minor] Gamma-levels caption never discloses that only the top 4
  strikes are shown, and the printed percentages don't sum to 100% with no
  explanation.** `total_strikes` isn't published (only `total_gamma_oi`
  is), so a literal "top 4 of N strikes" isn't available. **Fixed**: the
  caption now discloses coverage as a percentage of total gamma open
  interest instead.

---

## Shipped 2026-08-22, round 8 (26 findings confirmed, all fixed)

Round 8 checked the round-7-fixed page. **No section reached 80 pre-fix.**
Pre-fix scores:

| Section | R8 |
|---|---|
| Left watchlist rail | 76 |
| Auto-TA | 74 |
| vs Peers | 74 |
| Sector Heatmap | 64 |
| Flow boards | 62 |
| Right rail panels | 60 |
| Data honesty | 60 |
| Financials | 55 |
| Chart Stage | 58 (real score — see methodology note below) |

**26 findings confirmed** across the 9 sections (Data honesty's one finding
was the same underlying bug as Chart Stage's phantom-candle finding, counted
once in the fix pass). None of the round-7 fixes broke or regressed; every
round-8 finding is new ground the deeper pass reached, the same pattern as
every prior round.

**A methodology note worth keeping, again**: the raw run's Chart Stage
reviewer returned schema-valid placeholder garbage (`section:"test"`,
`summary:"test summary sentence one. test sentence two."`, a `"t"`-titled
finding) — the exact failure mode round 7's own methodology note warned
about, on the exact section it warned about it happening to (Auto-TA, that
time). Caught by reading `journal.jsonl` rather than trusting the returned
report, then re-run standalone with a content-sanity retry script
(`docs/review/chart-section-redo.js`) that rejects a review whose section
name, summary, or any finding field looks like a placeholder and retries up
to 4 times before accepting one. Real score: 58, with 3 confirmed findings.
**A schema pass is still not a content pass — check every section's score
against the real journal before trusting it, not just the ones that "look
low."**

They are ordered by section in review order; within each section, blocker
first, then major, then minor.

#### Chart Stage — 58

- **[blocker] Chart fabricates a phantom trading day on weekends and
  holidays, with no disclosure.** index.html: `stageDailyData` (live-append
  daily path and adhoc daily path), `seriesQuads` (feeds the 1W resample).
  `priceSessionNow()` returns `"closed"` whenever `isTradingDay()` is false,
  but the live-append branches never checked it — they only branched on
  premarket vs. everything else. Since `pollTvPrices()` runs unconditionally
  every tick and the scanner keeps returning Friday's last OHLC over a
  weekend, the chart built and appended a full synthetic "today" candle
  under Saturday's or Sunday's real calendar date, with `syntheticReal=true`
  so none of the existing fabrication disclosures fired. The same unguarded
  pattern in `seriesQuads` gave the weekly chart a phantom week too. This is
  exactly the class of bug the fetcher's `write_history` guard exists to
  prevent server-side, with no client-side counterpart until this fix. Same
  underlying bug as Data honesty's one confirmed finding this round.
  **Fixed**: all three synthetic-bar branches now gate on
  `isTradingDay(new Date())`.
- **[major] Chart never repaints when the OS auto-switches light/dark, while
  the heatmap now does.** The `prefers-color-scheme` change listener added
  in round 7 for the heatmap's `_heatRGB` cache never called `stageTheme()`
  or `stageRender()`, so a chart left open across an OS-scheduled dark-mode
  switch kept its old-theme background, grid, text and candle colors glued
  onto a now-dark page. **Fixed**: the same listener now also calls
  `stageTheme()` and, if a symbol is open, `stageRender()` and
  `renderStageTab()`, when no explicit `desk.theme` is stored.
- **[major] Weekly view's current (partial) candle is mislabeled "closed"
  any weekday afternoon before Friday.** `stageSetOhlc`'s todayTag logic used
  today's own intraday session state even when `STAGE.iv==="1W"`, so hovering
  the current week's still-building candle on a Tuesday afternoon after the
  close printed "this week, closed" — asserting the weekly bar was settled
  three days early. **Fixed**: added `isLastTradingDayOfWeek()`; for the 1W
  view, "closed" now means today is the last trading day of the week, not
  merely after today's own close.

#### Automatic Technical Analysis — 74

- **[major] Breakout freshness/fit thresholds are bar counts, never scaled
  to the active chart interval — Daily and Weekly verdicts on the same
  ticker genuinely disagree.** `TA_FRESH_BARS`, `TA_MIN_SPAN` and
  `TA_MIN_WIN_FOR_TREND` are tuned for daily bars; switching to 1W (5x fewer
  bars per calendar week) or 15m/1H/4H (many more) changed what "recent" or
  "long enough" meant without changing the constant, so the same ticker
  (XLB) could show a fresh breakout on 1D and a stale/failed one on 1W for
  the identical calendar stretch. **Fixed**: new `TA_BARS_PER_DAY` map and
  `taBarScale()`/`taFreshBars()`/`taMinSpanScaled()`/`taMinWinForTrend()`
  helpers scale all three thresholds by the active interval; every call site
  in `taFitLine`, `taRegrade` and the `tooShort` summary now reads the
  scaled value.
- **[major] S/R "levels" caption never states distance, though the filter
  allows levels up to ~20% away with identical formatting to a level 1%
  away.** AMAT's live 1Y chart shows a support band 19.3% below spot printed
  with the same "under $X ×N" wording as a 1%-away level, with no way to
  tell them apart from the text alone. **Fixed**: each level's text now
  includes a %-distance figure computed from the near edge of the level
  (reusing `taSrSide`'s own side determination, never re-derived).
- **[minor] "Too short to fit a trend line" message hardcodes "try 3M or
  longer" even when 3M can't add bars or doesn't apply.** SKHY/SKHX (30/28
  total daily bars, under the minimum at every window including 1Y) and
  every non-1D interval (1W/15m/1H/4H, which have no "3M" range control)
  got the identical dead-end suggestion. **Fixed**: the suggestion now only
  appears when `STAGE.iv==="1D" && STAGE.tf!=="1Y"`, matching the sibling
  "no trend line fits" message's own existing gate; the bar-count number now
  reads `taMinWinForTrend()`.

#### Left watchlist rail — 76

- **[major] MOVERS and shopping-list boxes show hotOf()/statsOf() figures
  without checking liveStale(), so a frozen quote reads as a live mover.**
  Neither summary box checked the per-symbol staleness the individual rail
  rows already carry. **Fixed**: both boxes now append a STALE tag (with a
  tooltip) next to any name whose price feed has gone quiet.
- **[minor] isLeveraged()/LEV_NAME_RE has no keyword for plain
  (non-leveraged) inverse funds, so the shopping list's own exclusion
  promise doesn't hold for them.** ProShares' plain inverse funds (SH, PSQ,
  DOG, MYY) are named "Short S&P500"/"Short QQQ"/etc. — none of "inverse",
  "ultra", or "2x" appear, so they slipped past the exclusion the tooltip
  advertises. **Fixed**: `LEV_NAME_RE` now also matches "short" followed by
  a major index name.
- **[minor] Shopping list silently caps at 3 names with no overflow
  disclosure, unlike the MOVERS box two lines above it in the same panel.**
  **Fixed**: added a "+N more — sort by range" note, mirroring MOVERS' own
  "+N more — sort by hot" pattern.

#### Financials tab — 55

- **[blocker] Revenue/NI/FCF chart and the EPS chart have no outlier clamp,
  unlike Margins/YoY — a single anomalous quarter visually flattens the
  rest.** The `robustClampMag` outlier clamp shipped in round 6 for
  Margins/YoY was never extended to the two chart types sitting right next
  to them. Live on LITE's EPS array and NBIS's FCF. **Fixed**: both charts
  now compute and apply the same clamp; the shared caption note now
  describes "one or more charts" instead of naming only margins/growth.
- **[major] Tapping a financials chart's data band breaks the chart grid's
  layout on ordinary desktop widths.** `#chartread` moves itself into
  whichever `.gwrap` grid the tapped chart lives in via
  `insertAdjacentElement`, but had no `grid-column` of its own, so it took
  only one 300px track instead of spanning the row. **Fixed**: added
  `.gwrap .chartread{grid-column:1/-1}`.
- **[major] The "vendor duplicated this row" caveat fires on a real,
  non-duplicate quarter pair when only EPS coincidentally rounds the
  same.** ONTO's real, distinct Q2/Q3 24 quarters happened to round EPS to
  the same figure while revenue genuinely differed; the check only compared
  EPS. **Fixed**: now requires revenue AND EPS to both match at the same
  index before flagging a probable duplicate.
- **[minor] A stale sidecar build silently ages every quarterly/annual
  chart with no flag on the Financials tab, while the adjacent STALE
  tooltip explicitly (and now incompletely) lists what it thinks is
  affected.** **Fixed**: the "built {date}" text now carries the same STALE
  badge Fwd P/E and Next earnings already show, off the same
  `fundBuiltStaleDays` check.

#### Sector Heatmap — 64

- **[major] Tile tooltip prints market cap as if it were the day's dollar
  volume traded.** When `r.dvol` was null for a real stock (missing
  volume data that day, not a fund sized by dollar volume), the tooltip fell
  back to market cap but kept the "traded per day" wording. **Fixed**: the
  fallback now reads "market cap (no dollar-volume reading today)" instead.
- **[major] The global tile-count cap runs before sector grouping, so whole
  sectors can vanish with no sector-level notice.** A small-cap-heavy sector
  (Utilities, Real Estate) could sort entirely below the cutoff and
  disappear from the map, with only a generic "N smaller names left off"
  count. **Fixed**: the cap now diffs the sector set before and after
  slicing and names any sector that vanished entirely in the footer note.
- **[minor] postmarket_change is fetched but never read, so the map has no
  after-hours equivalent of the rail's AFT chip.** **Fixed**: after-hours,
  a tile's 1D reading now swaps to the live postmarket print (tagged POST),
  mirroring the existing PRE/PREV convention.

#### vs PEERS tab — 74

- **[major] Revenue-growth-indexed chart computes which peer lines are
  stale vs live, then discards that fact instead of disclosing it.** The
  `sources` object (sidecar vs. scanner per peer) was computed but the
  printed note stayed the generic "sidecar where the desk has one" sentence
  regardless of what actually got used. **Fixed**: the note now names which
  peers, if any, came from the live scanner instead of the daily sidecar.
- **[minor] Primary-listing tie-break for a collapsed dual-class issuer is
  written but never called.** `_tickerRank()` existed to prefer a plain
  ticker over a suffixed dual-listing on a collision, but `ingest()`'s
  `seenIssuer` collision check just kept whichever row arrived first. The
  "/"-suffix half was already redundant with an existing filter; only the
  "."-suffix half needed it. **Fixed**: wired `_tickerRank()` into the
  collision branch so a better-ranked line can now replace an
  already-accepted one for the same issuer.
- **[minor] The metric-bar HTML is fully rebuilt twice on every peers-tab
  open.** Only PEG (via `derivedPeg`/`FUND_CACHE`) needs fund data that
  isn't ready on first paint; every other metric already renders its final
  value immediately. The old code recursed into `renderPeersInto` a second
  time regardless, tearing down and rebuilding the whole section (every
  metric, the key, the source note) just to refresh PEG, discarding any
  tap-to-read state on an unrelated chart in the process. **Fixed**:
  extracted the per-metric chart builder into `oneMetricChartHTML()`; the
  post-fund-load step now patches only PEG's own chart node in place via
  `outerHTML`, and the recursive call/`isRedraw` parameter are gone.

#### Right rail panels + top rail — 60

- **[major] Fed-odds card: headline % and legend % for the same "hike"
  reading can disagree.** The card headline used plain `toFixed(0)`; the
  legend used largest-remainder rounding across all three legs so they sum
  to 100 — the two round the same number two different ways and can print
  different whole-percent figures a few inches apart. **Fixed**: extracted
  the largest-remainder logic into a shared `fedLegPct()` helper and a
  `hikePct` field computed once in `normalizeFedOdds`; the card headline,
  the rail chip, and the FED HIKE RISK banner all read the same value now.
- **[major] Market-state lamp flips a full poll cycle ahead of the tape
  tiles it sits directly above.** The lamp rides a 1-second clock-derived
  repaint (added round 7); `renderTape()`'s PRE/AFT tags only repainted on
  the 30-second data poll, so the lamp could read OPEN or AFTER HOURS up to
  30 seconds before the tiles agreed. **Fixed**: `renderTape()` (a pure
  render off already-cached data, no network call) now runs on the same
  1-second timer as the lamp.
- **[minor] News panel's staleness badge can freeze forever during exactly
  the total-outage scenario staleness exists to catch.** `renderCats()`
  already recomputes its own staleness badge on a standalone 30-second
  timer regardless of whether `fetchData()` got a new payload; News had no
  equivalent — its badge only updated from `renderNews()`'s own call inside
  the data-fetch success path, which never fires during an outage.
  **Fixed**: new `tickNewsStat()` rewrites just the `#newsstat` badge span
  on the same 30-second timer, without a full `renderNews()` rebuild (which
  would throw away keyboard focus on a headline link, per the existing
  `tickNewsStamps()` comment).

#### Flow boards — 62

- **[blocker] MOSTLY INTRINSIC badge's real detection method never runs —
  o.spot is never published.** The frontend logic (added in round 7 to fix
  the badge's flicker) reads `o.spot` from each BigOrder row, but
  `build_snapshot.py`'s `big_candidates.append()` never included a `spot`
  field — verified against the live `origin/data:data.json` payload.
  **Fixed**: added `spot` to the BigOrder row dict and to
  `DATA_CONTRACT.md`'s BigOrder schema.
- **[major] Conviction and Swing boards lose their live price/% block on
  phone widths — CSS class collision.** Both boards' live price/change span
  shared the `.nm` class with sector-table company names; the mobile media
  query's `td .nm{display:none}` rule (meant only for those names) silently
  hid the live price on a phone too. **Fixed**: renamed the boards' span to
  `.livepx` with its own (unhidden) CSS rule.
- **[minor] The 'VOL > OI' new-position badge disappears on mobile along
  with the column it's glued to.** The badge was appended inside the Open
  Interest `<td>`, which the mobile media query hides outright to fit the
  table. **Fixed**: moved the badge into the Side cell, which is never
  hidden at mobile.

#### Data honesty — 60

- **[blocker] Chart fabricates a "today, closed" candle on days the market
  never opened.** Same underlying bug as Chart Stage's finding #1 above —
  fixed once, by the same change (the `isTradingDay()` gate on the
  synthetic-bar branches).

---

## Shipped 2026-08-22, round 7 (27 findings confirmed, 1 refuted, all fixed)

Round 7 checked the round-6-fixed page against Zach's 2026-08-21 ruling that
the passing bar is 80, not 90. **No section reached 80 pre-fix.** Highest was
Chart Stage at 79 — one point short. Full pre-fix scores:

| Section | R7 |
|---|---|
| Chart Stage | 79 |
| Financials | 65 |
| Sector Heatmap | 64 |
| Flow boards | 62 |
| Data honesty | 62 |
| Left watchlist rail | 60 |
| vs Peers | 58 |
| Right rail panels | 52 |
| Auto-TA | 47 |

**27 findings confirmed, 1 refuted** (a Biggest Orders IV-ceiling finding in
Flow boards — real defect, fabricated example ticker; see that section). None
of the 26 round-6 fixes broke or regressed; every round-7 finding is new
ground the deeper pass reached, same pattern as every prior round.

**A methodology note worth keeping**: this round's raw run produced two unusable
section results that a later session should watch for. The Financials
reviewer hit the StructuredOutput retry cap (5 failed calls, no valid output)
and was silently dropped by `results.filter(Boolean)` — the section was simply
absent from the report, not scored low. Separately, the Auto-TA reviewer
returned schema-VALID placeholder garbage (`section:"test"`, `summary:"test
summary sentence one. test summary sentence two."`, a finding with fields
`"t"`/`"1"`/`"f"`/`"x"`) that passed structural validation because it had the
right shape, not real content — the adversarial verifier caught and refuted
the fake finding, but the section score itself was worthless. Both were
caught by reading `journal.jsonl` directly rather than trusting the workflow's
summary, then fixed with a small targeted re-run script that adds a
content-sanity check (short summary, or any finding field ≤2 chars) and
retries before accepting a review. **Read the journal, not just the returned
report, before treating any round's scores as real** — a schema pass is not
a content pass.

They are ordered by section in review order; within each section, blocker
first, then major, then minor.

#### Chart Stage — 79

- **[blocker] The one disclosure that a candle is fabricated/pre-market-only
  can be silently truncated away.** index.html:515-522 (CSS), 5601-5644
  (stageSetOhlc). The fabricated/pre-market tag ("CLOSE ONLY" / "· pre-market")
  is concatenated LAST in the OHLC readout string. At ≤640px the container
  switches to `white-space:normal; max-height:30px` with `overflow:hidden`
  and no ellipsis, so a 3rd wrapped line is hard-clipped — and the disclosure
  tag, always last, is always the first thing lost. Fix: put the tag FIRST,
  or render it as its own non-truncatable badge outside the clipped line.
  Note: accurate on the mechanics; the certainty of "runs past two lines on
  every phone" should be read as "on narrow phones combined with the
  extended-hours date suffix," not universal — but the tag is always the
  part that would be lost first, since it's always last in the string.
- **[major] Daily/weekly chart gives a fabricated or pre-market-only "today"
  candle zero visual distinction, unlike intraday.** Lines 5449-5461 (ext
  dimming gated on `STAGE.intraday`), 5233-5357 (`STAGE.intraday` hardcoded
  false for 1D/1W). Intraday extended-hours bars dim to 50%/20% opacity; the
  daily/weekly view's live "today" candle — fabricated bracket or
  pre-market-only — draws at full opacity, visually identical to a settled
  day. Fix: apply the same dimming whenever `STAGE.synthetic` is true on the
  1D/1W views, so the visual channel (not just a truncatable text tag) tells
  the reader this bar isn't settled.
- **[minor] Chart's Bollinger Bands include the live/synthetic price,
  contradicting the codebase's own no-live-contamination rule for the same
  indicator.** Lines 7816-7843 (`stageTA`'s BB block uses `STAGE.rows`,
  which includes the live-appended candle) vs. 2774-2799 (`bollingerOf`'s
  documented completed-closes-only design). A full `stageTA()` recompute
  (window/interval click, overlay toggle, reopening the symbol — not the
  30-second poke itself) folds in whatever live price is current at that
  click, shifting the caption's band numbers with no new completed bar, and
  can disagree with what `bollingerOf()` reports for the same ticker at the
  same instant. Fix: compute the chart's BB from completed closes only, same
  convention as `bollingerOf`, optionally plotting the live close as a point
  against the frozen band.

#### Automatic Technical Analysis — 47

- **[blocker] An EXTENDED trend line is colored as if it never broke,
  directly contradicting its own caption.** Lines 7714-7718 (fit-time
  color), 7855-7863 (`stageTAPoke` live recolor), 7999-8006 (EXTENDED
  caption). Only `status==="BREAKOUT"` flips the color; RETEST, FAILED and
  EXTENDED all keep the pre-break color. EXTENDED can only occur on a
  confirmed, matured break (price ran >12% past the line, or the break is
  >12 sessions old) — never a false positive. A resistance line that broke
  out and ran 14% past is still drawn red ("resistance") while its own
  caption reads "...price has run 14.2% past it — the move is already
  made." Persists on every 30-second poke. Fix: treat any non-INTACT status
  as needing the flipped color once a break is confirmed (or at minimum add
  EXTENDED to the flip condition) — mirrors the `taSrSide` fix already
  applied to the horizontal S/R lines for this exact bug class.
- **[major] On-chart Bollinger Band dollar levels freeze shortly after the
  chart opens and never update all session, despite the code's own comment
  claiming otherwise.** Lines 7816-7843, 7893-7897 (comment says "computed
  on settled bars," only `.side` is actually re-derived), 8079-8093. Unlike
  the rail's `bollingerOf(sym)`, the on-chart band is computed over
  `STAGE.rows` including today's live-appended candle, baked in once at the
  boot-race full render and never recomputed. Verified against real
  bars.json: MU's upper/lower band shifts by $2.04/$5.97 depending on
  whether the render-time price snapshot or the day's actual close is used.
  Fix: recompute mid/upper/lower on every `stageTAPoke` (cheap — rerun
  `rollMA`/`rollStd`), or switch to the settled-bars-only convention
  `bollingerOf` already uses.
- **[major] The drawn SMA20/50/200 lines freeze at the same open-time
  snapshot while the adjacent legend text recomputes live.** Lines
  5469-5471 (MA `setData` only in full `stageRender`), 2737-2755
  (`statsOf`/`seriesFull` recompute fresh every call), 8888-8889 (legend
  prints "X-day · +Y% vs it" from the fresh call). The legend's stated
  percentage and the true visual gap to the drawn MA line can describe two
  different underlying values for any name that moved since the chart's
  last full render. Fix: recompute and re-set the last point of each MA on
  every live poke, or make the legend read the same frozen last-MA value the
  lines use.
- **[minor] The lone S/R axis price badge is assigned once and can end up on
  the wrong level as price moves.** Lines 7766-7771 (`nearestIdx` picked
  once at full render), 7803-7813, 7889-7892 (poke recolors every S/R line
  but never revisits which one gets the axis badge). If a different level
  becomes the genuinely closest intraday, the axis badge stays on the
  now-farther level until the next full re-render. The text caption stays
  correct (`taSrSide` re-runs live); only the one number on the price axis
  can point at the wrong line. Fix: recompute `nearestIdx` from the live
  price inside `stageTAPoke` and toggle `axisLabelVisible` in the same pass
  that already recolors the lines.

#### Left watchlist rail — 60

- **[blocker] Pasting a custom watchlist string never fetches facts or
  daily bars for the new names — the multi-device sync feature silently
  ships incomplete rows.** Lines 2885-2951 (`wlIoApply`) vs. 1178-1200
  (`wlAdd`). `wlAdd` (single search-add) explicitly calls
  `adhocEnsureFacts`/`adhocEnsureDaily`; `wlIoApply` (bulk paste) never does.
  Paste "PLTR,SNOW,DDOG" and apply: rows appear with price/name, but no
  52-week range bar, no earnings countdown, and they can never trigger the
  hot badge or appear in MOVERS/shopping-list — no matter how big a move —
  until the page is fully reloaded or each chart is opened individually.
  Fix: call both enrichment functions for every newly added symbol in
  `wlIoApply`'s success branch, same as `wlAdd`.
- **[major] `adhocEnsureFacts` and `adhocEnsureDaily` run as two unchained,
  racing fetches — losing the race permanently kills a searched ticker's
  hot-mover detection for the session.** Lines 1191/1198-1200, 1219-1233,
  2300-2339 (guard at 2331), 2420-2469. `adhocEnsureDaily` only writes
  `avg_move` if `adhocEnsureFacts` already populated `ADHOC_FACTS[sym]` —
  an ambient existence check, not a chained `.then()`. If the plain GET to
  stockanalysis.com wins the race against the TV scanner POST, the write is
  silently skipped, and every later call short-circuits on the now-existing
  `ADHOC_BARS[sym].D` without retrying. Fix: chain the two calls, or gate
  the `avg_move` write on an explicit `.then()` instead of an ambient check.

#### Financials tab — 65

- **[major] CBRS's live sidecar has byte-identical duplicate quarters and
  nothing in `renderGrowth` catches it.** Lines 6718-6880; no plausibility
  check exists in the function. Live `fund/CBRS.json`: Q1 23/Q2 23 both
  carry revenue exactly 4,332,000 and EPS exactly -0.907903 to six decimals;
  Q1 24/Q2 24 both carry revenue exactly 68,201,000 and EPS exactly
  -0.709393 — almost certainly a duplicated row from the semiannual-filer
  fetch. Plotted as fact on every chart with no caveat. Fix: add a
  duplicate-adjacent-period check (two consecutive periods both non-null and
  exactly equal) alongside the existing missing-data/outlier checks.
- **[minor] The tap-to-read band prints its answer below the entire
  Financials tab, not near the chart the reader tapped.** Lines 925-929
  (single shared `#chartread` div placed AFTER `#stagetabbody`), 6503-6531,
  9995-10011. On a 390px phone, tapping the first chart's answer appears
  after every other chart and the full caveat note — the reader has to
  scroll past everything on the exact device class this mechanism ("a
  phone never surfaces `<title>` on tap") was built to serve. Fix: give each
  chart its own inline readout directly beneath it, or reposition the single
  readout under whichever chart was tapped.
- Refuted: "`axisChartSVG` only ever draws one clip-arrow per series per
  direction, so an earlier clipped point vanishes with no marker at all."

#### Sector Heatmap — 64

- **[blocker] Ticker label can clip to a different real ticker with no
  ellipsis.** Lines 570-585, 8555-8589. `.hm-tile b`/`span` have no
  `white-space:nowrap`/`text-overflow:ellipsis` — unlike every other
  truncatable label in the file. A 5-letter ticker at the minimum
  label-showing tile size can clip to a different, real, currently-listed
  symbol (e.g. a clipped GOOGL reading as GOOG, both present on the same
  S&P 500 map). Fix: give `.hm-tile b`/`span` the same nowrap/ellipsis
  treatment plus `max-width:100%` (needed because column-direction
  `align-items:center` doesn't stretch the child).
- **[major] "Desk" heatmap universe includes names the user explicitly hid
  from the watchlist.** Lines 8189-8194 (`heatDeskTickers`), 1164-1210
  (`wlHidden`/`wlRemove`). Hiding a pinned name pushes it onto
  `desk.wl.hidden` without removing it from `RAIL_GROUPS`; `heatDeskTickers`
  never consults `wlHidden()`. A hidden name's tile still renders on the
  "Desk" map, sized and colored normally, with no note that it's not
  actually on the visible watchlist. Fix: filter `heatDeskTickers()` by
  `wlHidden()` the same way the rail itself does.
- **[minor] Heatmap pole colors go stale on an OS-driven theme change (no
  in-app toggle).** Lines 8331-8338, 9925-9939; no `prefers-color-scheme`
  change listener anywhere in the file. `_heatRGB` only invalidates on the
  in-app theme button click. Leave the tab open across an OS-scheduled
  light/dark switch with the heatmap open: tiles keep mixing the OLD
  theme's `--up`/`--dn` hex with the NEW theme's neutral midpoint. Fix: add
  a `matchMedia('(prefers-color-scheme: light)')` change listener that
  clears `_heatRGB` and re-renders, alongside the existing explicit toggle.

#### vs PEERS tab — 58

- **[blocker] Ranking captions go blank ("too few peers reported to rank")
  even when the chart above draws a full multi-peer comparison, whenever a
  curated set only partially resolves.** Lines 6968-6993 (`peersFor` only
  caches `if(live.length === syms.length)`), 9053-9071 (`peerStat` reads
  only the global `PEERS_CACHE`, never the `res` object already in hand),
  9188-9214. If any one of a curated 4-peer set fails to resolve on a given
  cycle, the chart draws correctly but the cache never populates, so every
  caption reads "too few peers to rank" directly under a chart with 4 real
  bars. Fix: pass the resolved `res.peers` into `peerStat` instead of
  re-reading a module-global cache. Note: the bug doesn't persist for the
  whole session as stated — reopening the tab retries the fetch and can
  self-heal — but it reliably breaks the caption on any render where the
  curated set only partially resolves.
- **[major] A peer chart can assert every peer is "more than 5× from SYM in
  size" when SYM's own market cap is simply unknown, not actually 5×
  off.** Lines 7022-7054, 9108-9123. `inBand()` treats a null `myCap` as
  "not in band" rather than "unknown" — common for foreign issuers/thin OTC
  names the scanner hasn't backfilled. The footer then names all four
  peers as size-mismatched with a specific, false numeric claim. Fix:
  distinguish "not in band" from "can't tell" — skip the ✳ marking (or
  name the real reason: no market cap for SYM) when `myCap` is null.
- **[minor] The indexed-revenue-growth chart disappears with zero
  explanation whenever fewer than 2 qualifying series clear the 5-quarter
  minimum**, breaking the file's own "a failed feed keeps its slot" rule.
  Lines 9235-9263. No fallback branch, no note — unlike every other
  empty/partial state in the file. Fix: append a one-line reason naming
  which names lacked enough revenue history, instead of omitting the
  section outright.

#### Right rail panels + top rail — 52

- **[blocker] FED HIKE RISK banner calls a 32% hike chance "near a coin
  flip" and fires below the documented 40% threshold.** index.html:3646-3651
  (`fedAlarmHTML`), 1826 (`loud` = `alarm===true || grade==="HOSTILE"`);
  fetcher/context.py `FED_HIKE_HOSTILE_PCT=25.0`; README.md:327. Live
  payload today: `{hike_pct:31.7, hold_pct:67.0, chg_1d_pp:4.1,
  grade:'HOSTILE', alarm:false}`. `loud` is true purely from the 25% grade
  floor, but `fedAlarmHTML` only has two phrasings ("jumped hard today" or
  "near a coin flip"), so a 2-to-1-against-a-hike reading with no daily
  jump prints "near a coin flip" — while README.md tells Zach the banner
  only appears above 40% or on a 10pp move, neither true here. Fix: add a
  third "why" branch for the HOSTILE-but-not-alarm case, and reconcile
  README.md's stated threshold with the actual 25% grade floor.
- **[major] 21 of 22 memory-market catalysts (SK Hynix, Samsung,
  hyperscaler AI-capex earnings, DRAM/NAND settles) never appear in the
  default catalysts view.** index.html:4364-4369 (`catPassesCurated`
  requires `c.ticker && desk[c.ticker]` for `kind==='memory'`); most memory
  events carry `ticker:null` by design (non-US-ticker companies, index-wide
  events — documented normal in DATA_CONTRACT.md). Only the "Memory" filter
  tab surfaces them, with no on-screen count or note that anything was
  dropped. Fix: drop the ticker-match requirement for `kind==='memory'`
  (mirror the anchor exception, or gate on importance like the econ branch
  does).
- **[minor] Reduced-motion users see every headline in the news ticker
  twice, back-to-back.** Lines 4632-4642, CSS 108-111. With OS reduce-motion
  on, the animation disables and the strip switches to manual scroll, but
  the track still contains the full item list twice (the duplicate is only
  `aria-hidden`, not invisible to scrolling). Fix: build the track from a
  single non-duplicated copy of `items` when reduced-motion is active.

#### Flow boards — 62

- **[blocker] "MOSTLY INTRINSIC" badge on the Biggest Orders board mixes a
  live spot price with a stale contract "last" price.** index.html
  4184-4198. `spotNow` is the 30-second live poll; `lastPx` is the option's
  frozen ~7-minute-old fetcher snapshot. If live price moves before the next
  publish, intrinsic value can recompute above the stale premium, driving
  extrinsic share negative (clamped to 0) and firing the badge purely from
  the timing mismatch, not because the contract actually lost extrinsic
  value — flickering on and off every 30 seconds with no indication the two
  numbers are from different moments. Fix: compute intrinsic against the
  snapshot's own spot, or detect impossible negative extrinsic and suppress
  the badge with a staleness tooltip instead.
- **[major] `contractLine` prints an unbounded, sometimes-nonsensical IV
  reading with no sanity ceiling.** index.html 3849-3866; only guard is
  `iv>0`. Live examples today: XLF (iv=8.4748 → "IV 847%"), AAOI (757%), XLV
  (559%), CORZ (511%) — all 0DTE, delta≈±1.0 deep-ITM pricing artifacts, not
  real implied vol. Fix: cap displayed IV (e.g. ~300%) and fall back to a
  dash with a tooltip noting a 0DTE/deep-ITM contract's quoted IV isn't
  reliable. Note: the finding's own XLY example was fabricated/stale (its
  live `iv` is actually 0.0, already suppressed by the existing guard) —
  the underlying code flaw is real, but cite XLF/AAOI/XLV/CORZ instead.
- **[major] Swing board never shows today's price or % change, though the
  row code already computes it.** index.html 4132-4140. `dq =
  dispQuote(liveBySym(c.ticker))` is computed but `dq.ch` is never rendered
  — the same field Conviction shows one section above using the identical
  live-poll mechanism. A trader has to open each ticker's chart just to see
  whether the name is up or down today. Fix: render the same
  price/±change block Conviction already builds, using the `dq` object
  already in scope.
- **[minor] DATA_CONTRACT.md's `etf_flows` note contradicts `renderETF`'s
  actual, intentional behavior.** DATA_CONTRACT.md 833-834 vs. index.html
  4285-4295. The doc says the frontend renders nothing when `etf_flows` is
  null/empty; the code deliberately keeps the card visible with an
  explanatory note instead (matching the "a feed that fails keeps its slot"
  convention elsewhere). The doc was never updated when that behavior
  changed. Fix: rewrite the `etf_flows` note to describe the current
  always-show-a-reason behavior.

#### Data honesty — 62

- **[blocker] "Short % float" reads from the same daily sidecar as "Fwd
  P/E", but only Fwd P/E and Next earnings get the STALE badge — and the
  chart tab's own source line contradicts itself about it.** Lines
  5954-6031, 9482-9484; DATA_CONTRACT.md:653-715. `fund.short_pct_float`
  never gets `fundStaleSub` appended, unlike the two sibling fields sourced
  from the identical `fund` object and build date. The source-line sentence
  names short interest as sidecar-sourced, then its own STALE tooltip in the
  same sentence omits it from the warning about that very sidecar. Fix:
  compute Short % float's own staleness sub-label the same way Fwd P/E's is
  computed, and rewrite the tooltip to name every field it claims comes from
  the sidecar.
- **[major] The framework's forward-EPS filters diff consensus `eps_ntm`
  across weeks/months with no split adjustment, unlike price bars which have
  one.** fetcher/context.py:2759-2786 vs. 1256-1351 (`_repair_split_breaks`).
  `consensus_history.json` snapshots raw `eps_ntm` weekly with no
  split-ratio check; a 2-for-1 split between two snapshots would halve
  `eps_ntm` mechanically and fail the Forward EPS revision filter for a
  company whose outlook didn't move at all. Not yet observed live (only one
  week of history exists since the feature shipped), but the misfiring path
  is already live and will start firing once 12-26 week lookbacks have data
  to compare. Fix: check for a split-sized break in price/share-count
  history between snapshot dates before diffing `eps_ntm`; skip (UNKNOWN)
  or rescale if one is found.
- **[minor] The framework verdict word collapses "clean record, still
  gathering data" and "mixed record, already failing" into the same
  label.** fetcher/context.py:2666, 2723-2733. `_FRAMEWORK_VERDICTS` maps
  `passed=3` to "ADD" whether the other 2 filters are UNKNOWN or FAILED —
  both render an identical chip. Not yet reachable live (today's data only
  has the 3-pass/2-unknown case), but will start mattering once the
  consensus-history filters resolve over the coming months. Fix: fold
  `filters_unknown` into the verdict word once some filters have resolved.

The review script is unchanged at `docs/review/nine-section-review.js`. The
two-section content-sanity re-run used for the Financials/Auto-TA redo is not
separately committed (it was a throwaway variant of the same COMMON/SCHEMA);
a future session hitting the same "schema-valid but empty content" failure
mode should add the `looksLikePlaceholder`-style check directly into the
main script rather than re-deriving it.

### Score trajectory, and what "80" would take

| Section | R3 | R4 | R5 | R6 (pre-fix) | R7 |
|---|---|---|---|---|---|
| Right rail panels | 69 | 72 | 78 | 72 | 52 |
| Data honesty | 72 | 81 | 78 | 58 | 62 |
| Sector heatmap | 74 | 76 | 74 | 48 | 64 |
| Flow boards | — | 74 | 73 | 72 | 62 |
| Left rail | 46 | 72 | 72 | 64 | 60 |
| vs Peers | 82 | 73 | 71 | 55 | 58 |
| Financials | 85 | 71 | 64 | 48 | 65 |
| Auto-TA | 56 | 67 | 58 | 48 | 47 |
| Chart stage | 69 | 67 | 55 | 42 | 79 |

The scores are not tracking quality in the way the numbers suggest. Every
round's reviewer opens a page whose previous faults are gone and goes deeper,
so a section that improved can score lower. Round 6's 26 fixes all held —
round 7 refuted 0 of them and found entirely new ground instead (Right rail
panels' drop from 72 to 52, for instance, is a live, currently-wrong Fed-odds
banner and a memory-catalysts filter gap, neither related to anything round 6
touched). The finding LISTS are the useful output, not the number. None of
the nine sections has reached 80 yet; Chart Stage's 79 is the closest.

**Round-7 fix pass (2026-08-22):** all 27 confirmed findings above were
fixed the same day. The non-obvious decisions, condensed, live in
`CLAUDE.md`'s "Guardrails added 2026-08-22, round-7 fix pass" section —
notably a new shared `taTrendFlipped`/`taSrBadgePick` pair for Auto-TA's
color/badge bugs (mirroring `taSrSide`'s existing pattern), the on-chart
Bollinger Band switching to completed-closes-only (which incidentally fixed
the Chart Stage minor finding in the same change), and a `_BUILDING`
verdict-word suffix plus a matching `_ratio_matches_split` guard on the
fetcher side. Verified: the full `fetcher/` pytest suite (270 passing,
including new tests for both fetcher-side fixes) and a `node --check` syntax
pass on the extracted inline script. **Not yet verified**: a fresh
nine-section review run against the fixed page (see "Round 8 verification
is pending" under Open, above) — treat the post-fix behavior as reasoned
through and tested, not yet re-scored by an independent reviewer.

---

## Shipped 2026-08-21, round 6 (26 findings, all fixed and verified live)

Round 6 ran 2026-08-21 (script: `docs/review/nine-section-review.js`, ~75
agents). All nine sections were scored and every finding went through
adversarial verification. **26 findings confirmed, 2 refuted** (both in the
heatmap section — a font-measurement claim and a tile-count-floor claim,
neither held up).

All 26 confirmed findings below are now FIXED, committed, and verified —
against the real live TradingView scanner via a rebuilt Playwright harness
(not just a code read) for the JS-side fixes, and against the full
`fetcher/` pytest suite (266 passing) for the fetcher-side one. The full
mechanism, the reviewer's original "Fix" text, and the adversarial verifier's
"Note" corrections are kept below as the historical record of what was wrong
and why the fix takes the shape it does; `CLAUDE.md`'s "Guardrails added
2026-08-21, round-6 fix pass" section has the condensed version of each
decision. They are ordered by section in review order; within each section,
blocker first, then major, then minor.

#### Chart Stage — scored 42 pre-fix

- **[blocker] Today's candle freezes at the pre-market bracket after the
  market opens.** Lines 9199-9243, 9211-9214, 5062-5068 & 5245, 1541-1546.
  `STAGE.premarketBar` is set once on the full pre-market render; every
  30-second poll after that trusts the cached flag instead of re-deriving
  `priceSessionNow()`, so once the regular session opens, the candle body,
  high, low and volume stay frozen at the pre-market bracket all day — only
  the header price keeps ticking — until the user manually changes
  interval/window/symbol. Fix: recompute `priceSessionNow()` on every poke;
  once past premarket, fall back to the existing live.o/h/l +
  `candleClose(live)` branch. Note: mechanism confirmed exactly as described;
  worth knowing the underlying cause is that TradingView's
  `premarket_close`/`premarket_change` columns stay frozen at the morning
  print rather than going null at the open, contradicting the code's own
  inline comment near line 2396.
- **[blocker] bars.json is fetched once per page load and never refreshed — a
  tab left open across a day boundary silently loses sessions.** Lines 1320,
  1892-1901, 9129, 5081-5083/5053. `ensureBars()` memoizes `BARS_CACHE`
  forever, no TTL, unlike `INTRA_CACHE`'s 5-minute refresh. Fix: staleness-check
  `BARS_CACHE.built` against the CT calendar day and re-fetch, same pattern as
  `INTRA_CACHE`. Note: the verifier corrected the description of the damage —
  the per-poll path prefers real live OHLC over `prevClose` when available, so
  it isn't simply "showing Friday's close as Monday's." The real damage: any
  completed session that elapses while the tab stays open is never added to
  the stored bars array at all — it's a missing day, not a mislabeled one —
  and it hits the daily/weekly chart, S/R, Bollinger Bands and %-stats alike.
- **[major] Vertical zoom-out can drive the log-scale price floor to exactly
  0.** Lines 4905-4933, 4926, 4930-4931, 5186/5190. Reachable with one ordinary
  wheel-scroll-out notch on a real, currently-tracked ticker (SOXS: 6M
  high/low 497.6/31.7 auto-triggers log mode; one notch computes a floor
  clamped to 0). Fix as proposed ("clamp `lo` to a small epsilon") turns out to
  be the wrong fix — see note. Note: the verifier reworked the math — the
  actual failure is not a discontinuity at 0, it's a squashing problem: the
  clamped range puts the real candle data into roughly the top 18% of the pane
  after one zoom notch, an ~82%-tall dead zone below it. An epsilon floor
  barely helps (log-coordinate ~2.0 vs. the real low's ~5.5). The fix that
  actually works is clamping `lo` to the window's own minimum low (or a
  proportionate margin below it), not to a small positive number.
- **[minor] 4H resample's session bucket boundary ignores half trading
  days.** Lines 4610-4617, 1481-1483, 1510. `slot4H` hardcodes the pm-bucket
  ceiling at minute 900 (3:00 PM) with no half-day check, unlike
  `priceSessionNow()` which already consults `MARKET_HALF_DAYS`. On a half day
  (2026-11-27, 2026-12-24, 2027-11-26), post-close bars land in the regular
  session bucket undimmed. Fix: look up `MARKET_HALF_DAYS` in `slot4H` too.
  Note: the fix as proposed is incomplete — bars from 12:00-12:30 CT on a half
  day land in the "am" bucket (ceiling 750), not "pm", so both the 750 and 900
  ceilings need to collapse to the half day's actual close (720), not just the
  900 one.

#### Automatic Technical Analysis — scored 48 pre-fix

- **[blocker] Horizontal S/R price-line color freezes at chart-open price
  while its caption keeps re-grading against the live price.** Lines
  7451-7506, 7539-7573, 7730-7749. `stageTA()` colors the dashed S/R line once
  from `taSrSide(l, lastPx)` at chart-open; `stageTAPoke()` re-grades the
  trend lines and the caption text every 30 seconds but never touches
  `STAGE.srLines`. A level drawn red ("overhead") while price has since risen
  above it can show a caption in green saying "under" the same level — the
  exact contradiction the code's own 2026-08-21 guardrail for `taSrSide` was
  written to prevent, just split across two call sites. Fix: have
  `stageTAPoke()` re-derive each S/R line's color the same way, via
  `priceLine.applyOptions({color:...})`, same pattern as the trend lines.
- **[major] Chart-pattern "shape" caption (triangle/wedge/flag) is computed
  once and never re-checked against the live re-graded status of the two
  lines it names.** Lines 7293-7295, 7449, 7539-7573, 7724-7727.
  `taShapeLabel` only excludes a fit-time `FAILED` status, not `BREAKOUT`; and
  `summary.shape` is computed once inside the full `stageTA()` pass, never
  recomputed by `stageTAPoke()`. A pattern name like "ascending triangle
  (support rising)" can keep showing after the caption two lines below it
  says that same support line broke down today. Fix: gate `taShapeLabel` on
  the live-regraded status, and recompute/clear `summary.shape` from
  `stageTAPoke()` — or at minimum blank it whenever either line regrades to
  `FAILED`, `BREAKOUT`, or `EXTENDED`.

#### Left watchlist rail — scored 64 pre-fix

- **[major] The paste-list "apply" box tells you a hidden pinned ticker is
  fine when it is invisible.** Lines 1132-1134, 2771-2822 (esp. 2784, 2817).
  `wlIoApply`'s `railHasSym` check never consults `wlHidden()`, so typing a
  hidden ticker into the "your custom list as text" box and clicking apply
  reports "already pinned, left alone" while the ticker stays hidden — the
  one tool that looks like it should undo a hide silently can't. Fix: inside
  the `railHasSym` branch, also check `wlHidden()` and unhide + report
  "unhidden" instead.
- **[major] `isLeveraged()` misclassifies an ordinary stock as a
  leveraged/inverse wrapper because of a bare "bear" match.** Lines 2758,
  2759-2763, 2928-2929, 3021. `LEV_NAME_RE`'s bare `bear` alternative has no
  digit guard (unlike `bull`, which requires `bull\s*\d`), so "Build-A-Bear
  Workshop, Inc." (ticker BBW, a real toy retailer) matches `\bbear\b` and
  gets sorted/excluded exactly like a leveraged ETF. Fix: require the same
  digit/qualifier guard on `bear` that `bull` already has.
- **[minor] A hidden pinned ticker that later drops out of `RAIL_GROUPS`
  becomes a permanent, unfixable phantom in the "N pinned hidden" count.**
  Lines 2896-2901, 2914-2920, 2953-2961. The ghost-row "+back" generator only
  iterates current `RAIL_GROUPS` membership, so a hidden ticker later dropped
  from the rail list has no row to un-hide it from, yet the "N pinned hidden"
  count still includes it forever. Fix: prune `wlHidden()` against the
  current `RAIL_GROUPS` union on render, or show orphaned entries as their own
  "no longer tracked" line. Note: the historical precedent the finding cited
  (BESIY/IFNNY/SPX/VIX/SPMO churn) is about the fetcher's `PINNED` list, not
  this file's `RAIL_GROUPS` array — a different list, though the same
  "ticker lists churn" premise still holds for `RAIL_GROUPS`.

#### Financials tab — scored 48 pre-fix

- **[blocker] Margins chart has no outlier clamp, so a stub-era ratio hides
  the current quarter.** Lines 6483-6491, 6052-6063, 6062. `axisChartSVG`'s
  y-domain spans the raw min/max of the whole series with no ceiling.
  Verified live on NBIS (Nebius): a post-spin-off Q2 24 net margin of -4588%
  compresses the current quarter (-32.7%) to under 1 pixel of a 138px plot.
  Also reproduced on CBRS, CIFR, CORZ, LITE, RIOT, CLSK, APLD. Fix: pass a
  clamp into the margins/YoY `axisChartSVG` calls and reuse the existing
  clip-arrow + caption convention. Note: the working clamp precedent the
  finding pointed to is actually the peers-tab revenue-growth-lines chart
  (line 8897), not `peerBarsSVG` (which has its own separate inline clamp).
  Also: for CIFR the extreme value is in the *current* quarter, not a stub
  era, so a naive "clamp to N× trailing-4Q median" could itself flatten a
  genuinely newsworthy current print — the fix needs to guard both directions.
- **[major] A semiannual filer's chart is titled and labeled as quarterly.**
  Lines 6472, 6509-6514, 6096, 5927-5946. CBRS (Cerebras, on the PINNED list)
  reports twice a year; `periodsPerYear()` correctly detects `ppy=2` and the
  YoY caption says so correctly, but the main "Quarterly — reported USD"
  panel header is a hardcoded literal that never checks `ppy`. Label-thinning
  at 8 periods also makes the axis read like one point per year. Fix: compute
  `periodsPerYear()` once near the top of `renderGrowth` and word the glabel
  off it. Note: the EPS panel header (line 6511) doesn't actually say
  "Quarterly" at all — it's silent on cadence, not actively wrong — so the fix
  should target the glabel at 6472 first; adding a cadence word to the EPS
  header is optional polish, not a correction of an active lie.
- **[minor] Hover tooltips print a plain hyphen for negative EPS/margin
  values; the axis 2px away prints the page's real minus sign.** Lines
  5863-5879 vs. 5897 and 6033. `hoverFormatter`'s `pct`/`num` branches never
  got the U+2212 substitution the `money` branch and `tickFormatter` already
  use. Fix: apply the same substitution in the `pct`/`num` branches. Note: the
  bug is slightly more pervasive than stated — the end-of-line series legend
  (line 6249) goes through the same broken `hoverFormatter` path too, not just
  the point tooltip; only the axis gridlines themselves are unaffected.

#### Sector Heatmap — scored 48 pre-fix (2 findings confirmed, 2 refuted)

- **[blocker] Pre-market 1D tiles show yesterday's move mislabeled as
  today's, with no PREV flag.** Lines 7787, 7799, 7912, cf. 2392-2397 and
  1556. `HEAT_COLS` never requests `premarket_change`/`postmarket_change`, so
  `chg["1D"]` reads the stale `change` column the codebase elsewhere
  documents as "the previous session before the bell" — every other surface
  in the file tags this PREV, the heatmap has no equivalent. Fix: add
  premarket/postmarket change columns and flag or hatch the tile during those
  sessions. Note: the verifier said this understates scope — it's wrong for
  the entire pre-market (and symmetrically after-hours) window, not just a
  narrow moment before the first pre-market print.
- **[major] No-data hatch pattern never renders because inline `background:`
  overrides `background-image`.** Lines 8224 vs. 588-599. The `hm-tile nodata`
  class's `repeating-linear-gradient` hatch never paints because the inline
  `style="background:rgb(...)"` shorthand resets `background-image` to none —
  a null-data tile looks like an ordinary dull-gray tile. Fix: use
  `background-color` (longhand) inline instead of `background`, or move the
  hatch to a `::before`/`::after` overlay.
- Refuted: "sector-label font measurement locks onto a guessed fallback" and
  "tile-count floor overrides the area-based labelling target" — neither held
  up under adversarial check.

#### vs PEERS tab — scored 55 pre-fix

- **[blocker] A single failed scanner request permanently mislabels a real
  ticker as unresolved.** Lines 6700-6718, 2331-2374. `adhocEnsureFacts`'s
  `.catch` swallows a network failure and resolves `null`; `_peersByIndustry`
  then unconditionally caches `{peers:[], source:'unresolved'}` for that
  symbol with no retry gate — a transient scanner hiccup on a freshly-searched
  ticker permanently shows "no US listing resolved" for the rest of the
  session, surviving symbol switches and data polls; only a full page reload
  clears it. Fix: distinguish a network/HTTP failure from a genuine empty
  response in `adhocEnsureFacts`, and only cache "unresolved" when the fetch
  actually completed with no usable data.
- **[major] Indexed-revenue chart's end-of-line ticker label can float at the
  wrong height with no off-scale mark.** Lines 6155-6213, 8887-8912. The
  end-label "off" flag (draws the ↑ arrow) is set only when *every* point of a
  line was clipped by the clamp ceiling, not when the *true final* data point
  is clipped — a peer that tracks the group and then spikes past the ceiling
  only in its last quarter or two shows its name label pinned at an earlier,
  lower height with no ↑ marker, misrepresenting where the line actually
  ended up. Fix: base the "off" decision on the series' true last value, not
  on whichever point the visible polyline last touched.
- **[minor] A peer's failed fundamentals fetch is indistinguishable from
  "still loading" for as long as the tab stays open.** Lines 2139-2180,
  8632-8668, 8628. `ensureFund` deliberately never caches a failed fetch (so
  the next open retries), but `metricReason` reads that same missing-key
  state as "still loading…" with no distinction from an already-failed fetch,
  and nothing re-polls while the tab stays open. Fix: give the failed path a
  distinct signal from "never attempted," and word it as "didn't load —
  reopen to retry." Note: there is one hidden automatic retry (the
  `isRedraw=true` recursive call), but its result never reaches the screen
  because the "loading…" text is committed to `innerHTML` before the retry
  settles — the underlying cause is "the display is never revisited," not
  "the fetch only tries once."

#### Right rail panels — scored 72 pre-fix

- **[major] Weekly options expiration permanently leaks into the curated
  catalysts default view.** Lines 4190-4206 (index.html), fetcher/context.py
  1065-1093. `catIsAnchorByName`'s `/options expiration/` regex matches
  "weekly" just as it matches monthly/quarterly, so LOW-importance weekly
  OpEx rows bypass the curation floor forever — verified live against
  2026-08-21's data.json (three weekly rows leaking into "Next two weeks" /
  "Later + anchors" today). Fix: restrict the anchor exception to
  monthly/quarterly titles only, or require `importance !== 'LOW'`.
- **[major] Fed-hike numeral, header chip and warning banner disagree about
  whether the same reading is alarming.** Lines 3386-3390, 3508-3513,
  3515-3536, CSS 312-316. Verified live: `fed_odds = {hike_pct:31.6,
  alarm:false, grade:'HOSTILE'}` produces three different verdicts from the
  same object in one render — the header chip and the banner both gate on raw
  `fed.alarm` (false, so no warning appears), while `fedOddsHTML` computes its
  own local `alarm = f.alarm||f.grade==="HOSTILE"` (true) and uses it to skip
  the neutral-ink override, leaving a red 32% numeral with no explanatory text
  directly under a calm header chip. Fix: compute one "loud" boolean once
  (e.g. `alarm===true || grade==="HOSTILE"`) and use it everywhere fed-odds
  loudness is rendered. Note: the fedcard's border/background does NOT go red
  — only the numeral's text color does, via a separate `quiet` toggle — so the
  visible artifact is a red number in an otherwise normal card, smaller than
  "bright red" suggests, but the three-way disagreement and its root cause are
  accurate.

#### Flow boards — scored 72 pre-fix

- **[major] Biggest Orders board reports a total chain-vendor outage as a
  quiet market.** index.html 4002-4013 vs. 3786-3799. When
  `universe.with_options` hits 0 (the CBOE chain vendor fails entirely),
  `data.big_orders` is necessarily also empty, but `renderOrders` only checks
  `Array.isArray` (true for `[]`) and prints "No contract has traded enough
  today" — a false claim about a quiet tape — on the same cycle Conviction and
  Swing correctly say "that is the chain vendor, not a quiet tape." Fix: check
  `universe.with_options===0` the same way `boardEmptyHTML` does before
  falling back to the generic empty message.
- **[major] "the cap is never silent" promise is false for a ticker capped
  outside the naive top-12.** fetcher/build_snapshot.py 1801-1828, surfaced at
  index.html 4055-4063 and the tip text. `earned[ticker]` only counts rows
  inside the naive top-12 by raw premium, but the final board is built by a
  greedy per-ticker-capped(3) walk over the *full* pool that backfills past
  rank 12. A ticker whose qualifying rows straddle that boundary can lose rows
  to the 3-per-ticker cap while still reading `earned<=3`, so it's excluded
  from the disclosure entirely — fewer contracts shown than qualified, with no
  note. Fix: compute earned/shown from the actual `shown` dict the greedy loop
  produces, not from a slice bounded by the unrelated top-12 constant.
- **[minor] Board-cut note claims names are hidden "below the line" even when
  none are.** index.html 3767-3779. When every tracked name clears the score
  bar, `boardCutNoteHTML` still prints "...the rest of the watchlist sits
  below the line. show all N" with an inert-looking button. Fix: only print
  that clause and button when `cut.strong < cut.total`. Note: the button
  isn't fully inert — it does toggle a "showing all" state and re-render the
  note text — but the underlying row list doesn't change, since it already
  equals the full list.
- **[minor] Swing board's widest column stays exposed at phone width while
  Conviction's equivalent is hidden.** index.html 790-814, 3961-3997. At
  ≤640px, Conviction hides its two widest columns; Swing hides only one,
  leaving Trend, IV rank, and the long "Suggested contract" column in the DOM
  at 390px, forcing far more sideways scrolling. Fix: extend the same
  phone-width column trim to the swing table. Note: the verifier corrected the
  mechanism — the suggested-contract `<td>` body actually wraps via
  `max-width:42ch`; the real forcing agents are the two extra un-hidden
  columns plus the column *header* (`<th>`), which the wrap rule never
  touches and which sets the width floor. No comment "claiming parity"
  between the two boards actually exists in the file — the fix should extend
  the hide list, not delete a comment that isn't there.

#### Data honesty — scored 58 pre-fix

- **[blocker] SPY/QQQ/DIA/IWM top tape never shows a stale/frozen indicator,
  unlike the macro tiles beside it.** Lines 1081-1086, 2518-2533, contrast
  2535-2573 and 2480-2490. `macroTileHTML` checks `macroSymStale()` and shows
  a FROZEN badge; `mainTileHTML`, rendering the same top tape row, calls
  `dispQuote(LIVE[t.tv])` directly with no staleness check at all — if the
  scanner silently drops SPY for several polls while its neighbors keep
  answering, SPY's tile keeps looking exactly as fresh as a live one
  indefinitely. Fix: give `MAIN_TAPE` the same `liveStale`-style check and
  FROZEN tag `macroTileHTML` already has.
- **[major] The open chart's header price never shows STALE.** Lines
  8324-8338, contrast 2823-2860 and 2480-2485. `liveStale(sym)` exists and is
  correct but is called from exactly one place: the watchlist rail row.
  `stageHeaderHTML` — the big price/percent at the top of an open chart, the
  number actually being watched to decide a trade — reads the same `LIVE[sym]`
  object with no staleness check at all, so the rail row can show STALE while
  the chart header directly above the same chart looks current. Fix: call
  `liveStale(sym)` inside `stageHeaderHTML` and render the same badge pattern.
- **[minor] Fundamentals grid's Fwd P/E and Next earnings cells carry no
  staleness signal even though their source is a once-a-day sidecar that can
  silently stop updating.** Lines 5799-5808, 5813, 5836, contrast 5831 and
  9090-9097. If the fundamentals fetch fails for days running, `fund.built`
  stays stuck on an old date while `fund.pe_forward`/`fund.next_earnings`
  render with no sub-label or color change — a week-old forward P/E looks
  identical to today's. Fix: compare `fund.built` against `data.session_date`
  and surface an amber/STALE sub-label past a threshold. Note: the existing
  `isStaleFlow`/`isStaleContext` helpers compare a millisecond timestamp
  against `Date.now()`, gated to trading hours — they aren't a direct fit for
  a day-based `fund.built` comparison; a fix needs its own day-based rule, not
  a reuse of those helpers.

The review script is committed at **`docs/review/nine-section-review.js`** so it
does not depend on a session directory. Re-run it with:

    Workflow({scriptPath: "docs/review/nine-section-review.js"})

Roughly 75 agents and 45 minutes. Expect it to find things — that has been true
every round. Round 6's findings were almost all things rounds 3-5 never
reached, and several were holes in earlier rounds' own fixes (the S/R
color/caption split, the Fed-odds three-way disagreement).

The committed copy carries two lessons the earlier runs paid for: it tells the
reviewer that `data/` is gitignored and can be stale (a round-4 reviewer called
a working feature broken because the local sidecars were months old), and it
tells the verifier to check the live payload with `git show origin/data:...`.

## Shipped 2026-08-21

**bars.json v4 is live.** `git show origin/data:bars.json` now reads `4 True`
(version 4, `sessions` calendar present) — the daily rebuild published it on
its own, signature-gated on `BARS_BUILD_SIG` as designed. `barSessionDates`
takes over from the walk-back reconstruction, `BAR_DATES_APPROX` is false, and
`isTradingDay` now prefers the published calendar over the hard-coded table.
No page change was needed — the page was already written to prefer v4's
calendar once it showed up. `MARKET_HOLIDAYS` in index.html still needs
extending each December as its own maintenance item — that did not go away
with v4.

## Shipped in rounds 4 and 5 (28 commits, all browser-verified)

The chart no longer paints one company's name over another's bar. The
pre-market candle is the range from yesterday's close to the pre-market print
instead of a second copy of yesterday's bar. Earnings and rating markers all
draw. Trend-line verdicts re-grade against the price on screen and the "stayed
above it since" claim is counted against the bars. A scanner answer with no
rows counts as a failed poll. A dead symbol wears a STALE chip. 4H candles
bucket on session boundaries. The market-state lamp knows the holiday calendar.
The heatmap labels 97% of its tiles. The year-over-year chart reads the filing
cadence off the labels. Every panel that used to vanish now explains itself.
Phone tap targets went from 69 under the minimum to 2.

Full detail: `docs/superpowers/plans/2026-08-19-trading-platform-redesign.md`,
rounds 4 and 5. The rules those rounds added are in `CLAUDE.md`.

---

## Verification harness

The Playwright harness lives in the session scratchpad and does not survive.
Rebuild recipe, which took a few tries to get right:

- Serve the repo root over plain HTTP on 127.0.0.1 (any free port). The page
  keys off `location.hostname` being localhost to read `./data/` instead of the
  raw GitHub URLs, so file:// will not work.
- Launch Chromium with `executable_path="/opt/pw-browsers/chromium"`. Playwright
  in this image looks for a headless-shell build that is not installed, so the
  default launch fails; the symlink above is the browser that exists.
- Route **every** request through a `page.route` bridge that fetches external
  hosts server-side with `urllib` and fulfils them with
  `access-control-allow-origin: *`. The sandbox proxy resets the browser's TLS,
  so the page cannot reach TradingView or Yahoo directly.
- Set `timezone_id="America/Chicago"`. Half the page's logic is CT-clock-driven.
- Expect 404s in the console for `data/fund/*.json` — the local sidecar set is
  small. Filter them out; anything else is a real error.
- To exercise a session-dependent code path (pre-market swap, STALE badges,
  half-day boundaries) outside market hours, monkey-patch `priceSessionNow`
  in-page (`window.priceSessionNow = () => 'premarket'`) rather than trying to
  fake the system clock — round 6's verification did this to confirm the
  heatmap's PRE/PREV tagging end-to-end against the real scanner.
- The heatmap needs `HEAT.univ` set and `renderHeatBar(); heatRender(true);`
  called explicitly if the view was never switched to "heat" through the UI —
  calling `heatFetchNow(univ)` directly is the fastest way to check the data
  side without fighting DOM layout timing.

Useful element ids and selectors, since they are not guessable: `#stagetabbody`
(tab body), `#staget` (TA caption), `#stageohlc` (crosshair readout), `#heatwrap`,
`#chartread` (tap readout), `[data-iv]` / `[data-tf]` / `[data-ta]` / `[data-tab]`
(chart controls), `.wr[data-sym]` (rail rows). `renderAll(data)` takes the
payload; calling it bare throws.

What the probes measured, all currently clean:

- Zero JS errors across every ticker x interval x tab x TA toggle x width x theme
- Zero sub-4.5:1 text in either theme, on the boards and on the heatmap
- 166 keyboard stops, all named; no duplicate ids; no unnamed pressed controls
- Prices agreeing across the rail, the chart header and the boards
- The "% shown" chip matching the visible window exactly on every name
- 266 fetcher tests passing
