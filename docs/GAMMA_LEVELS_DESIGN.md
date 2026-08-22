# Design ruling: gamma concentration levels

## VERDICT: APPROVED WITH CHANGES

Fable, architect. 2026-08-22. Spec reviewed against the live code on branch
`claude/tiktok-desk-evaluation-gf8a2g`. The spec is sound in intent and in
its hard limit. Four corrections were required before build; they are folded
into this design. Sonnet builds from THIS document, not from the spec, where
the two disagree.

Changes from the spec (summary):

1. **The facts wiring path in the spec is wrong.** `facts.<TICKER>` is built
   in `context.py` from TradingView scanner rows; the gamma numbers come from
   the CBOE chain in `build_snapshot.analyze_ticker`, a different module and
   a different loop. The merge point is `run_cycle`, after
   `context.build_context` returns. Exact wiring below.
2. **Omitted vs. null was underspecified.** The spec said "null when the
   chain is absent." Corrected to mirror `framework`'s convention: the key is
   OMITTED when no chain was analyzed, `null` when a chain was analyzed but
   failed the thresholds. The frontend distinguishes the two.
3. **SPY is NOT pinned** — the spec's question 3 implied it might be.
   Confirmed absent from `PINNED`. Ruling below: do not add it in this build.
4. **Snapshot `spot` can be null** (`fetch_chain` can return `spot: None`).
   The aggregation does not need spot, so a null spot does not null the gamma
   object; the frontend's position words come from the live price anyway.

## Scope rulings (the three open questions)

**(a) Unsigned only. CONFIRMED — signed flip level is OUT.**
Reason: a signed GEX and its flip level require assuming who bought and who
sold each contract, the exact assumption this desk's aggressor-tilt guardrail
already rules free CBOE data cannot support ("this data cannot distinguish a
bought call from a written one"). A signed version, if Zach ever asks, is a
separate spec with its own documented assumption and its own sign-off.

**(b) Chart-only for v1. CONFIRMED — no `gammaOf(sym)` rail scanner.**
Reason: unlike Bollinger, the rail scanner would add no new information — the
levels are once-a-day per-ticker values already sitting in `facts`, not a
recomputation over bars — so the rail version is pure UI that can wait for a
live-review verdict on whether the chart lines earn their keep. If it comes
later, follow the Bollinger dual-call-site pattern (shared constants, two
readers).

**(c) Universe: PINNED as-is. SPY is NOT added.**
Verified in `fetcher/build_snapshot.py`: `PINNED = WATCHLIST + SECTOR_ETFS`
(line ~411). QQQ is in `WATCHLIST` (Zach's 2026-07-17 add) and all 11 SPDR
sector ETFs are in `SECTOR_ETFS`, so index and sector gamma are covered.
SPY exists only on the page's main tape / heatmap; it has never been in the
options universe. Reason for not adding it: the curated universe is Zach's
fixed watch by explicit ruling (2026-07-17, re-ruled 2026-08-15) — an agent
does not widen it to serve a feature. QQQ already gives the index-gamma read.
Flag to Zach in the delivery note: "SPY gamma would need SPY pinned — one
word from you adds it," and stop there. TRACK_ONLY names (NRGU, OILU, STLL,
SKHX, AAOG) never reach a chain fetch, so they simply never carry a `gamma`
key — that is the existing mechanism, no new code.

## Guardrail audit of the spec

- Display-only, never feeds `conviction_score`/`swing_score`: spec complies.
  This design adds the enforcement point: the gamma object is attached in
  `run_cycle` AFTER both boards are already built, so it is structurally
  unable to feed a score. Keep it that way.
- Unsigned + neutral coloring: spec complies (mirrors the Bollinger
  "volatility, never bullish/bearish" rule). `--gex` is one neutral hue for
  every line; weight, not color, carries magnitude.
- DATA_CONTRACT.md first: spec states it; this design fixes the exact text
  (below). The FETCHER unit's first commit touches DATA_CONTRACT.md.
- "A feed that fails keeps its slot": spec complies; exact reason strings
  fixed below so the two units cannot drift.
- Pinned-only universe: spec complies; no client-side gamma compute for
  ad-hoc names, ever (the page has no chain source and must not grow one).
- Constants disclosed as un-backtested heuristics: required — `GAMMA_DTE_HI`,
  `GAMMA_TOP_K`, `GAMMA_MIN_CONTRACTS` carry a comment naming them first-pass
  heuristics, same disclosure class as `UOA_HOT_MULT` / `TA_FLAG_MIN_BARS`.
- Tests exercise the real function: the spec's `test_gamma.py` is kept, with
  the binding rule that tests call `analyze_ticker` itself with synthetic
  chains and read `result["gamma"]` — never a copied-out aggregation loop
  (the round-6/round-7 lesson, twice burned).
- One rule, one helper, every surface: the frontend's nearest-wall
  above/below words and the line labels come from ONE function
  (`gexSide`-equivalent, named below), the `taSrSide` pattern.

## Data contract (FIXED interface — both units build against this verbatim)

Add to `DATA_CONTRACT.md`'s `facts.<TICKER>` block, after `framework`:

```
// ── Gamma concentration levels (added 2026-08-22) — UNSIGNED options-
// positioning walls from the same CBOE delayed chain the flow numbers read.
// Computed in build_snapshot.analyze_ticker, merged into facts by run_cycle.
// KEY OMITTED (not present, not null) when no chain was analyzed this cycle
// (TRACK_ONLY name, chain fetch failed, no quote). Present as null when a
// chain WAS analyzed but had fewer than GAMMA_MIN_CONTRACTS usable contracts
// in the DTE window. Never partially filled. Display-only reference — never
// a scoring input.
"gamma": {
  "spot": 112.34,              // chain's own spot at compute time; null if
                               // CBOE served no usable price (levels stand)
  "dte_hi": 45,                // the GAMMA_DTE_HI window used, disclosure
  "levels": [                  // top GAMMA_TOP_K strikes by gamma_oi, DESC;
                               // may hold fewer than K when the chain has
                               // fewer distinct strikes with gamma
    {"strike": 115.0,          // OCC strike, $
     "gamma_oi": 1234567.8,    // sum(|gamma| * open_interest * 100) at strike
     "oi": 45210,              // total open interest summed at strike (int)
     "pct": 34.2},             // gamma_oi / total_gamma_oi * 100, 1dp
    ...
  ],
  "peak_strike": 115.0,        // levels[0].strike
  "total_gamma_oi": 3609846.2, // window-wide sum, the pct denominator
  "expiries_used": 7,          // distinct expiries contributing (int)
  "contracts_used": 2841,      // contracts that carried a usable gamma (int)
  "computed_from": "cboe_delayed_chain"   // fixed literal
}
```

Null-behavior table (normative):

| Situation | Value |
|---|---|
| TRACK_ONLY / chain fetch failed / no quote | key OMITTED |
| chain analyzed, `contracts_used < GAMMA_MIN_CONTRACTS` | `null` |
| chain analyzed, thresholds met, spot missing | object with `"spot": null` |
| a contract with missing/non-numeric `gamma` | contract skipped; not in `contracts_used` |
| a contract with `open_interest` 0 or missing | contributes 0; still counts in `contracts_used` if gamma present |
| strike whose summed `gamma_oi` is 0 | excluded from `levels` |
| `context.build_context` raised (no `facts` key at all) | gamma absent with it — fail-soft, no new top-level key |

Definition (normative): per contract in `0 <= dte <= GAMMA_DTE_HI`,
`gamma_oi = abs(gamma) * open_interest * 100`, accumulated per strike, calls
and puts both adding. `abs()` is belt-and-suspenders — long-option gamma is
positive for both sides, but a vendor sign quirk must not subtract. No
`spot^2` scaling (ranking is identical, raw figure stays legible — spec's
reasoning, accepted).

Constants (in `build_snapshot.py`'s constants block, near `UOA_HOT_MULT`,
each commented as a first-pass, NOT-backtested heuristic):

- `GAMMA_DTE_HI = 45`
- `GAMMA_TOP_K = 4`
- `GAMMA_MIN_CONTRACTS = 20`
- No per-contract OI floor in v1 (revisit on live review; do not add the
  constant until it has a value that does something).

No `history.json` archiving in v1 — accepted as specced. If a gamma-over-time
view is ever wanted, follow the `consensus_history.json` precedent.

## WORK UNIT 1 — FETCHER (Sonnet A)

Files: `DATA_CONTRACT.md`, `fetcher/build_snapshot.py`,
`fetcher/test_gamma.py` (new). Nothing else.

Order of work: DATA_CONTRACT.md first (paste the contract block above),
then code, then tests.

1. **Constants** — add the three `GAMMA_*` constants to the constants block
   (around the `UOA_HOT_MULT` region, ~line 209), with the heuristic
   disclosure comment.
2. **`analyze_ticker`** (~lines 745–998):
   - Init before the loop: `gamma_by_strike: dict[float, dict] = {}` and
     `gamma_contracts = 0`, `gamma_expiries: set[str] = set()`.
   - Inside the existing `for opt in chain["options"]` loop, after the
     `vol/oi/last/delta/iv` reads (~line 790): read
     `g = _num(opt.get("gamma"))`; if `g is not None and 0 <= dte <= GAMMA_DTE_HI`,
     accumulate `abs(g) * oi * 100.0` and `oi` into `gamma_by_strike[strike]`,
     increment `gamma_contracts`, add `yymmdd` to `gamma_expiries`. One pass,
     no second loop over the chain.
   - After the loop, next to the other reductions (~line 960): if
     `gamma_contracts >= GAMMA_MIN_CONTRACTS` and the window-wide total > 0,
     build the object exactly per the contract (levels sorted desc by
     `gamma_oi`, top `GAMMA_TOP_K`, zero-gamma strikes excluded, `pct`
     rounded 1dp, `oi` int, `spot` = `chain["spot"]` which may be None);
     else the value is `None`. Add `"gamma": <object-or-None>` to the return
     dict.
3. **`run_cycle` wiring**:
   - In the chain loop (~line 1491, right after `analysis = analyze_ticker(...)`):
     collect `gamma_by_ticker[ticker] = analysis["gamma"]` into a dict
     initialized next to `big_orders_pool` (~line 1474).
   - After the `context.build_context` try/except (~line 1880), before the
     `data = {...}` assembly: merge —
     ```python
     _facts = context_fields.get("facts")
     if isinstance(_facts, dict):
         for _t, _g in gamma_by_ticker.items():
             if _t in _facts:
                 _facts[_t]["gamma"] = _g
     ```
     A ticker with a chain but no facts entry gets nothing (fail-soft); a
     cycle where context raised carries no gamma (fail-soft, no new key).
     This point is AFTER both boards are built — gamma cannot feed a score.
4. **`fetcher/test_gamma.py`** (new) — every test builds a synthetic
   `chain = {"spot": ..., "iv30": None, "options": [...]}` with hand-built
   OCC symbols and calls the REAL `build_snapshot.analyze_ticker(ticker,
   chain, session_date)`, asserting on `result["gamma"]`. No copied
   aggregation logic anywhere in the test file. Cases (all from the spec,
   plus the corrections):
   - call + put at one strike both add to that strike's `gamma_oi` (unsigned);
   - a negative vendor `gamma` adds its absolute value;
   - `dte = 45` included, `dte = 46` excluded (boundary both sides);
   - top-K selection order and `pct` math against a known total;
   - fewer than `GAMMA_MIN_CONTRACTS` usable contracts -> `gamma is None`;
   - a contract with `gamma` missing is skipped and does NOT count toward
     `contracts_used`;
   - `oi` missing/0 with gamma present: counts as a contract, contributes 0;
   - `spot: None` chain still produces a full object with `"spot": None`;
   - `expiries_used` counts distinct expiries, `contracts_used` counts
     contracts.

Acceptance:
- `cd fetcher && python -m pytest test_gamma.py -q` green.
- Full suite green: `python -m pytest -q` in `fetcher/` (no regression in
  the six existing test files).
- One live sanity probe (builder runs it, records output in the PR body,
  does NOT commit data): fetch one real chain (MU) and confirm the CBOE rows
  actually carry a numeric `gamma` field — the spec asserts this; verify it,
  don't assume it. If CBOE does not serve `gamma`, STOP and report; the
  whole feature rests on that field.
- `data.json` shape check: build a dry snapshot and confirm `facts.MU.gamma`
  matches the contract, `facts.NRGU` (TRACK_ONLY) has NO gamma key.

## WORK UNIT 2 — FRONTEND (Sonnet B)

Files: `index.html` only.

1. **`--gex` token** — one neutral hue (distinct from `--bb` purple and the
   S/R up/dn colors; a teal/cyan family works against both palettes), defined
   in ALL FOUR palette blocks where `--bb` appears today (lines ~21, ~40,
   ~52, ~63: dark root, light `prefers-color-scheme` override, and both
   explicit `data-theme` blocks). Add a matching `--gexbg` if a pill/legend
   chip needs it. Never define it in only one block.
2. **State + reset** — `STAGE.gammaLines = []`, a separate array from
   `STAGE.srLines`, never co-mingled. Clear it in `stageTAClear()` (remove
   each price line from `STAGE.s.candle`, same try/catch pattern as srLines,
   ~line 7868) and rely on `stageShow`'s existing reset path calling through
   the same clear — verify the previous symbol's gamma lines cannot survive a
   symbol switch (the 2026-08-20 "a view that changes symbol clears its data
   first" rule).
3. **Draw** — in `stageTA()` (or a `stageGamma()` called immediately after
   it from the same call sites), read `factsOf(STAGE.sym)?.gamma`. Draw each
   level via `STAGE.s.candle.createPriceLine`, color `cssVar("--gex")`,
   `lineWidth` scaled by `pct` (peak thickest, e.g. 1–3), label
   `GEX $<strike> (<pct>%)`, `axisLabelVisible` on the peak only (the axis
   is already contested by the S/R badge — one gamma badge max). Push
   `{level, line}` onto `STAGE.gammaLines`. Levels do not move intraday —
   positions set at full render only.
4. **One side function** — `gexSide(strike, lastPx)` (the `taSrSide`
   pattern): returns above/below/at. It is the ONLY source for the caption's
   "nearest wall above/below spot" words, re-derived in `stageTAPoke()` on
   every live poke from the live close — never cached at render. Coloring
   stays neutral `--gex` regardless of side (magnitude, not direction); only
   the words move.
5. **Caption** — one line in the TA legend area (`stageTALegend` region /
   `#staget`), plain words per the spec's template: peak and next walls,
   nearest above/below the LIVE price, "options-positioning magnets, not a
   direction call," "from settled open interest, N expiries within
   <dte_hi> days, as of <data.session_date>." Counts come from
   `expiries_used`; never invent them.
6. **Failure slots** (exact reason strings, shared with the tooltip):
   - key omitted on a desk name: "no options chain read for this name this
     cycle" (TRACK_ONLY names land here);
   - `gamma === null`: "chain too thin for a gamma read";
   - off-desk / ad-hoc name (`!STATE.data?.facts?.[sym]` and not pinned):
     "gamma levels are a desk-name feature" — same convention as intraday
     bars. No client-side compute, ever.
   The slot always renders one of these lines; it never disappears.
7. **Staleness** — day-based, against `data.session_date` (the
   `fundBuiltStaleDays` shape, ~line 1874 — a DAY comparison, not the
   millisecond `isStaleFlow`/`isStaleContext` helpers). Print the "as of"
   unconditionally; add a STALE tag when `session_date` is behind the
   current trading day. The OI vintage line ("from settled open interest")
   prints always — it is a property of the data, not a staleness state.
8. **Tooltip parity** — `stageSourceLine` (~line 9706) gains one clause
   naming the gamma read's source and vintage, using the same strings as
   the caption. One rule, one helper, every surface.

Acceptance:
- Open MU: gamma lines draw in `--gex`, peak thickest, caption prints, the
  above/below words flip as the live price crosses a level (simulate by
  editing `STAGE.rows`' last close in devtools and calling `stageTAPoke()`).
- Switch MU -> LLY mid-flight: no MU gamma line survives.
- Open NRGU (TRACK_ONLY): "no options chain read" line, slot kept.
- Add an ad-hoc name via search: "desk-name feature" line, slot kept.
- Hand-edit a local `data.json` to `gamma: null`: "chain too thin" line.
- Both themes (explicit toggle AND OS `prefers-color-scheme`) show the
  token; check contrast of the label against both chart backgrounds.
- No page JS re-derives any fetcher threshold (the standing rule): the page
  reads `dte_hi` from the payload for its caption, never hardcodes 45.

## Unit independence

The contract block above is the full interface. Unit 1 never touches
`index.html`; Unit 2 never touches the fetcher and can build against a
hand-written `data.json` fixture matching the contract. The two land as one
PR or two stacked commits on the gamma branch — fetcher first, so the live
`data.json` carries the field before the page reads it (the page tolerates
its absence either way via the omitted-key path).

## Merge sequencing (binding)

Another session is rebuilding this desk right now, editing
`build_snapshot.py` and `index.html`. Do NOT merge gamma into that moving
base, and do not have the rebuild rebase onto gamma.

1. Gamma work proceeds on `claude/tiktok-desk-evaluation-gf8a2g` (or a child
   branch) against the base it forked from. No merges to `main` from this
   branch while the rebuild is in flight.
2. The rebuild session finishes and lands on `main` first. It has priority —
   it is fixing live findings; gamma is a new feature.
3. THEN: `git rebase main` the gamma branch onto the finished rebuild.
   Expected conflict surface: `analyze_ticker`'s return dict and `run_cycle`
   (small, mechanical) and `index.html`'s stageTA/stageTAPoke/stageTAClear
   region (larger — re-read those functions after rebase, since the rebuild
   may have restructured them; re-verify insertion points rather than
   force-applying old hunks). The gamma branch owns all conflict resolution.
4. Re-run the full fetcher test suite and the frontend acceptance list AFTER
   the rebase, then merge to `main` per the standing merge rule.
5. If the rebuild has not landed within a reasonable window, gamma waits.
   The base does not move under a feature branch twice.

## Delivery note to Zach (for the parent session)

One plain-English paragraph: what the lines mean (the spec's "How to read
it" is good — keep its voice), that they are unsigned by design, and the
one open question: "Want SPY added to the desk universe so it gets gamma
walls too? QQQ covers the index read today."
