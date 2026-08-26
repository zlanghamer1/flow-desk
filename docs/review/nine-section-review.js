/* Nine-section review of index.html, with adversarial verification.
 *
 * Ran as rounds 4 and 5 on 2026-08-20. Round 4 found 72 findings across the
 * nine sections; round 5 re-reviewed the fixed page and found another 72. Both
 * rounds' confirmed findings are fixed — see the plan doc's round-4 and round-5
 * sections, and CLAUDE.md's guardrails.
 *
 * HOW TO RUN (Claude Code, from the repo root):
 *
 *     Workflow({scriptPath: "docs/review/nine-section-review.js"})
 *
 * It spawns 9 section reviewers, then one adversarial verifier per finding —
 * roughly 75 agents and 45 minutes. Every verifier is told to REFUTE, and to
 * default to real=false when unsure, so the confirmed list is short by design:
 * round 5's pass refuted 70 of 72 because the fixes had already landed.
 *
 * ANCHORED SCORING (Zach's 2026-08-26 ruling, after round 17: "the
 * adversarial agents have a moving goalpost for each review"). The header
 * note this replaces admitted the reviewer-assigned scores were not
 * comparable between rounds — a fresh harsh reviewer with an 8-finding
 * budget calibrates its number to how much it found, so the score measured
 * review depth, not page quality, and "80+ on all nine" could never
 * terminate honestly. The score is now COMPUTED, not opined:
 *
 *     score = 100 − 25·(confirmed blockers) − 10·(confirmed majors)
 *                 −  3·(confirmed minors),  floored at 0
 *
 * counted AFTER the adversarial verify stage, so a refuted finding costs
 * nothing. Same ruler every round: reviewers find, verifiers gate,
 * arithmetic scores. The reviewer's own 0-100 impression is still recorded
 * as `reviewerScore` for trend-reading, but the pass bar reads the computed
 * number only. 80+ therefore means concretely: zero blockers AND at most
 * two majors (or one major plus up to three minors, or six minors).
 *
 * THE PASS BAR IS 80, not 90 (Zach's 2026-08-21 ruling) — the `below90`
 * variable name below is legacy from before that ruling; the threshold it
 * filters on is 80.
 *
 * SONNET AGENTS (Zach's 2026-08-26 ruling, "Continue sonnet agents review
 * to 80+ score on all"): every review and verify agent below pins
 * model:'sonnet' explicitly, matching the repo's model-role convention
 * (Sonnet builds and reviews; Fable architects). The same ruling restored
 * the numeric finish line: rounds continue until all nine sections score
 * 80+ in a single round.
 *
 * PLACEHOLDER-GARBAGE RETRY (added 2026-08-22, round 9): a section reviewer
 * agent can return schema-VALID content that is actually a placeholder —
 * `section:"test"`, a two-sentence lorem-ipsum-style summary, a finding
 * titled "t" — because the JSON Schema only checks shape, not substance.
 * This happened twice before this fix existed (round 7's Auto-TA, round 8's
 * Chart Stage), and both times required a human to notice, read
 * journal.jsonl by hand, and hand-write a standalone retry script
 * (docs/review/chart-section-redo.js) to get a real score. Each section's
 * review stage now runs through looksLikePlaceholder() with up to 4
 * attempts before accepting a result, the same check that one-off script
 * used — so a broken run can no longer pass as a real score without anyone
 * noticing.
 */
export const meta = {
  name: 'flow-desk-nine-section-review',
  description: 'Score nine sections of the Flow Desk page, verify every finding adversarially',
  phases: [
    { title: 'Review', detail: 'nine independent section reviewers' },
    { title: 'Verify', detail: 'adversarial check on each finding' },
  ],
}

// REPO's absolute path varies by environment/session — this script does not
// hardcode one. Pass it via Workflow's `args.repoRoot`; falls back to this
// session's known checkout if the caller omits it (a later session on a
// different workspace path MUST pass args.repoRoot rather than edit this).
const REPO = (args && args.repoRoot) || '/home/user/flow-desk'
const FILE = REPO + '/index.html'

const COMMON = `
You are reviewing a single-file trading dashboard at ${FILE} (about 14,000 lines: CSS in a
<style> block, all JS in one inline <script>). Supporting files: ${REPO}/DATA_CONTRACT.md
(the payload contract), ${REPO}/fetcher/context.py (the publisher), and
${REPO}/data/*.json (real published payloads you can read to see actual shapes and values).

NOTE on ${REPO}/data/: it is gitignored local test data and can be stale. Before you
build a finding on what a payload does or does not contain, check the live copy:
  git show origin/data:fund/MU.json   (or data.json, bars.json, bars_intraday.json)
A round-4 reviewer reported a real feature as broken because the local sidecars were months old.

The owner is a construction project executive, not a programmer. He uses this page to decide what to
trade. He has said repeatedly: he wants a REAL trading platform, and he does not want to be lied to by
the interface.

Score the section 0-100 on whether it is genuinely good, not whether it is finished. A 90 means: a
professional trader would use this section daily and it would not mislead them. Be harsh.

Read the actual code. Do not guess. Cite line numbers. For each problem, give a CONCRETE failure:
specific ticker, specific value, specific screen width, specific sequence of clicks — something that
could be reproduced.

Do NOT report:
- style preferences with no user-visible consequence
- things already handled by a nearby guard (read the surrounding code first)
- "add a test" or "add a comment" suggestions
- anything you cannot point at a line for

Return findings ordered by severity. Cap at 8 findings; only report what genuinely matters.
`

const SCHEMA = {
  type: 'object',
  required: ['section', 'score', 'summary', 'findings'],
  additionalProperties: false,
  properties: {
    section: { type: 'string' },
    score: { type: 'integer', minimum: 0, maximum: 100 },
    summary: { type: 'string', description: 'two sentences: what works, what is holding the score down' },
    findings: {
      type: 'array',
      maxItems: 8,
      items: {
        type: 'object',
        required: ['title', 'lines', 'failure', 'severity', 'fix'],
        additionalProperties: false,
        properties: {
          title: { type: 'string' },
          lines: { type: 'string', description: 'line numbers or a range in index.html' },
          failure: { type: 'string', description: 'concrete reproducible failure: ticker, value, width, clicks' },
          severity: { type: 'string', enum: ['blocker', 'major', 'minor'] },
          fix: { type: 'string', description: 'the specific change that would fix it' },
        },
      },
    },
  },
}

const VERDICT = {
  type: 'object',
  required: ['real', 'confidence', 'why'],
  additionalProperties: false,
  properties: {
    real: { type: 'boolean' },
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
    why: { type: 'string' },
    correction: { type: 'string', description: 'if the finding is partly right, what it should say instead' },
  },
}

const SECTIONS = [
  { key: 'chart', prompt: `Review the CHART STAGE: the Lightweight Charts candle chart, its interval buttons (15m/1H/4H/1D/1W), window buttons, volume pane, crosshair readout, price/time axis behaviour, earnings markers, analyst-rating markers, zoom and pan, log-scale switching, and the legend. Look at stageRender, stageDraw, the STAGE object, barSessionDates, candleClose, preMarketBar, stageTickFmt, stageMarkers, showEarnPopover, slot4H/resample4H, and everything that draws on the chart.` },
  { key: 'auto-ta', prompt: `Review the AUTOMATIC TECHNICAL ANALYSIS: trend-line fitting, support/resistance levels, breakout/retest/failed grading, RSI, moving averages, the TA toggle buttons, and every caption or badge that states a TA conclusion in words. Look at taFitLine, taLevels, taContainTol, taRegrade, stageTAPoke, stageTALegend, TA_RETEST_NEAR, the RSI guides, and the caption text. Judge especially whether any stated conclusion can be WRONG in a way a trader would act on.` },
  { key: 'watchlist-rail', prompt: `Review the LEFT WATCHLIST RAIL: the ticker search box and its dropdown, adding and removing names, the movers/shopping-list box at the top, the sort strip, each row's two lines (symbol, price, change, name, earnings countdown, hot multiple, edit), the session tags (PRE/PREV/AFT/STALE), persistence across reloads, and the phone collapse. Look at renderWL, tsSearch/_tsQuery/tsPick, wlAdd/wlRemove/wlIoApply, dispQuote, hotOf, statsOfUncached, earnDaysNow, isLeveraged.` },
  { key: 'financials', prompt: `Review the FINANCIALS tab: the quarterly and annual bar/line charts, the axis and hover formatting, the tap-to-read band, the metric table with its reasons for missing values, the summary sentences, the data-source caveats, and the sidecar fallback path. Look at axisChartSVG, titleFormatter, tickFormatter, hoverFormatter, periodsPerYear, yoyPct, ttmEpsOf, derivedPeg, metricReason, METRIC_REASON_LONG, renderGrowth.` },
  { key: 'heatmap', prompt: `Review the SECTOR HEATMAP view: the squarified treemap layout, the colour scale, the text contrast and truncation inside tiles, the tooltips, keyboard access, the sector grouping, the tile-count cap, and what happens at narrow widths or with missing data. Look at heatRender, heatFetch/heatFetchNow, squarify, heatColor, heatTextColor, heatClampFrom, and the footer copy.` },
  { key: 'peers', prompt: `Review the vs PEERS tab: peer-group selection (curated and generated), the comparison table, the ranking sentences, the scale and clipping behaviour, the size-outlier mark, the loading and redraw path, the indexed-revenue chart, and how missing peer data is stated. Look at PEER_GROUPS, PEER_GROUP_LABEL, peersFor, _peersByIndustry, renderPeersInto, peerBarsSVG, peerStat, PEER_LAST.` },
  { key: 'panels', prompt: `Review the RIGHT RAIL PANELS: Morning Brief, sector rotation table, catalysts, news, plus the top rail (market-state lamp, clock, tape tiles, macro tiles, Fed hike odds) and the rolling news ticker. Look at renderBrief, renderSectorSection, renderCats, renderNews, renderNewsTicker, renderMarketState, priceSessionNow/isTradingDay, renderTape, macroTileHTML, fedOddsHTML, fedDaysToMeeting, countdown, dedupeNews, elapsedShort.` },
  { key: 'flow-boards', prompt: `Review the FLOW BOARDS: the conviction board, the swing board, the biggest-orders board and the ETF board — their columns, sorting, scores, tooltips, cut notes, live-vs-snapshot reconciliation, empty states, and horizontal scrolling. Look at renderConv, renderSwing, renderOrders, renderETF, rowHTMLConv, the table() helper, boardCutNoteHTML, boardCoverageHTML, boardEmptyHTML, contractLine, flowPctHTML, wireBoardCut, refreshLiveUI.` },
  { key: 'data-honesty', prompt: `Review DATA HONESTY across the whole page: every number the page shows, and whether the page states truthfully where it came from, how old it is, and how precise it is. Hunt for anything the page presents as fact that is actually inferred, approximated, stale, or from a different source than implied. Check delayed-quote disclosure, staleness stamps (ageStampHTML, liveStale, macroSymStale), the price-feed failure banner, approximate dates (BAR_DATES_APPROX, MARKET_HOLIDAYS, weekdayDatesEndingAt), the CLOSE ONLY and STALE and FROZEN and PREV tags, rounded figures presented as exact, and any sentence that overstates what the data supports.` },
]

function looksLikePlaceholder(review) {
  if (!review) return true
  if (!review.section || review.section.toLowerCase() === 'test') return true
  if (!review.summary || review.summary.length < 20) return true
  const bad = (review.findings || []).some(f =>
    !f.title || f.title.length <= 2 ||
    !f.lines || f.lines.length <= 2 ||
    !f.failure || f.failure.length <= 2 ||
    !f.fix || f.fix.length <= 2
  )
  return bad
}

phase('Review')

const results = await pipeline(
  SECTIONS,
  async (s) => {
    let review = null
    for (let attempt = 0; attempt < 4; attempt++) {
      review = await agent(COMMON + '\n\n' + s.prompt, {
        label: 'review:' + s.key + '-attempt' + attempt, phase: 'Review', schema: SCHEMA, effort: 'high',
        model: 'sonnet',
      })
      if (!looksLikePlaceholder(review)) break
      log(s.key + ' review attempt ' + (attempt + 1) + ' looked like placeholder garbage (section="' +
        (review && review.section) + '") — retrying')
      review = null
    }
    return review
  },
  (review, s) => {
    if (!review || !review.findings || !review.findings.length) return { review, verdicts: [] }
    return parallel(review.findings.map(f => () =>
      agent(`Adversarially verify this review finding about ${FILE}.

FINDING: ${f.title}
LINES: ${f.lines}
CLAIMED FAILURE: ${f.failure}
PROPOSED FIX: ${f.fix}

Read the actual code at and around those lines. Your job is to REFUTE this finding. Default to
real=false when you are not sure. It is NOT real if:
- a guard nearby already prevents the failure
- the line numbers point somewhere else entirely
- the claimed value or behaviour does not match what the code does
- the "failure" is a style preference with no user-visible consequence
- the data shape it assumes does not match the LIVE payload (git show origin/data:...) or DATA_CONTRACT.md

It IS real only if you can trace the exact path from code to the stated failure. If it is partly
right, set real=true and put the accurate version in "correction".`,
      { label: 'verify:' + s.key, phase: 'Verify', schema: VERDICT, effort: 'high', model: 'sonnet' })
      .then(v => ({ finding: f, verdict: v }))
    )).then(verdicts => ({ review, verdicts: verdicts.filter(Boolean) }))
  }
)

// Anchored score from CONFIRMED findings only — see the header's 2026-08-26
// ruling. Fixed deductions, same ruler every round.
const DEDUCT = { blocker: 25, major: 10, minor: 3 }
function anchoredScore(confirmed) {
  const loss = confirmed.reduce((s, f) => s + (DEDUCT[f.severity] || 3), 0)
  return Math.max(0, 100 - loss)
}

const report = results.filter(Boolean).map((r, i) => {
  const confirmed = r.verdicts.filter(v => v.verdict && v.verdict.real).map(v => ({
    title: v.finding.title, lines: v.finding.lines, severity: v.finding.severity,
    failure: v.finding.failure, fix: v.finding.fix,
    confidence: v.verdict.confidence, correction: v.verdict.correction || null,
  }))
  return {
    // All 4 retry attempts can still fail — say so explicitly rather than
    // reporting "unknown" with no indication the section's score is missing,
    // not merely unlabeled. A failed review scores null, never a clean 100:
    // no findings because nothing was reviewed is not a pass.
    section: r.review ? r.review.section : (SECTIONS[i].key + ' (all 4 review attempts returned placeholder garbage — re-run this section)'),
    score: r.review ? anchoredScore(confirmed) : null,
    reviewerScore: r.review ? r.review.score : null,   // the raw impression, trend-reading only
    summary: r.review ? r.review.summary : '',
    confirmed,
    refuted: r.verdicts.filter(v => !v.verdict || !v.verdict.real).map(v => v.finding.title),
  }
})

// PASS BAR IS 80 (Zach's 2026-08-21 ruling), read on the ANCHORED score —
// see the file header note.
const below = report.filter(r => r.score !== null && r.score < 80).map(r => r.section + ' ' + r.score)
log('below 80 (anchored): ' + (below.length ? below.join(', ') : 'none'))

return { report, below80: below }
