/* Targeted re-run of just the CHART STAGE section from nine-section-review.js.
 *
 * Round 8's full nine-section run (2026-08-22) had this section's reviewer
 * return schema-valid placeholder garbage (section:"test", a "t"-titled
 * finding) — the exact failure mode round 7's methodology note warned about.
 * This script adds a content-sanity check with retries before accepting a
 * review, then verifies whatever real findings come back, mirroring the
 * throwaway re-run used for round 7's Financials/Auto-TA redo.
 *
 * Run: Workflow({scriptPath: "docs/review/chart-section-redo.js"})
 */
export const meta = {
  name: 'flow-desk-chart-section-redo',
  description: 'Re-run the Chart Stage section review with a content-sanity retry',
  phases: [
    { title: 'Review', detail: 'chart stage reviewer, retried until real content' },
    { title: 'Verify', detail: 'adversarial check on each finding' },
  ],
}

const REPO = (args && args.repoRoot) || '/home/user/flow-desk'
const FILE = REPO + '/index.html'

const COMMON = `
You are reviewing a single-file trading dashboard at ${FILE} (about 8,700 lines: CSS in a
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

const CHART_PROMPT = `Review the CHART STAGE: the Lightweight Charts candle chart, its interval buttons (15m/1H/4H/1D/1W), window buttons, volume pane, crosshair readout, price/time axis behaviour, earnings markers, analyst-rating markers, zoom and pan, log-scale switching, and the legend. Look at stageRender, stageDraw, the STAGE object, barSessionDates, candleClose, preMarketBar, stageTickFmt, stageMarkers, showEarnPopover, slot4H/resample4H, and everything that draws on the chart.`

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
let review = null
for (let attempt = 0; attempt < 4; attempt++) {
  review = await agent(COMMON + '\n\n' + CHART_PROMPT, {
    label: 'review:chart-attempt' + attempt, phase: 'Review', schema: SCHEMA, effort: 'high',
  })
  if (!looksLikePlaceholder(review)) break
  log('Chart Stage review attempt ' + (attempt + 1) + ' looked like placeholder garbage (section="' +
    (review && review.section) + '") — retrying')
  review = null
}

phase('Verify')
let verdicts = []
if (review && review.findings && review.findings.length) {
  verdicts = await parallel(review.findings.map(f => () =>
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
      { label: 'verify:chart', phase: 'Verify', schema: VERDICT, effort: 'high' })
      .then(v => ({ finding: f, verdict: v }))
  ))
}
verdicts = verdicts.filter(Boolean)

const result = {
  section: review ? review.section : 'Chart Stage (all attempts returned placeholder garbage)',
  score: review ? review.score : null,
  summary: review ? review.summary : '',
  confirmed: verdicts.filter(v => v.verdict && v.verdict.real).map(v => ({
    title: v.finding.title, lines: v.finding.lines, severity: v.finding.severity,
    failure: v.finding.failure, fix: v.finding.fix,
    confidence: v.verdict.confidence, correction: v.verdict.correction || null,
  })),
  refuted: verdicts.filter(v => !v.verdict || !v.verdict.real).map(v => v.finding.title),
}

log('Chart Stage redo score: ' + result.score)
return result
