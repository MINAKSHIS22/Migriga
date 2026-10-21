# Migriga Analytics: Data Dictionary, Cleaning Policy & KPI Definitions

## Source

| Item | Value |
|---|---|
| File | `data/raw/online_retail_09_10.csv` (copied unchanged from the supplied file; SHA-256 `a988e188…5fc4e8`) |
| Provenance | *Online Retail II*, UCI Machine Learning Repository, Year 2009-2010 sheet (525,461 records, the same count as the UCI sheet), with columns renamed `Invoice→InvoiceNo`, `Price→UnitPrice`, `Customer ID→CustomerID`. |
| Citation | Chen, D. (2012). *Online Retail II* [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D |
| Licence | CC BY 4.0 (attribution required, reuse permitted) |
| Nature | Historical transactions of a UK-based online gift retailer, 2009-12-01 to 2010-12-09, prices in GBP. **These are not Migriga sales or customers.** |

### Profile of the supplied file (computed by the ETL, run #4)

| Metric | Value |
|---|---|
| Records read / accepted / rejected / loaded | 525,461 / 525,461 / 0 / 525,461 |
| Distinct invoices / stock codes (raw) / products (normalised) | 28,816 / 4,631 / 4,480 |
| Distinct customers / countries | 4,383 / 40 |
| Blank `CustomerID` | 107,927 (20.5%) |
| Blank `Description` | 2,928 |
| Exact duplicate rows | 6,865 |
| Negative-quantity lines | 12,326 (10,205 cancellations + 2,121 stock adjustments) |
| Cancellation lines / invoices (`C` prefix) | 10,206 / 4,592 |
| Zero-price lines / negative-price lines | 3,687 / 3 (`A` bad-debt adjustments) |
| Non-merchandise lines (postage, fees, manual…) | 2,965 |
| Stock codes upper-cased (e.g. `85123a`) | 1,494 lines |
| Lines by type | SALE 511,565 · CANCELLATION 10,205 · STOCK_ADJUSTMENT 2,121 · ZERO_PRICE 1,566 · ADJUSTMENT 4 |

## Cleaning & validation rules (`etl/transform.py`)

| Rule | Policy |
|---|---|
| Raw data | Read as text, stored verbatim in `stg_raw_sales`. The CSV file is never written. |
| Whitespace | `InvoiceNo`, `StockCode`, `Country` trimmed. Descriptions collapse repeated whitespace. |
| Stock code | Upper-cased (`85123a` and `85123A` are the same product). The source value is kept in staging. |
| Rejections | Missing invoice, missing stock code, unparseable date, non-numeric / non-integer / zero quantity, non-numeric price. The row goes to `etl_rejected_rows` with its reason and raw JSON. (0 in the supplied file.) |
| Dates | `%m/%d/%Y %H:%M`, with an ISO-8601 fallback. |
| CustomerID | `13085` or `13085.0` becomes `13085`. Blank or non-numeric values map to the **anonymous member (customer_key 0)**. Identities are never invented. |
| Country | Blank values become `Unknown`. `Unspecified` (a real source value) is kept as-is. |
| Duplicates | The source has no line number. Lines identical on all 8 fields are numbered by occurrence. Every line is loaded (nothing is merged), and occurrences 2+ get `is_duplicate = 1`, which excludes them from all measures. |
| Line identity | `line_fingerprint = sha1(normalised fields + occurrence #)`, unique in the fact table. `source_row_number` gives traceability back to the CSV and to staging. |
| Product description | Canonical value = the most frequent non-empty description, preferring SALE lines. The number of variants is kept. |

### Line classification (`fact_sales.line_type`)

| Type | Rule | In sales measures? |
|---|---|---|
| `SALE` | Normal invoice, quantity > 0, price > 0 | Yes (gross) |
| `CANCELLATION` | Invoice starts with `C` (quantity < 0) | Yes (subtracted for net) |
| `STOCK_ADJUSTMENT` | Normal invoice with quantity < 0 (damages, write-offs, price 0) | No |
| `ZERO_PRICE` | Quantity > 0 at price 0 (samples, free items) | No |
| `ADJUSTMENT` | `A` invoices (bad debt), negative prices, or a C-invoice with positive quantity (1 line) | No |

`is_product = 0` for non-merchandise codes: `POST, DOT, M, C2, D, S, B, CRUK, ADJUST*, BANK CHARGES,
AMAZONFEE, TEST*, GIFT, GIFT_*_*` (postage, carriage, manual, discount, samples, fees, vouchers, test items).
These lines stay in the warehouse but are excluded from product sales and basket mining. The dashboard
reports their total separately.

## Star schema

**Fact grain:** one row in `fact_sales` per accepted source invoice line.

| Table | Key | Columns |
|---|---|---|
| `fact_sales` | `sales_key` (surrogate) | `date_key`, `product_key`, `customer_key`, `country_key` (FKs); `invoice_no` (degenerate dimension); `source_row_number`; `line_fingerprint` (UNIQUE); `invoice_datetime`; `invoice_hour`; **measures** `quantity`, `unit_price`, `line_amount` (= quantity × unit_price, signed); flags `line_type`, `is_product`, `is_cancellation`, `is_duplicate`; `etl_run_id` |
| `dim_date` | `date_key` (yyyymmdd) | `full_date`, `day`, `month`, `month_name`, `quarter`, `year`, `year_month`, `year_quarter`, `iso_week`, `weekday_num` (1=Mon), `weekday_name`, `is_weekend`. One row per calendar day in the data range. |
| `dim_product` | `product_key` | `stock_code` (natural key, UNIQUE), `description`, `description_variants`, `item_class` (MERCHANDISE / SERVICE_OR_FEE), `is_product`, `first_seen`, `last_seen` |
| `dim_customer` | `customer_key` | `customer_id` (UNIQUE; `__ANONYMOUS__` for key 0), `is_anonymous`, `primary_country` (country on most of the customer's lines), `first_invoice_date`, `last_invoice_date`. No demographics: none exist in the source. |
| `dim_country` | `country_key` | `country_name` (UNIQUE) |

Support tables: `stg_raw_sales` (raw text copy), `etl_run_log`, `etl_rejected_rows`, `warehouse_meta`
(`schema_version`, `data_version`, `loaded_at`).

```
dim_date ──┐
dim_product ──┤
               ├──< fact_sales >──┬── dim_customer (key 0 = anonymous)
               │                  └── dim_country
```

## KPI definitions (shared by the dashboard, OLAP and segmentation)

Eligible lines = `is_duplicate = 0 AND is_product = 1 AND line_type IN ('SALE','CANCELLATION')`.

| KPI | Definition |
|---|---|
| Gross sales | Σ `line_amount` on SALE lines |
| Cancelled value | Σ −`line_amount` on CANCELLATION lines. Cancellations cannot be linked reliably to the original invoice, so they count in the period of the cancellation. |
| Net sales | Gross sales − cancelled value |
| Orders | `COUNT(DISTINCT invoice_no)` over SALE lines (never invoice lines) |
| Invoice lines | Count of SALE lines |
| Units sold | Σ `quantity` on SALE lines |
| Average order value | Gross sales ÷ orders |
| Identified customers | Distinct `customer_key ≠ 0` with ≥ 1 SALE line |
| Repeat-customer rate | Identified customers with ≥ 2 distinct SALE invoices ÷ identified customers (within the filters) |
| Anonymous share | Gross sales with `customer_key = 0` ÷ gross sales |
| Products sold / active countries | Distinct product / country keys with SALE lines |

Revenue is **not profit**, because the source has no cost data.

## Analytical policies

| Analysis | Lines used |
|---|---|
| Sales reporting | Eligible lines as above. Anonymous purchases are included. |
| Market basket | One basket per invoice with ≥ 1 merchandise SALE line. Items = stock codes, counted once per basket. Cancellations, stock adjustments, zero-price lines, adjustments, fees and duplicates are excluded. |
| Segmentation | Identified customers only (`customer_key ≠ 0`), eligible merchandise lines. R = days from the last SALE to the reference date (day after the last SALE in the warehouse, 2010-12-10). F = distinct SALE invoices. M = own gross − own cancellations. Customers with no SALE or with net M ≤ 0 are excluded and counted. |
