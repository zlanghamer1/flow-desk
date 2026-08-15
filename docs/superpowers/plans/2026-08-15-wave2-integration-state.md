# Wave-2 integration state (2026-08-15 — INTEGRATED)

Wave 2 is built, seam-tested, and integrated. Both Sonnet builders finished
(fetcher: 121 tests green; page: 4 fixture passes green). The architect then
closed the cross-agent seams before shipping:

## Seams found and closed at integration (architect, this session)
1. **fund/{SYM}.json shape mismatch** — the page was written against an
   internal shape (`short_pct`, `eps_actual`/`eps_estimate`, nested
   `growth{quarterly,annual}` with `labels`) while DATA_CONTRACT.md (the
   authority) ships `short_pct_float`, `eps`/`eps_est`, top-level
   `quarterly`/`annual` with `periods`. Fixed page-side with
   `normalizeFund()` at the fetch boundary (same pattern as
   normalizeBrief/normalizePositions), tolerant of both shapes.
   Verified with a Playwright pass driving the modal off a REAL live-built
   NVDA sidecar (fwd P/E 22.6, short 1.3%, 12-quarter + 4-year growth
   charts, E-badge popover EPS 1.87 vs 1.77 +5.54%, backdrop close) — all
   green, zero non-network console errors.
2. **E-badges sat on fiscal quarter-end, not report date** — added
   `report_date` (Yahoo `reportedDate`) to the contract + fetcher rows;
   page anchors chart E-badges on `report_date || date` and the popover
   says "Reported <date>". Pinned in the fetcher test suite (still 121).
3. **CLAUDE.md guardrail refresh** — NRGU/WTI removed from the
   "deliberately-excluded" list (reinstated by Zach's full TV-list ruling);
   the exclusion note in build_snapshot.py documents both cases.

## Remaining steps (if this session dies mid-close)
1. Commit all + push branch `claude/trading-dashboard-plan-6okdac`,
   ff-merge to main, push main (deploys page via pages.yml).
2. Forced cycle: github MCP `actions_run_trigger` refresh-loop.yml ref=main
   inputs {"force":true}; poll
   raw.githubusercontent.com/zlanghamer1/flow-desk/data/ for
   data.json facts.SMCI, bars.json v2 quads, fund/NVDA.json.
3. Curl live page for wave-2 markers (candleChartSVG, LEVERAGED,
   normalizeFund). Final report to Zach (include: tab "(n)" = hot-mover
   count; MRVL short % now resolves 4.103% via stockanalysis.com).

## Zach-side open items (remind at close)
- Secrets still pending: `VAULT_READ_TOKEN` (flow-desk) + `DESK_PASSPHRASE`
  (ClaudeVault) — brief panel + Position Guard light up when set.
- Brief panel goes live Monday 6:23 CT automatically (vault side shipped).
- Fast-follows on file: Overnight Asia panel, watchlist diff-nag option,
  .ics export + phone manifest, brief-email retirement after a proving week.

## Standing cautions
- data branch: loop force-push only. Pages stays branch-mode. None ≠ 0.
- BOARD_CAP 80; TRACK_ONLY = {SKHX, NRGU, OILU, STLL, AAOG} enforced in
  select_candidates() only.
