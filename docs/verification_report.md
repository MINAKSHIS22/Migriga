# Final Verification Report: Migriga Analytics

Date: 2026-10-21 · Environment: macOS, Python 3.14.4, FastAPI 0.141, pandas 3.0.5, scikit-learn 1.9.1.

## 1. Audit of the original repository (before changes)

| Area | Finding |
|---|---|
| Stack | FastAPI (`server.py`) serving static HTML/CSS/JS, SQLite `migriga.db`, no build step, no `requirements.txt`, no tests |
| Working | Storefront, product list/detail/search, auth (salted SHA-256 + session tokens), admin portal (stats, orders, stock, customers), recommendation endpoints. All returned 200 in a smoke test. |
| Design system | `css/style.css` tokens: ivory/blush/rose-gold (#B07D62) / gold (#C5A059), Cinzel + Playfair Display + Plus Jakarta Sans. Admin portal uses a dark theme in an inline `<style>`. |
| Missing | Any warehouse, ETL, OLAP, Apriori, RFM/K-Means, analytics UI, tests, dependency manifest |
| Caveats | Seeded admin `admin@migriga.com / admin123` and admin page auto-login (pre-existing, left as is and documented). The recommendation model trains on separate Amazon beauty metadata and is unrelated to the retail CSV. |

## 2. Files added / modified

* **Modified:** `server.py` (auth deps moved to `backend/deps.py`, analytics router, `/analytics` route, warm-up);
  `admin.html` (inline CSS moved to `css/admin.css`, links/card to Analytics); `.gitignore`; `README.md`.
* **Added:** `etl/` (6 modules + `schema.sql`), `analytics/` (6 modules), `backend/analytics_api.py`, `backend/deps.py`,
  `analytics.html`, `css/admin.css`, `css/analytics.css`, `js/analytics/*.js` (7), `js/vendor/chart.umd.min.js`
  (Chart.js 4.4.1 from cdnjs), `data/raw/online_retail_09_10.csv` (byte-identical copy), `tests/` (7 files + fixture),
  `docs/` (6 files), `requirements.txt`, `.env.example`.

## 3. ETL (actual execution on the supplied CSV)

| Run | Trigger | Status | Read | Accepted | Rejected | Loaded | Seconds |
|---|---|---|---|---|---|---|---|
| 1 | CLI | FAILED (null-handling bug, fixed; no data committed) | – | – | – | – | – |
| 2 | CLI | SUCCESS | 525,461 | 525,461 | 0 | 525,461 | 36.1 |
| 3 | CLI | SKIPPED_UNCHANGED (same SHA-256) | 525,461 | 0 | 0 | 0 | 0.5 |
| 4 | Web UI (`web:admin@migriga.com`, force) | SUCCESS | 525,461 | 525,461 | 0 | 525,461 | 43.4 |

Post-load verification passed: 525,461 facts = accepted rows; Σ line_amount £9,539,484.63 matches the transform;
0 FK violations, 0 orphan keys, 0 duplicate fingerprints. While run 4 was in progress, a second run request
returned **409**, and the dashboard still answered from the previous committed state.

Warehouse tables: `fact_sales` 525,461 · `stg_raw_sales` 525,461 · `dim_date` 374 · `dim_product` 4,480 ·
`dim_customer` 4,384 · `dim_country` 40 · `etl_rejected_rows` 0.

## 4. Functionality verified in the browser (built-in browser, desktop 1280 px and mobile 375 px)

| Check | Result |
|---|---|
| Original storefront and admin portal load; admin shows the new Analytics link/card | ✔ |
| `/analytics` sign-in gate reuses the admin session; every tab is reachable by navigation | ✔ |
| Dashboard KPIs from the warehouse (net £9,557,223; 20,573 orders) | ✔ |
| Country filter (Germany → net £178,723) and product search picker (22423 cakestand) update the KPIs and charts | ✔ |
| OLAP: month → roll-up → quarter → year (2009 £778,343 / 2010 £8,778,880); click 2010 → quarters summing to the year; pivot quarter × weekday with reconciling totals; SQL shown | ✔ |
| Apriori defaults: 20,573 baskets, 1,415 itemsets, 943 rules in 1.3 s; changing parameters re-mines (Germany, 0.005); identical parameters hit the cache | ✔ |
| Segmentation k=4: 4,269 customers, silhouette 0.332, profiles, scatter, elbow, histograms, paginated table | ✔ |
| ETL page: real run started from the UI, progress polling, history updated | ✔ |
| DWM Lab: Apriori playground reproduces the textbook example; a concept button opens the OLAP preset | ✔ |
| No horizontal page overflow at 375 px on any analytics section | ✔ (fixed one caption overflow) |
| Brand: Migriga name, rose-gold/gold/charcoal palette, Cinzel/Playfair/Jakarta fonts | ✔ |
| Server stopped and restarted; analytics served from the persisted warehouse | ✔ |

CSV exports (OLAP, rules, itemsets, segments, per-cluster) were checked through the API tests, including
filtered content. They were not downloaded through the browser UI.

## 5. Tests

`python3 -m pytest -q` → **89 passed** (see `docs/testing.md`). Two genuine defects were found and fixed while
writing the tests: OLAP `limit=0` fell back to 500 instead of being rejected, and a test's pruning
assumption was wrong (replaced with a dataset that forces pruning).

## 6. Remaining limitations

* Dataset is a UK gift retailer's history, not Migriga data. There is no cost data (revenue ≠ profit) and no demographics.
* Cancellations cannot be matched to their original sale invoices. They count in the period they occur.
* Identical source lines are flagged as duplicates by policy. Some may be genuine repeated scans.
* K-Means silhouette at k=4 is moderate (0.33). Segments are descriptive partitions.
* Background jobs run in threads inside the web process. A server restart loses in-memory job results
  (they are recomputed on demand). The ETL itself is crash-safe.
* The seeded admin credentials and admin auto-login are pre-existing development conveniences and should be
  changed before deployment.
* The existing recommendation engine was not modified and does not use the warehouse.

## 7. UI/UX update: light theme and simplified navigation (2026-10-21)

* **Changed files:** `analytics.html` (new sidebar shell; no longer loads `css/admin.css`), `css/analytics.css`
  (rewritten as a token-based light theme), `js/analytics/core.js` (router, light chart theme, page helpers,
  staged "Apply filters" bar, chart resizing), `dashboard.js` (rewritten), new `sales.js` and `products.js`
  (detail that used to sit on the dashboard), `olap.js`, `basket.js`, `segmentation.js`, `etl.js` and `lab.js`
  (restructured with progressive disclosure). Backend, ETL, warehouse and analytics code are unchanged.
* **Verified in the browser** (1440×900 desktop and 375×812 mobile):
  * All 8 sidebar routes load, and the active link is highlighted.
  * Mobile menu opens and closes, and closes after navigation.
  * Dashboard KPIs and insights recompute after "Apply filters" (Jun–Aug 2010: £1,947,711; 4,521 invoices).
  * OLAP roll-up (2009 £778,343 / 2010 £8,778,880), drill-down (quarters sum to 2010), dice (France +
    Germany), pivot, swap and slice (Friday) all run real queries.
  * Apriori reruns with new thresholds (support 0.02 → 331 itemsets, 37 rules), and clicking a rule
    explains it. Segment filter works, and all charts in collapsed panels render when opened.
  * Real forced ETL run from the new page succeeded (525,461 rows). Project Guide Apriori demo works.
  * No horizontal overflow at 375 px on any page, including after a desktop→mobile resize with all panels
    open (fixed stale chart canvas widths). No JavaScript errors in the console.
* **Tests:** `python3 -m pytest -q` → 89 passed. There is no frontend build step (plain HTML/CSS/JS);
  every analytics JS file passes a syntax check.
* CSV export buttons call the same endpoints as before; their content is covered by the API tests, and the
  files were not downloaded through the browser.
