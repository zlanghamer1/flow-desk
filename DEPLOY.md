# Deploying Flow Desk

Ops facts only. The user-facing docs — URL, what it does, restart steps,
honest limits — live in README.md. This file is just how the deploy and the
loop are wired.

## Deploy method

Pages runs in **branch mode from `gh-pages`**. `.github/workflows/pages.yml`
copies `index.html` from `main` onto `gh-pages`; GitHub's built-in "pages
build and deployment" then publishes it. **Do not** flip Settings → Pages to
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
re-triggers itself so it covers the whole session. A daily scheduled backup
start (~8:03 AM CT — moved earlier 2026-08-24 for more buffer before the
8:30 AM open; 8:00 AM CT is the earliest the loop will do anything at all)
exists in case the redispatch chain ever breaks.

## Restarting

See README.md → "How to restart the loop if it stops". From a Claude session,
just say "deploy flow-desk" — the remote is the standard proxy URL and the
pushes are the normal `git push origin main` / `git push origin data`.

## History

Deployed 2026-07-16: repo pushed, Pages went live, and the first forced cycle
published real data to the `data` branch. The ClaudeVault mirror at
`market-data/flow-desk/repo/` remains the durable backup.
