# Flow Desk

## What this is

Flow Desk is a personal trading platform. A full-size chart sits front and
center, with the Morning Brief and the sector-rotation board to the side,
the scored options-flow boards below, and a rolling news ticker across the
very top. It uses only free data sources. There are no logins, no API keys
to manage, and nothing to pay for.

## The 2026-08-19 redesign, in plain terms

The page used to open charts in a popup. Now the chart is the page:

- **The chart is front and center.** Candles, volume, moving averages, and
  earnings badges, drawn by TradingView's own open-source chart engine
  (vendored in `vendor/`, credited in the footer). You can zoom with the
  mouse wheel, drag to pan, and the crosshair's price and date labels follow
  your cursor. Interval buttons (15m to weekly), window buttons (1M to 1Y),
  and a log-scale override sit above it.
- **Search any US ticker.** The box in the left rail searches by symbol or
  company name. Picking a result charts it, pulls its history straight from
  TradingView in your browser, and fills a fundamentals card from the live
  scanner, even for names far outside the desk universe.
- **Add and remove watchlist names.** The star in the chart header or the
  rail's **edit** mode adds custom names and hides pinned ones. Custom adds
  live in this browser only, and the rail says so. The server-curated
  universe (boards, daily bars, financial sidecars) never changes from the
  page.
- **Auto technical analysis.** Selecting a stock fits trend lines through
  its swing highs and lows, and draws horizontal support/resistance levels
  color-coded to where price sits against them (red overhead, green
  underneath, blue when price is inside the band). When both a resistance
  and a support line fit, the caption under the chart also names the shape
  the pair draws — ascending/descending/symmetrical triangle, rising/falling
  wedge, ascending/descending channel, trading range, or bull/bear flag.
  A third toggle draws Bollinger Bands (20-period average, ±2 standard
  deviations). The watchlist rail's **Band crosses** box separately flags
  any rail ticker whose price just crossed its own band — and, listed first
  and bolded, any name that touched or sits at/below its LOWER band today, or whose
  price is within 1% above it (Zach's alert ask, 2026-08-26), including a
  dip that bounced back inside.
  Checked from the daily bars every poll, whether or not that ticker's
  chart is open. A touch is a fact about a stretched move, never a buy
  call, so the rows stay the panel's neutral purple. RSI and
  EMA panes were removed 2026-08-21 (the fundamentals grid still carries a
  daily RSI(14) reading). All of this is display-only. Nothing here scores
  or signals. Since the 2026-08-26 declutter, Bollinger Bands are the only
  overlay on by default — moving averages, trend lines, S/R levels, the
  volume profile and the gamma lines are one click away on the overlay bar.
- **Unusual options activity.** Both flow boards flag a name whose 0-7 day
  options volume is running well above its OWN normal level (3× its trailing
  20-session average, not just whichever name traded the most), and label
  the lean BULLISH, BEARISH, HEDGING, or MIXED. HEDGING fires on the one
  signature free data can honestly call protective: heavy put activity while
  the stock is NOT falling. Needs 20 sessions of history to activate on a
  ticker; until then it's silently absent, never guessed. Display-only —
  it never moves either board's score.
- **A 5-metric scoring framework.** Below the chart, a filter panel checks
  each name against five repricing/validation/sustainability tests (forward
  EPS revisions, NTM revenue growth, analyst revision velocity, operating
  margin expansion, FCF growth) and rolls them into a verdict — BUY, ADD,
  HOLD, or AVOID. It is a reference for theses, not a signal: it never moves
  the conviction or swing score, and two of the five filters read "building"
  for months after a fresh deployment while enough weekly history
  accumulates. Works best on growth names; mature dividend payers score
  lower by design.
- **Financials and peers.** Tabs under the chart chart quarterly revenue,
  net income, free cash flow, margins, and growth, and compare the focused
  name against its peers (curated sets where the vendor taxonomy lies, for
  example MU against the memory complex; same-industry-by-size otherwise).
- **A sector heatmap.** The CHART/HEATMAP toggle swaps in a Finviz-style
  map of the S&P 500, the Nasdaq 100, or the desk universe. Tile size is
  market cap, color is the move over 1D/1W/1M/YTD, sector headers isolate a
  sector, and clicking any tile charts it.
- **A rolling news ticker** of tagged headlines leads the page. Hover
  pauses it; click opens the story.
- **Position Guard is gone** (removed 2026-08-19 at Zach's direction). The
  trade-stops math and the Morning Brief's own guard section live on
  outside this page.

## The 2026-08-26 declutter, in plain terms

The desk now uses the whole desktop window instead of stopping at a fixed
width, and it leads with plain sentences instead of walls of small text:

- **A quick read under the chart.** One sentence says whether the open name
  is leaning bullish, leaning bearish, or mixed, and why — computed from
  the price against its own 50-day and 200-day averages, nothing else. It
  is a description of the chart, not advice, and it never feeds any score.
  The full moving-average legend, the auto-TA caption and the gamma caption
  sit behind a **chart notes** button next to it.
- **Bollinger Bands are the only chart overlay on by default.** Moving
  averages, trend lines, support/resistance levels, the volume profile and
  the gamma lines are one click away on the overlay bar. The gamma lines
  used to draw on every desk name unconditionally; they are a GEX toggle
  now.
- **Each flow board opens with a quick read too** — "the fast options money
  today leans bullish — 36 of 57 tracked names…" — restating the header
  counts as a sentence a newer trader can follow, with the calls/puts
  basics one hover away.
- **"How to read this" text collapses behind small buttons** across the
  page. What never collapses: anything that dates or doubts the data —
  as-of stamps, STALE badges, "this feed did not answer" reasons, currency
  warnings, clipped-outlier notes. Those stay printed, always.

Warnings about the data itself never hide behind a click. Explanations of
how to read a panel do.

## The URL

**https://zlanghamer1.github.io/flow-desk/**

Open that link any time. It updates itself — there's nothing to install or run.

## How the data flows

1. A scheduled job (a "GitHub Action") wakes up roughly every 7 minutes while
   the market is open.
2. Each time it wakes up, it looks at a fixed, curated watch list — your
   watchlist names plus the 11 sector-index ETFs (XLE, XLC, XLP, and the
   rest) — and pulls free, 15-minute-delayed options data from CBOE and live
   stock prices from TradingView for each one. It no longer screens the whole
   market, so the boards only ever show names you chose to watch.
3. It scores each stock onto two boards:
   - **Conviction** — short-term activity, expiring in the next 0–7 days.
   - **Swing** — longer-term activity, expiring anywhere from 2 weeks to 6 months out.
   It also ranks every name's individual contracts against each other for the
   **Biggest orders today** board (below).
4. The results are saved to a file called `data.json` and published to a
   separate branch of this repository (the `data` branch).
5. The website reads that file to draw the boards, and separately checks
   TradingView every 30 seconds so the prices on screen keep moving between
   refreshes. Those prices are **15 minutes behind the tape** — the 30-second
   poll is how often the page re-reads a delayed print, not how fresh the
   print is. TradingView's own metadata says so (`update_mode:
   delayed_streaming_900`), and lining 30 samples up against a real-time feed
   on 2026-08-19 put the lag at 16 minutes on every name tested.

## The two direction estimators (added 2026-07-18)

Free data can't directly see whether a trade was a buy or a sell, but two
things get squeezed out of the same free feed to get closer:

- **AGGR TILT (conviction board)** — every refresh, each contract that traded
  is checked against its bid/ask spread: a trade printed near the ask counts
  as *bought*, near the bid as *sold*. Calls bought + puts sold = bullish
  premium; calls sold + puts bought = bearish. The tilt is the day's running
  balance, −100% to +100%. It only samples one trade per contract per refresh
  (~7 min), so it's a rough proxy — the card shows how many dollars it's
  based on, and shows "sampling" until enough trades classify.
- **OI-confirm (swing board, under OI BUILD)** — the next morning, yesterday's
  longer-dated volume is checked against today's open interest. If open
  interest grew by at least 25% of that volume, yesterday's flow became held
  positions (**OPENING ✓** — conviction). If it shrank that much, positions
  were being unwound (**CLOSING ✗**). Anything between is **CHURN** —
  day-traded or rolled, not held.

Both nudge the 0–100 scores a little (tilt: ±5 on conviction; OI-confirm: +5
or −10 on swing) but never dominate them.

## FLOW % — dollars, not contracts (added 2026-07-25)

Each conviction card shows two put/call readings side by side, and they answer
different questions:

- **C/P** counts **contracts**. 2.35x means 2.35 calls traded for every put.
- **FLOW %** counts **dollars**. "73% PUT" means 73 cents of every dollar of
  option premium that changed hands today went to the put side.

They can disagree badly, and when they do the dollars are usually the honest
read. A near-money put on a $920 stock with expensive volatility can cost
several times what a call costs, so the put side can soak up most of the money
while the contract count looks balanced. MU on Jul 24 2026 did exactly that —
a roughly even contract ratio sitting on a heavily put-weighted premium book.
FLOW % is what commercial flow desks show, and it's why their boards flagged
MU as put-heavy when a contract-count read called it neutral.

**Near-the-money only, since Jul 28 2026.** FLOW % counts dollars traded on
strikes within 20% of the current price, and ignores everything further out.
Here's why. An option deep in the money costs almost exactly what it's already
worth — a call to buy a $1,200 stock at $790 costs about $410 no matter what
anyone thinks happens next. It's a way of holding the stock, not a bet on it.
Count those dollars and a handful of contracts can drown out the entire real
book. LLY on Jul 27 2026 did exactly that: seven such call strikes, about 330
contracts between them, were 79% of all the call money and made the card read
84% CALL. The honest number was 60%. (The contract count was misleading in the
opposite direction the same day — 82% of the put contracts were penny options
miles from the price, padding the count with noise.)

Two separate ways of throwing out that paper — the 20% band, and simply
dropping anything whose price is nearly all built-in value — landed within
0.3 of a point of each other, which is why the number is trustworthy now.

If nothing traded near the money, the card shows a dash rather than a number
nobody could defend.

FLOW % is display only — it doesn't move the 0–100 score. **NET FLOW still
counts the whole 0–7 day bucket**, so it can still be inflated by that same
deep-in-the-money paper — LLY's read +$15.5M where the near-money figure was
+$1.0M. Changing NET FLOW would change every score and every stored history
row, so it's a separate decision, not folded into this one.

## Biggest orders today (added 2026-07-31)

Below the two scored boards is a plain ranked list: the individual option
contracts having the **biggest day for their own name**, across every name on
the watch list. It's built from the same free CBOE data the "institutional
options flow" posts circulating on social media use.

**Ranked against each name's normal, not on raw dollars (changed 2026-09-03).**
On raw dollars the board was SPY, QQQ, NVDA and one other name every single
day, by size alone — a $2M line in SPY is an ordinary hour, a $2M line in a
small name is its whole month. So each line now carries a **× normal** figure:
the dollars through that one contract divided by what its name usually trades
in a whole day of near-money, short-dated options (averaged over its last 20
sessions). The board sorts on that column. Read a line like
`AEHR CALL $35  2026-09-19 (16d)   4.1×   $410K` as: *this one contract did
about four normal days' worth of Aehr's options business today.* A name with
fewer than 20 sessions of history shows "no baseline" and sits at the bottom,
ranked on raw dollars — the page never guesses a ratio. The raw dollar figure
is still printed beside it.

**One line is one contract's whole day, NOT one order.** This is the honest
limit and it's worth being clear about, because it's exactly where those posts
oversell. Paid services ("a $6M sweep just hit NVDA") read a trade-by-trade
tape and can point at a single order. Free CBOE data publishes a **daily total
per contract** — every trade in that contract added together, from a hedge fund's
block to somebody's single lottery ticket. So the numbers here are much bigger
than a paid feed's, and they are a different measurement, not a better one.

Two filters keep the list meaningful:

- **Only strikes within 20% of the stock price.** Same reason FLOW % has that
  rule (above): a deep-in-the-money option costs almost exactly what it's
  already worth, so a few of those carry enormous "dollars" while betting on
  nothing. Unfiltered, that paper would permanently own the top of this list.
- **Only expiries inside 6 months**, and a minimum dollar size, so a quiet day
  shows a short list instead of padding it with noise.

**At most 3 rows per name.** On the first live cycle, 0-DTE QQQ calls held 5 of
the 12 rows at strikes a dollar apart ($683 through $687, all expiring that
afternoon) — an honest ranking that used up the board to say one thing five
times. The cap frees those rows for the next-loudest *other* contracts, so you
still get 12, just across more names. **The cap always says what it cost**: the
line under the board names anything that earned more rows than it got ("AMZN
earned 5 of these rows, showing 3"), because a trimmed list that doesn't admit
it was trimmed reads like the whole picture.

**What it can't tell you:** which side traded. There's no buyer/seller
information in free data, so a big put line might be a hedge on a stock someone
owns, an outright bearish bet, or someone *selling* puts to collect income —
which is bullish. Any post claiming a list like this proves institutions are
"heavily bullish" or "hedging downside" is adding a story the data doesn't
carry. This board is display only; no line here moves any score.

**Amazon, Meta and AMD joined the watch list the same day**, so this board can
see the mega-cap names that actually dominate that tape — AMZN and MSFT calls
owned the top of it on day one, and none of the three had been on the desk
before. Apple, Tesla and Netflix were considered and left off.

## The semi ETF flows card (added 2026-07-19)

A small card near the top of the page shows whether real invested money went
**into or out of** the big semiconductor ETFs — SMH, SOXX, SOXL, SOXS, and
DRAM — the previous session, plus each fund's one-month total. ETFs create
and destroy shares as money enters and leaves, so the day-over-day change in
a fund's share count times its price per share is a good estimate of the
dollars that actually moved. When flows run the same direction several days
in a row, the card shows the streak (e.g. "3d inflow").

This answers a different question than the boards: the boards show what fast
options traders are doing right now, while this card shows what slower money
— retirement accounts, advisors, funds, and dip-buying retail — did
yesterday. It updates once per session, mixes retail and institutional money
together, and never affects any score. It's context, not a signal.

**Splits show "split — n/a" (added Jul 28 2026).** A fund split changes the
share count without a dollar moving, so on a split day the share-count method
can't tell you anything. SOXL and SOXS reverse-split routinely, and a 1-for-10
reverse split would otherwise print an outflow of roughly 90% of the fund on a
day nobody sold anything — the same kind of fake number as the CRWD split that
produced a bogus −74.9% in the Jul 1 2026 morning brief. The card detects it
(share count and price per share moving by opposite, matching factors) and
withholds the number rather than showing a zero, because a flat day isn't what
was observed either.

## Pre-market and after-hours prices (added 2026-08-17)

Outside regular trading hours, prices carry a small amber **PRE** or **AFT**
tag — on the index strip across the top, on the watchlist rail, and in the
header of any chart you open. When you see that tag, two things are true:

- The price shown is the latest extended-hours print, not yesterday's close.
- The percentage next to it is measured from the right starting point — the
  prior close for PRE, today's 3:00 PM CT close for AFT. Before this change the
  page showed a pre-market price beside yesterday's finishing percentage, which
  is two different days in one line.

The mover tags (and the count in the browser tab) follow the same number, so at
7am they describe this morning's gap rather than yesterday's session.

Two things worth knowing. Extended-hours volume is thin, so a large pre-market
move on light volume often doesn't survive the open — the tag is there partly
to remind you of that. And the four macro tiles (VIX, the 10-year yield, crude,
the dollar) never show a tag, because those markets trade nearly around the
clock: the price already on the tile *is* the overnight read.

## Clicking the index strip (added 2026-08-17)

Every tile in the top strip now opens a chart, the same one the watchlist rows
open — SPY, QQQ, the Dow, small caps, VIX, the 10-year yield, crude and the
dollar, each with two years of daily candles and the 20/50/200-day averages.

The four macro tiles and the index ETFs show no fundamentals panel, and that is
correct rather than missing: an index has no earnings, no margins and no P/E.
The chart, the moving averages and the catalyst calendar all work normally.

## Chart windows, log scale, and one bad price history (added 2026-08-18)

Three fixes to the chart, all from opening SOXS. (These predate the
2026-08-19 redesign; the drawer they mention became the center-stage chart,
and every behavior below carried over.)

**The window buttons stay put.** 1M / 3M / 6M / 1Y used to vanish the moment
you picked an intraday view (15m, 1H, 4H) and come back only when you clicked
1D again. The chart remembers your last interval between tickers, so one click
on 15m quietly stripped those buttons off every chart you opened afterward.
They are always on screen now. On an intraday view none of them is highlighted,
and clicking one means "show me that much history" — it switches the chart back
to daily candles.

**Charts that fall off a cliff now use a log scale.** SOXS is a 3x inverse
semiconductor fund in a semiconductor bull market, so it decays: a year ago it
traded near $4,250, today near $40. On a normal price axis that puts every
recent candle in a 1-pixel line along the bottom — the chart was flat because
the scale was, not because the fund stopped moving. When a window spans more
than 4x top-to-bottom AND the recent bars have been squeezed into less than a
fifth of the pane, the chart switches to a log scale, where the same percentage
move takes the same vertical space anywhere on the chart. A **log scale** chip
says when that is in force. Ordinary names are untouched — MU's 1Y chart spans
11x on its own and still reads fine straight, so it stays as it was.

**SOXS's older prices were simply wrong, and are now repaired.** Yahoo, which
supplies the daily history, returned every SOXS bar before May 26 priced
exactly 15 times too high — $1,159.50 for a day that Polygon and TradingView
both put at $77.30. It is a split the feed never applied to its own history,
and no version of the request fixes it. The fetcher now detects that kind of
break (a bar that OPENS a factor away from the previous close, which is what a
split looks like and what a crash does not) and rescales the earlier bars,
volumes included. The repaired series matches Polygon day for day. A
**split-rescaled 15×** chip on the chart says it happened, because a history
that changes shape overnight should say why.

## Chance of a Fed rate increase (added 2026-08-18)

The Morning Brief panel carries a card showing **the odds that the Fed raises
interest rates at its next meeting**, taken from Polymarket — a betting market
where people put real money on the outcome. One big number, a bar showing the
three possible results, and how the odds have moved.

The bar splits 100% three ways: a rate **increase** in red, **no change** in
grey, a **rate cut** in green. Red is the hostile outcome for stocks, which is
the same colour logic the rest of the page uses.

Underneath, three changes: **today**, **1 week**, and **1 month**. The daily one
is there because it is usually the interesting one. Odds can sit still for a
month and then move ten points in an afternoon on one speech, and a weekly
number smears that flat.

A red banner appears above the card whenever the reading is graded HOSTILE
upstream — the odds pass 25%, or they jump 10 points in a single day —
corrected 2026-08-22 from an earlier draft of this page that said the floor
was 40%; 40% is where the wording inside the banner changes, not where it
first appears. A same-day jump of 10+ points says "jumped hard today"
whatever the starting level, so an 8% chance becoming 19% shouts even though
19% still sounds small. Short of that, odds at or above 40% say "near a coin
flip"; anything HOSTILE below 40% says "elevated enough to flag, short of a
coin flip."

Three things to keep in mind:

- **This is a price, not a forecast.** It tells you what people betting money
  currently think. Crowds priced this way are decent and not right.
- **It does not move the verdict score.** The RISK-ON / RISK-OFF number at the
  top of the panel is built from eight overnight inputs and has a measured
  track record behind it. The Fed odds sit beside that number and colour the
  wording, deliberately. Nothing gets to move a tested number on a hunch, and
  there is no track record for this reading yet — every daily value is being
  recorded so the question can actually be answered in a few months.
- **A "hike" means any increase**, a quarter point or more, at that one meeting.
  The separate "any hike this year" line at the bottom of the card is a looser
  question and usually a much bigger number.

If the card is missing, the odds could not be read — a market too thinly traded
to mean anything, or a feed that was down. The card disappears rather than
showing a 0%, because 0% would be a real claim and a wrong one.

## Terms, privacy, and risk disclosure (added 2026-09-03)

The footer links to a second page, `legal.html`, that says in plain English
what the site is and is not: research, not advice; data at least 15 minutes
behind; no accounts and no trackers; your watchlist edits stay in your own
browser. It lists every outside service your browser talks to and every
setting the page stores. The operator's legal name, contact, and governing
law are shown in brackets until they are filled in. Bracketed items are
pending legal review; everything else on that page is true today.

## Could this be sold? (added 2026-09-03)

Not as it stands, and the reasons are not in the code. Every feed the desk
uses is licensed for personal use or is an undocumented endpoint, GitHub
Pages and GitHub Actions both forbid running a paid service, and a static
page has no way to tell a subscriber from anyone else. What a product would
need, what it would cost, and in what order to do it is written up in
`docs/MONETIZATION.md`, with the vendor-by-vendor terms in
`docs/DATA_LICENSING.md`. The short answer: the desk stays a personal tool
until someone pays a data vendor for the right to show its numbers to other
people.

## Its limits

- **Options data is 15 minutes delayed.** It's free CBOE data, not a live feed.
- **"Net flow" is a proxy, not real order flow.** Free data can't tell you
  whether a trade was a buyer or a seller — it only shows how much option
  premium changed hands and in which direction the volume leaned. Treat it as
  a clue, not a fact. The AGGR TILT estimator above narrows this gap but is
  itself a sampled approximation, not the real tape.
- **The biggest-orders board shows daily totals per contract, not single
  orders.** Individual blocks and sweeps need a paid trade-by-trade feed. See
  that section above — this is the difference that makes those social-media
  "big flow" posts look like they're seeing something you can't.
- **The Fed-hike odds are a betting market, not the Fed.** Polymarket prices
  what gamblers expect, and it has been wrong before. It also never moves the
  verdict score — see that section above for why.
- **This is not financial advice.** It's a personal research tool. Nothing on
  the boards is a recommendation to buy or sell anything.

## How to restart the loop if it stops

The refresh loop is designed to keep itself running all day on its own, but if
it ever stalls or you want to check on it:

1. Go to this repository on GitHub.
2. Click the **Actions** tab.
3. Click **"Refresh Loop"** in the left sidebar.
4. Click the **Run workflow** button (top right of the list) and confirm.
   - If you're testing this after the market has closed, tick the **force**
     checkbox first — that tells it to run one cycle anyway instead of
     waiting for market hours.

## What each file is

- **`index.html`** — the website itself. This is the whole dashboard.
- **`legal.html`** — the terms, privacy, and risk-disclosure page the footer
  links to.
- **`fetcher/`** — the behind-the-scenes scripts that pull data, score it,
  and publish it. You never need to open or run these by hand.
- **`.github/workflows/refresh-loop.yml`** — the schedule that keeps the
  data flowing during market hours.
- **`.github/workflows/pages.yml`** — the schedule that publishes the
  website itself whenever it changes.
- **`.github/workflows/ci.yml`** — runs every test on every change: the
  fetcher's tests and a headless-browser check that both pages load with
  their feeds cut off.
- **`tests/`** — that headless-browser check (`test_page_smoke.py`).
- **`docs/MONETIZATION.md`** and **`docs/DATA_LICENSING.md`** — what it would
  take to sell this, and the terms of every data source it uses.
- **`data.json`** — the live snapshot the website reads. You won't see this
  file on the `main` branch — it only lives on the `data` branch, since it's
  regenerated constantly and doesn't need a history of its own on `main`.
- **`history.json`** — the fetcher's day-over-day memory (per-name flow, open
  interest, IV history, and each session's biggest-orders board — what powers
  persistence, OI-confirm and IV rank, and what makes the biggest-orders board
  checkable later). Like `data.json` it lives only on the `data` branch, not on
  `main`.
