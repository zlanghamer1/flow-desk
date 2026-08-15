# Wave-2 integration state (2026-08-15, session handoff note)

**Live site:** The Desk is deployed and verified at zlanghamer1.github.io/flow-desk
(commit c1fb813 on main). Vault side shipped (brief_summary.json + desk_private
blob on real sends). This doc is the handoff for the IN-FLIGHT wave 2.

## In flight: two Sonnet builders editing this repo's working tree (do NOT commit their files mid-build)
1. **Fetcher wave-2** — finishes the TV-list sync per Zach's FINAL ruling
   (leveraged INCLUDED — supersedes the interrupted draft's "minus all
   leveraged" comment sitting in the dirty build_snapshot.py); adds
   `TRACK_ONLY = {SKHX, NRGU, OILU, STLL, AAOG}` (quotes/facts/bars/rail yes,
   CBOE chains never — SKHX ghost-liquidity ruling 2026-07-25); WTI = W&T
   Offshore equity (his TV list has it; crude stays the tape tile); IFNNY/IFNN
   stays out (delisted); META/AMD/CVX dropped (off his updated lists);
   bars.json v2 `[o,h,l,c]` quads; facts gains TV fundamentals (verified live:
   price_earnings_ttm, price_earnings_growth_ttm, net/gross/operating/fcf
   margins, debt_to_equity, return_on_equity, price_sales_ratio,
   price_book_ratio, enterprise_value_ebitda_ttm, dividends_yield_current,
   price_target_average, recommendation_mark); per-symbol `fund/{SYM}.json`
   daily sidecars (earnings history w/ actual-vs-estimate + surprises,
   next_earnings, quarterly/annual revenue+EPS, short % float, forward P/E)
   sourced from **stockanalysis.com JSON (verified working mid-build**: NVDA
   fwd P/E 22.59, PEG 0.51, margins, next earnings Aug 26 2026 AMC, quarterly
   + annual income statements all resolved live**)**.
2. **Page wave-2** — LEVERAGED rail group (SOXL SOXS MUU RAM SKHX STLL AAOG
   NRGU OILU) + WTI in watchlist group + new wlnote; candlesticks (v2 quads,
   v1 line fallback); Finviz-style large modal (~1280×90vh, backdrop-click +
   Esc close, date/price axes, SMA20/50/200 — **200d amber**, MA value labels,
   clickable E earnings markers → actual-vs-estimate cards, upcoming-E hollow
   marker, catalyst markers/list, fundamentals grid w/ extended buyer's-lens
   coloring (PEG ≤1 green ≥2 red; net margin ≥20 green <0 red; Debt/Eq ≤0.5
   green ≥2 red; target vs price ≥+15% green), quarterly+annual revenue/EPS
   bar charts, lazy fund/{SYM}.json fetch, position/conviction/swing/headlines
   blocks carried); catalyst DEFAULT filter = HIGH econ + desk-ticker events +
   anchors, "All" pill reveals MEDIUM; tab-badge legend line in movers box.
   Exchange table adds: SOXL/SOXS=AMEX, MUU=NASDAQ, RAM=CBOE, OILU=AMEX,
   STLL/AAOG=CBOE, WTI=NYSE; SKHX/NRGU best-guess, "—" harmless.

## Integration checklist when builders report (order matters)
1. Review diffs (git diff; agents were told no git). Run `python3 -m pytest
   fetcher/ -q` — must be green.
2. Page fixture test: fixtures live in
   `/tmp/claude-0/-home-user/b5a237c8-5ad3-578b-8f0b-eeef7bd77252/scratchpad/servedir/`
   (data/data.json + data/bars.json; serve dir over localhost http.server;
   page auto-uses ./data/ paths on localhost). Playwright chromium at
   /opt/pw-browsers/chromium, args --no-sandbox; for TV-live tests launch with
   proxy={"server":$HTTPS_PROXY,"bypass":"127.0.0.1,localhost"} — browser TV
   calls DON'T work from this sandbox either way; verify symbol tables by
   replaying scanner POSTs server-side instead (Content-Type text/plain).
   Assert computed styles, never class names.
3. Commit fetcher+contract+page together, push branch
   `claude/trading-dashboard-plan-6okdac`, ff-merge to main, push main
   (this deploys the page via pages.yml and arms the loop).
4. Trigger forced cycle: github MCP `actions_run_trigger` run_workflow
   refresh-loop.yml ref=main inputs {"force":true}; then poll
   `raw.githubusercontent.com/zlanghamer1/flow-desk/data/data.json` for
   `facts` containing a NEW ticker (e.g. SMCI) + bars.json v2 + `fund/NVDA.json`.
5. Verify live page markers (curl the site: candle code, LEVERAGED group,
   modal strings), update plan doc + SYSTEMS.md addendum if scope moved,
   final report to Zach.

## Zach-side open items (remind at close)
- Secrets still pending: `VAULT_READ_TOKEN` (flow-desk) + `DESK_PASSPHRASE`
  (ClaudeVault) — brief panel + Position Guard light up when set.
- Brief panel goes live Monday 6:23 CT automatically (vault side shipped).
- Fast-follows on file: Overnight Asia panel, watchlist diff-nag option,
  .ics export + phone manifest, brief-email retirement after a proving week.
- His Qs already answered: tab "(n)" = hot-mover count (legend line shipping
  in wave 2).

## Standing cautions for whoever finishes this
- Stop-hook will nag about the dirty tree until step 3 — that is deliberate;
  never commit half-built agent files.
- data branch: loop force-push only. Pages stays branch-mode. No scoring/
  weights/history-guard changes are part of wave 2. None ≠ 0 everywhere.
- BOARD_CAP is 80 in the draft (universe ~60 + SPDRs); keep.
