# Making the desk a product: readiness assessment and roadmap

Written 2026-09-03 in response to the goal "make the desk a professional
grade trading site that could be monetized." The vendor-terms facts behind
this document are in `docs/DATA_LICENSING.md`.

## The answer first

The desk cannot be sold as it is today. Three things block it, and none of
them is a code problem:

1. **Data rights.** Every price, option quote, headline, and financial
   statement on the page comes from a feed licensed for personal use, or from
   an undocumented endpoint with no license at all. Charging money for the
   page would break TradingView's, Cboe's, Yahoo's, and stockanalysis.com's
   terms on the first day.
2. **Hosting rules.** GitHub Pages bans commercial software as a service.
   GitHub Actions bans workloads that are not about building the repo. The
   site and the refresh loop both run on those free tiers.
3. **No way to charge.** The page is a static file that reads public data
   files. It has no login, no way to tell a subscriber from a visitor, and no
   way to stop anyone from reading `data.json` directly. A paywall needs a
   server that checks who is asking before it answers.

The code itself is in better shape than most paid dashboards' front ends:
19 review rounds, 347 fetcher tests, and every panel prints its own as-of
time and says when its feed failed. What the desk lacks is a business wrapped
around it: licensed data, a server, an entity, and paperwork.

One prior ruling matters here. On 2026-06-14 Zach declined paid data feeds
for the personal desk, and the vault says not to re-pitch them. That ruling
stands for the personal tool. A product is a different question: the vendor
invoice is the price of the right to charge other people. There is no free
path to a paid product. This document does not re-pitch paid feeds for
personal use. It states that a product needs them.

## Where the desk stands against a professional bar

| Area | Today | Bar for a paid product | Gap |
|---|---|---|---|
| Data rights | Free feeds, personal-use terms, undocumented endpoints | Written display rights from a vendor for every feed | Large. Costs money every month. |
| Reliability | GitHub Actions cron, best-effort schedule (the 2026-08-24 backup start fired 43 minutes late), one public repo, no monitoring | A scheduler you control, alerting when a cycle fails, a status page, an uptime target | Medium |
| Accounts and billing | None | Login, subscription billing, a billing portal, a data API that checks the subscription | Large. A new backend. |
| Legal | One "not financial advice" line in the honesty box | Terms of use, privacy notice, risk disclosure, a legal entity, attorney review | Small. Drafted in this pass; entity and review remain. |
| Product | One curated universe (the owner's watchlist), settings kept in each browser, one 943 KB HTML file | Per-user watchlists stored server-side, alerts, onboarding, a name and domain you own, a front end split into modules | Medium to large |
| Code quality | 347 tests, but none ran in CI; no front-end test | Tests run on every change; the page is smoke-tested | Closed in this pass |

## What shipped in this pass

These are the parts that needed no accounts, money, or decisions:

- `legal.html`: terms of use, privacy notice, risk disclosure, and data
  attribution, in plain English, linked from the footer and shipped by
  `pages.yml`. The operator's legal name, contact, and governing law are
  visible bracketed placeholders. They are Zach's to fill.
- Head metadata on `index.html`: description, social-card tags, theme color,
  canonical URL. Search engines and link previews now describe the page.
- The visible copy no longer names the owner. Two tooltips said "Zach's
  2026-08-26 ruling" and "Zach's alert ask"; they now name the rule. Code
  comments keep their history.
- `.github/workflows/ci.yml`: the fetcher's 347 tests and a new headless
  page smoke test run on every push to main and every pull request. Until
  now nothing in CI ran them.
- `tests/test_page_smoke.py`: loads `index.html` and `legal.html` in headless
  Chromium at 1440 px and 390 px with every external host blocked, and fails
  on any uncaught page error or sideways scroll. This is the first automated
  check that the page survives its feeds being down, which every review round
  since 2026-08-19 has required by rule.
- `fetcher/test_pages_ship.py`: fails if a root HTML page is missing from
  `pages.yml`'s publish lists or if the footer links to a page that does not
  exist.
- This document and `docs/DATA_LICENSING.md`.

## What the desk could honestly be sold as

The paid flow tools sell real-time, trade-level data: Unusual Whales around
$50 a month, Cheddar Flow $85 to $99, FlowAlgo $149 (2026 review prices;
verify). They can say "a $6M sweep just hit NVDA." The desk cannot, and the
README already explains why: free and delayed data gives day totals per
contract, not single orders. Licensing delayed data does not change that.

So the desk does not compete as a day-trading flow tool. It competes as
something slower:

- A swing desk. Flow measured against each name's own normal day, open
  interest confirmed the next morning, a 5-filter framework, plain-English
  reads, and a page that says when it does not know. Built for someone who
  checks the market a few times a day, not every minute.
- Priced below the flow tools. A 15-minute-delayed product cannot charge
  real-time money. $10 to $20 a month is the range.
- With a free tier that shows yesterday's boards, so the site keeps its
  audience and the paid tier sells today's.

Two other models exist and are weaker fits:

- Free site, paid newsletter (the Morning Brief). This is the publisher model.
  It still needs licensed data to build the brief, so it removes the paywall
  work but not the data bill.
- Free site, donations or sponsorships. Legal on a hobby footing, but it does
  not fix the hosting terms once money flows, and it does not pay for data.

Recommendation: the swing desk subscription on licensed delayed data. It is
the only model where the desk's actual strength, its honesty about what the
data can and cannot say, is the product.

## The money

Break-even is decided by the data contract, not by the code.

| Monthly cost | Data | Hosting, auth, payments | Total | Subscribers needed at $15 |
|---|---|---|---|---|
| Small vendor sells delayed display rights | $300 | $50 | $350 | about 25 |
| Massive published business tier | $2,500 | $50 | $2,550 | about 175 |

Card fees take about 3% plus 30 cents per charge on top. Both rows are before
the attorney, the entity's annual fees, and your time. Fifty subscribers at
$15 is $750 a month. That covers the small-vendor row with room to spare and
does not come close to the published business tier. Get the vendor quote
before anything else, because it decides which of those two businesses this
is.

## Roadmap

Each phase ends at a gate. Do not start the next phase until the gate is met.

**Phase 0, done in this pass.** Legal drafts, metadata, CI, smoke test, this
assessment.

**Phase 1, decisions. Zach, about a week.**

- Pick the posture: 15-minute-delayed swing desk (recommended) or real-time.
- Form the entity (an LLC) and have an attorney read `legal.html`.
- Get written quotes from at least two data vendors for "customer-facing
  display of 15-minute-delayed US stock and options data" at 100 users. Ask
  for the display right in writing.
- Pick a name and buy a domain. "The Desk" is generic and cannot be owned.
- Gate: a signed data agreement and a formed entity.

**Phase 2, backend. Build, several sessions.**

- Move the fetcher off GitHub Actions to a scheduler you control: a small
  cloud machine on a cron, or a serverless cron. Cost $5 to $20 a month.
- Store the published files in object storage behind a small API that checks
  a login before it answers. The page reads from that API instead of
  `raw.githubusercontent.com`.
- Add login and billing: a hosted auth service, plus Stripe for checkout,
  the customer billing portal, and webhooks that turn a payment into access.
- Move the site off GitHub Pages to a host that allows commercial use.
- Gate: a test subscriber can pay, log in, and see today's boards. A
  non-subscriber cannot fetch the data by any path.

**Phase 3, replace the feeds. Build, overlaps Phase 2.**

- Swap each row marked Blocked in `docs/DATA_LICENSING.md` for its licensed
  replacement. SEC EDGAR replaces stockanalysis.com for US filers at no cost.
- Delete any feature that has no licensed source instead of leaving it on a
  scraped feed. Today that likely means the S&P 500 and Nasdaq 100 heatmaps
  and the three consensus-based framework filters.
- Add a test that fails when the page or the fetcher calls a host outside an
  allowlist.
- Gate: the allowlist test passes. Zero calls to unlicensed hosts.

**Phase 4, product. Build.**

- Per-user watchlists stored server-side. Today they live in each browser.
- Email or push alerts. The Band-crosses panel is the seed; `CLAUDE.md`
  already notes that push is new architecture, not an extension.
- Onboarding for a first-time visitor, a status page, and monitoring that
  pages you when a cycle fails.
- Split `index.html` into modules while the data layer is changing anyway.

**Phase 5, launch.** A small paid beta at an introductory price, then public.

## Decisions only Zach can make

1. Posture: delayed swing desk or real-time. Recommendation: delayed.
2. Pay for data: yes or no. "No" ends this roadmap and the desk stays a
   personal tool, which is a fine outcome.
3. Entity and attorney: required before the first charge.
4. Name and domain.
5. Which features to drop if no licensed source fits the budget.
6. Price.

## Legal notes for the attorney conversation

- The desk's content is impersonal: the same boards for every visitor, no
  per-user recommendations. That is the shape federal law treats as
  publishing rather than investment advice (the publisher's exclusion in the
  Investment Advisers Act of 1940). Keep it that shape. Never add a "buy this
  for your account" feature.
- The 5-metric framework prints BUY, ADD, HOLD, and AVOID. Those are Zach's
  words and they were not changed in this pass. Expect an attorney to ask for
  neutral tier names such as "passes 5 of 5" in a paid product.
- Options carry a mandated risk disclosure. `legal.html` points to the
  Options Clearing Corporation's booklet. Confirm the exact language.
- The privacy notice is short because the site stores nothing about a
  visitor. Adding accounts changes that. Update the notice in the same change
  that adds login.

## What this pass did not do, and why

- No backend, billing, auth, or vendor accounts. Each needs Zach's accounts,
  money, or entity.
- No renaming of BUY/ADD/HOLD/AVOID. Flagged above, not changed.
- No split of `index.html` into modules. It works and it is tested. Splitting
  it now would reopen review surface with no data-layer change to justify it.
  Do it in Phase 2.
- No removal of any feed. Removing feeds before their replacements exist
  would break the personal tool for no gain. The allowlist test in Phase 3 is
  where that happens.
