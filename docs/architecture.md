# Migriga Analytics: System Architecture

Migriga is a FastAPI + SQLite beauty storefront with an admin portal. Migriga Analytics extends it
with a separate analytical warehouse, a repeatable ETL pipeline, an OLAP engine, Apriori market-basket
mining and RFM/K-Means customer segmentation, all served through the same FastAPI app and presented
in the admin portal's dark rose-gold design.

## Components

```
                     ┌──────────────────────────── Browser ─────────────────────────────┐
                     │ welcome.html  login.html  index.html (store)  admin.html         │
                     │ analytics.html + js/analytics/*.js + Chart.js (js/vendor)        │
                     └───────────────┬──────────────────────────────┬───────────────────┘
                                     │ /api/*  (existing)           │ /api/analytics/*  (admin only)
                     ┌───────────────▼──────────────────────────────▼───────────────────┐
                     │ server.py (FastAPI)          backend/analytics_api.py (APIRouter)│
                     │ backend/deps.py: get_current_user / require_admin (shared)       │
                     │ backend/recommendation_engine.py (existing, unchanged)           │
                     └──────┬──────────────────────────────┬───────────────────┬────────┘
                            │                              │                   │
              ┌─────────────▼──────┐        ┌──────────────▼──────┐   ┌────────▼──────────────┐
              │ migriga.db          │        │ analytics/          │   │ analytics/jobs.py     │
              │ (operational: users,│        │  warehouse.py policy│   │ background worker pool│
              │ products, orders…)  │        │  olap.py            │   │ + result cache        │
              └─────────────────────┘        │  dashboard.py       │   └────────┬──────────────┘
                                             │  market_basket.py   │◄───────────┘
                                             │  customer_segmentation.py
                                             └──────────┬──────────┘
                                                        │ read-only connections
   data/raw/online_retail_09_10.csv ──► etl/ (extract → transform → load) ──► data/warehouse/migriga_warehouse.db
        (never modified)                  etl/run_etl.py, etl/lock.py              (star schema + staging + audit)
```

* **Operational store vs warehouse.** `migriga.db` keeps the store's users, products, orders and sessions.
  The warehouse is a separate file (`data/warehouse/migriga_warehouse.db`). Analytics code opens it
  read-only (`mode=ro`), and only the ETL writes to it.
* **Auth.** Every `/api/analytics/*` route depends on `require_admin` (the same session-token check used by
  the existing admin endpoints, moved into `backend/deps.py` so both share it).
* **Frontend.** `analytics.html` is a hash-routed single page with a grouped sidebar:
  Overview (`#dashboard`), Explore Data (`#sales`, `#products`, `#olap`), Data Mining (`#basket`, `#segments`),
  Data Management (`#etl`) and Help (`#lab`, the Project Guide). Each route is one module in `js/analytics/`,
  sharing `core.js` (API client, auth gate, router, chart theme, tables, filter bar, page helpers).
  The analytics section uses a **light theme** defined entirely by tokens on `.analytics-body` in
  `css/analytics.css`. These tokens are derived from Migriga's own tokens in `css/style.css`: ivory/cream
  surfaces, rose gold `#B07D62` as the accent, rose-gold-dark `#8E5840` for text-safe links, and the Cinzel /
  Playfair Display / Plus Jakarta Sans fonts. The admin portal keeps its dark theme (`css/admin.css`), which
  the analytics page no longer loads. Charts use the brand rose gold for single series and a validated,
  colour-blind-safe categorical palette on white for multi-series charts. Chart.js 4.4.1 is vendored in `js/vendor/`.
* **Progressive disclosure.** Each analytics page shows *What does this do?* and *What data is used?*, then
  only the essential controls, the main result and a plain-language interpretation. Advanced settings,
  metric definitions, SQL, model metrics and logs sit in `<details>` panels. Charts inside closed panels are
  drawn or resized when the panel opens.

## ETL workflow

1. **Lock.** `etl/lock.py` creates `<warehouse>.etl.lock` (O_EXCL + PID). A second run from the CLI or
   web fails with *"Another ETL run is already in progress"*, and a stale lock from a dead PID is removed.
2. **Audit row.** `etl_run_log` gets a `RUNNING` row. Any `RUNNING` rows left by a crashed process are
   marked `INTERRUPTED`.
3. **Extract** (`etl/extract.py`). This step detects the encoding (UTF-8 with BOM, or latin-1 fallback) and
   the delimiter, reads every column as text, validates the 8 required columns, records the SHA-256 and
   assigns `source_row_number`.
4. **Change detection.** If the SHA-256 equals the last successful run's and `--force` is not given, the run
   is logged as `SKIPPED_UNCHANGED` and nothing is written.
5. **Transform** (`etl/transform.py`). Parses and validates values, rejects unusable rows with a reason,
   classifies lines, flags duplicates, computes fingerprints and builds the dimension members. See
   `data_dictionary.md`.
6. **Load** (`etl/load.py`). Runs in **one `BEGIN IMMEDIATE … COMMIT` transaction**:
   upsert `dim_date`, `dim_product`, `dim_customer` (with the anonymous member, key 0) and `dim_country` on
   their natural keys, so surrogate keys stay stable. Then a **full refresh** of `fact_sales` (delete and
   insert, with `UNIQUE(line_fingerprint)` guarding against duplicate facts), a refresh of the
   `stg_raw_sales` raw copy, rejected rows into `etl_rejected_rows`, and `warehouse_meta.data_version = run_id`.
   Any exception rolls everything back.
7. **Verify.** Fact count = accepted rows, Σ`line_amount` = transform total, `PRAGMA foreign_key_check`,
   orphan-key LEFT JOINs and duplicate-fingerprint check. The results are stored in the run's `quality_json`.

**Changed input strategy:** a changed file triggers a full refresh of the facts in a single transaction.
Dimension rows are upserted and never deleted, so a product that disappears from a new source keeps its
key. This is standard dimension behaviour, and such a product has no facts. Readers keep seeing the
previous state until the commit (SQLite WAL).

## Performance & reliability

* Indexes on every fact foreign key, on `invoice_no`, and a composite `(is_duplicate, is_product, line_type, date_key)`.
* Dashboard queries run **in parallel** on separate read-only connections. The full 525k-row
  dashboard takes about 1.7 s uncached; OLAP queries take about 0.4 s.
* `analytics.warehouse.ResultCache` (LRU) caches dashboard/OLAP results keyed by
  `(warehouse path, data_version, params)`, so a new ETL load automatically invalidates them.
* Apriori, K-Means and ETL run as **background jobs** (`analytics/jobs.py`, 2 worker threads, at most 4 active).
  Identical requests reuse the running or finished job. Clients poll `GET /api/analytics/jobs/{id}` for
  progress. Jobs are cleared after a successful ETL.
* On startup the server pre-computes the default dashboard and the k=4 segmentation in the background.
* Errors: a missing warehouse returns `503 warehouse_unavailable`, bad parameters return `422 invalid_parameter`,
  a concurrent ETL returns `409`, and too many jobs returns `429`. Stack traces go only to the server log.

## Security notes

* All analytics endpoints require an admin session. ETL runs and mining jobs are therefore restricted to admins.
* SQL is built only from whitelisted dimension/measure expressions; every user value is a bound parameter.
* Paths come from configuration or environment variables, never from requests. No upload endpoint exists.
* CSV exports neutralise spreadsheet formula injection (`=`, `+`, `-`, `@` prefixes).
* Customer-level output contains only the source's anonymised numeric CustomerID and country.
* **Existing limitation (not introduced here):** `backend/database.py` seeds `admin@migriga.com / admin123`
  and `admin.html` auto-signs in with it for convenience. Change these before any real deployment.
  The new analytics page does not auto-sign in; it shows the admin sign-in form.
