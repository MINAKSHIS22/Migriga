# Data Warehousing & Data Mining Concepts in Migriga Analytics

Each concept below runs in the application. The UI page and source file are given for each one.

## 1. Data warehouse
A subject-oriented, integrated, time-variant, non-volatile store for analysis, kept apart from the
operational database. Migriga keeps the operational store in `migriga.db` and the warehouse in
`data/warehouse/migriga_warehouse.db`. Analytics opens the warehouse read-only, and only the ETL writes to it.
**UI:** ETL & Data Quality. **Code:** `etl/schema.sql`, `analytics/warehouse.py`.

## 2. ETL and data quality
Extract → Transform → Load with logging, rejection reasons, duplicate flags, change detection (SHA-256),
a single-transaction load, post-load verification and a cross-process lock.
**UI:** ETL & Data Quality (Run ETL button calls `etl.run_etl.run_etl` in a background job).
**Code:** `etl/*.py`. Details: `architecture.md`, `data_dictionary.md`.

## 3. Facts, dimensions and the star schema
`fact_sales` (grain: one accepted invoice line; additive measures quantity and line_amount) joins to
`dim_date`, `dim_product`, `dim_customer` and `dim_country` through surrogate keys. `invoice_no` is a
degenerate dimension. Unknown customers map to an explicit member (key 0) instead of NULL.

## 4. OLAP roll-up and drill-down
The time hierarchy is year › quarter › month › day (`analytics/olap.py: TIME_HIERARCHY`).
*Roll-up* moves the GROUP BY to a coarser level. *Drill-down* fixes a member (adds a slice such as
`Year = 2010`) and groups by the next finer level. Example on the real data: 2010 net sales of £8,778,880
break down into Q1 £1.88M, Q2 £1.91M, Q3 £2.12M and Q4 £2.86M, and the quarters sum exactly to the year.

## 5. Slice, dice and pivot
*Slice* fixes one dimension: `CAST(dim_expr AS TEXT) = ?`. *Dice* combines filters on date range, countries,
products and customers. *Pivot* groups by two dimensions and lays one out as columns (`run_query` pivot
mode). The ⇄ button swaps rows and columns. The generated SQL and bound parameters are shown under every result.

## 6. Association-rule mining (Apriori)
Level-wise generation of frequent itemsets:
1. L1 = items with support ≥ min_support.
2. Ck = join pairs of L(k−1) itemsets that share their first k−2 items.
3. **Prune**: drop any candidate with an infrequent (k−1)-subset (the Apriori / downward-closure property).
4. Count the support of the remaining candidates and keep those ≥ min_support (Lk).
5. From every frequent itemset I, emit rules A → I∖A that meet the confidence and lift thresholds.

Support counting uses vertical bitmaps (bit i = basket i contains the item; support = popcount of the
AND of the item bitmaps). This speeds up counting without changing which itemsets Apriori finds. The tests
cross-check the output against brute-force enumeration.
**UI:** Market Basket; DWM Lab playground (step-by-step trace). **Code:** `analytics/market_basket.py`.

## 7. Support, confidence, lift
* support(X) = |baskets ⊇ X| / |baskets|
* confidence(A→C) = support(A∪C) / support(A)
* lift(A→C) = confidence(A→C) / support(C). A value of 1 means independence, above 1 a positive association.

A high lift shows co-occurrence, **not causation**. On the real data, for example, the three colours of the
"35809A/35810A/35811A" product family reach lift ≈ 204 because they are sold as a set.

## 8. RFM analysis
Recency, Frequency (distinct invoices) and Monetary (gross − own cancellations), computed for identified
customers against a fixed reference date (the day after the last purchase: 2010-12-10), not today's date.

## 9. K-Means clustering
Features: log1p(R, F, M) → StandardScaler. Model: `KMeans(n_clusters=k, n_init=10, random_state=seed)`.
Clusters are numbered by median monetary value (highest first). Each one is described only by how its
median R/F/M compares with the overall median (±15% counts as "typical"). The tool assigns no marketing
labels such as "VIP". The fitted scaler and centres are saved to `data/processed/segmentation_model.json`.

## 10. Evaluation and limitations
* **Silhouette** (−1…1) and **inertia (WCSS)** are reported for the chosen k and for k = 2…10. On the real
  data k = 2 has the highest silhouette (0.42) and k = 4 scores 0.33, which is moderate separation. RFM
  data seldom forms well-separated clusters, so treat the segments as a descriptive partition, not as natural groups.
* Silhouette is undefined with fewer than 2 clusters or with one customer per cluster. The API reports why.
* **Dataset**: a single UK gift retailer, 2009–2010. It is not Migriga's data, and patterns do not transfer to
  a beauty store. There is no cost data (so no profit) and no demographics.
* **Cancellations** cannot be matched reliably to their original invoices. They reduce net sales in the
  period they occur, and they reduce each customer's own monetary value.
* **Duplicates**: identical lines may be genuine repeated scans. They are kept but excluded by policy, and
  the policy is disclosed.
* **Anonymous purchases** (≈ 12% of gross) count in sales but not in customer metrics or segmentation.
* Apriori with very low support explodes combinatorially. The UI enforces min_support ≥ 0.003, a
  3,000,000-candidate cap, and at least 5 supporting baskets per pattern.
* The existing **beauty recommendation engine** (`backend/recommendation_engine.py`) is trained on a different
  dataset (Amazon All Beauty metadata). It is unchanged and does not use the retail warehouse.
