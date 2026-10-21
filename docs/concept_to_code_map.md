# Concept-to-Code Map

The same table is shown in the app under **Project Guide → Concept-to-code map**.

| Concept | Source file | Function / object | API endpoint | Tables / artefacts | UI page |
|---|---|---|---|---|---|
| Data warehouse | `etl/schema.sql`, `analytics/warehouse.py` | `connect()` (read-only) | `GET /api/analytics/overview` | all `dim_*`, `fact_sales` | Data Warehouse & ETL |
| Extract | `etl/extract.py` | `extract()`, `file_sha256()` | `POST /api/analytics/etl/run` | `stg_raw_sales` | Data Warehouse & ETL |
| Transform / cleaning | `etl/transform.py` | `transform()`, `classify_lines()`, `normalize_customer_id()`, `parse_dates()` | `POST /api/analytics/etl/run` | `etl_rejected_rows` | Data Warehouse & ETL |
| Load, rerun safety, rollback | `etl/load.py`, `etl/lock.py` | `load()`, `verify()`, `ETLLock` | `POST /api/analytics/etl/run` | `fact_sales` (`UNIQUE line_fingerprint`), `warehouse_meta` | Data Warehouse & ETL |
| ETL orchestration (CLI) | `etl/run_etl.py` | `run_etl()`, `main()` | — (`python -m etl.run_etl`) | `etl_run_log` | — |
| ETL monitoring | `backend/analytics_api.py` | `etl_status()`, `etl_rejected()` | `GET /api/analytics/etl/status`, `GET /api/analytics/etl/rejected` | `etl_run_log`, `etl_rejected_rows` | Data Warehouse & ETL |
| Star schema | `etl/schema.sql` | — | — | `fact_sales`, `dim_date`, `dim_product`, `dim_customer`, `dim_country` | Data Warehouse & ETL, Project Guide |
| Shared sales policy | `analytics/warehouse.py` | `ELIGIBLE_SALES`, `build_filters()` | all analytics endpoints | — | all |
| Roll-up / drill-down | `analytics/olap.py`, `js/analytics/olap.js` | `TIME_HIERARCHY`, `roll_up_level()`, `drill_down_level()`, `rollUp()`, `drillDown()` | `POST /api/analytics/olap` | `fact_sales ⋈ dim_date` | OLAP Explorer |
| Slice / dice | `analytics/olap.py` | `_where()`, `build_filters()` | `POST /api/analytics/olap` | `fact_sales ⋈ all dims` | OLAP Explorer |
| Pivot | `analytics/olap.py`, `js/analytics/olap.js` | `run_query()` (pivot mode), `pivot()` | `POST /api/analytics/olap` | `fact_sales ⋈ all dims` | OLAP Explorer |
| OLAP export | `analytics/olap.py` | `to_csv_rows()` | `POST /api/analytics/olap/export` | — | OLAP Explorer |
| Basket construction | `analytics/market_basket.py` | `load_baskets()` | `POST /api/analytics/basket/jobs` | `fact_sales ⋈ dim_product` | Market Basket |
| Apriori | `analytics/market_basket.py` | `apriori()` | `POST /api/analytics/basket/jobs`, `POST /api/analytics/lab/apriori-demo` | — | Market Basket, Project Guide |
| Support / confidence / lift | `analytics/market_basket.py` | `association_rules()` | `GET /api/analytics/jobs/{id}`, `GET /api/analytics/basket/{id}/export` | — | Market Basket |
| RFM features | `analytics/customer_segmentation.py` | `compute_rfm()`, `eligibility()` | `POST /api/analytics/segmentation/jobs` | `fact_sales ⋈ dim_customer` | Customer Segments |
| K-Means | `analytics/customer_segmentation.py` | `prepare_features()`, `fit_kmeans()`, `describe_clusters()` | `POST /api/analytics/segmentation/jobs` | `data/processed/segmentation_model.json` | Customer Segments |
| Cluster evaluation | `analytics/customer_segmentation.py` | `silhouette()`, elbow loop in `segment()` | `GET /api/analytics/jobs/{id}` | — | Customer Segments |
| Segment export | `backend/analytics_api.py` | `segmentation_export()` | `GET /api/analytics/segmentation/{id}/export?cluster=` | — | Customer Segments |
| Dashboard KPIs & insights | `analytics/dashboard.py` | `get_dashboard()`, `build_insights()` | `GET /api/analytics/dashboard` | `fact_sales ⋈ all dims` | Dashboard, Sales Analysis, Products & Countries |
| Background jobs & caching | `analytics/jobs.py`, `analytics/warehouse.py` | `JobManager`, `ResultCache`, `cache_token()` | `GET /api/analytics/jobs/{id}` | `warehouse_meta.data_version` | Market Basket, Segmentation, ETL |
| Access control | `backend/deps.py` | `require_admin()` | all `/api/analytics/*` | `users`, `sessions` (migriga.db) | sign-in gate |
