# 2026-09-02 — UX-laws audit and redesign

Zach's ask: evaluate the Desk against the "20 UX laws" cheat sheet (Hick,
Fitts, Jakob, Miller, aesthetic-usability, Pareto, Occam, Parkinson, Postel,
peak-end, Von Restorff, Zeigarnik, Tesler, Doherty, goal-gradient,
proximity, similarity, closure, common region, uniform connectedness), build
a redesign that implements them, and have adversarial agents scrutinize it.

Scope: display layer only. No score, weight, payload field, universe, or
disclosure changed. Every standing ruling in CLAUDE.md holds (chart front
and center, boards open on the score-60 shortlist, BB-only chart default,
dynamic disclosures never behind a button, attribution kept, price
disclosures in the chart header).

## How the audit was done

The live page (main `66cbd07`) was rendered in headless Chromium against the
live `data` branch at 1440, 1920 and 390 px, dark and light. Measurements
came from the DOM, not from reading the code:

| Measurement (live, before) | 1440 px | 390 px |
|---|---|---|
| Page height | 4,647 px | 17,977 px |
| Horizontal overflow | none | content 592 px wide in a 390 px screen |
| Buttons | 48 | 48 |
| Tooltip targets (dotted underlines) | 376 | 376 |
| Tab stops | 311 | 307 |
| Words under 9.5 px (icon glyphs excepted) | 67 weekday labels at 8.5 px, plus every eyebrow, group header and chip at 9 px | same |
| Swing board row height | ~58 px | ~181 px (a 15-line cell) |
| Conviction board width vs its column | 856 px table in an 818 px column: last header cut mid-word | 674 px table, scroll-only |

## Law-by-law findings and what changed

| # | Law | Finding on the live page | Change |
|---|---|---|---|
| 1 | Hick | The chart toolbar is 17 same-looking buttons in one run (5 intervals, 4 windows, 6 overlays, log). The watchlist sort is 6 equal buttons plus edit on two lines. | Toolbar split into three labeled groups (interval / range / overlays). Watchlist sort is one native select plus edit, with the current sort explained in one line under it. Visible choices fall from 7 to 2; the tab-stop count rises by 3 because the new Bollinger rows are keyboard targets (a Miller-vs-Hick trade the page's own ticker-mention rule decides). |
| 2 | Fitts | Toolbar buttons ~20 px tall, 10.5 px type; tab buttons 10 px; filter buttons 10 px. | Toolbar buttons 26 px min height, 11 px type; tabs 11 px with 8/12 padding; filter buttons 24 px min height; section headers 36 px min height. |
| 3 | Jakob | Mostly conventional (TradingView-style stage, ⌘K palette, collapsible sections). Sort-as-buttons is not the convention for six options. | Sort became a `<select>`, the pattern every reader already knows. |
| 4 | Miller | Bollinger alerts render as one bold purple paragraph of nine tickers. Swing shows 32 equal rows with a filled pill on every one. | Alerts are a one-ticker-per-line list with a reason short enough for the 248 px rail (“touched, back inside”); the full sentence is the row's tooltip. Direction pills went to outline so only FIRING / NEW are filled (also #11). Board row count is unchanged: the score-60 shortlist is a standing ruling. |
| 5 | Aesthetic-usability | 114 text elements at 9–10 px on the desktop screen; eyebrows 9 px; 67 weekday labels at 8.5 px. | Type floor raised: eyebrows 10.5, section titles 11.5, table headers 10.5, chips 9.5–10.5, notes 10.5, weekday labels 9.5. Nothing that is a word sits under 9.5 px; the ◆ ticker separators and ▼ carets are icons and stay. |
| 6 | Pareto | The verdict, chart, alerts and top conviction rows are the 20%; they were already first. Not a failure. | Quick read under the chart gets its own box so it reads as a headline, not a footnote. |
| 7 | Occam | Three stacked explanation layers under the chart (quick read, chart notes, three overview footnotes). Already collapsed by the 2026-08-26 declutter ruling. | No change beyond typography. Kept as-is on purpose. |
| 8 | Parkinson | Boards default to the shortlist; catalysts default to HIGH. Already constrained. | None. |
| 9 | Postel | Search accepts any US ticker or company name; the palette accepts actions. Already liberal. | None. |
| 10 | Peak-end | The page ends on a 10.5 px legal paragraph. | Honesty box is a three-column reference (Freshness / Sources / Limits) at 11.5 px. Every sentence is kept; none is weakened. |
| 11 | Von Restorff | 376 dotted underlines, a filled BULL pill on 23 of 32 swing rows, and FIRING / E / since-flagged / NEW chips all compete. Nothing stands out. | Underlines inside table cells, quick reads and footnotes appear only on row hover/focus; headers and chips keep them. BULL/BEAR pills are outlined; FIRING and NEW stay filled and are now the only filled badges on a board. |
| 12 | Zeigarnik | "as of 13:24 CT" gives no sense of age; loading is a bare word. | As-of chips add "· 3 min ago", re-rendered every 30 s, never wrapping inside the chip. Loading shows a moving bar (chart) or shimmer rows (boards). Accepted: after hours the chip reads "18 h ago" beside the CLOSED lamp; that is the true age. |
| 13 | Tesler | Terms like OI-CONFIRM and CHURN carry tooltips already. The complexity is real. | None. |
| 14 | Doherty | Toggles and sorts respond instantly; cold load waits behind text-only messages. | Motion during waits (see #12). |
| 15 | Goal-gradient | The 5-metric framework prints "0 pass · 0 fail · 5 building" as text. | A five-segment strip (green / red / ringed gray / hatched) above the rows. The ring is there because a flat gray segment measured 1.13:1 against its panel. |
| 16 | Proximity | The toolbar's four groups sit 8 px apart with no labels. | 12 px gaps plus a label on each group; a group wraps rather than clips on a phone. |
| 17 | Similarity | Radio buttons (interval, range) and independent toggles (overlays) look identical. Dotted underlines mean both "tooltip" and "link". | Toggles render with a small square that fills when on (the checkbox convention; a circle would borrow the radio one and the page already uses dots for flows and the market lamp); radios keep the filled style. |
| 18 | Closure | At 1440 px the Conviction table (856 px) overran its 818 px column and cut its "Loudest contract" header mid-word at the column edge; on a phone the swing rows were 181 px tall because the last cell wrapped inside 77 px. | The live price moves to its own line under the ticker, so the table (674 px) fits the column. On phones the last cell keeps a 26ch floor and the board scrolls inside its own container. |
| 19 | Common region | The quick read, tabs and footnotes under the chart ran together. | Quick read boxed (see #6). Honesty box in three bordered columns. |
| 20 | Uniform connectedness | A focused ticker highlights its rail row and board rows, but not its tape tile. | Tape tile carries the same accent stripe. |

## Considered and not done

- A score-band ladder under each board (goal-gradient): a genuine idea, but a
  new visualization mid-redesign reopens review surface; deferred.
- Cutting the swing board below the score-60 shortlist: that shortlist is a
  ruling (2026-08-18), not a default to tune.
- Hiding the "Loudest contract" column on phones: the 2026-08-22 review put it
  back on purpose; it stays, and scrolls.

## Adversarial review

Five independent reviewers (UX-laws compliance, standing rulings and
regressions, responsive layout and accessibility, code correctness, and a
plain-language reader standing in for Zach's bar) each drove the redesigned
page in Chromium against the live payload and reported only what they
reproduced. Their findings and what happened to each are listed in the
"Results" section below.

## Results (adversarial review closed 2026-09-02)

Anchored score per the repo's 2026-08-26 ruling (100 − 25/blocker − 10/major − 3/minor over CONFIRMED findings, counted after the fix pass): every confirmed finding was fixed the same day or accepted with a written reason, so the redesign ships with **0 open blockers, 0 open majors**. Raw intake before fixes: 1 blocker, 10 majors, 16 minors (27 findings across six agents).

| Lens | Findings | Fixed | Accepted / refuted |
|---|---|---|---|
| Code correctness | 7 | 6 | 1 |
| Plain-language reader | 8 | 6 | 2 |
| Standing rulings | 3 | 2 | 1 |
| UX-laws compliance | 5 | 3 | 2 |
| Responsive and accessibility | 3 | 2 | 1 |
| Verifier (new) | 1 | 1 | 0 |

| # | Severity | Finding | Outcome |
|---|---|---|---|
| ux-1 | blocker | Overlays toolbar group clips the GEX toggle off-screen on phone, unreachable by scroll | **fixed** — At 390px the GEX button's right edge is 73px; the group wraps to a second row. |
| a11y-1 | major | #wlsel loses keyboard focus after an arrow-key sort change | **fixed** — Focus restored to the rebuilt select after an arrow-key sort change; the rail still re-renders. |
| code-1 | major | Watchlist sort <select> is destroyed and closed by the 30-second live-price poll | **fixed** — Sort box node unchanged across a repeat renderWL with the same sort key. |
| code-2 | major | BBCrosses '+N more' span looks identical to a real ticker row but is dead on click and unreachable by keyboard | **fixed** — '+N more' is a plain status line: no tab stop, no pointer cursor, click does nothing. |
| reader-1 | major | Bollinger list wraps its own worked example at the rail's real width | **fixed** — Plain rows fit one line (22px). A NEW row is two deliberate lines: ticker + NEW, then the reason indented under the reason column (46px), re-measured with production markup. |
| reader-2 | major | Six contextual sort tooltips collapsed into one 301-char tooltip; options carry none | **fixed** — Short tooltip on the select; the current sort's meaning prints in one line under it. |
| reader-3 | major | 5-metric framework strip is near-invisible in the common all-building state | **fixed** — Building segments carry an ink-colored ring. |
| reader-4 | major | Age-words chip line-wraps inside its own border on crowded board headers | **fixed** — Chip measured 17px tall, one line, at 1440px with live data. |
| ux-2 | major | Total tab stops increased 311→314 (desk) and 307→310 (phone) after the simplification | **accepted-ok** — Tab stops 307→310 on a phone, 311→315 on desktop; visible sort choices 7→2. Bollinger rows are keyboard targets by the page's own ticker-mention rule. |
| ux-3 | major | Type-floor claim leaves the smallest text (8px ×48, 8.5px ×67 — .ct .dt .w weekday labels) untouched | **fixed** — Weekday labels 9.5px, group headers 10px; the 8.5px cluster (67 elements) is gone. Icon-glyph exception now written into CLAUDE.md. |
| a11y-2 | minor | Overlays toolbar group wraps to its own row at 1440px but not at 1160/1280px | **accepted-ok** — Below 1380px the right rail drops under the grid, so the middle column is wider at 1280 than at 1440; the group wraps cleanly. |
| a11y-3 | minor | .pill.b/.pill.s outline stroke under 3:1 non-text contrast in 3 of 4 theme pairs | **fixed** — 72% mix measures 3.6:1 to 5.3:1 against both surfaces in both themes. |
| code-3 | minor | ageWordsHTML future-stamp guard (sec < -120) blanks the age chip when the viewer's clock is 5 minutes fast | **fixed** — A stamp up to 15 minutes ahead of the viewer's clock reads 'just now'. |
| code-4 | minor | CT wall-clock stamps carry a bounded ±1h age error across a DST transition day | **accepted-ok** — One-hour error on a DST night, documented in CLAUDE.md. |
| code-5 | minor | #stagerecap b.u{border-left-color} is dead CSS | **fixed** — Lean color now set on the quick-read box itself via :has(). |
| code-6 | minor | New .pill.b/.pill.s outline has no color-mix() fallback | **fixed** — Plain box-shadow declared before the color-mix line. |
| code-7 | minor | .wlsel has two (pointer:coarse) min-height rules (26px then 28px) | **fixed** — Duplicate coarse-pointer rule removed. |
| reader-5 | minor | Age words show up to 24h with no tie to market-closed state, then vanish abruptly | **accepted-ok** — The age is true and the OPEN/CLOSED lamp sits in the top bar. |
| reader-6 | minor | Visible toolbar labels 'bars'/'window' are less clear than the aria-labels 'Chart interval'/'Chart range' | **fixed** — Labels read interval / range / overlays. |
| reader-7 | minor | Toggle dot reuses a 7px circle glyph already meaning two other things, and borrows radio semantics for a multi-select group | **fixed** — Toggle glyph is an 8px square. |
| reader-8 | minor | Honesty box's Sources column restates Freshness facts | **accepted-ok** — The remaining overlap is one sentence that names the scanner as a source and its cadence in the same breath; disclosure sentences are kept verbatim, not re-edited. |
| rulings-1 | minor | Quick-read box's bullish/bearish left-accent color never renders (dead CSS, same as code-5) | **fixed** — Same fix as code-5. |
| rulings-2 | minor | Orphaned watchlist sort [data-ws] click handler left after the select migration | **fixed** — No [data-ws] element or handler remains. |
| ux-4 | minor | Audit's 'Loudest contract header clipped at 1440px' claim does not reproduce against the viewport | **refuted-ok** — Before: 843px table in an 818px column, header cut at the column edge (1067px), not the viewport. Audit wording made precise. |
| ux-5 | minor | .expbtn misses the 24px touch-target floor under pointer:coarse (23px measured) | **fixed** — Expander buttons 26px tall under a coarse pointer. |
| verify-1 | minor | CLAUDE.md's type-floor claim contradicted by three still-live 8px icon-glyph rules | **fixed** — CLAUDE.md's type-floor rule now names the icon-glyph exceptions (◆ separators, ▼ arrows and carets). |
| rulings-3 | info | .dvg mobile 70px rule unreachable — pre-existing, not this diff | **accepted-ok** — Pre-existing dead rule, unrelated to this change. |

Verification harness: headless Chromium against the live `data` branch through a urllib relay (the sandbox proxy resets browser TLS), at 390/640/768/900/1024/1160/1280/1440/1920 px, dark and light. Fetcher suite: 337 passed after the final patch.
