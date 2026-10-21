# Testing

```bash
python3 -m pytest -q
```

Tests never touch the real warehouse or write to `migriga.db`. Each test builds a throw-away warehouse from
`tests/fixtures/sample_retail.csv` in a temp directory, selected through `MIGRIGA_SOURCE_CSV`,
`MIGRIGA_WAREHOUSE_PATH` and `MIGRIGA_MODEL_PATH`. `tests/test_real_warehouse.py` adds consistency checks on
the real warehouse and is skipped if that warehouse has not been built.

| File | Covers |
|---|---|
| `test_data_quality.py` | required columns, missing/empty file, BOM, raw file unchanged, CustomerID normalisation, description cleaning, date parsing, line classification, rejection reasons, duplicate flagging, deterministic fingerprints, canonical descriptions, dimension members |
| `test_etl.py` | initial load counts, referential integrity, unchanged-source skip, forced rerun without duplicate facts and with stable surrogate keys, UNIQUE fingerprint constraint, changed-source refresh, rollback on failure, missing source logged as FAILED, rejected-row log, concurrent-run lock, stale-lock recovery, interrupted-run marking |
| `test_olap.py` | monthly aggregation, all measures, roll-up = sum of children, drill-down with slices, slice, dice, customer filter, pivot cells/totals, pivot swap, empty result, parameter validation (incl. injection attempts), bound parameters |
| `test_market_basket.py` | textbook (Tan et al.) itemsets and rule metrics, brute-force cross-check on random data, thresholds, max_len, pruning trace, empty input, parameter validation, warehouse basket construction, mining on the warehouse, minimum-supporting-baskets guard |
| `test_segmentation.py` | distinct-invoice frequency, net monetary, reference date, eligibility exclusions, log + z-score scaling, feature validation, k validation, insufficient data, seeded reproducibility, silhouette edge cases, warehouse RFM values, model persistence |
| `test_api.py` | admin-only access (403), 503 without a warehouse, overview schema, dashboard values equal direct SQL, filters change results, OLAP endpoint + CSV export, real Apriori job + caching + export, segmentation job + filtered export, safe job errors, ETL status and a web-triggered run, Lab demo, existing storefront/admin/static routes still work |
| `test_real_warehouse.py` | every raw record loaded or rejected, FK integrity, unique fingerprints, classification consistency, net = gross − cancelled |

## Hand-computed fixture expectations

`tests/fixtures/sample_retail.csv` has 22 records: 3 invalid (bad quantity, bad date, missing stock code),
1 exact duplicate, 1 postage line, 1 cancellation, 1 stock adjustment, 1 zero-price sample, 1 bad-debt
adjustment, 4 anonymous lines, a lower-case stock code and a `17850.0` CustomerID.

* Gross = 177.43, cancelled = 2.55, net = 174.88, orders = 6, lines = 13, units = 49, identified customers = 3
* Monthly net: 2009-12 = 63.58, 2010-01 = 58.62, 2010-03 = 52.68. France gross = 32.28.
* Baskets: {85123A,71053,84406B}, {85123A,71053}, {22423,85123A}, {22423,71053}, {22423,85123A}, {71053,85123A}
  → with min support 2/6: 71053 → 85123A has confidence 0.75 and lift 0.9.
* RFM (reference date 2010-03-03): 17850 → R 2, F 2, M 100.99; 13047 → R 91, F 1, M 5.94; 12583 → R 1, F 2, M 32.28.

## Latest results

`python3 -m pytest -q` → **89 passed** (85 fixture-based + 4 on the real warehouse).
