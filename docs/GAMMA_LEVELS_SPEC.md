# Build spec: gamma concentration levels

Status: proposed. Needs Fable's scope sign-off before any code.
Author role: Opus (traffic/spec). Builder: Sonnet.
Date: 2026-08-22. Origin: evaluation of a TikTok "3 positioning data
sources" clip. COT and prime-brokerage data were rejected in that
evaluation; dealer gamma was the one idea worth building.

## Summary

Add a display-only overlay that shows where options open interest carries
the most gamma for a pinned name. Those strikes act as price magnets and
walls near expiry. Draw them as horizontal lines on the stage chart, with a
one-line caption.

The desk already downloads everything this needs. The CBOE delayed-quotes
chain the fetcher pulls for every pinned name returns `gamma`,
`open_interest`, `delta`, and `iv` on every contract. Today the fetcher
reads only `delta` and `iv` and keeps near-money flow totals, then discards
the rest. This feature reads `gamma` and `open_interest` from the same
contracts, in the same loop, and aggregates them by strike. No new data
source. No second fetch. No new network dependency to break.

## How to read it (for the trader)

Gamma levels are price magnets. They mark the strikes where the most options
are stacked up. Near expiry, big options positions pull the stock toward
those prices and make it sticky there. Think of them as support and
resistance drawn from options positioning instead of from a chart line.

How to use them day to day:

- **The peak wall is the strongest magnet.** If the stock is drifting and no
  news is out, it tends to get pulled toward the nearest big wall and stall
  there. That is a spot to expect a pause, not a breakout.
- **Walls are where moves slow down.** A rally into a wall above often
  stalls. A sell-off into a wall below often finds a floor. They are not
  guarantees, they are the levels where options hedging pushes back.
- **The pull is strongest close to expiry.** Monday of expiry week, the walls
  matter a lot. Three weeks out, they matter less. The caption says how far
  out the expirations run.
- **Cross-check with the desk's other lines.** When a gamma wall sits right
  on a moving average or an Auto-TA support line, that level is worth more
  than either one alone.

What it does **not** tell you:

- It does not say up or down. A wall is a level, not a direction. The stock
  can sit above or below a wall.
- It does not say "expect a calm day" or "expect a wild day." That reading
  needs to know which side the big players are on, and free data cannot tell
  us that (see the next section). So the desk stays quiet on it, on purpose.
- It is a once-a-day picture. The walls are set from yesterday's settled
  positions and refresh overnight. They do not move around during the day.

One-line version: **the lines mark where the stock is likely to get stuck or
slowed. Trade toward them, expect a fight at them, and don't read a direction
into them.**

## The one hard limit, decided up front

This feature is **unsigned**. It reports where gamma is concentrated. It
does **not** claim whether dealers are long or short that gamma, and it does
**not** compute a gamma "flip" or zero-gamma level.

Why: a signed gamma-exposure number, and the flip level derived from it,
both require assuming who bought and who sold each option. This desk already
established that free CBOE data cannot make that call. See the aggressor-tilt
rule in `CLAUDE.md`: "this data cannot distinguish a bought call from a
written one (covered-call income vs. a directional bet)." A signed GEX
reading would rest on the exact assumption the desk refuses everywhere else.

So the honest, defensible reading is: "these strikes carry the most gamma;
near expiry, price tends to gravitate toward them." That is what unsigned
gamma concentration supports. The directional claim ("dealers are short,
expect a volatile day") is out of scope, on purpose. If Zach specifically
wants the signed flip level later, that is a separate change with its own
documented assumption and its own sign-off — not part of this build.

## Posture (matches the desk's existing reference-data fields)

- **Display-only. Never feeds `conviction_score` or `swing_score`.** Same
  posture as `flow_pct`, the aggressor tilt, `facts.framework`,
  `facts.op_margin`, `facts.short_pct`.
- **Neutral coloring. Magnitude, not direction.** Line weight scales with
  gamma concentration. No green/red by side. This mirrors the Bollinger
  rule: "a band cross reads volatility, never bullish or bearish."
- **A feed that fails keeps its slot.** If the chain is missing or too thin,
  gamma is `null` and the stage prints a one-line reason. It never renders a
  guessed or zeroed level.
- **The page never widens the server universe.** Pinned names only. Off-desk
  watchlist adds show "not available for off-desk names," the same way
  intraday bars already do.

## Data model

### DATA_CONTRACT.md first

Edit `DATA_CONTRACT.md` before touching code — that is the standing rule.
Add a `gamma` object under `facts.<TICKER>`, alongside `framework`.

```
facts.<TICKER>.gamma = {
  "spot":            <float>,     // spot used for the calc
  "dte_hi":          <int>,       // expiry window, in days (GAMMA_DTE_HI)
  "levels": [                     // top-K strikes by gamma concentration, desc
    {"strike": <float>, "gamma_oi": <float>, "oi": <int>, "pct": <float>},
    ...
  ],
  "peak_strike":     <float>,     // levels[0].strike, the largest wall
  "total_gamma_oi":  <float>,     // sum across the window, for the pct base
  "expiries_used":   <int>,       // disclosure count
  "contracts_used":  <int>,       // disclosure count
  "computed_from":   "cboe_delayed_chain"
}
```

`facts.<TICKER>.gamma` is `null` when the chain is absent or below the
minimum thresholds. Never partially filled.

### Definition of `gamma_oi`

Per contract, within the expiry window:

```
gamma_oi(contract) = gamma * open_interest * 100
```

`gamma` and `open_interest` come straight from the CBOE row. `100` is the
contract multiplier. This is an **unsigned** notional gamma per 1-point move,
summed by strike. It deliberately omits the `spot^2` scaling some GEX
formulas add; the ranking of strikes is identical either way, and the raw
figure stays legible. Aggregate by strike:

```
by_strike[strike] += gamma_oi(contract)      // calls and puts both add
```

Calls and puts both contribute their absolute gamma. Gamma is the same sign
for long calls and long puts, so this is not a directional mix — it is a
concentration measure.

### Expiry window and thresholds (first-pass heuristics)

Add near the other fetcher constants, and disclose them as un-backtested,
same class as `UOA_HOT_MULT` and the Auto-TA flag-pole threshold:

- `GAMMA_DTE_HI = 45` — include contracts with `0 <= dte <= 45`. Far-dated
  gamma is negligible for the pin effect. Start here; tune after live review.
- `GAMMA_TOP_K = 4` — number of strike levels to publish and draw.
- `GAMMA_MIN_CONTRACTS = 20` — below this, the chain is too thin; publish
  `null`.
- `GAMMA_MIN_OI = 0` per contract — no floor at first; revisit if noise shows
  up in live review.

## Fetcher changes (`fetcher/build_snapshot.py`)

The chain is already iterated once in the per-ticker analysis loop (the
`for opt in chain["options"]` loop that reads `delta`, `iv`, `volume`,
`open_interest`). Add gamma aggregation **inside that existing loop** — read
`opt.get("gamma")`, gate on `0 <= dte <= GAMMA_DTE_HI`, and accumulate into a
`by_strike` dict. No second pass over the 11k-contract chain.

After the loop, reduce `by_strike` to the top-K levels, compute `pct` of
`total_gamma_oi`, and attach the `gamma` object to the ticker's `facts`
entry. Guard on `contracts_used >= GAMMA_MIN_CONTRACTS`, else `null`.

Cost: near zero. MU's chain is ~11,600 contracts and the loop already visits
every one. This adds two dict reads and one accumulate per contract.

### Where it is stored

`facts.<TICKER>.gamma` in `data.json`, written the same place
`facts.framework` is written in `context.py` / `build_snapshot.py`. It is a
fresh read each cycle. Open interest only changes overnight, so the level
positions are effectively a daily snapshot; that is expected and disclosed,
not a bug. No `history.json` archiving in v1 — add later only if a
gamma-over-time view is wanted, and if so, follow the `consensus_history.json`
precedent (lives on the `data` branch, guarded by `write_history`).

## Frontend changes (`index.html`)

### Chart overlay

Draw the top-K gamma strikes as horizontal price lines on the stage chart.

- Reuse the `createPriceLine` machinery, but keep a **separate array**
  `STAGE.gammaLines`, distinct from `STAGE.srLines` (the Auto-TA S/R lines).
  Do not co-mingle the two. Clear and rebuild `STAGE.gammaLines` in
  `stageShow` alongside the existing `STAGE.srLines` reset.
- New color token `--gex`, defined in both light and dark palettes, distinct
  from `--bb` (Bollinger) and the S/R colors. Neutral hue.
- Line weight scales with `pct` — the peak wall is thickest. Label each line
  with the strike and its share, e.g. `GEX $250 (34%)`.
- Strike positions do not move intraday (open interest is settled), so
  positions are set at full render only. The **position word** in the caption
  ("nearest wall above / below spot") is re-derived on each live poke as spot
  moves — the same pattern `taSrSide` / `stageTAPoke` already use for the S/R
  lines. Do not cache "above/below" at render time.

### Caption / legend

One line under the chart, in plain words:

> Gamma walls (from open interest): $X peak, then $Y, $Z. Nearest above spot
> $A, nearest below $B. These are options-positioning magnets, not a
> direction call. From settled open interest, N expiries within 45 days, as
> of <snapshot date>.

Rules:

- Neutral phrasing. No bullish/bearish read. Position words are geometric.
- State the inputs count ("N expiries", "from settled open interest") — a
  reading says how much it had, same as the macro backdrop's "graded on 4 of
  7."
- If `facts.gamma` is `null`, print the reason ("no chain for this name" /
  "chain too thin for a gamma read"), do not hide the slot.
- Off-desk / ad-hoc watchlist names: "gamma levels are a desk-name feature,"
  the same convention as intraday bars. Do not attempt a client-side compute.

### Staleness

Age the reading against `data.session_date`, day-based, the way
`fundBuiltStaleDays()` handles the once-a-day sidecar fields. Do not reuse
the intraday `isStaleFlow` / `isStaleContext` millisecond helpers — wrong
shape for a daily snapshot.

### Tooltip parity

Whatever the caption states as a rule, `stageSourceLine`'s tooltip and any
other surface naming the gamma read must state the same thing. "One rule, one
helper, every surface."

## Tests (`fetcher/test_gamma.py`)

Pin the behavior, and exercise the **real** aggregation function, not a copy
of it — the round-6/round-7 lesson (a test that mirrors the code keeps
passing against a copy of a bug).

- Unsigned aggregation: a synthetic chain where calls and puts at one strike
  both add to that strike's `gamma_oi`.
- DTE window: a contract at `dte = 46` is excluded; at `dte = 45` included.
- Top-K selection and `pct` math against a known `total_gamma_oi`.
- Thin chain (`contracts_used < GAMMA_MIN_CONTRACTS`) returns `null`.
- Missing `gamma` field on a contract is skipped, not treated as zero-with-OI.

## Verification before shipping

- Run one live cycle. Eyeball MU and QQQ gamma walls against a public GEX
  reference for sanity of the strike locations. Expect the **strike
  locations** to line up; the sign/flip will differ because this build is
  unsigned by design — note that in the review, do not "fix" it.
- Confirm open interest is prior-day settled (CBOE serves settled OI), so the
  daily-snapshot framing is accurate.

## Open scope questions for Fable

1. **Unsigned only, confirmed?** This spec builds concentration levels, not a
   signed flip level, for the reason in "The one hard limit" above. Confirm
   that is the intended scope, or rule that the signed version is wanted with
   its assumption documented.
2. **Chart-only for v1?** Recommend yes. A rail-wide scanner panel (a
   `gammaOf(sym)` mirror of `bollingerOf(sym)`) can come later; if it does,
   follow the Bollinger dual-call-site pattern — chart overlay reads
   `STAGE.rows`-adjacent state, rail reads a per-sym helper, both share one
   set of constants.
3. **Universe.** The feature covers whatever is in `PINNED` — that already
   includes QQQ and the 11 SPDR sector ETFs (index and sector gamma, the
   classic use) plus the single names. Confirm SPY is pinned, or add it, if
   index gamma is a priority.
