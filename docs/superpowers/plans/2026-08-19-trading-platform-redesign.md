# 2026-08-19 — Trading-platform redesign (plan of record)

Zach's directive, verbatim intent: make the desk look and function like a
true trading platform (his reference screenshots: TrendSpider's terminal and
Finviz's S&P 500 map). The chart stops being a popup and goes front and
center, with the Morning Brief and sector rotation to the side. He asked for:
ticker search with watchlist add/remove, auto trend lines on selection,
better financial graphs relative to competitors, zoom on the charts with the
price and date text following the cursor, and a sector heatmap for the day
with filters. Mid-build he added two more rulings: remove Position Guard
entirely, and put a rolling market-news ticker of links at the very top.

This document supersedes the layout half of
`2026-08-14-trading-dashboard.md`. That plan's data plumbing, scoring rules,
and honesty copy all still stand; its modal drawer and column ordering do
not.

## What shipped, by commit

1. `1c21092` (fetcher, deployed first so data existed before the page needed
   it): `facts` gains `sector`/`industry` off the same scanner call;
   `fund/{SYM}.json` gains quarterly and annual `ni` (from the income
   statement already fetched) and `fcf` (a fourth stockanalysis request,
   cash-flow statement, joined by datekey). `FUND_BUILD_SIG` forces the
   same-day rebuild. DATA_CONTRACT.md updated first. 189 fetcher tests.
2. `6e4fea9`: the center stage. Vendored TradingView Lightweight Charts
   v5.2.1 replaces the hand-rolled SVG engine; the modal is deleted. Native
   wheel/pinch zoom, drag pan, and a crosshair whose price/date axis labels
   track the cursor. Preserved from the SVG engine: the two-condition auto
   log axis (plus a manual override button), the split-rescaled chip,
   earnings markers with click popovers, extended-hours dimming, CT intraday
   axis labels, always-visible window buttons, and the live synthetic today
   candle (which now ratchets its high/low instead of forgetting the day's
   range). New: a visible-range % chip that reads whatever the zoom shows.
   Brief, sector rotation, and semi ETF flows moved to the right rail;
   boards kept the middle, under the chart; tabs under the chart absorbed
   the modal's panels.
3. `0f92a21`: search and watchlist. The left-rail box searches the scanner's
   name/description match (exact symbol first, then market cap). Custom adds
   and hidden pinned names live in localStorage per browser, disclosed with
   the house no-silent-caps line, with an edit mode and a comma-list
   export/import. Ad-hoc names get live quotes on the 30s poll, a
   scanner-snapshot fundamentals card, and bar history.
   **The bar-history source in this commit was wrong and was replaced the
   same day** — it opened TradingView's chart websocket from the browser, and
   that host allowlists exact `Origin` values, so every searched ticker
   failed with a 403 (Zach hit it on TSLA). The claim in this bullet that
   "the endpoint accepts any Origin" came from a probe whose client sent its
   own TradingView Origin. See Round 2 below for the measurement and the
   replacement. They never get options boards or the daily sidecar, and the
   page says so.
4. `6ccbaa3`: auto technical analysis, display-only. Pivot/trendline
   geometry ported verbatim from `scripts/trendline_break_scan.py`
   (PIVOT_K=4, MIN_SPAN=20, TOUCH_TOL=2%, CONTAIN_TOL=1.2%), generalized to
   a resistance line through swing highs plus a support line through swing
   lows, solid between anchors and dashed in projection. Horizontal S/R
   levels from 2%-clustered pivots (2+ touches, top three). RSI(14) pane
   with 30/70 guides. EMA200 toggle. Fit on the selected window so lines do
   not rewrite mid-drag. A summary line names what was fit and repeats
   "display only, never a signal".
5. `260ecca`: financials and peers. The Financials tab charts quarterly
   revenue/net income/FCF as validated three-color lines with direct
   last-value labels, derived margins, revenue YoY, EPS, and annual rows.
   The vs Peers tab compares six TTM metrics as focused-vs-muted bars,
   labels every bar with its ticker, and indexes quarterly revenue to 100
   with the fiscal-calendar caveat stated. Peer sets: curated where the
   vendor taxonomy lies (MU → SKHY/SNDK/WDC/STX, the memory complex;
   COHR → LITE/AAOI/FN), same-TradingView-industry by market cap otherwise,
   widened by a live scanner query when the local universe is thin; one
   batch scanner call fills facts for off-universe peers. Funds get "baskets
   have no margins".
6. `f8dedcc`: the heatmap. CHART ⇄ HEATMAP toggle; squarified treemap;
   S&P 500 and Nasdaq 100 straight off the scanner's symbolset filter plus
   a Desk universe; tile size = cap; diverging red/neutral/green built from
   the page's own tokens, clamped ±3/±6/±12/±25% by period with the scale
   legend drawn in the footer; sector headers isolate; any tile click charts
   the name through the ad-hoc path; refreshes on the 2-minute cadence only
   while visible.
7. `8d7411f`: Zach's two mid-build rulings plus all ten findings from the
   code-review pass (the `$$` scope bug was the serious one: scoped queries
   bound handlers document-wide). Position Guard is gone from the page: the
   passphrase panel, the WebCrypto path, the position blocks, their TIPS
   entries, and the footer line. The rolling news ticker leads the page:
   tagged TradingView headlines as scrolling links, seamless loop, hover to
   pause, reduced-motion gets a static strip, rebuilt only when headlines
   change.

## Rulings to keep

- **Chart engine**: vendored, pinned, attributed. The attribution logo and
  footer credit are Apache-2.0 conditions.
- **Auto-TA never scores.** It is chart furniture.
- **The page never widens the server universe.** Custom adds are quotes,
  charts, and scanner facts only; per browser; disclosed.
- **Position Guard stays gone** unless Zach asks for it back. `desk_private`
  still publishes; nothing reads it. The vault still builds the blob; ask
  Zach before touching that side.
- **The 2026-08-18 rulings carried over**: window buttons always render, the
  log-axis pair of conditions, the split repair and its chip, IN/OUT follows
  the money, boards open on the score-60 shortlist.

## Verification

- Fetcher: 189 pytest cases green, including nine new ones for ni/fcf and
  the fund signature gate. `test_tips_sync` green throughout (no scoring
  copy changed).
- Page: Chromium against the live data branch and live scanner responses at
  1440px and 390px, dark and light, zero console or page errors. Scripted
  checks: wheel zoom moves the visible-range chip; the crosshair OHLC
  readout follows the cursor; search "nike" → NKE charts 520 daily and 600
  15-minute bars over a replayed real websocket session; star add persists
  across reload and removal works; hide/restore a pinned name with the
  disclosure line; SOXS still auto-logs (on the windows the repaired data
  calls for) and shows "split-rescaled 15×"; MU carries 5 earnings markers;
  the heatmap draws 502 S&P tiles in 17 sectors, isolates, rescales its
  legend per period, and a tile click charts NVDA; the ticker rolls 40 live
  headline links; Position Guard absent.
- The websocket transport could not be exercised end-to-end from the build
  sandbox (its proxy resets browser TLS), so the page's client was tested
  against captured real frames. **That gap is exactly where the Origin bug
  hid**: replaying frames proves the parser, not the handshake. Round 2
  closed it by driving a real Chromium at the real origin through a
  purpose-built TLS relay. Lesson: a transport tested only against a replay
  has not been tested.

## Open items

- Custom watchlist is per browser. Carrying it across devices is the
  export/import string in the rail's edit mode. If Zach wants one list
  everywhere, that needs a write path the static page deliberately does not
  have; pinning names into the server universe via a config edit remains
  the covered route.
- ~~The TradingView chart websocket is unofficial…~~ **Resolved in Round 2:
  it blocks browser origins outright.** Searched names now use
  stockanalysis.com for daily bars; intraday for those names has no
  browser-readable source and the stage says so.
- `desk_private` and the vault's `build_desk_private.py` still run for a
  panel that no longer exists. Retiring that pipeline is a vault-side
  decision for Zach.
- Pre-market cosmetic quirk carried over from the SVG engine: before the
  loop's first cycle of the day, daily bars reconstruct dates ending at the
  prior session, so the synthetic candle can label itself with yesterday's
  date until ~8:00 CT. Correct during market hours.


---

## Round 2 (same day) — Zach's punch list, two follow-ups, and the first review pass

His list, verbatim, and what each became:

- *"What is the purpose of the second search ticker up top? doesn't search all
  stocks."* Both boxes now run the same live scanner search. The palette keeps
  actions and shows desk names first, then anything else that matched.
- *"scrolling over the price to the far right should expand/contract the
  candles vertically."* Wheel over the price axis stretches the candles
  (`STAGE.vZoom`, applied through the candle series'
  `autoscaleInfoProvider`), a chip shows the factor, double-clicking the axis
  resets it, and the wheel over the plot still zooms time.
- *"If you click a trend, S/R button etc. it will reset the view."* Toggles
  are wrapped in `stageKeepView`, which captures and restores the visible
  logical range around the series rebuild.
- *"financials vs peers should have better color coding … Color code
  different companies that are being compared to."* Each company holds one
  colour across every peer chart, from a palette validated with the dataviz
  six-checks in both themes; a colour key sits above the charts; every bar is
  also labeled with its ticker, so identity never rests on colour.
- *"I see a button to add a stock … but not seeing a button to remove."* One
  control in the chart header reads the rail's current state and both adds and
  removes, including hiding a pinned name and restoring it.
- *"Searching for TSLA has error 'no chart history available'."* Root cause:
  `data.tradingview.com` enforces an exact-host `Origin` allowlist. Replaced
  by stockanalysis.com's history API. See the guardrail in CLAUDE.md.
- *"Many financials missing Q# dates and number references … Revenue text
  overlapping."* New `axisChartSVG` kit: value gridlines on round numbers,
  period labels thinned to a 34px minimum gap, latest values moved into the
  legend (that is what was overlapping), tooltips on every mark.
- *"CRWD PEG blank."* PEG falls back to P/E over TTM EPS growth; where trailing
  earnings are negative it cannot exist and the cell says so. Multiples carry
  peer-relative colouring plus the market rule of thumb in the tooltip.
- *"analyst rating updates should be included in charts."* Yahoo's
  `upgradeDowngradeHistory`, riding the sidecar's existing quoteSummary call.
- *"No quarterly financials for TSLA."* Searched names now get financials from
  the scanner's own quarterly history arrays, labeled by period-end month.
- *"TSLA is not on either flow board."* The message now explains that the free
  chain feed sends no CORS header, names what does work, and points at the
  one-line universe change that would fix it.
- *"if I click the E for upcoming pre-market, I can't have that box close."*
  The × was painted under the chart canvas. It sits above it now; clicking
  anywhere outside the card dismisses it; Escape closes it without clearing
  the ticker focus.

### The auto-TA rebuild

A nine-section review scored auto-TA 52 with eleven verified defects. The
biggest: the port enforced containment all the way to the last bar, so a line
was deleted at the exact moment price broke it — NVDA's 6-month ceiling
through four swing highs drew nothing. The fitter now matches
`trendline_break_scan.py`: containment between the anchors, 3% slack after,
the check stopping at the confirmed break, non-anchor touches only, spans
scaled to the window, distance bounded by six average daily moves AND the
window's own range, volatility-scaled S/R clustering, a pinned 0-100 RSI pane,
EMA on whatever bars are showing, and a caption built from the toggles that
are actually on. Measured after: 23 lines across 24 ticker/window cases, none
more than 12% from price.

### Rulings this round adds

- **Never re-attempt the TradingView chart websocket from the browser.** It is
  an Origin allowlist, not a bug, and a python probe cannot disprove it —
  check which Origin the client actually sent.
- **Chart overlays never join the price scale's autoscale.** Moving averages,
  trend lines and projections all pass `autoscaleInfoProvider: () => null`,
  and horizontal levels are bounded to near price, because a $563 average line
  and a $220 level squashed a $937 stock's year into a third of the pane.
- **Auto-TA draws only lines a trader would accept**, and says so when nothing
  qualifies rather than drawing a confident diagonal.

---

## Round 3 (same day) — the nine-section review, and what it found

Zach's instruction was to run a scrutinizing reviewer over the whole site and
keep working until every section scored 90. Nine independent Opus reviewers
drove the real page in Chromium against live data. Round 1 scores:

| Section | Score |
|---|---|
| Data honesty and failure modes | 40 |
| vs Peers | 44 |
| Inherited panels | 46 |
| Auto-TA | 52 |
| Financials | 52 |
| Left rail and search | 54 |
| Heatmap | 57 |
| Cross-cutting quality | 62 |
| Chart stage | (died mid-run) |

Every finding across the eight scored sections is fixed, each verified by
measurement in the same harness. The commits are one per section.

### The one that mattered most

**The page called its prices live, and they are 15 minutes old.** The honesty
box, the stage footnote and DATA_CONTRACT.md all said "live TradingView". The
scanner's own metadata says `update_mode: delayed_streaming_900`, and a
same-instant comparison against a real-time feed put the lag at 11 to 15
minutes on SPY, MU, CRWD and NVDA. Measured twice, once by the reviewer and
once independently before changing anything.

This is the second time in one day a claim on this page survived because
nobody measured the thing itself — the first was the TradingView websocket
Origin allowlist, where a python probe "proved" a handshake that the browser
could never make. Both failures have the same shape: a plausible statement,
a test that did not test it, and a document repeating the statement until it
read as established. The lesson stands as a ruling in CLAUDE.md.

### Themes across the other findings

- **Physical breakage from the move into rails.** The sector table wanted
  580px in a 372px column, so three columns were off-screen and the dollar
  figures were cut mid-number. Sorting deleted the Safe havens table. Between
  901 and 1240px the sticky watchlist painted over the entire right rail.
- **Charts authored for the wrong width.** SVG text scales with the viewBox,
  so a fixed font-size landed at 6px on the financials tab and 7px on the
  peers tab. Every chart now picks its geometry from the width it will render
  at, and the axis measures its own gutter.
- **Comparisons that were not comparisons.** The peer sets carried the same
  company twice (an ADR and its ordinary line), measured a $212B security
  vendor against a $6B bitcoin miner, and drew a "peer median" that included
  the focused company.
- **Empty states that blamed the wrong thing.** A missing sidecar read as
  "outside the desk universe". A failed intraday fetch read as a coverage
  limit. A typo read as "a market reading, not a company". A vendor gap read
  as "the vendor reports nothing" when the real answer was "this company is
  loss-making".
- **Accessibility the redesign never had.** The news ticker owned the first
  40 tab stops, none of the nine section headers were keyboard operable, and
  eleven light-theme text styles failed WCAG AA.

### Rulings this round adds

See CLAUDE.md, "Guardrails added by the 2026-08-19 review round" — the delay
label, source lines built from real state, the price layer surviving a
data.json outage, chart geometry following render width, one company per bar,
the cap band on peers, medians excluding the subject, missing readings never
rendering as zero, and unconditional age stamps.

## Round 4 (same day) — the re-review, and the second fix pass

The same nine reviewers re-scored the page after round 3's fixes. Nothing was
credited for history: each reviewer drove the current build and reported only
what they could reproduce.

| Section | Round 1 | Round 2 |
|---|---|---|
| Chart stage | (died mid-run) | 42 |
| Financials | 52 | 56 |
| vs Peers | 44 | 56 |
| Heatmap | 57 | 52 |
| Inherited panels | 46 | 61 |
| Auto-TA | 52 | 66 |
| Left rail and search | 54 | 70 |
| Cross-cutting quality | 62 | 71 |

Scores went up where the fixes held and down where a fix opened a new seam —
the heatmap lost points to an expand control that blanked the desk and to
tile labels that were the only text on the page failing WCAG AA. A second
pass of reviewers finds different defects, not the same ones twice.

### What the second pass caught

- **Physics the first pass never measured.** The tape's index labels were
  clipped at every desktop width from 1240 to 1920 while the phone showed
  them in full, because the ≤1160px grid rule rescued the narrow case and
  nothing rescued the wide one. The top rail forced a horizontal page scroll
  from 901 to 1060px. Moving the mouse over the chart made the whole page
  jitter, because the OHLC readout wrapped and unwrapped in a flex row.
- **Numbers that disagreed with each other on the same screen.** The
  Conviction board's footer counted 60+ names and firing names together and
  labelled the sum "score 60+", two feet from a Morning Brief tile that
  counted only the 60+ names. Both are now printed, separately.
- **Silence where a feed failed.** A macro quote that never resolved removed
  its tape tile and let the survivors stretch. Sector rotation, ETF flows,
  tagged headlines and the ticker each vanished on an empty payload. The
  backdrop tooltip promised seven readings while the grade was computed on
  four. All of them now say what happened.
- **Colour that carried no information.** The Fed card's "no change" segment
  — 70% of the bar — was painted in the track colour, so the bar read as
  "29% hike and nothing else". Heatmap tile ink bottomed out at 3.77:1.
- **Comparisons that formatted away their own point.** PEG printed MU 0.026
  and SKHY 0.034 as the same "0.03" directly under a caption ranking one
  above the other. Each chart now takes just enough decimals to keep its own
  values apart.
- **Vintage mixing.** One bar chart can hold desk names from the morning
  snapshot and searched peers pulled from the scanner seconds ago. The tab
  now names which is which.

### Rulings this round adds

- **A responsive rule that rescues the narrow case must be checked at the
  wide one.** Two separate clipping defects lived above the breakpoint that
  fixed them below it.
- **A header that carries live text holds a fixed height.** The chart header
  reserves its OHLC line at a constant 15px (30px on a phone), so the chart
  below it never moves as the crosshair moves.
- **Two numbers describing the same thing on one screen must agree, or say
  why they differ.** Counting rules that differ get their own sentence.
- **A clamp above the tallest bar is not a clamp.** When the spread is
  genuinely wide and nothing can be clipped, the caption prints the ratio
  instead of leaving a four-pixel bar to look like a rendering fault.
- **Contrast is picked, not assumed.** Tile ink falls back to pure black or
  white whenever both themed inks land under 4.5:1.
