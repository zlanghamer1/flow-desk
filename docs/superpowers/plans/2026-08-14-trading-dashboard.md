# The Desk — Trading Dashboard Plan of Record

> **Status: PROPOSED — awaiting Zach's approval.** Nothing on the live site,
> the refresh loop, or the Morning Brief changes until he says go.
> Mockup of the proposed page: `2026-08-14-trading-dashboard-mockup.html`
> (same folder). Written 2026-08-14 by the architect session (Fable), following
> the vault's `writing-plans` conventions at phase granularity; each phase gets
> its bite-sized TDD task breakdown from an Opus spec session at execution time,
> per the model-role convention in `flow-desk/CLAUDE.md`.

**Goal:** One page — the existing Flow Desk URL — that becomes the single place
Zach looks: live prices, the options-flow boards, the Morning Brief's verdict /
sector rotation / safe havens / Core Five, and a forward catalyst calendar
(econ events, earnings, memory-complex dates), refreshing itself all session.

**Architecture:** Keep everything that already works. The GitHub Actions loop
stays the only writer of the `data` branch and gains three cheap fetches
(econ calendar, earnings dates, news). The Morning Brief engine stays the only
place its numbers are computed and starts publishing a small JSON summary the
loop folds into `data.json`. The site (`index.html`) is rebuilt as the full
desk. No paid data, no new services, no second loop.

**Tech stack:** unchanged — static `index.html` on GitHub Pages (branch mode),
Python-stdlib fetcher on GitHub Actions, free CBOE + TradingView + FRED
endpoints, TradingView scanner polled client-side for live prices.

---

## Part A — The plan in plain English (for Zach)

### What you get

One web page, at the same address you already use
(https://zlanghamer1.github.io/flow-desk/), laid out like a trading desk:

1. **Top bar** — market open/closed, the day's verdict chip (risk-on /
   neutral / risk-off, same number the 6:23am email computes), and when each
   piece of data last refreshed.
2. **Live ticker strip** — SPY, QQQ, DIA, IWM, VIX, the 10-year yield, oil,
   and the dollar. Prices update every 30 seconds in your browser, the same
   way the current site's prices do.
3. **Morning Brief panel** — the email's three cards, on the page: the verdict
   with its plain-words line and macro backdrop, the 11-sector rotation board
   with money-flow columns, the safe-haven rows (gold, treasuries, cash), and
   the Core Five strip. The RETREAT WATCH and WHALES-ARE-HIDING banners appear
   here when they fire.
4. **Catalyst calendar** — the new piece. The next ~3 weeks of scheduled
   market events in one column: CPI, PCE, jobs report, FOMC dates from the
   maintained econ calendar; earnings dates for every name the desk watches
   (pulled from TradingView automatically); the memory-complex dates (MU
   earnings, DRAM contract settlements); and options-expiration / quarter-turn
   markers. Each event shows a countdown and an importance tag. The countdowns
   tick live.
5. **The flow boards** — Conviction, Swing, Biggest Orders, and the semi ETF
   flows card, exactly as they work today, restyled to match the new page.
   Every honesty label survives (15-minute delay, day-total-per-contract, no
   buy/sell side in free data).
6. **Watchlist grid** — your names with live price, day move, relative volume,
   and days-to-earnings.
7. **News rail** — headlines tagged to your names from TradingView's news
   feed, with the red rotation banner when several headlines hit rotation
   keywords.

### What it replaces, and when

| Today | After |
|---|---|
| Flow Desk site | Becomes this page (same URL, same data loop) |
| Morning Brief email, 6:23am | Keeps sending until you say stop. The page shows the same content all day. Turning the email off is your call, made after you've lived with the page — and the cron-job.org pinger is on your account, so repointing/deleting it is a step only you can do. |
| Morning brief artifact skill (`/morning`) | Retires once the page covers it |

Watchdog emails, Trade Stops, the Action List engine, and all theses/triggers
are untouched.

### What stays off the public page (important)

The flow-desk repo and its site are **public**. Your positions, trade stops,
theses, kill triggers, and the Action List verdicts are personal financial
data and do not belong on a public page. The plan ships the dashboard fully
market-data-only. A locked "private layer" (position guard, action list,
stops) is designed as an optional later phase — it would live in an encrypted
file only a passphrase in your browser can open — but it is off until you
explicitly want it. Same reason the Core Five panel shows levels and RSI but
not the TRIM/ADD rebalance chips.

### What I need from you (four decisions)

1. **Mockup approval** — open the mockup, say what to change. Layout, order,
   density, colors, name ("THE DESK" is a placeholder).
2. **Email's future** — keep the 6:23am email running alongside the page
   indefinitely, or plan to turn it off after a trial period?
3. **Private layer** — want the positions/action-list/stops panel behind a
   passphrase in a later phase, or keep personal data off the page entirely?
4. **Action List on page** — if yes to the private layer: verdicts render
   watch-only (backtest attempt #1 failed its gates; the standing rule says
   never present them as validated instructions).

### What it costs

Nothing. Every data source is free and keyless (CBOE delayed chains,
TradingView scanner/calendar/news, FRED CSV), the repo is public so Actions
minutes are free, and Pages hosting is free. The only new credential is a
read-only token so the public loop can read the brief summary out of the
private vault repo — created once in GitHub settings, ~2 minutes.

---

## Part B — What the research says (10+ video transcripts)

Five Sonnet research agents pulled **full transcripts from 16 YouTube videos**
(YouTube blocks datacenter IPs; the working route was yt-dlp's
`web_embedded`/`tv` player clients, captions only, no media). One agent's
batch — product walkthroughs (OpenBB, Koyfin, TradingView widgets) — was fully
IP-blocked on every access path; it substituted documented product research
and said so. The set spans two 3–4-hour full builds (JavaScript Mastery's
Signalist, 712k views, and CryptoPulse, 280k views), six working-trader screen
tours (Humbled Trader 190k, SMB Capital 78k, TraderTV Live 95k, others), three
catalyst-calendar walkthroughs (TTrades 120k lead), three dashboard-design
tutorials (DesignCourse 320k lead), and a Streamlit + a React build. The
findings that survive into this plan:

### B1. What traders actually keep on screen (6 transcripts: Humbled Trader, SMB Capital, TraderTV Live, Matt Owen, Abdullah Rasheed, James Rich Young)

- **A permanent index strip, separate from any single name** — SPY/QQQ/IWM/VIX
  tiles or a live index chart, answering one question fast: *is my stock
  moving, or is the whole tape moving.* (4 of 6 videos, independently.)
- **One symbol change should cascade everywhere** — panels follow the active
  ticker rather than being navigated independently.
- **Watchlists are ranked scanner output rebuilt each session, not static
  lists** — which is exactly Flow Desk's scored-board model.
- **News/catalysts get their own visible surface**, symbol-tagged, with
  macro headlines split from single-name headlines.
- **Premarket is a fixed numbered sequence** (scan → news per candidate →
  levels → written plan), i.e. the Morning Brief is the right anchor panel.
- **The most repeated opinion in the whole set: prune ruthlessly.** If a panel
  doesn't help find, enter, or manage a trade, it doesn't get screen space.
  More monitors/panels ≠ better trading.
- **Small screens are their own layout**, not a scaled-down desktop.

### B2. Catalyst/calendar craft (3 transcripts: TTrades, Dividend Data, StocksToTrade)

- **Event hierarchy is real and rankable:** earnings first ("half the year"),
  FOMC + jobs report as the week's anchor events, CPI/PPI/PCE second tier,
  story catalysts last and least reliable.
- **The planning horizon is the week.** Traders scan the full week's calendar
  Monday morning and mark which days are trade/avoid — so the module leads
  with This Week, then Next, not a flat list.
- **Impact tiers carry different behavior** (high = stand aside into the
  print; low = ignore). Countdowns should visually distinguish *approaching* →
  *imminent* → *cleared*.
- **Forecast / prior / actual is what makes an event row useful** — the
  surprise is what moves the market, so the row must carry those fields
  (TradingView's calendar endpoint provides them).
- **BMO/AMC timing flags on earnings matter** ("reported this morning" ≠
  "tonight after the close").
- **Filter ruthlessly to relevance:** US macro only, earnings for the
  watchlist only — never a global firehose.
- **Bellwether flag:** some prints matter beyond their ticker (mega-cap capex
  reads for the memory complex — `memory_events.csv` already models this).

### B3. Dashboard visual design (3 transcripts: DesignCourse, PamElA, Pierluigi Giglio)

- **Never pure black or pure white** — tinted near-blacks/off-whites; panel
  separation via small luminance steps, not hard borders.
- **KPI anatomy:** small low-contrast label, one oversized high-contrast
  number (≈14px label / 40px value), directional green/red chip *immediately
  adjacent* to the number it modifies.
- **Spend green/red only on direction; spend the one saturated accent on one
  thing at a time.** Everything else stays muted so the signal pops.
- **Stack two hierarchy signals** (size + weight, or size + contrast) — never
  size alone. All-caps micro-labels get letter-spacing.
- **4-pt spacing scale, thin low-opacity dividers, nested corner radii smaller
  than their parent** — density with order, not clutter.
- **Ranking boards: color only the leader saturated**, the rest muted — the
  color itself carries the ranking (adopted for the sector board bars).

### B4. Product teardowns (docs-based — OpenBB, TradingView widgets, Koyfin)

- **The ticker tape pinned at the very top is the genre's canonical opener**;
  dark, dense, card-per-concern layouts are the genre default, not a style
  choice.
- **Composable cards per concern beat one fused view** (Koyfin custom
  dashboards, TV widget taxonomy, OpenBB menu tree all converge here).
- **Embedding TradingView widgets costs a live external CDN dependency plus
  their branding on every load** — flow-desk stays self-contained against its
  own `data.json`, which also keeps the page fast and offline-tolerant.
- **Free products gate on data depth/freshness** (Koyfin 2-dashboard cap,
  sheets' 20-min delay); running our own fetcher avoids both ceilings — the
  architecture we already have is the one the market charges to escape.

### B5. Build-tutorial lessons (4 transcripts: Signalist, CryptoPulse, Ritvik CFA Streamlit, Magic Settings React)

- **Design the refresh cadence around the data source's free-tier limits, not
  the reverse** — every build's architecture bends around its API ceiling
  (CoinGecko 10k calls/mo at 30/min; Alpha Vantage's tiny daily allowance
  forced one creator to disable IDE autosave). One shared Actions cycle
  serving every visitor — our model — is the shape they all converge toward.
- **Tier the liveness:** polling for list views, true realtime reserved for
  the one view that needs it. Maps exactly to our 30s client prices +
  7-min flow loop.
- **Dark theme is stated as the deliberate financial-UI default** ("easier on
  the eyes, better contrast for numbers over long sessions"), built from a
  small token set, not per-panel styling.
- **One generic typed table component reused everywhere** beats re-solving
  sorting/empty-states per panel; empty/skeleton states are first-class or
  the page reads as broken.
- **Alerts scoped to threshold + fixed template set** (their
  upper/lower/volume emails) — which is precisely the Watchdog's existing
  design; no rules engine belongs in the page.
- TradingView's *embeddable widgets* are the tutorials' shortcut to
  professional charts — but per B4 they cost an external CDN dependency and
  branding; the desk stays self-contained against its own data.

### Decisions this research changed in the plan

1. Catalyst rows gain `forecast` / `prior` / `actual` (nullable) and a
   `session` flag (BMO/AMC) — see contract in C4.
2. Catalyst UI groups by **Today / This Week / Next / Later**, with
   approaching→imminent→cleared countdown states and impact chips.
3. The live index strip is pinned first, ticker-tape style, and kept separate
   from single-name panels.
4. Sector-board bars color the leaders saturated, the tail muted.
5. Typography/spacing follow B3 exactly (no pure black, tabular numerals,
   4-pt scale, green/red = direction only).
6. Lower-priority sections are collapsible; the prune-ruthlessly rule is the
   tiebreak on every "should this panel exist" argument.
7. Skeleton/stale states are first-class: every panel renders a labeled
   placeholder rather than a blank while its key is absent.
8. Symbol-cascade interaction (click a ticker → highlight it everywhere)
   lands in Phase 3.

### The v2 interactive prototype (same day, after Zach's design review)

Zach rejected the v1 card-grid look ("redundant, AI slop") and pointed at the
Wall-Street-cockpit reference (mcpmarket `trading-analysis-dashboard-template`:
dense panels, light/dark switching, chart interactions, demo/live playback,
keyboard command palette, single-file HTML). The mockup was rebuilt as a
working prototype — `2026-08-14-trading-dashboard-mockup.html` is now the
**binding layout and interaction spec for Phase 2**, verified interactive in
Chromium at 1440px and 390px, both themes, zero console errors.

**Design language (v2):** one continuous surface with hairline dividers — rows,
not repeated cards; a three-column cockpit (watchlist rail / analysis column /
catalysts+news rail) over a pinned tape; one restrained steel-blue accent with
green/red reserved for direction; tabular numerals everywhere; full light and
dark themes driven by one token set (dark native, light equal-quality); area
sparklines with endpoint markers.

**Interactions implemented in the prototype, each traced to research:**

1. **Ticker focus cascade + detail drawer** — click any symbol anywhere (or
   pick in the palette): every board highlights it, others dim, news and
   catalysts filter, and a drawer opens with a segmented 1D/1W/1M/3M chart
   (crosshair readout), quote/levels, its board stats, its catalysts, its
   headlines. (Screen-setup transcripts: "type one ticker once, every panel
   re-points"; SMB's timeframe ladder.)
2. **Command palette** — ⌘K / Ctrl-K / `/`: fuzzy tickers + actions (focus,
   jump to section, collapse/expand all, theme, replay). (Reference template.)
3. **Live catalyst countdowns** with approaching → imminent (<48h, amber) →
   cleared states, plus type filters (Econ/Earnings/Memory/OpEx) and a
   HIGH-only toggle. (TTrades impact tiers.)
4. **Forecast / prior / actual** on econ rows. (TTrades: the surprise is the
   signal.)
5. **Sortable boards** — one reusable table renderer, click-to-sort on score,
   flows, premium, expiry. (CryptoPulse reusable DataTable pattern.)
6. **Collapsible sections** with persisted state; palette carries
   collapse/expand-all. (Every screen tour: prune ruthlessly.)
7. **Theme toggle** — light/dark tokens, explicit choice beats OS preference.
   (Reference template.)
8. **Demo replay** — animates the tape to preview live 30s behavior, clearly
   labeled, disabled under reduced-motion. (Reference template's demo/live
   playback.)
9. **Tooltip layer** — hover/tap definitions carrying the TIPS honesty copy on
   every metric. (House rule + dataviz interaction spec.)
10. **Watchdog status chip** in the rail — alerts summarized where attention
    lands, not another panel. (TraderTV: alerts replace staring.)

### v3 — Zach's second review (same day)

Six changes, all implemented and re-verified (both widths, both themes, zero
console errors):

1. **Core Five retired as a panel.** The five names live in the watchlist rail
   like everything else; their levels/RSI detail lives in the drawer.
2. **Watchlist = his full TradingView list, leveraged ETFs excluded**
   (SOXL / SOXS / MUU out by rule — the flow boards still scan them; the rail
   says so). Groups: Watchlist / Semis & Memory / Mega cap & Energy — 26 names.
3. **52-week range bar on every rail row** — track, filled-to-current, diamond
   marker, lo/hi labels — for shopping value (CRWD at 17% of range) and
   spotting hot runners (AXTI at 93%) at a glance. Repeated large in the
   drawer with a "position in range" line.
4. **Relative movers, not absolute** — a name highlights only when today's
   move is ≥1.8× its OWN average daily move (MU's 2% is normal; GOOGL's 2% is
   an event). Amber tag shows the multiple; the rail's Movers box lists them
   with the "vs usual" arithmetic spelled out. Threshold is one tunable
   constant.
5. **Drawer chart upgrades** — segments now 1D/1W/1M/3M/6M/1Y; a chip states
   the % change over the selected segment; dashed 50-day and 200-day overlays
   draw on the chart with a legend stating distance from each ("+7.5% vs
   50-day · +33.8% vs 200-day").
6. **Analyst actions + fundamentals snapshot in the drawer** — actions table
   (date, action pill, firm, rating change, target change, colored by
   direction) and a snapshot block (market cap, fwd P/E, short % of float,
   beta, avg volume, dividend yield, avg daily move, next earnings, RVOL).

**New data these features need (Phase 1 verification list):**

| Need | Source plan |
|---|---|
| 52-week high/low, market cap, beta, avg volume | TV scanner fields (`price_52_week_high/low`, `market_cap_basic`, …) — same batch call the loop already makes; confirm exact field names in the Phase 1 probe |
| Average daily move (relative-mover base) | computed by the loop from cached daily bars (20-session mean of abs % change) — no new source |
| Daily closes for drawer charts + 50/200-day MAs | loop publishes a `bars.json` (≈260 closes per rail name, built via the existing `fetch_tv` websocket pattern); client computes MAs and segment % |
| Short % of float | TV scanner first; if absent, stockanalysis/finviz as named alternates — verify before promising, fail to "—" |
| Analyst actions history | **open** — TV carries ratings summaries but not a clean action-history feed; candidates: finviz/stockanalysis scrape or Benzinga RSS. Phase 1 verifies; if no reliable free source, the drawer section renders only what's available and says so. Display-only either way — the desk never scores off analyst opinions. |

### v3.1 — final architect pass (approved-direction polish)

Added to the prototype after a "what's still missing for this specific user"
review, filtered by the prune rule:

1. **Watchlist sort views** — `groups / 52w↑ / Δ% / hot` control on the rail.
   The `52w↑` view is the value-shopping mode Zach described: lowest-in-range
   first (CRWD, MRVL, LLY lead), hot runners sink to the bottom.
2. **Shopping list line** in the alerts box — the three names nearest their
   52-week lows, precomputed next to the hot movers, so both ends of his
   "shop value / trim runners" loop are one glance.
3. **Overnight — Asia panel** (right rail, above catalysts): KOSPI, SK Hynix
   and Samsung in Seoul, Nikkei, TSMC in Taipei, plus a divergence read line
   (Seoul pop vs US ADR fade). His heaviest position is MU — the Korea session
   is the memory-complex tell that moves it premarket. Sources are already
   routed and verified in `DATA_SOURCES.md` (TV global scanner / `fetch_tv`:
   KRX:KOSPI, KRX:000660, KRX:005930, TVC:NI225, TWSE) — fetched once by the
   morning context build, labeled with its session date.
4. **Tab badge** — the browser tab shows "(2) The Desk" when hot movers are
   active, so a parked tab signals without being opened.
5. **Price formatting** matches his reference snippet (`1,204.10`), tabular
   everywhere.

Build-phase requirements this pass adds (plan-only, no prototype change):

- **Session states**: the page must render distinct premarket / after-hours /
  closed treatments (state chip, "as of Friday's close" labeling, next-open
  line) — `data.json.market_state` already supplies the state.
- **Stale-data law**: any panel older than 2× its cadence renders an amber
  "as of <time>" badge — this repo's incident history (asof drift, dead feeds
  rendered flat) makes silent staleness the #1 forbidden failure.
- **Calendar export**: a "download .ics" action on the catalyst panel so
  high-impact events land in Outlook next to his site visits (Phase 3;
  generated client-side from the catalysts key).
- **Install-to-phone**: a web-app manifest so the page installs as an icon on
  his phone (Phase 3, two small files, no behavior change).
- **Breadth-regime chip** (optional): `brief_summary.json` may carry the
  vault's breadth-thrust regime state as one more backdrop chip — computed
  system already exists; Zach opts in or not.
- **Big-orders repeat flag** (Phase 3): once `history.json`'s archived boards
  accumulate, mark contracts appearing ≥3 straight sessions.
- **Threshold alignment note**: the dashboard's relative hot-mover rule (1.8×
  own average) and the Watchdog's absolute D4 rule (−3% legs) measure
  different things on purpose; if Zach later wants the Watchdog to go
  relative, that is a registered-engine change with its own decision.

Deliberately NOT added, per the prune rule: news sentiment scores, social
feeds, level-2/tape widgets, multi-layout workspaces, alert-builder UI (the
Watchdog already owns alerting), and any panel duplicating what the boards
already say.

---

## Part C — Technical architecture

### C1. Sources inventory ("all available resources," mapped to panels)

| Resource | Verified | Feeds |
|---|---|---|
| CBOE delayed chains (`cdn.cboe.com/.../options/{SYM}.json`) | live since 2026-07-16 | Conviction / Swing / Biggest Orders (unchanged) |
| TV scanner, server-side POST | live | quotes, RVOL, earnings-date fields, ETF SO/NAV flows |
| TV scanner, **browser CORS** (`Content-Type: text/plain` trick) | live, powers today's 30s prices | live ticker strip, watchlist grid live prices |
| TV economic calendar (`economic-calendar.tradingview.com/events`) | probed ✅ 2026-07-16 | catalyst calendar (econ leg) — also refills `econ_calendar.csv` |
| TV news (`news-mediator.tradingview.com/.../symbol?...`) | probed ✅ | news rail |
| FRED keyless CSV (`fredgraph.csv?id=...`) | ✅ 2026-08-02 (Actions transport untested — fail-soft) | macro backdrop readings (via brief summary; no new direct dependency) |
| Morning Brief engine (ClaudeVault, private) | in production | verdict, plain-words, backdrop grades, sector board, havens, Core Five |
| `data/econ_calendar.csv` (hand-maintained, verified thru 2026-12-30) | in production | catalyst calendar (authoritative for Fed/BLS/BEA dates) |
| `data/memory_events.csv` (hand-kept) | in production | catalyst calendar (memory-complex leg) |
| `history.json` (60 sessions) | in production | per-name net-flow sparklines (Phase 3) |
| GitHub Actions loop + `data` branch + `gh-pages` | in production | unchanged mechanics |

### C2. Writers and branches — the no-fight rule

The refresh loop **force-pushes the `data` branch every cycle**; it must stay
the *only* writer there (standing guardrail). So nothing new ever pushes to
`data`. Instead:

- **Loop-side additions** (econ calendar, earnings fields, news, brief pickup)
  happen *inside* `build_snapshot.run_cycle` and ride the existing force-push.
- **Brief summary** is committed by the morning-report workflow **to ClaudeVault
  `main`** as `market-data/data/brief_summary.json` (it already commits
  `score_history.csv` there — same pattern, same workflow). The flow-desk loop
  reads it via the GitHub contents API with a **fine-grained PAT secret
  (`VAULT_READ_TOKEN`, Contents: read-only, ClaudeVault only)** and folds it
  into `data.json` under `brief`. Fail-soft: token missing/expired/404 ⇒
  `brief.stale=true` with the last date it did have, site labels "as of
  <date>"; the boards never blank. Log hygiene: never print the fetched body
  in the public repo's Actions log.

Why not recompute the brief in flow-desk: the synthesis verdict is a
**registered engine that measurably works close-to-close** (35 sessions,
monotonic) and its inputs must not drift or fork. One computer, one number.
The email and the page show the same verdict because they read the same
engine's output.

### C3. Cadence

| Layer | Refresh | Mechanism |
|---|---|---|
| Prices (strip, watchlist, cards) | 30 s | client → TV scanner (existing pattern; add `TVC:` macro symbols — verify browser CORS on the `global` market during build; fallback: loop provides them in `data.json`) |
| Options boards / flow | ~7 min, 08:00–15:20 CT | existing loop, unchanged |
| Catalysts + news | hourly gate inside the loop cycle | new fetches in `run_cycle`; catalysts also rebuilt on the first cycle of the day |
| Brief panel | daily, first cycle ≥ 6:25 CT picks it up | ClaudeVault workflow writes summary at 6:23 CT send |
| Countdown timers | 1 s | pure client-side, no fetch |

Off-hours force runs keep the existing rule: `data.json` refreshes, history is
never written when `market_state == "closed"`, and the catalyst fetch runs
fine on a forced cycle (it writes no history).

### C4. `data.json` contract additions (DATA_CONTRACT.md is edited FIRST, per repo doc authority)

New top-level keys, all optional — an old snapshot without them renders the
current site's content, so deploy order can never break the page:

```jsonc
"brief": {
  "date": "2026-08-14", "stale": false,
  "verdict": "NEUTRAL", "score": 1, "plain_words": "…",
  "backdrop": {"grade": "NEUTRAL",
               "readings": [{"name": "10Y", "grade": "HOSTILE"}, …]},   // 6 rows
  "gap_note": true,             // RISK-ON days: render the gap-edge qualifier
  "sectors": [{"etf": "XLK", "rel_1w_pp": 1.2, "pp_1w": 2.0, "pp_1m": 4.1,
               "flow_1w": 2.4e9, "flow_1m": 1.1e10, "tag": "IN"}, …],   // 11 rows
  "retreat_watch": false,
  "havens": [{"etf": "GLD", "pct_1w": 0.8, "pct_1m": 2.4,
              "flow_1w": 6.1e8, "flow_1m": 2.9e9}, …],                  // 5 rows
  "havens_totals": {"sectors": 1.2e9, "treasuries": -4.0e8,
                    "gold": 6.1e8, "cash": 2.0e8},
  "whales_hiding": false,
  "core_five": [{"ticker": "GOOGL", "vs50_pct": 2.1, "vs200_pct": 8.0,
                 "rsi": 58, "vs_basket_3m_pp": -1.2}, …]                // 5 rows
},
"catalysts": [   // sorted by datetime; horizon ≤ 28 days PLUS standing anchors always
                 // included past the window: next FOMC decision, next CPI, and each
                 // pinned name's next earnings (B2's anchor-event finding).
                 // Rebuilt daily + hourly.
  {"date": "2026-08-19", "time_ct": "13:00", "title": "FOMC Minutes (July)",
   "importance": "HIGH|MEDIUM|LOW", "kind": "econ|earnings|memory|market",
   "ticker": null, "session": null,        // earnings only: "BMO"|"AMC"|null
   "forecast": null, "prior": null, "actual": null,   // econ only, from TV; null when unpublished
   "source": "econ_calendar|tv_earnings|memory_events|market_calendar"}
],
"news": {"items": [{"ticker": "MU", "title": "…", "ts": "…", "url": "…"}],
         "rotation_banner": false},
"context_updated_at": "2026-08-14T14:32:00Z"
```

`brief` mirrors `market-data/data/brief_summary.json` verbatim (the vault side
is the source of truth for its shape; DATA_CONTRACT.md documents it as
"published by the Morning Brief engine — do not compute these fields here").
Every number renders with its own freshness label; a missing key renders
nothing, never a zero — the house None-≠-0 rule.

### C5. Honesty and copy rules that must survive the redesign

- Biggest Orders stays labeled **day-total-per-contract, not single orders** —
  in all four places (section intro, tooltip, `notes.big_orders`, contract).
- FLOW % is described as **what traded**, never as a forecast (pre-registered
  gate unmet).
- The verdict renders as the **morning read** with its date; on RISK-ON days
  the gap-edge qualifier renders (84% of the verdict's edge is the overnight
  gap — the page must not imply a live green light).
- ETF/sector flows are **context, flows chase returns** — keep the wording.
- No buy/sell side exists in free data — tilt stays a "sampled proxy."
- **No leveraged-ETF decay/risk warnings anywhere** (Zach's ruling 2026-08-09).
- Not financial advice footer stays.
- `TIPS` tooltip text and `build_snapshot.py` scoring stay in sync — the
  redesign carries every existing tooltip forward and adds new ones for the
  brief panel and catalysts.

### C6. Guardrails carried forward unchanged

- `data` branch: loop force-push only; never hand-pushed.
- Pages stays **branch mode from `gh-pages`**; `pages.yml` keeps shipping
  `index.html` only (single-file site remains the pattern — all CSS/JS inline).
- Excluded tickers (BESIY, IFNNY, NRGU, WTI, SPX, VIX, SPMO) stay out of the
  options universe. (`TVC:VIX`/`TVC:US10Y` in the live strip are *index
  quotes*, not chain members — the exclusion note concerns the options boards.)
- Weekend/closed cycles never write history.
- Everything fail-soft: one bad fetch skips and logs, never blanks the page.
- Scheduled jobs keep a non-TV fallback where one exists; a TV outage must
  never blank the boards (CBOE and TV legs already fail independently).
- Workflow files are edited as rarely as possible (schedule-recognition reset).

---

## Part D — Build phases

Model roles per `flow-desk/CLAUDE.md`: **Opus** turns each phase into a
bite-sized TDD build spec, **Sonnet** builds it, **Haiku** does mechanical
sweeps, **Fable** rules on scope changes and gives final approval. Every build
session loads `security-and-hardening` (external fetches + workflow edits) and
`verification-before-completion`. Each phase lands as its own PR-sized merge:
tests green, screenshots taken, then merge to main per the standing rule.

### Phase 1 — Data layer (both repos)

**ClaudeVault** (`market-data/morning-report/`):
- `render.py`/`generate.py`: after a real `--send`, also write
  `market-data/data/brief_summary.json` (shape above). Same send-only gate as
  the score row — a dry run must never touch it (`test_send_sentinel.py`
  pattern extends to it).
- Workflow stages the new file (lesson: `recs_history.csv` was written by
  everything and committed by nothing).
- Tests: summary written on send only; shape-complete when sections resolve;
  keys absent (never zero) when a section failed.

**flow-desk** (`fetcher/`):
- New `fetcher/context.py`: `fetch_brief_summary()` (contents API + PAT,
  fail-soft, no body logging), `fetch_econ_calendar()` (TV events endpoint,
  window now→+28d, merge with committed `econ_calendar.csv` mirror —
  hand-maintained CSV wins on conflicts), `fetch_earnings_days()` (TV scanner
  `earnings_release_next_date` for the PINNED universe — rides the existing
  batch quote call), `fetch_news()` (TV news per watchlist symbol, hourly
  gate, rotation-keyword scan ported from `headlines.py`), `build_catalysts()`
  (merge econ + earnings + `memory_events.csv` + OpEx/quarter-turn from a
  ported `market_calendar` table).
- `build_snapshot.run_cycle`: fold the new keys into `data.json`; hourly gate
  via a timestamp in the existing `.prev_cycle.json` job-local file.
- `refresh-loop.yml`: expose `VAULT_READ_TOKEN` secret to the job env. (One
  deliberate workflow edit, batched with nothing else.)
- DATA_CONTRACT.md updated first; `fetcher/test_context.py` covers: merge
  precedence, horizon clipping, hourly gate, PAT-missing fail-soft, stale
  brief labeling, rotation-banner threshold, None-≠-0 on every field.

**Exit:** a forced off-hours cycle publishes a `data.json` carrying real
`brief`, `catalysts`, `news` keys; current live site still renders untouched.

### Phase 2 — The page (`index.html` v2)

- Full rebuild to the approved v2 prototype (this folder) — **the prototype is
  the binding layout + interaction spec**: cockpit columns, focus cascade,
  drawer, command palette, countdown states, sortable tables, collapsibles,
  light/dark tokens, tooltip layer. Build = swap its sample-data object for
  `data.json`/`brief`/`catalysts`/`news` renderers; all CSS/JS stays inline in
  the single file.
- Existing renderers (cards, big-orders board, ETF card, tooltips) are ported,
  not rewritten — their copy and TIPS entries move verbatim.
- New renderers: brief hero + sector board + havens + Core Five; catalyst
  timeline with live countdowns; news rail + rotation banner; live macro strip
  (client scanner probe first, `data.json` fallback).
- Old-snapshot tolerance: every new section renders nothing when its key is
  absent.
- Verification: Chromium screenshots at 1100px and 390px on live `data.json`
  plus a fixture snapshot *without* the new keys (the repo's standing
  screenshot discipline). The 390px dollar-column lesson generalizes: at phone
  widths, tables drop their secondary columns (big orders loses Vol/OI, the
  sector board loses its 1-month pair) so the dollar column is visible without
  a swipe — the mockup implements and proves this treatment.

**Exit:** Zach looks at the deployed page and signs off. Pages deploy is the
same `pages.yml` copy — no ops change.

### Phase 3 — Polish

- Sparklines: per-name net-flow trend from `history.json` sessions on the
  cards; 30-day price sparks for the strip if the client scanner leg proves
  out (else skip — YAGNI).
- Collapsible sections with state in `localStorage`; "next high-impact event"
  callout in the top bar.
- Retirement decisions executed per Zach's answers (email off → disable
  morning-report send + he repoints the cron-job.org pinger; `/morning` skill
  retired; README/DEPLOY/SYSTEMS.md rewritten to describe the desk).

### Phase 4 — Private layer (only if Zach opts in)

- `positions.json.enc` — AES-GCM, key derived from a passphrase (PBKDF2,
  WebCrypto), decrypt client-side only; encrypted blob published on the `data`
  branch by a vault-side workflow through the same single-writer rule
  (folded via the loop, like the brief). Panel: Position Guard mirror, stops
  distance, Action List verdicts (**watch-only wording enforced**).
- Never render before decrypt; passphrase never stored; wrong passphrase =
  panel stays closed, page otherwise full.

---

## Part E — Risks and mitigations

| Risk | Mitigation |
|---|---|
| TV endpoint shape drift / outage | fail-soft per leg + stale labels; CBOE boards independent; econ calendar has the committed CSV mirror |
| PAT expiry breaks brief pickup | 1-year fine-grained token; `brief.stale` label degrades gracefully; maintenance note in SYSTEMS.md next to the econ-calendar runway nag |
| Public Actions log leaks vault content | fetch step never echoes bodies; only writes the parsed file; reviewed in Phase 1 |
| Browser CORS blocked for `global` scanner market | strip symbols ride `data.json` from the loop (7-min freshness on macro rows — acceptable) |
| Page weight growth (news + catalysts + brief) | `data.json` stays a single small file; news capped (e.g. 20 items); no images; target < 150 KB gzipped |
| Workflow-edit schedule reset | the one `refresh-loop.yml` edit ships alone, off-hours, with a forced-cycle check after |
| Scope creep re-scoring boards | conviction/swing scoring, weights, and universe are explicitly out of scope for every phase |

## Part F — Success criteria

1. One URL replaces the morning email + Flow Desk for a full trading week
   without Zach opening either.
2. Every panel shows its own freshness stamp; nothing renders a stale number
   as current, ever.
3. Catalysts within 28 days are on the page with correct CT times and live
   countdowns; nothing high-importance in `econ_calendar.csv` is missing.
4. Phone-usable at 390px — no horizontal scroll, dollar figures never clipped.
5. All existing tests pass; new fetches covered; two screenshot checks in CI
   notes; zero changes to scores, weights, or the pinned universe.
