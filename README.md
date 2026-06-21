# NSE Fundamental Analysis — Enterprise Screener

A pure fundamental-analysis screener for NSE-listed stocks: valuation ratios, profitability,
financial stability, multi-year growth trends, DCF/intrinsic value estimation, and
sector-relative peer comparison — across the Nifty 50, Nifty 500, or a custom watchlist.

> **No technical/price-action indicators.** This is fundamentals-only by design, per the
> original request: ratios, growth trends, balance-sheet strength, and intrinsic value.

---

## What this actually is (read before trusting the output)

This is a **research aid**, not a stock-picking oracle and not investment advice. Specifically:

- **Data source is `yfinance`**, an unofficial wrapper around Yahoo Finance. It has no SLA,
  rate-limits aggressively without warning, and has inconsistent field coverage — especially
  for banks/NBFCs (different statement structure than manufacturers) and recently-listed
  companies (short financial history).
- **The DCF and Graham Number models are built from 2–4 years of public data and generic
  assumptions** (an 11% discount rate, 4% terminal growth, by default). Real equity research
  spends days per company refining these inputs. Treat the output as "is this worth a closer
  look," not a price target.
- **A full Nifty 500 run on first use will be slow** (potentially 15–40+ minutes) because
  yfinance has no safe bulk-fetch endpoint for this much fundamental data — it's one
  ticker at a time, with deliberate jittered delays to avoid being rate-limited. A 6-hour
  on-disk cache makes subsequent runs much faster.
- **yfinance can and will fail on individual tickers.** The app isolates failures per-symbol
  (one bad ticker won't kill the whole run) and reports failures transparently rather than
  hiding them.

If you need institutional-grade reliability (guaranteed uptime, audited financials, real-time
data), you'd want a licensed data vendor (e.g., a paid NSE/BSE feed, Refinitiv, Bloomberg, or
a service like Tijori/Screener.in's API) behind this same scoring engine — see "Extending data
sources" below for how to swap that in without rewriting the analysis logic.

---

## Features

| Pillar | What it covers |
|---|---|
| **Valuation** (20 pts) | PE, PB, PEG — both absolute and sector-relative |
| **Profitability** (20 pts) | ROE, ROA, net margin, operating margin |
| **Stability** (20 pts) | Debt/Equity, current ratio, quick ratio (with sector-aware handling — banks/NBFCs aren't penalized for inherent leverage) |
| **Growth & Trend** (25 pts) | Multi-year revenue & net income CAGR, YoY growth consistency, operating margin trend direction |
| **Valuation Upside** (15 pts) | Blended intrinsic value (DCF + Graham Number + relative valuation) vs current price |

Every pillar score is shown separately in the deep-dive view — the total is never a black box.

**Three independent valuation models**, blended into a single fair-value range:
1. Two-stage DCF on Free Cash Flow
2. Graham Number (conservative intrinsic value formula)
3. Relative valuation (sector median PE/PB applied to the company's own EPS/Book Value)

**Universe options:** Nifty 50 (fast), Nifty 500 (full — slower, see above), or a custom
comma-separated symbol list.

**Sector peer comparison:** sector median multiples, percentile rank within sector, and
score rank within sector.

---

## Quick start

```bash
git clone <your-repo-url>
cd nse-fundamental-screener
pip install -r requirements.txt
streamlit run app/main.py
```

Then open the local URL Streamlit prints (usually `http://localhost:8501`).

### First run recommendation
Start with **Nifty 50** and a small `max_stocks` slider value to confirm everything works
in your environment before attempting a full Nifty 500 run.

---

## Project structure

```
nse-fundamental-screener/
├── app/
│   └── main.py                  # Streamlit entry point — run this
├── scripts/
│   └── export_daily.py          # Headless pipeline for scheduled/automated exports
├── utils/
│   ├── data_fetcher.py          # yfinance wrapper: retries, backoff, disk caching, universe loader
│   ├── trend_analysis.py        # Multi-year CAGR, growth consistency, margin trend
│   ├── valuation.py             # DCF, Graham Number, relative valuation, blending
│   ├── scoring_engine.py        # Five-pillar composite scoring (0-100)
│   ├── peer_comparison.py       # Sector medians, percentile ranks
│   └── exporter.py              # Converts results to the external JSON/CSV feed schema
├── data/
│   ├── nifty500_fallback.csv    # Static snapshot used only if the live NSE Indices fetch fails
│   ├── cache/                   # Runtime parquet cache (gitignored, regenerated automatically)
│   └── exports/                 # Daily JSON/CSV exports (committed — this is what external sites fetch)
├── .github/workflows/
│   └── daily_export.yml         # GitHub Action: runs the export daily, auto-commits the result
├── .streamlit/config.toml       # Theme & server defaults
├── requirements.txt
└── README.md
```

---

## How the Nifty 500 list is sourced

The app fetches the live constituent list from NSE Indices
(`niftyindices.com/IndexConstituent/ind_nifty500list.csv`) on each session (cached 24h).
If that endpoint is unreachable, rate-limited, or has changed format, it falls back to
`data/nifty500_fallback.csv` — a bundled static snapshot covering ~210 well-known large/mid-cap
constituents. **The fallback is not a complete, current Nifty 500 list** — refresh it
periodically from the official source if you rely on it, or treat a fallback-triggered run
as partial coverage.

---

## Extending data sources

The fetcher is built around an abstract `DataSource` interface in `utils/data_fetcher.py`.
To add another provider (e.g., an official NSE API, a paid vendor, or a different scraper):

1. Subclass `DataSource` and implement `fetch(self, symbol) -> FetchResult`.
2. Populate the same `FetchResult` fields (`info`, `financials`, `balance_sheet`, `cashflow`,
   `quarterly_financials`, `history`) so the rest of the pipeline (scoring, valuation, trends)
   works unmodified.
3. Pass your new source into `fetch_universe(symbols, source=YourSource())` in `app/main.py`.

This means you can swap or combine data sources (e.g., yfinance for price data, a paid API
for audited financials) without touching the scoring or valuation logic.

---

## Pushing this to GitHub

This directory is ready to become a git repo. From inside it:

```bash
git init
git add .
git commit -m "Initial commit: NSE fundamental screener"
git branch -M main
git remote add origin <your-empty-github-repo-url>
git push -u origin main
```

(I can't push to GitHub directly from this environment — no outbound network access — so
this is the one step you'll need to run yourself.)

---

## Exporting for external consumption (techno-fundamental combo)

If you have a **separate website doing technical analysis** and want to combine it with
this fundamental data, the recommended approach — given a different stack/host and no
shared database — is: **this repo publishes a daily JSON file; your other site fetches it
over plain HTTPS.** No API server, no database, no shared infrastructure required.

### How it works

```
Streamlit app / scheduled script  →  commits JSON to GitHub  →  your site fetches raw URL
```

1. **GitHub Actions runs daily** (`.github/workflows/daily_export.yml`, scheduled for
   after NSE market close) and writes `data/exports/latest.json` + `latest.csv`, then
   auto-commits them.
2. Your other website fetches the **raw file URL** directly:
   ```
   https://raw.githubusercontent.com/<your-username>/<your-repo>/main/data/exports/latest.json
   ```
3. Parse it, join on `symbol`, combine with your technical scores.

You can also run the export manually any time:
```bash
python scripts/export_daily.py --universe NIFTY500
# or, for a quick test:
python scripts/export_daily.py --universe NIFTY50
```
Or trigger the GitHub Action on demand from the repo's **Actions** tab ("Run workflow").

### JSON schema

```jsonc
{
  "schema_version": "1.0",
  "generated_at": "2026-06-21T18:00:00+00:00",   // UTC ISO 8601 — check freshness here
  "universe": "NIFTY500",
  "stock_count": 487,
  "data_source": "yfinance (Yahoo Finance, unofficial)",
  "disclaimer": "...",
  "stocks": {
    "RELIANCE": {
      "symbol": "RELIANCE",
      "company_name": "Reliance Industries Ltd.",
      "sector": "Energy",
      "industry": "Petroleum",
      "price": 2500.5,
      "ratios": {
        "pe": 24.3, "pb": 2.1, "roe_pct": 12.5,
        "debt_to_equity": 45.2, "profit_margin_pct": 8.3
      },
      "growth": {
        "revenue_cagr_pct": 11.2, "net_income_cagr_pct": 9.8,
        "margin_trend": "expanding",
        "revenue_growth_consistency_pct": 100.0, "years_of_data": 4
      },
      "valuation": {
        "dcf_fair_value": 2650.0, "graham_number": 2400.0,
        "blended_fair_value": 2700.0, "estimated_upside_pct": 8.0,
        "valuation_models_used": 3
      },
      "fundamental_score": {
        "total": 72, "rating": "🟢 BUY",
        "pillars": { "valuation": 14, "profitability": 12, "stability": 15, "growth": 20, "valuation_upside": 11 },
        "key_notes": ["Strong ROE", "Margins expanding"]
      }
    }
    // ...one entry per symbol, keyed for O(1) lookup
  }
}
```

Numeric fields are `null` (not `NaN`) when data was unavailable — this is valid JSON
that any standard parser handles cleanly. **Always check `generated_at`** in your
consuming code so a stale fetch (e.g. if the daily Action failed) is visible rather
than silently treated as current.

### Example fetch code

**Python:**
```python
import requests
data = requests.get(
    "https://raw.githubusercontent.com/<you>/<repo>/main/data/exports/latest.json"
).json()
reliance = data["stocks"]["RELIANCE"]
print(reliance["fundamental_score"]["total"], reliance["fundamental_score"]["rating"])
```

**PHP:**
```php
$json = file_get_contents("https://raw.githubusercontent.com/<you>/<repo>/main/data/exports/latest.json");
$data = json_decode($json, true);
echo $data["stocks"]["RELIANCE"]["fundamental_score"]["total"];
```

**JavaScript / Node:**
```javascript
const res = await fetch("https://raw.githubusercontent.com/<you>/<repo>/main/data/exports/latest.json");
const data = await res.json();
console.log(data.stocks.RELIANCE.fundamental_score.total);
```

### Combining with technical analysis (techno-fundamental score)

A simple combined score on your technical site might look like:
```python
combined_score = 0.5 * fundamental_data["fundamental_score"]["total"] + 0.5 * your_technical_score
```
Weight however makes sense for your strategy — the fundamental score is 0-100 by design
specifically so it's easy to blend with another 0-100 technical score.

### Important caveats for this approach

- **This is a daily snapshot, not real-time.** Fine for fundamentals (they don't move
  intraday), but don't expect this to update faster than once a day unless you change
  the Action's cron schedule and re-run more often (mind yfinance rate limits if you do).
- **`raw.githubusercontent.com` has no uptime SLA** — it's reliable in practice but not
  contractually guaranteed. For a public repo this is free; for a private repo you'd need
  to pass a GitHub token in the fetch request's `Authorization` header from your other site.
- **If you outgrow this** (need real-time, need write access from multiple services, need
  auth), migrate to a small Postgres/Supabase instance and point both apps at it — the
  `utils/` scoring logic doesn't change, only where the output is written/read.

---



- **Not investment advice.** Scores and "fair value" estimates are model outputs from limited
  public data, not recommendations.
- **yfinance reliability varies.** Expect some tickers to fail on any given run, especially
  during high-traffic periods or for very recently listed/delisted companies.
- **DCF is unreliable for financial-sector companies** (banks, NBFCs, insurers) since their
  cash flow statements don't map cleanly to the Free-Cash-Flow-to-Firm model. The app detects
  this and falls back to Graham Number / relative valuation instead, with a visible warning
  rather than a silently wrong number.
- **No technical analysis, sentiment data, or news-based signals** — this is deliberately
  fundamentals-only.
- **No real-time intraday pricing** — `currentPrice` from yfinance can lag by minutes.

---

## License

MIT — see `LICENSE`.
