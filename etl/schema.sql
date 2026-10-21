-- MIGRIGA Analytics Warehouse - Star Schema (SQLite)
-- Fact grain: one row per accepted source invoice line (see docs/data_dictionary.md).

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS warehouse_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- ---------------------------------------------------------------- Dimensions
CREATE TABLE IF NOT EXISTS dim_date (
    date_key      INTEGER PRIMARY KEY,          -- yyyymmdd smart key
    full_date     TEXT NOT NULL UNIQUE,         -- ISO yyyy-mm-dd
    day           INTEGER NOT NULL,
    month         INTEGER NOT NULL,
    month_name    TEXT NOT NULL,
    quarter       INTEGER NOT NULL,
    year          INTEGER NOT NULL,
    year_month    TEXT NOT NULL,
    year_quarter  TEXT NOT NULL,
    iso_week      INTEGER NOT NULL,
    weekday_num   INTEGER NOT NULL,             -- 1 = Monday ... 7 = Sunday
    weekday_name  TEXT NOT NULL,
    is_weekend    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_product (
    product_key          INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code           TEXT NOT NULL UNIQUE,  -- natural key (upper-cased source StockCode)
    description          TEXT NOT NULL,         -- canonical (most frequent) description
    description_variants INTEGER NOT NULL DEFAULT 0,
    item_class           TEXT NOT NULL,         -- MERCHANDISE | SERVICE_OR_FEE
    is_product           INTEGER NOT NULL,
    first_seen           TEXT,
    last_seen            TEXT
);

CREATE TABLE IF NOT EXISTS dim_customer (
    customer_key       INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id        TEXT NOT NULL UNIQUE,    -- source CustomerID; '__ANONYMOUS__' for key 0
    is_anonymous       INTEGER NOT NULL DEFAULT 0,
    primary_country    TEXT,
    first_invoice_date TEXT,
    last_invoice_date  TEXT
);

CREATE TABLE IF NOT EXISTS dim_country (
    country_key  INTEGER PRIMARY KEY AUTOINCREMENT,
    country_name TEXT NOT NULL UNIQUE
);

-- ---------------------------------------------------------------- Fact
CREATE TABLE IF NOT EXISTS fact_sales (
    sales_key         INTEGER PRIMARY KEY AUTOINCREMENT,
    date_key          INTEGER NOT NULL REFERENCES dim_date(date_key),
    product_key       INTEGER NOT NULL REFERENCES dim_product(product_key),
    customer_key      INTEGER NOT NULL REFERENCES dim_customer(customer_key),
    country_key       INTEGER NOT NULL REFERENCES dim_country(country_key),
    invoice_no        TEXT NOT NULL,            -- degenerate dimension
    source_row_number INTEGER NOT NULL,         -- 1-based record ordinal in the source CSV
    line_fingerprint  TEXT NOT NULL UNIQUE,     -- sha1(normalised fields + occurrence #)
    invoice_datetime  TEXT NOT NULL,
    invoice_hour      INTEGER NOT NULL,
    quantity          INTEGER NOT NULL,
    unit_price        REAL NOT NULL,
    line_amount       REAL NOT NULL,            -- quantity * unit_price (signed)
    line_type         TEXT NOT NULL CHECK (line_type IN
                        ('SALE','CANCELLATION','STOCK_ADJUSTMENT','ZERO_PRICE','ADJUSTMENT')),
    is_product        INTEGER NOT NULL,
    is_cancellation   INTEGER NOT NULL,
    is_duplicate      INTEGER NOT NULL,
    etl_run_id        INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_fact_date      ON fact_sales(date_key);
CREATE INDEX IF NOT EXISTS ix_fact_product   ON fact_sales(product_key);
CREATE INDEX IF NOT EXISTS ix_fact_customer  ON fact_sales(customer_key);
CREATE INDEX IF NOT EXISTS ix_fact_country   ON fact_sales(country_key);
CREATE INDEX IF NOT EXISTS ix_fact_invoice   ON fact_sales(invoice_no);
CREATE INDEX IF NOT EXISTS ix_fact_eligible  ON fact_sales(is_duplicate, is_product, line_type, date_key);

-- ---------------------------------------------------------------- Staging & ETL audit
CREATE TABLE IF NOT EXISTS stg_raw_sales (
    source_row_number INTEGER PRIMARY KEY,
    InvoiceNo   TEXT, StockCode TEXT, Description TEXT, Quantity TEXT,
    InvoiceDate TEXT, UnitPrice TEXT, CustomerID  TEXT, Country  TEXT,
    etl_run_id  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS etl_run_log (
    run_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at       TEXT NOT NULL,
    finished_at      TEXT,
    status           TEXT NOT NULL,             -- RUNNING | SUCCESS | SKIPPED_UNCHANGED | FAILED | INTERRUPTED
    triggered_by     TEXT,
    source_file      TEXT,
    source_sha256    TEXT,
    source_size      INTEGER,
    rows_read        INTEGER,
    rows_accepted    INTEGER,
    rows_rejected    INTEGER,
    rows_loaded      INTEGER,
    elapsed_seconds  REAL,
    quality_json     TEXT,
    warnings_json    TEXT,
    error_message    TEXT
);

CREATE TABLE IF NOT EXISTS etl_rejected_rows (
    rejected_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    etl_run_id        INTEGER NOT NULL REFERENCES etl_run_log(run_id),
    source_row_number INTEGER NOT NULL,
    reason            TEXT NOT NULL,
    raw_record_json   TEXT NOT NULL
);
