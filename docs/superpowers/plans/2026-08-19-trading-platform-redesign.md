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
   scanner-snapshot fundamentals card, and real daily/weekly/intraday bars
   pulled in the browser over TradingView's chart websocket (the
   `fetch_tv.py` protocol; the endpoint accepts any Origin, verified
   2026-08-19). They never get options boards or the daily sidecar, and the
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
  against captured real frames and the protocol was verified live
  server-side with the desk's own Origin. First fully-live browser test is
  Zach opening the page.

## Open items

- Custom watchlist is per browser. Carrying it across devices is the
  export/import string in the rail's edit mode. If Zach wants one list
  everywhere, that needs a write path the static page deliberately does not
  have; pinning names into the server universe via a config edit remains
  the covered route.
- The TradingView chart websocket is unofficial. If it ever blocks browser
  origins, searched names degrade to quotes + fundamentals with an honest
  note; pinned names are unaffected (bars.json).
- `desk_private` and the vault's `build_desk_private.py` still run for a
  panel that no longer exists. Retiring that pipeline is a vault-side
  decision for Zach.
- Pre-market cosmetic quirk carried over from the SVG engine: before the
  loop's first cycle of the day, daily bars reconstruct dates ending at the
  prior session, so the synthetic candle can label itself with yesterday's
  date until ~8:00 CT. Correct during market hours.
