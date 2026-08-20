# Flow Desk — what is still open

Written 2026-08-20, at the end of the review rounds. Everything in the
"Shipped" list below is done, verified and merged. Everything under "Open" is
work a later session can pick up. Nothing here blocks using the page.

---

## Open — in the order they are worth doing

### 1. Publish bars.json v4 (biggest real-world gap)

**What:** `fetcher/context.py` has emitted `BARS_VERSION = 4` since
2026-08-19 — a `sessions` calendar plus a `bar_dates` map of per-ticker
exceptions. The live `data` branch still serves v3, which carries no dates at
all.

**Why it matters:** with no calendar, the page reconstructs every daily and
weekly date by walking back one trading day per bar. That is why the crosshair
carries an "≈", why earnings and rating popovers warn about the candle they sit
on, and why a trend line's break date reads "broke Aug 11 (approx)". The
reconstruction now skips weekends and a hard-coded holiday table (back-filled
through 2024), so the drift is small — but it is still a reconstruction.

**How:** the daily rebuild is signature-gated on `BARS_BUILD_SIG`, so the next
full rebuild publishes v4 on its own. Confirm with:

    git show origin/data:bars.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('v'), 'sessions' in d)"

When it reads `4 True`, `barSessionDates` takes over, `BAR_DATES_APPROX` goes
false, every "≈" and every approximation note disappears on its own, and
`isTradingDay` starts preferring the published calendar over the hard-coded
table. No page change is needed.

**Until then:** `MARKET_HOLIDAYS` in index.html has to be extended each
December. It currently runs 2024 through 2027.

### 2. Round 6 of the review was never scored

Round 5's adversarial verification finished after the fixes: of 72 findings it
checked, **70 were refuted because they were already fixed**, and the two it
confirmed are both closed (one was the board footer, already corrected; the
other was a caveat sentence made false by its own fix, corrected after).

Round 6 itself was launched and stopped before it scored anything, so there is
no round-6 finding list.

Rounds 4 and 5 each ran nine section reviewers with adversarial verification;
every confirmed finding from both is fixed. Round 6 was launched and stopped
before it scored anything, so there is no round-6 finding list.

Re-run round 6 with:

    Workflow({scriptPath: ".../flow-desk-review-r4-wf_9e7063ce-dfb.js"})

Expect it to take roughly 45 minutes and to find things — that has been true
every round. Round 5's findings were almost all things rounds 3 and 4 never
reached, and several were holes in round 4's own fixes.

### 3. Score trajectory, and what "90" would take

| Section | R3 | R4 | R5 |
|---|---|---|---|
| Right rail panels | 69 | 72 | 78 |
| Data honesty | 72 | 81 | 78 |
| Sector heatmap | 74 | 76 | 74 |
| Flow boards | — | 74 | 73 |
| Left rail | 46 | 72 | 72 |
| vs Peers | 82 | 73 | 71 |
| Financials | 85 | 71 | 64 |
| Auto-TA | 56 | 67 | 58 |
| Chart stage | 69 | 67 | 55 |

The scores are not tracking quality in the way the numbers suggest. Every
round's reviewer opens a page whose previous faults are gone and goes deeper,
so a section that improved can score lower. The finding LISTS are the useful
output, and those have been getting more specialised each round — round 5's
chart list ran from "markers are silently dropped" (severe, real) down to "the
closing-auction bar is dimmed as extended hours" (polish).

If a later session wants the number itself to move, the lever is the review
prompt, not the page: score against a fixed rubric carried between rounds
rather than against each reviewer's fresh read.

### 4. Deferred by judgement, not by omission

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

The Playwright harness and probes live in the session scratchpad, which does
not survive. To rebuild: serve the repo on 127.0.0.1:8899, launch Chromium at
`/opt/pw-browsers/chromium`, and route every external host through a
server-side fetch (the sandbox proxy resets the browser's TLS, so the page
cannot reach TradingView directly). What the probes measured, all currently
clean:

- Zero JS errors across every ticker x interval x tab x TA toggle x width x theme
- Zero sub-4.5:1 text in either theme, on the boards and on the heatmap
- 166 keyboard stops, all named; no duplicate ids; no unnamed pressed controls
- Prices agreeing across the rail, the chart header and the boards
- The "% shown" chip matching the visible window exactly on every name
- 150 fetcher tests passing
