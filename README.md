# Migriga
Migriga Beauty: a modern beauty &amp; cosmetics e-commerce website featuring a curated product collection, product browsing, and a clean, user-friendly shopping experience.

The site now includes **Migriga Analytics**, a Data Warehousing & Data Mining (DWM) module inside the admin
portal: a star-schema warehouse, a repeatable ETL pipeline, an OLAP Explorer, Apriori market-basket analysis,
RFM + K-Means customer segmentation, a sales dashboard and a DWM Lab that maps each concept to its code.

> **Data notice.** Migriga Analytics uses historical transactions of a UK-based online gift retailer
> (Dec 2009 – Dec 2010, GBP): Chen, D. (2012). *Online Retail II* [Dataset]. UCI Machine Learning Repository.
> https://doi.org/10.24432/C5CG6D, licensed CC BY 4.0. **These are not Migriga sales or customers.**

## Features

| Area | What it does |
|---|---|
| Storefront (`/store`) | Product catalogue, search, filters, bag, checkout, orders (unchanged) |
| Admin portal (`/admin`) | KPIs, orders, inventory, customers, beauty dataset, recommendation model (unchanged; now links to Analytics) |
| **Migriga Analytics** (`/analytics`, admin only) | Light, Migriga-branded interface with a grouped sidebar: |
| · Overview → Dashboard | Four KPIs (eligible sales value, invoices, units, identified customers), sales over time, top products, top countries, three computed insights, "Explore more" links; date filter |
| · Explore Data → Sales Analysis | Monthly net sales, weekday/hour patterns, cancellations, customer purchase frequency, monthly table |
| · Explore Data → Products & Countries | Top products by value and quantity, sales by country, country and product tables |
| · Explore Data → OLAP Explorer | Plain-language operations: Summarise (roll-up), More detail (drill-down), One value only (slice), Several filters (dice), Compare side by side (pivot); CSV export; SQL under Technical details |
| · Data Mining → Market Basket (Apriori) | Support / confidence / lift controls, top rules with a plain-language explanation of the selected rule, itemsets, charts, CSV export (background job) |
| · Data Mining → Customer Segments (RFM) | RFM explained, segment cards and sizes, interpretation; RFM charts, customer table, silhouette/elbow under expandable panels |
| · Data Management → Data Warehouse & ETL | Status summary (source, last run, rows processed/rejected, warehouse checks), real ETL runs; quality profile, classification, tables, run history and rejected rows in panels |
| · Help → Project Guide | How the parts fit together, a viva walkthrough, the ten DWM concepts with links, Apriori step-by-step demo, KPI definitions, concept-to-code map |

Every page follows the same pattern: *What does this do?* → *What data is used?* → essential controls → results → interpretation → expandable technical details.

## Project structure

```
Migriga/
├── server.py                 # FastAPI app (existing) + analytics router + /analytics page
├── index.html  admin.html  login.html  welcome.html  analytics.html
├── css/  style.css  components.css  responsive.css  admin.css (dark admin theme)  analytics.css (light analytics theme)
├── js/   app.js products.js store.js ui.js   vendor/chart.umd.min.js
│        analytics/ core.js dashboard.js sales.js products.js olap.js basket.js segmentation.js etl.js lab.js
├── backend/  database.py auth.py deps.py recommendation_engine.py train_recommendation.py analytics_api.py
├── etl/      config.py extract.py transform.py load.py lock.py run_etl.py schema.sql
├── analytics/ warehouse.py olap.py dashboard.py market_basket.py customer_segmentation.py jobs.py
├── data/raw/online_retail_09_10.csv      # source (never modified)
├── data/warehouse/migriga_warehouse.db   # built by the ETL (git-ignored)
├── data/processed/                       # saved K-Means model metadata (git-ignored)
├── tests/    pytest suite + fixtures/sample_retail.csv
└── docs/     architecture.md data_dictionary.md dwm_concepts.md concept_to_code_map.md testing.md
```

## Setup

**Prerequisites:** Python 3.10+ (verified on 3.14). No Node.js build step is needed.

```bash
cd Migriga
```

```bash
python3 -m pip install -r requirements.txt
```

**Dataset placement:** the ETL reads `data/raw/online_retail_09_10.csv` (already in place). To use another
location, set `MIGRIGA_SOURCE_CSV` (see `.env.example`; variables are read from the environment).

**Build the warehouse (ETL):** this takes about 40 s for 525k rows.

```bash
python3 -m etl.run_etl
```

Rerunning is safe. An unchanged source is skipped, `--force` rebuilds, and a changed file is fully refreshed in
one transaction. You can also run the ETL from **Analytics → Data Warehouse & ETL → Run ETL**.

**Run the app** (backend and frontend are served together):

```bash
python3 server.py
```

Then open http://127.0.0.1:3000 (Windows users can still double-click `run_website.bat`).

| Page | URL |
|---|---|
| Get started / login | http://127.0.0.1:3000/ |
| Storefront | http://127.0.0.1:3000/store |
| Admin portal | http://127.0.0.1:3000/admin |
| Migriga Analytics | http://127.0.0.1:3000/analytics (or "Migriga Analytics ↗" in the admin header). Routes: `#dashboard`, `#sales`, `#products`, `#olap`, `#basket`, `#segments`, `#etl`, `#lab` |

Analytics requires an admin account. The seeded development admin is `admin@migriga.com` / `admin123`
(created by `backend/database.py`; change it for any real deployment).

**Run the tests:**

```bash
python3 -m pytest -q
```

## Verified results (supplied CSV)

* ETL: 525,461 rows read, 525,461 accepted, 0 rejected, 525,461 loaded; verification passed
  (row count, Σ line_amount, FK integrity, unique fingerprints). 6,865 duplicate lines flagged; 10,205
  cancellation lines; 2,965 non-merchandise lines.
* Warehouse: `fact_sales` 525,461 · `dim_date` 374 · `dim_product` 4,480 · `dim_customer` 4,384 (incl. anonymous) · `dim_country` 40.
* Dashboard (all data): net sales £9,557,223 · gross £9,804,647 · cancelled £247,424 · 20,573 orders · AOV £476.58.
* Apriori (support 0.01, confidence 0.3, max size 3): 20,573 baskets, 1,415 frequent itemsets, 943 rules, about 1.3 s.
* Segmentation (k = 4, seed 42): 4,269 customers clustered (45 excluded), silhouette 0.332.
* Tests: 89 passed.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Analytics shows "The data warehouse is not ready" | Run `python3 -m etl.run_etl` or use the ETL page. |
| `ETL FAILED: Source file not found` | Put the CSV in `data/raw/` or set `MIGRIGA_SOURCE_CSV`. |
| "Another ETL run is already in progress" | Wait for it to finish. A lock left by a crashed run is removed automatically. |
| Apriori: "Minimum support is too low" / "too few baskets" | Raise min support (each pattern must occur in ≥ 5 baskets; candidate cap 3,000,000). |
| Analytics asks to sign in | Sign in with an admin account; customer accounts are refused. |
| Port 3000 in use | Stop the other process, or run `python3 -m uvicorn server:app --port 3001`. |
| `ModuleNotFoundError` | Run commands from the `Migriga/` folder after installing `requirements.txt`. |

More detail: [docs/architecture.md](docs/architecture.md), [docs/data_dictionary.md](docs/data_dictionary.md),
[docs/dwm_concepts.md](docs/dwm_concepts.md), [docs/concept_to_code_map.md](docs/concept_to_code_map.md),
[docs/testing.md](docs/testing.md), [docs/verification_report.md](docs/verification_report.md).
