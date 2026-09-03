# Deploying Flow Desk

Ops facts only. The user-facing docs — URL, what it does, restart steps,
honest limits — live in README.md. This file is just how the deploy and the
loop are wired.

## Deploy method

Pages runs in **branch mode from `gh-pages`**. `.github/workflows/pages.yml`
copies `index.html`, `legal.html`, and `vendor/` from `main` onto `gh-pages`;
GitHub's built-in "pages build and deployment" then publishes it. A new root
HTML page has to be added to all three lists in that workflow (`paths:`,
`git checkout main --`, `git add`); `fetcher/test_pages_ship.py` fails if one
is missing. **Do not** flip Settings → Pages to
"GitHub Actions" mode — branch mode is intentional (the workflow token can't
create a Pages site, and the auto-created github-pages environment rejects
`actions/deploy-pages` runs from `main`). If Pages ever gets turned off:
Settings → Pages → source **Deploy from a branch** → branch **gh-pages**
(root).

## How the loop stays alive

`.github/workflows/refresh-loop.yml` runs `fetcher/loop.py`, which publishes a
fresh `data.json` + `history.json` to the `data` branch every ~7 minutes
during the extended window (08:00–15:20 CT, Mon–Fri). The universe is a fixed
curated watchlist plus the 11 SPDR sector ETFs — there is no market screen.
Before GitHub's job-time limit the loop prints `REDISPATCH` and the workflow
re-triggers itself so it covers the whole session.

### What actually starts the day (corrected 2026-09-03)

The redispatch chain is not a daily starter. `loop.py` exits when the publish
window closes at 15:20 CT, so on any day the loop starts after ~09:50 CT it
never reaches its 5.5h redispatch threshold, never prints `REDISPATCH`, and
the chain never fires. **Every session's first run comes from a cron firing or
a dispatch.** 8:00 AM CT is the earliest a firing does anything at all —
`market_guard.should_publish()` returns false before that and the run exits in
seconds.

That makes a delayed cron a blank desk, which is what happened on 2026-09-03:
neither 08:03-target cron had fired by 11:38 AM CT, so `data.json` still
carried the previous afternoon's publish and every payload-driven panel — the
Morning Brief tile, both flow boards, catalysts, news — read a day stale. The
three sessions before it each got exactly two firings, every one of them
2.6–5h late. GitHub schedule triggers are documented best-effort and this
repo has been getting the bad end of that.

Two mitigations:

1. **In-repo (done 2026-09-03):** the workflow now carries eight cron entries
   at minute :03 across 13:00–20:00 UTC instead of two. Any firing that lands
   outside the window exits in seconds; whichever one lands inside it first
   starts the loop for the rest of the session, and the `refresh-loop`
   concurrency group serializes the rest. This widens coverage; it does not
   make the scheduler punctual.
2. **The real fix — an external pinger.** ClaudeVault hit this identical
   failure on 2026-06-12 (its Morning Brief skipped outright, its watchdog
   delivering one slot in four hours) and solved it with a cron-job.org job
   that POSTs the workflow's `dispatches` endpoint on a clock GitHub does not
   control. Those two jobs still fire on the minute today while this repo's
   crons run hours late. Setup steps, token scope, and the standing rules are
   in ClaudeVault's `market-data/event-alerts/EXTERNAL_TRIGGER.md`. flow-desk
   needs its own third job:

   - URL: `https://api.github.com/repos/zlanghamer1/flow-desk/actions/workflows/refresh-loop.yml/dispatches`
   - Method POST, body `{"ref":"main"}`, headers `Authorization: Bearer <PAT>`
     and `Accept: application/vnd.github+json`
   - Schedule: weekdays 8:03 AM, timezone America/Chicago

   The existing `workflow-pinger` PAT is scoped to ClaudeVault only, so this
   needs its repository access widened to include flow-desk (or a second
   fine-grained token with Actions: Read and write on flow-desk). That is the
   one step a session cannot do for itself.

### Starting a session's loop by hand

`gh workflow run refresh-loop.yml --repo zlanghamer1/flow-desk`, or the
equivalent API dispatch. Do **not** pass `force: true` during market hours —
that runs exactly one guard-bypassing cycle and will not chain.

## CI

`.github/workflows/ci.yml` runs on every push to `main` and every pull
request, with a read-only token and pinned dependencies. Two jobs:
`fetcher-tests` (`pytest fetcher`) and `page-smoke` (`pytest tests`, headless
Chromium loading `index.html` and `legal.html` from a local static server
with every external host blocked). Added 2026-09-03; before that the test
suite only ran when a session ran it by hand.

## Hosting terms (read before charging for the site)

GitHub Pages does not allow commercial software as a service, and GitHub
Actions does not allow workloads unrelated to building the repo. The current
deploy is fine for a personal tool and not for a paid one. The move-off plan
is in `docs/MONETIZATION.md`.

## Restarting

See README.md → "How to restart the loop if it stops". From a Claude session,
just say "deploy flow-desk" — the remote is the standard proxy URL and the
pushes are the normal `git push origin main` / `git push origin data`.

## History

Deployed 2026-07-16: repo pushed, Pages went live, and the first forced cycle
published real data to the `data` branch. The ClaudeVault mirror at
`market-data/flow-desk/repo/` remains the durable backup.
