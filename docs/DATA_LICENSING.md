# Data licensing inventory

Written 2026-09-03 for the monetization assessment in `docs/MONETIZATION.md`.
This file lists every outside service the desk calls, what that service's
terms allow, and what a paid product would need instead. Vendor pages were
read on 2026-09-03; prices and terms change, so re-check each one before
signing anything.
Quoted text is verbatim from the vendor page named in that row. The Cboe row
is a paraphrase of the Subscriber Agreement and the delayed-quotes pages; the
PDF did not extract cleanly, so confirm the exact wording before relying on it.

## The short version

- Every market-data feed the desk uses today is licensed for personal,
  non-commercial display, or is an undocumented internal endpoint with no
  license at all. None of them can be shown to paying customers.
- The chart library is the exception. TradingView Lightweight Charts is
  Apache-2.0. Commercial use is fine as long as the attribution stays.
- The hosting is also a blocker. GitHub Pages bans commercial software as a
  service, and GitHub Actions bans workloads that are not about building the
  repo. The desk runs on both.

A personal research tool sits inside what these vendors tolerate. The moment
the desk charges money, every row marked **Blocked** below becomes a terms
violation and a business risk (a blocked IP, a cease-and-desist, or a vendor
that changes an undocumented endpoint on a Tuesday).

## What the desk calls today

| Service and endpoint | Used for | Called from | Terms today | Paid product |
|---|---|---|---|---|
| Cboe `cdn.cboe.com/api/global/delayed_quotes/options/{SYM}.json` | Options chains: volume, open interest, IV, greeks, spot. Feeds both flow boards, biggest orders, gamma levels, unusual activity. | Fetcher, every ~7 min | Cboe's delayed-quotes pages license the data for personal, non-commercial use, prohibit pulling it with automated tools, and reserve redistribution for parties under a Cboe data agreement (Cboe Subscriber Agreement and Market Data Policies, cdn.cboe.com/resources/membership/). | **Blocked.** Needs licensed options data from a vendor that grants display rights. |
| TradingView `scanner.tradingview.com/america/scan` and `/global/scan` | Prices (15-minute delayed), fundamentals, ticker search, heatmap universes, consensus estimates, RSI and moving averages, share counts and NAV for ETF flows. | Fetcher and the page (the browser polls it every 30 seconds) | TradingView Terms of Service, section 3: content and market data are "licensed for exclusive display-only use"; "we do not permit commercial usage of any of our services or APIs"; their provider agreements "strictly forbid the sublicensing, assigning, transferring, selling, loaning, or any distribution of TradingView content, including market data, for any form of compensation." The scanner is also undocumented. | **Blocked.** |
| TradingView `news-mediator.tradingview.com` | Tagged headlines and the news reels. | Fetcher | Same terms as above. | **Blocked.** |
| TradingView `economic-calendar.tradingview.com/events` | Economic calendar rows in Catalysts. | Fetcher | Same terms as above. | **Blocked.** The hand-kept CSV in ClaudeVault is not affected. |
| Yahoo Finance `query1.finance.yahoo.com/v8/finance/chart`, `/v10/finance/quoteSummary`, `/v1/test/getcrumb` | Daily bars (`bars.json`), intraday bars, next-earnings date, parts of the fund sidecar. | Fetcher | Unofficial and undocumented. Yahoo's terms allow personal, non-commercial use and do not allow redistribution. The crumb handshake exists because Yahoo does not intend this as an API. | **Blocked.** |
| stockanalysis.com `/stocks/{sym}/.../__data.json` (fetcher) and `/api/symbol/s/{sym}/history` (page) | Quarterly and annual financial statements, statistics, price history for searched names outside the desk universe. | Fetcher and the page | Their help center: "we don't offer any sort of programmatic access," and "we have licenses to display the data, but not redistribute or resell programmatically." | **Blocked.** |
| Polymarket `gamma-api.polymarket.com/events`, `clob.polymarket.com/prices-history` | Fed rate-change odds card. | Fetcher | Public, documented, no key. The docs pages found do not state commercial-display terms. | **Verify.** Ask Polymarket in writing; likely fine with attribution. |
| GitHub `raw.githubusercontent.com` (this repo's `data` branch; ClaudeVault through a read-only token) | The desk's own published files, the Morning Brief summary, memory events, the econ CSV. | Page and fetcher | The content is the operator's own. The hosting terms are the issue (next section). | Move to storage the product controls. |
| `vendor/lightweight-charts.standalone.production.js` | The chart engine. | Page | Apache-2.0. The in-chart attribution logo and the footer credit are license conditions. | **OK.** Keep both credits. |

## Hosting and compute terms

GitHub Pages documentation, "Prohibited uses":

> GitHub Pages is not intended for or allowed to be used as a free
> web-hosting service to run your online business, e-commerce site, or any
> other website that is primarily directed at either facilitating commercial
> transactions or providing commercial software as a service (SaaS).

GitHub Terms for Additional Products and Features, GitHub Actions:

> Actions should not be used for: ... Any activity that places a burden on
> our servers, where that burden is disproportionate to the benefits provided
> to users (for example, don't use Actions as a content delivery network or
> as part of a serverless application ...); or If using GitHub-hosted
> runners, any other activity unrelated to the production, testing,
> deployment, or publication of the software project associated with the
> repository where GitHub Actions are used.

What this means for the desk: the refresh loop is a market-data pipeline
that runs all day on GitHub-hosted runners, and the `data` branch is a
content delivery path the page reads every 30 seconds. As a personal project
that sits in the zone GitHub tolerates. A product that charges for it does
not. Both the pipeline and the site have to move before the first dollar.

## Licensed replacements and what they cost

Prices are what the vendor pages showed on 2026-09-03. Individual plans do
not cover a product: Massive labels every individual tier "Individual use
only," and its terms say that if you use the services for business or
commercial purposes you may not use plans labeled for individual use.
Customer-facing display needs a business plan, and business options pricing
is "talk to sales." Zach's existing Polygon key is an individual plan and
cannot carry the product.

| Need | Licensed option | Tier a product needs | Price seen | Notes |
|---|---|---|---|---|
| Stock prices and bars (15-minute delayed is fine for a swing desk) | Massive (the company formerly named Polygon.io); also Databento, Intrinio, Twelve Data, Finnhub | Business plan with display and redistribution rights | Individual: Starter $29 (15-min delayed), Developer $79, Advanced $199 (real-time). Business: Stocks Business $2,499/mo real-time; delayed business pricing not published. | Ask sales for "customer-facing display of 15-minute-delayed data" and get the display right in writing. |
| Options chains, open interest, greeks, IV | Massive Options; Cboe DataShop (direct); Databento (OPRA); Tradier; Intrinio; ORATS | Business plan with display rights | Individual: Starter $29 (15-min delayed), Developer $79, Advanced $199. Business: contact sales. | Trade-level tape (what "sweep" alerts need) is a different cost class, usually thousands per month plus exchange fees. The desk does not need it for its day-total posture. |
| Financial statements | SEC EDGAR XBRL `companyfacts` API | Free, public domain | $0 | US filers only. Requires a `User-Agent` header and stays under 10 requests per second. Foreign issuers that file 20-F (TSM) are covered; issuers with no SEC filing (SK hynix) are not. |
| Consensus estimates (forward EPS, forward revenue, analyst counts) | Financial Modeling Prep, Intrinio, Benzinga, Zacks via a vendor; Massive Financials & Ratios | Business | Massive Financials & Ratios $29/mo individual; business pricing not published | Filters 1 to 3 of the 5-metric framework depend on this. The cheapest honest move is to drop those three filters until a licensed source exists. |
| Headlines | Massive news (included in stock plans), Benzinga, Finnhub | Business | Not published | Only headline text and link; the full article stays on the publisher's site. |
| Economic calendar | Trading Economics API (paid); or the BLS, BEA, and Federal Reserve release schedules (free, public) | n/a | $0 to build from public schedules | The hand-kept CSV already carries the high-importance rows. |
| Index constituents for the S&P 500 and Nasdaq 100 heatmaps | S&P Dow Jones Indices and Nasdaq license constituent lists commercially; ETF holdings files (SPY, QQQ) are public but carry their own redistribution terms | Verify | Not published | Or keep only the Desk-universe heatmap and drop the two index maps. |
| Fed odds | Polymarket public API | Verify | $0 | Written confirmation with attribution. |
| Chart engine | TradingView Lightweight Charts | Apache-2.0 | $0 | Keep the logo and the footer credit. |

Rough monthly data bill for a small paid product: the honest number is
"contact sales," because every vendor prices customer-facing display
separately. Expect low hundreds per month at the small end from a vendor that
sells delayed display rights, and $2,500 or more per month on Massive's
published business tier. That range decides whether the desk is a hobby that
pays for itself or a business. See the break-even math in
`docs/MONETIZATION.md`.

## Order of operations

1. Decide the product's posture: 15-minute-delayed swing desk, or real-time.
   Real-time multiplies the vendor bill and adds per-user exchange fees.
2. For each row marked **Blocked**, get written display rights from a vendor
   or drop the feature. Do not keep a feature running on an unlicensed feed
   "for now."
3. Move the pipeline and the site off GitHub's free tiers.
4. Add a test that fails when the page or the fetcher calls any host outside
   an allowlist. Today the allowlist would fail on six hosts; the day it
   passes is the day the desk can charge.
5. Only then take a payment.
