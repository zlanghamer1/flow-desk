# Desk verdicts — design (2026-09-11)

## The ask

`/goal refine & tighten up the desk. Make it where recommendations for buys
and sells are decided and clearly seen based on the weighted composite of all
data.`

## Decision

Add one decision layer on top of everything the desk already collects. The
fetcher computes it once per cycle (`fetcher/verdict.py`) and publishes it as
`data.json.verdicts`. The page renders it as a **Verdicts board** at the top
of the middle column and repeats the same call wherever a name appears: the
flow-board rows, the Overview tab's headline strip, and the watchlist rail.

`conviction_score` and `swing_score` do not change. They become two of the
nine inputs. Standing ban 10 (a display-only field never feeds a board score)
still holds for both board scores; the composite is a separate, additive
layer that reads the display-only fields and never writes back into either
score.

## Alternatives considered

1. **Fold the new inputs into `conviction_score` / `swing_score`.** Rejected.
   Both boards mean one specific thing (fast flow; persistent flow), and ban
   10 exists because those weights were never validated against anything
   else. Mixing fundamentals into a flow score destroys both readings.
2. **Compute the composite in the page from published fields.** Rejected.
   It would re-derive a grade in JavaScript (the desk computes `grade` and
   `alarm` in the fetcher, never in JS), it could not be pinned by `pytest`,
   and the vault's Morning Brief could not read it.
3. **A rule engine with gates and precedence, like the vault's
   `action_engine.py`.** Rejected as the main mechanism. The ask names a
   weighted composite. Two gates survive where a weight cannot express the
   fact: a coverage gate (too few inputs → no call) and an earnings gate
   (a report inside three days → HOLD).

## Inputs

Nine readings. Each maps to a signed value in −1..+1 or `null`. `null` is
never treated as zero: the weight of a null input drops out of the
denominator, and the coverage gate below decides whether a call is allowed
at all.

| key | page label | code | weight | source (fetcher) | mapping | null when |
|---|---|---|---|---|---|---|
| `trend` | Trend | TR | 20 | settled daily closes from `bars.json` (SMA50, SMA200) and the cycle spot | leg(m) = 0 if \|spot/m − 1\| < 0.003, else sign(spot − m); v = 0.5·leg(SMA50) + 0.5·leg(SMA200) | fewer than 200 closes, or no spot |
| `rs63` | Rel str | RS | 10 | same closes for the name and for SPY | v = clamp(((c[−1]/c[−64] − 1) − (spy[−1]/spy[−64] − 1)) / 0.20) | fewer than 64 closes for either |
| `framework` | 5-metric | FW | 20 | `facts.<T>.framework.verdict`, suffix `_BUILDING` / `_CAPPED` stripped | BUY_5 +1.0, BUY_4 +0.75, ADD +0.4, HOLD 0.0, AVOID −1.0 | `BUILDING`, `NOT_APPLICABLE`, or absent |
| `analyst_rating` | Rating | AR | 8 | `facts.<T>.rec_mark`, `rec_total` | v = clamp((1.43 − mark) / 0.45) | `rec_mark` null or `rec_total` < 5 |
| `target_upside` | Target | TG | 7 | `facts.<T>.target`, cycle spot, `rec_total` | v = clamp(((target/spot − 1) − 0.20) / 0.30) | target or spot null, or `rec_total` < 5 |
| `flow_today` | Flow 0–7d | F7 | 10 | the name's ConvictionCard | v = (+1 BULL / −1 BEAR) × score/100 | no ConvictionCard this cycle |
| `flow_persist` | Flow swing | FS | 15 | the name's SwingCard | v = (+1 BULL / −1 BEAR) × score/100 | no SwingCard this cycle |
| `valuation` | PEG | PG | 5 | `facts.<T>.peg`, `pe`, `sec_type` | v = clamp((1.5 − peg) / 1.5) | peg null or ≤ 0; pe null, ≤ 0 or > 150; `sec_type` = fund |
| `market` | Market | MK | 5 | `data.brief.score` | v = clamp(score / 5) | brief absent, `brief.stale` true, or score null |

Weights sum to 100. `clamp` bounds to −1..+1.

**Why these centers.** Analyst ratings and targets are bullish on almost
every listed name, so raw values would push every verdict up. The centers
come from a keyless scanner probe on 2026-09-10 over 2,731 US stocks with at
least five analysts and a market cap above $2B: median `recommendation_mark`
1.43 (10th–90th percentile 1.115–1.90), median 12-month target 20% above
price (10th–90th percentile +3% to +51%). The spans (0.45 and 0.30) put
those percentiles near ±1. On the desk's own 63 names the median target sat
35% above price and no rating was worse than 1.98, so without centering
both inputs would have read positive for every name.

**Why `trend` reads the 50-day and 200-day, not the 20/50 the Swing board
uses.** The quick read under the chart already judges price against its own
50-day and 200-day averages with a ±0.3% dead zone. Two verdicts about the
same thing on one screen must agree, so the composite uses the same
definition. `flow_persist` still carries the Swing board's 20/50 trend inside
its score; that overlap is accepted and documented.

**Why flow is 25 of 100.** `flow_today` and `flow_persist` share one
direction sign (SwingCard's direction is the sign of the same 0–7 day net
flow). Flow is what this desk is for, so it keeps a quarter of the weight,
but the vault's own measurement (`results/flow_accuracy_2026-07.md`) found
no predictive accuracy, so it does not dominate. Trend and relative strength
(30) have the most outside support; the 5-metric framework (20) rests on
the vault's measured correlations; analysts (15) are centered as above;
valuation and market backdrop (5 each) are small deliberately.

**Fed-hike odds are not an input.** The standing ruling says they grade the
backdrop and never move a verdict score. `brief.score` is computed without
them, so `market` inherits that ruling.

## Score, gates, call

```
weight = Σ w_i over resolved inputs
score  = round(100 × Σ w_i·v_i / weight)            −100..+100
coverage gate: weight ≥ 50 AND resolved inputs ≥ 3, else score = null, call = null
call   = BUY  if score ≥ +35
         SELL if score ≤ −35
         HOLD otherwise
earnings gate: 0 ≤ facts.earn_days ≤ 3 → call = HOLD, note = "earnings in Nd"
               (score unchanged and still printed)
```

Measured on the 2026-09-10 publish: 56 of 63 names cleared the coverage
gate; scores ran −62 to +62 with a median near zero; the ±35 line gave 9
BUY, 8 SELL, 39 HOLD and 7 no-call. No name sat inside the earnings gate
that day.

## Evidence class

Unvalidated. The weights, centers, spans, thresholds and gates above are set
by judgment and pre-registered here and in the vault's
`portfolio-thesis/decisions-log.md`. Changing any of them needs a dated
amendment there first, then a labeled backtest attempt reported honestly,
per Decision 6 of the Action List design (once-only backtest honesty). The
page states the limit in the honesty box. No sentence on the page explains
the method; the honesty box is the one sanctioned home for that fact.

## Payload

`data.json.verdicts` — OPTIONAL top-level key, omitted when the cycle
computed nothing. Full field list in `DATA_CONTRACT.md`.

```json
"verdicts": {
  "v": 1,
  "thresholds": {"buy": 35, "sell": -35},
  "min_weight": 50, "min_inputs": 3, "earnings_gate_days": 3,
  "order": ["trend","rs63","framework","analyst_rating","target_upside",
            "flow_today","flow_persist","valuation","market"],
  "weights": {"trend": 20, "rs63": 10, "framework": 20, "analyst_rating": 8,
              "target_upside": 7, "flow_today": 10, "flow_persist": 15,
              "valuation": 5, "market": 5},
  "counts": {"buy": 9, "sell": 8, "hold": 39, "none": 7},
  "by_ticker": {
    "MU": {
      "score": 34, "call": "HOLD", "note": null,
      "n": 8, "n_total": 9, "weight": 80,
      "inputs": {
        "trend": {"v": 1.0, "note": "above 50d · above 200d"},
        "framework": {"v": null, "note": "building"},
        "...": {}
      }
    }
  }
}
```

`note` on a ticker is the one-line reason a call was held or withheld:
`"earnings in 2d"` for the earnings gate, `"3 of 9 inputs · weight 35 of
100"` for the coverage gate, `null` otherwise. `note` on an input is the
bare fact behind its value (or the reason it is null), written to change
with the data and never as a sentence that reads the same every day.

Weights and thresholds are published so the page never hardcodes them. The
page never re-derives `call` or `score`; it reads them. `order` and the page's
label map are a cross-file pair pinned by `fetcher/test_sync_constants.py`.

## Page surfaces

All five read one payload and share two functions: `verdictOf(sym)` (the
ticker entry or null) and `verdictPillHTML(sym)` (the call badge). Nothing
else derives a call.

1. **Verdicts board** (`#s-verd`, new section above the "Flow boards — the
   signal" eyebrow, under its own eyebrow "Verdicts — the call"). Header
   stat: `N buy · N sell · N hold · N no call` plus the standard age stamp.
   Quick-read line from the same counts: `N buys and N sells today ·
   strongest buy XLE (+62) · strongest sell XLI (−62)`. Columns: Name (ticker,
   live price line as on the other boards), Call (filled pill), Score (signed
   number with U+2212 and a diverging bar with tick marks at the buy/sell
   thresholds), Inputs (nine chips in `order`, two-letter code, colored by
   sign, dashed and dimmed when null, tooltip = label, value, points and the
   input's note), Coverage (`n of n_total`, dimmed below full). Default sort:
   score desc; null scores sink. Default cut shows BUY and SELL rows only,
   with the standard disclosed cut note and "show all" button
   (`showAllBoards.verd`). Rows carry `data-sym`, `role="button"`,
   `tabindex="0"`. Empty states: `verdicts` absent → one line saying no
   verdicts are in this publish and they arrive with the next cycle;
   `by_ticker` empty → no name had enough inputs for a call this cycle.
   The header stat and as-of stamp print before any early return.
2. **Call pill on Conviction and Swing rows**, in the Name cell after the
   BULL/BEAR pill, so a flow reading that disagrees with the composite is
   visible on the flow board itself. HOLD renders as a quiet outline pill;
   no verdict renders nothing.
3. **Overview tab headline strip** (`stageVerdictHTML(sym)`, first block in
   the Overview tab body, above the 52-week range): the pill, the signed
   score, `on N of 9 inputs`, the as-of time, the diverging bar, then one row
   per input in `order` with its label, value, points contributed and note;
   null inputs dimmed with their note. A searched name outside the desk
   universe gets one line saying no desk verdict exists for it. A held call
   prints its `note` beside the pill.
4. **Watchlist rail**: a `verdict` sort (score desc, no-verdict names sink)
   with a per-row score line in that view, and a small BUY/SELL mark on the
   ticker line in every view. HOLD and no-call print nothing in other views.
5. **Honesty box → Limits**: one sentence stating the verdicts are a
   hand-weighted composite of nine readings with no backtest behind them.

Filled badges: FIRING, NEW and the verdict call are the only filled badges on
a board. The call pill uses the page's tinted-fill convention
(`--upbg` / `--dnbg` background with `--up` / `--dn` text), the same pattern
FIRING already uses, so contrast is the text token's, already measured AA in
both themes.

## Tests

- `fetcher/test_verdict.py`: every input mapping at its edges (predicted
  values, not observed), null handling per input, weights sum to 100,
  renormalization arithmetic, coverage gate (both legs), earnings gate,
  thresholds, signed-zero rounding, funds, TRACK_ONLY names, payload shape,
  determinism, `bars.json` read from disk when the cycle did not rebuild it.
- `fetcher/test_sync_constants.py`: `VERDICT_INPUT_ORDER` (fetcher) equals
  the key set of `VERDICT_INPUT_LABELS` (page).
- `tests/test_page_smoke.py`: a payload with BUY, SELL, HOLD-by-earnings and
  no-call rows renders the board at 1440 and 390 with no page error and no
  sideways scroll; the default cut shows the two calls and the note names the
  rest; "show all" reveals every row; a negative score prints U+2212; the
  Conviction row carries the pill; the rail sorts by verdict; an absent
  `verdicts` key prints the one-line reason.

## Rollout

1. `DATA_CONTRACT.md` first, then fetcher, then page.
2. `pytest fetcher` and `pytest tests`; render at 1440 and 390 against the
   real published payload with computed verdicts.
3. Merge to `main` (Pages redeploys `index.html`), then dispatch
   `refresh-loop.yml` with `force=true` so `data.json` carries `verdicts`
   tonight instead of at the next weekday cron. Fetch it back and read it.
4. Vault: `SYSTEMS.md` Desk entry, decisions-log registration, mirror resync.

## Decided without Zach — open to being overturned

- The weights, centers, spans and the ±35 thresholds.
- Three call words (BUY / HOLD / SELL) with the signed score carrying
  strength, rather than five tiers.
- The earnings gate at three days.
- Sector ETFs and leveraged wrappers get verdicts like any other name when
  they clear the coverage gate.
- The verdict pill appears on the flow-board rows (adds one badge per row).
