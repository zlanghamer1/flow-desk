# Day-trade tools — design record (2026-09-23)

Zach's `/goal`, 2026-09-23: "make the desk even better … Make it where I have
the easy to use tools to be a day trader." Adversarial assessment ran first
(status audit, premise red-team, real-time source hunt); this spec is what
survived it.

## The line this design holds

The desk's stock prices are 15 minutes behind the tape (ban 8). Its intraday
bars trail further: the 15m file rebuilds on a 25-minute gate, so a drawn bar
can be ~40 minutes old. Measured on the published 15m file (3 sessions), the
median move in the first 15 minutes after the open was 2.7% on MU, 3.4% on
CRWD and 3.3% on COHR, while a day trader's stop is often 0.5–1% away.

So the desk **plans and referees**; the broker (Fidelity) and TradingView's
own real-time chart **time** the trade. Every tool below answers a question
that is still true 16 minutes later. Nothing here times an entry or exit,
fires a price alert, or relabels a delayed price.

Rejected by the red-team, not built: delayed price/breakout alerts (fire after
the move), the 21-day verdicts relabeled as day calls, options flow as a
trigger, live P&L marked to a delayed price, an opening-range tool (the range
is drawn 30–50 minutes after it forms).

## Measured facts this spec rests on (2026-09-22 close, keyless scanner)

- **The scanner's plain `VWAP` column is NOT volume-weighted.** It equals the
  daily bar's (high + low + close) / 3 to the cent on MU (1074.475), SPY, NVDA,
  V and CRWD. It must never be labeled VWAP.
- **`VWAP|5` and `VWAP|15` ARE the regular session's volume-weighted average**,
  computed on 5- and 15-minute bars. `VWAP|15` matched a hand VWAP over the
  desk's own 15m file (regular-session bars with volume) within 0.02% on all
  five names (MU 1077.459 vs 1077.646, SPY 773.876 vs 773.845, NVDA 228.677
  vs 228.647, V 363.417 vs 363.425, CRWD 248.059 vs 248.094). The first draft
  of this spec probed only the plain column and wrote "a real VWAP needs the
  15m file, desk names only" — the 2026-09-05 mistake (asking for less than
  the vendor offers, then recording the gap as the vendor's). The architect
  review caught it. `VWAP|5` serves every name, searched ones included.
- **`time` is the epoch of the regular session the regular columns describe**
  (08:30 CT). Its CT date is the only honest label for `open`, `high`, `low`,
  `close` and `change`: for the first ~16 minutes after the bell the delayed
  feed still carries yesterday, so the clock alone mislabels them. `time|5`
  is the start of the last 5-minute bar behind `VWAP|5`.
- **`relative_volume_10d_calc` = today's running volume ÷ the average FULL
  session of the prior 10 sessions.** MU 1.1571 against 29,188,467 ÷ mean of
  bars.json's last 10 settled volumes = 1.1577 (same on NVDA, V, SPY). So at
  9:00 CT a normal name reads ~0.1. It is honest only labeled "× avg day".
- **`relative_volume_intraday|5` does not reduce to that ratio at the close**
  (MU 1.231 vs 1.157) and its semantics cannot be measured with the market
  closed. Not used.
- **`ATR` is Wilder's ATR(14) with today's bar included** — exact to three
  decimals on MU (50.503), NVDA, V and SPY against bars.json plus the day's
  scanner bar.
- **`premarket_time` is the epoch of the pre-market session's start** (08:00Z
  = 03:00 CT on 2026-09-22). `premarket_high/low/volume` belong to the CT day
  of `premarket_time`; that date is the freshness check.
- The regular-session columns (`open`, `high`, `low`, `close`, `change`) still
  describe the previous session during pre-market (existing CLAUDE.md rule).
- Yahoo's 15m bars carry zero volume outside 08:30–15:00 CT on settled days,
  and a zero-volume post-close bar can carry a bad wick under the 4% repair
  floor (SPY 2026-09-21 15:00 low 762.07 vs the day's real low 766.03). No
  level in this design is read from an intraday bar's high or low.
- The scanner answers a whole-market filtered scan from the browser (the host
  reflects any Origin; `update_mode: delayed_streaming_900`). Fields verified
  in `/america/metainfo`: `premarket_change`, `premarket_volume`,
  `premarket_high`, `premarket_low`, `premarket_time`, `postmarket_change`,
  `postmarket_volume`, `gap`, `change_from_open`, `float_shares_outstanding_current`,
  `ATR`, `earnings_release_date`, `earnings_release_next_date`, `is_primary`,
  `type`, `typespecs`.
- FINRA Regulatory Notice 26-10 replaced the pattern-day-trader rule and its
  $25,000 minimum effective 2026-06-04; Fidelity has discontinued it. Nothing
  outside the trader caps trade count any more, which is why the daily limits
  below exist.

## What ships

### 1. Day trade tab (stage tab `dt`, per focused name)

A sixth tab under the chart, "Day trade". Works for pinned AND searched names
(it reads the scanner row and daily bars, both of which searched names have).

**Levels sheet.** One row per level: label (dated, never "yesterday"), price,
signed distance from the delayed price (U+2212), and a "stop" button that
loads the level into the calculator's stop. Which levels print depends on the
CT phase, computed by one function `dtPhase(now)`:

| phase | when (CT) | levels |
|---|---|---|
| `pre` | `priceSessionNow` = premarket | pre-market high/low (only if `premarket_time`'s CT day is today); the prior session's high/low/close and VWAP from the regular columns, labeled with `time`'s date |
| `open` | `priceSessionNow` = open | when `time` is today: today's open/high/low and VWAP (`VWAP\|5`, "5m bars to HH:MM"); the previous trading day's high/low from its dated daily row, its close = `close − change_abs`. When `time` is not today yet: "today not in the feed yet" and that session's dated high/low/close/VWAP. Pre-market high/low in both cases (dated check) |
| `plan` | any other time | the last session's high/low/close and VWAP, labeled with `time`'s date; the header names the next session's date |

All phases add: 50-day and 200-day averages (the same `statsOf` series the
quick read uses), and ATR(14) from the scanner, with "range used" (`(high −
low) / ATR`) when the sheet describes today's session.

A level whose source is missing prints the bare fact in its row ("Sep 22 bar
not on file yet", "no pre-market print"). It never falls back to a different
day's value.

**Copy levels** button: writes a plain-text line to the clipboard ("MU · Sep 23
10:15 CT · 15-min delayed · Pre-mkt high 1040.74 · …") for pasting into
TradingView alerts. Clipboard failure prints "copy failed" in place.

**Size calculator.** Inputs: account ($), risk per trade (% of account,
default 1), side (long/short), entry (defaults to the delayed price, tagged
"delayed HH:MM"), stop (required). Outputs, from one pure function
`dtSize({acct, riskPct, side, entry, stop})`:
- shares = floor(acct × riskPct / 100 / |entry − stop|)
- $ at risk = shares × |entry − stop|
- position value and its multiple of the account
- 1R / 2R / 3R target prices
- loss if the fill slips to twice the stop distance
Refuses (returns a reason, never a number) when: stop missing, stop on the
wrong side of entry, stop equals entry, account or risk not positive, or
shares round to 0 (names the risk budget and one share's risk). Account and
risk % persist per browser (`desk.dt.acct`, `desk.dt.risk`); entry/stop reset
on a symbol change. When today's limits read DONE the calculator shows the
DONE chip.

### 2. Day limits (section `#s-day`, global)

Per browser, `localStorage` with an in-memory mirror and a save-failed line
(the watchlist's `WL_MEM` pattern).
- Caps: daily loss cap ($, default 2% of the saved account) and max trades
  per day (default 3).
- **A cap can always be lowered and can be raised only before today's first
  logged trade AND before 08:30 CT on a trading day.** The refusal prints
  "locked until tomorrow".
- Log a trade: ticker (defaults to the focused name), long/short, shares,
  entry, exit, followed-plan checkbox, note. P&L = (exit − entry) × shares,
  sign flipped for a short. Rows keyed by CT day (`ctDateKey`).
- Today: realized P&L, trades n of cap, loss budget left, and one status:
  OPEN, DONE (loss cap), DONE (trade cap). DONE is the section's one filled
  badge.
- History: trade count, net P&L, win rate, average win, average loss,
  followed-plan share. Under 30 trades the stats print with "N of 30 trades"
  beside them.
- Export CSV; backup and restore JSON (file download / file input).
- Delete a row with ×.

### 3. Gappers & movers (section `#s-gap`, global, whole market)

Browser-side POST to `TV_SCANNER_URL` (no new host). Mode follows the same
phase function, extended with the post-close window:
- `pre`: "Pre-market gappers", ranked by |`premarket_change`|, volume column
  `premarket_volume`, floor 50K shares.
- `open`: "Movers today", ranked by |`change`|, plus `gap` and
  `change_from_open`, volume floor 500K.
- after the close until 19:00 CT: "After-hours movers", |`postmarket_change`|,
  `postmarket_volume` floor 50K.
- otherwise: the last session's movers by |`change`|, labeled with its date.
Filters (persisted, `desk.gap.*`): direction all/up/down; min price $1 / $5 /
$20 (default $5); stocks only (default on: `type` = stock). Always: exchange
NASDAQ/NYSE/AMEX, `is_primary`.
Columns: ticker + name, price, move %, volume, "× avg day"
(`relative_volume_10d_calc`), float, earnings chip when the last or next
earnings release falls on today's or the prior session's CT date.
Top 12 shown, a disclosed "show all" to 30. Rows use `table()` (data-sym,
role, tabindex, focus restore). A click registers the ad-hoc name, focuses it
and opens the Day trade tab.
Refresh every 60 s only while the section is open and the page visible;
failure backs off 30 s → 60 s → … → 5 min. A failed or empty-under-rate-limit
response keeps the last good rows and prints the reason; the as-of stamp moves
only on a scan that returned rows. As-of and "15-min delayed" print
unconditionally.

### 4. Hotkeys

Outside any input, no modifier: `[` / `]` previous / next rail name; `1`–`5`
the five intervals in `IVS` order; `d` the Day trade tab. No palette entries:
the "Jump to <section>" entries were cut on 2026-08-18 as keystroke padding,
and this change does not re-add them.

### 5. Honesty fixes found by the audit

- The Fundamentals grid's "RVOL today" becomes "Volume vs avg day" (the number
  is unchanged; the label now says what it measures).
- Honesty box: Freshness gains the gappers cadence; Limits gains one sentence
  that the day-trade tools size and log trades, while entries and exits need a
  real-time broker quote.

## Rules that bind the build

- No explanation text (the 2026-09-05 ruling): no methodology prose, no
  `data-tip` lectures. Dynamic facts only.
- Display-only. Nothing here feeds a board score, a verdict, or the fetcher.
- No new external host; no fetcher or payload change.
- Every formatter prints U+2212 and guards signed zero (`fm1`/`fm2` family).
- Type floor 10px (10.5px for data labels); no sideways page scroll at 390px
  and 1440px; grid items `min-width:0`.
- One function per fact: `dtPhase`, `dtVwap`, `dtSize`, `dtLevels`,
  `dtJournalStats`, `gapScanBody` are the only places those rules live.

## Tests

`tests/test_day_trade.py` (headless Chromium, every external host blocked,
the scanner answered from fixtures, the clock pinned with `page.clock`):
calculator math and each refusal; VWAP against a hand-computed fixture;
levels per phase with a pinned clock; journal P&L, DONE at each cap, the
raise-lock; gappers rendering, click-to-focus, failure keeps the slot; no
sideways scroll at 390px with the new sections open.

## Architect review, 2026-09-23 (APPROVE WITH CHANGES) — adopted in full

1. Every regular-column level is dated from the row's own `time`, never the
   clock. During `open`, a `time` that is not today prints "Sep 22 session ·
   today not in the feed yet" and the levels carry Sep 22 labels. Same rule
   for the gappers' "Movers today". In `pre`, the "× avg day" column is
   dropped (it divides yesterday's full volume).
2. `dtPhase` is a thin map over `priceSessionNow(now)`: premarket → `pre`,
   open → `open`, anything else → `plan`.
3. bars.json holds the previous session only after the loop's first cycle of
   the day (≥ 08:00 CT, GitHub's schedule measured hours late). `ensureBars`
   no longer marks a stale file (`built` before today on a trading day) as
   today's fetch; `tick()` re-checks it every 10 minutes until it is current.
   The prior-session high/low reads only the daily row dated the previous
   trading day; otherwise the row prints the bare fact.
4. VWAP reads `VWAP|5`, stamped from `time|5` + 5 minutes, for every name.
   It prints only when `time|5`'s CT date is the session the sheet describes.
5. Ranking by |move| is two scans (descending and ascending) merged on the
   page. The `pre` scan filters `premarket_time` ≥ today 03:00 CT; the post
   scan filters `postmarket_time` ≥ today's close. Only `typespecs`
   containing `common` count as stocks.
6. `{"totalCount":0,"data":[]}` is a miss: last good rows and the as-of stamp
   stay, and the reason line reads "scan returned no rows".
7. `dtSize` refuses a missing, non-finite or non-positive entry or stop. The
   calculator floors shares; the journal accepts fractional shares.
8. Referee: today's rows are voided, never erased, and DONE latches for the
   CT day once reached. Restore JSON merges by `id`, validates each row and
   never removes or un-voids today's rows. The loss cap is stored in dollars
   when set, so a larger account never raises it. DONE when realized P&L ≤
   −cap; budget left = cap − max(0, −realized), a profit never enlarges it;
   a $0 trade is neither a win nor a loss. A cap may be raised only in the
   `plan` or `pre` phase and only before today's first logged trade. All day
   math goes through `ctDateKey` / `ctMinutesOfDay` / `isTradingDay`.
9. The section header prints "this browser" as a bare fact (ban 11
   precedent).
10. Settled question 10 ruling: the journal is not Position Guard. It holds
    closed trades only (entry and exit both required), never marks anything
    to a delayed price, never reads `desk_private`, never shows an open
    position.
11. The 30-second poll gains `change_abs`, `premarket_high`, `premarket_low`,
    `premarket_time`, `ATR`, `time`, `VWAP|5`, `time|5`, appended after the
    existing columns so every index already read stays put.
12. No `data-tip` on any new control. DONE uses the `--dnbg` / `--dn` tinted
    fill. Hotkeys are inert while focus is in an input, textarea, select or
    contenteditable element, or while the palette is open.

## Build contract (DOM ids and globals the tests read)

Globals (function declarations, reachable from `page.evaluate`):
`dtPhase(now)`, `dtSize(p)`, `dtLevels(sym, now)`, `dtJournal()`,
`dtJournalAdd(row, now)`, `dtJournalVoid(id, now)`, `dtJournalStats(rows)`,
`dayState(now)`, `dayCapsSet(caps, now)`, `gapMode(now)`,
`gapScanBodies(mode, filters, now)`, `gapMerge(resultsArray, mode, max)`.

- `dtSize({acct, riskPct, side, entry, stop})` → `{ok:true, shares, risk,
  pos, mult, targets:[r1,r2,r3], slip2}` or `{ok:false, err}`. `side` is
  `"long"` or `"short"`. A short's target at or below 0 is `null`.
- `dtLevels(sym, now)` → `{phase, sessKey, rows:[{k, label, px, miss}]}`;
  `k` ∈ pmh, pml, open, hi, lo, close, vwap, pdh, pdl, pdc, m50, m200, atr.
  `px` null with `miss` a string when the level is missing.
- `dtJournalAdd(row, now)` → `{ok, err?, id?}`; `row` = `{sym, side, shares,
  entry, exit, plan, note}`.
- `dayState(now)` → `{caps:{loss, trades}|null, n, pnl, budgetLeft, done,
  reason}`; `reason` ∈ `"loss"`, `"trades"`, null.
- `dayCapsSet({loss, trades}, now)` → `{ok, err?}`; a raise outside the
  window returns `{ok:false, err:"locked until tomorrow"}`.
- `gapMode(now)` → `"pre"` | `"open"` | `"post"` | `"last"`.

Storage keys: `desk.dt.acct`, `desk.dt.risk`, `desk.day.journal`,
`desk.day.caps`, `desk.gap.dir`, `desk.gap.px`, `desk.gap.stk`.

DOM:
- Stage tab button `#stagetabs button[data-tab="dt"]`, label "Day trade".
  Body: `#dtwrap[data-sym]`; levels `#dtlev` with one `.dtrow[data-lv=<k>]`
  per level (`.miss` class when missing) each carrying a
  `button.dtstop[data-px]` unless missing or `atr`; `#dtcopy`, `#dtcopymsg`.
  Calculator `#dtcalc`: inputs `#dtacct`, `#dtrisk`, `#dtentry`, `#dtstopin`;
  side buttons `#dtside button[data-side]`; output `#dtout` holding
  `.dtres[data-k=shares|risk|pos|r1|r2|r3|slip2]` or one `.dterr`.
- Section `#s-day` (header stat `#daystat`, body `#day`): caps inputs
  `#daycaploss`, `#daycaptrades`, button `#daycapsave`, message
  `#daycapmsg`; log form `#dtl-sym`, `#dtl-side` (select), `#dtl-sh`,
  `#dtl-en`, `#dtl-ex`, `#dtl-plan` (checkbox), `#dtl-note`, `#dtl-add`,
  `#dtl-msg`; today's table `#daytoday` with `tr[data-id]` and
  `button.dvoid`; stats `#daystats`; `#dayexport`, `#daybackup`,
  `#dayrestore` (file input).
- Section `#s-gap` (header stat `#gapstat`, body `#gap`): filters
  `#gapfilters` with `button[data-gdir]`, `button[data-gpx]`,
  `button[data-gstk]`; rows `#gap tr.rw[data-sym]`; reason line `#gapnote`.
