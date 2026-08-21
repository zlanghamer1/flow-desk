# Flow Desk — what is still open

Written 2026-08-20, at the end of the review rounds. Everything in the
"Shipped" list below is done, verified and merged. Everything under "Open" is
work a later session can pick up. Nothing here blocks using the page.

---

## Open — in the order they are worth doing

### 1. Round 7 findings — confirmed, not yet fixed (none of the 9 sections reach 80 yet)

Round 7 checked the now-fixed page against Zach's 2026-08-21 ruling that the
passing bar is 80, not 90. **No section reached 80.** Highest was Chart Stage
at 79 — one point short. Full scores:

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

### 2. Score trajectory, and what "80" would take

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

### 3. Deferred by judgement, not by omission

- **The chart's own attribution link** is 35x11 on a phone, under the 24px
  touch minimum. Lightweight Charts injects and sizes it; restyling a vendor's
  attribution is not ours to do. It is the only remaining under-minimum target.
- **Net flow and the BULL/BEAR pill count every strike; Flow % counts only
  strikes within 20% of spot.** They can point opposite ways on one row. Both
  tooltips now say so. Making them agree means changing what the publisher
  computes (`build_snapshot.py`, net_flow and direction), which is a data
  decision, not a display one.
- **The biggest-orders board ranks gross premium**, so deep in-the-money paper
  can lead on money already in the strike. Those rows are badged MOSTLY
  INTRINSIC rather than re-ranked, because the gross figure is the honest
  answer to "what traded"; ranking on extrinsic value would answer a different
  question. If that other question is the one worth answering, the change is
  one sort key.

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
