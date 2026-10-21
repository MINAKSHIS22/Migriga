# MIGRIGA Analytics - LOAD stage
# Writes dimensions, facts, staging rows and rejected rows into the warehouse inside a
# single transaction. Strategy (documented in docs/architecture.md):
#   * Dimensions are UPSERTED on their natural key, so surrogate keys stay stable across runs.
#   * fact_sales is a FULL REFRESH of the current source inside the same transaction; the
#     UNIQUE(line_fingerprint) constraint makes duplicate fact loading impossible.
#   * Any exception rolls the whole load back, leaving the previous warehouse state intact.
import json
import os
import sqlite3
from datetime import datetime

import pandas as pd

from .transform import ANONYMOUS_CUSTOMER_ID

SCHEMA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
SCHEMA_VERSION = "1"
BATCH = 50_000


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def connect(path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.execute("INSERT OR IGNORE INTO warehouse_meta(key, value) VALUES ('schema_version', ?)", (SCHEMA_VERSION,))


def mark_interrupted_runs(conn: sqlite3.Connection) -> int:
    """Runs left in RUNNING state by a crashed/killed process (only called while holding the ETL lock)."""
    cur = conn.execute(
        "UPDATE etl_run_log SET status='INTERRUPTED', finished_at=?, "
        "error_message=COALESCE(error_message, 'Process ended before the run completed; no changes were committed.') "
        "WHERE status='RUNNING'", (now_iso(),))
    return cur.rowcount


def last_successful_run(conn: sqlite3.Connection):
    row = conn.execute(
        "SELECT * FROM etl_run_log WHERE status='SUCCESS' ORDER BY run_id DESC LIMIT 1").fetchone()
    return dict(row) if row else None


def start_run(conn: sqlite3.Connection, triggered_by: str, source_file: str) -> int:
    cur = conn.execute(
        "INSERT INTO etl_run_log(started_at, status, triggered_by, source_file) VALUES (?, 'RUNNING', ?, ?)",
        (now_iso(), triggered_by, source_file))
    return int(cur.lastrowid)


def finish_run(conn: sqlite3.Connection, run_id: int, status: str, **fields) -> None:
    fields = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in fields.items()}
    fields["status"] = status
    fields["finished_at"] = now_iso()
    cols = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE etl_run_log SET {cols} WHERE run_id = ?", (*fields.values(), run_id))


def _records(df: pd.DataFrame, cols: list):
    sub = df[cols].astype(object).where(df[cols].notna(), None)
    return list(sub.itertuples(index=False, name=None))


def load(conn: sqlite3.Connection, run_id: int, raw: pd.DataFrame, tr, fail_after_facts: bool = False) -> int:
    """Loads one transformed source into the warehouse atomically. Returns fact rows loaded."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        # ---- dim_date
        conn.executemany(
            "INSERT INTO dim_date(date_key, full_date, day, month, month_name, quarter, year, year_month, "
            "year_quarter, iso_week, weekday_num, weekday_name, is_weekend) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(date_key) DO NOTHING",
            _records(tr.dates, ["date_key", "full_date", "day", "month", "month_name", "quarter", "year",
                                "year_month", "year_quarter", "iso_week", "weekday_num", "weekday_name",
                                "is_weekend"]))

        # ---- dim_product (upsert on natural key keeps product_key stable)
        conn.executemany(
            "INSERT INTO dim_product(stock_code, description, description_variants, item_class, is_product, "
            "first_seen, last_seen) VALUES (?,?,?,?,?,?,?) ON CONFLICT(stock_code) DO UPDATE SET "
            "description=excluded.description, description_variants=excluded.description_variants, "
            "item_class=excluded.item_class, is_product=excluded.is_product, "
            "first_seen=excluded.first_seen, last_seen=excluded.last_seen",
            _records(tr.products, ["stock_code", "description", "description_variants", "item_class",
                                   "is_product", "first_seen", "last_seen"]))

        # ---- dim_customer (key 0 = explicit anonymous / unknown member)
        conn.execute(
            "INSERT OR IGNORE INTO dim_customer(customer_key, customer_id, is_anonymous, primary_country) "
            "VALUES (0, ?, 1, NULL)", (ANONYMOUS_CUSTOMER_ID,))
        conn.executemany(
            "INSERT INTO dim_customer(customer_id, is_anonymous, primary_country, first_invoice_date, "
            "last_invoice_date) VALUES (?,0,?,?,?) ON CONFLICT(customer_id) DO UPDATE SET "
            "primary_country=excluded.primary_country, first_invoice_date=excluded.first_invoice_date, "
            "last_invoice_date=excluded.last_invoice_date",
            _records(tr.customers, ["customer_id", "primary_country", "first_invoice_date", "last_invoice_date"]))

        # ---- dim_country
        conn.executemany("INSERT OR IGNORE INTO dim_country(country_name) VALUES (?)",
                         [(c,) for c in tr.countries])

        product_keys = dict(conn.execute("SELECT stock_code, product_key FROM dim_product").fetchall())
        customer_keys = dict(conn.execute("SELECT customer_id, customer_key FROM dim_customer").fetchall())
        country_keys = dict(conn.execute("SELECT country_name, country_key FROM dim_country").fetchall())

        facts = tr.facts.copy()
        facts["product_key"] = facts["stock_code"].map(product_keys)
        facts["customer_key"] = facts["customer_id"].map(customer_keys).fillna(0).astype(int)
        facts["country_key"] = facts["country"].map(country_keys)
        if facts["product_key"].isna().any() or facts["country_key"].isna().any():
            raise RuntimeError("Dimension lookup failed for some fact rows.")
        facts["etl_run_id"] = run_id

        # ---- facts: full refresh of the current source
        conn.execute("DELETE FROM fact_sales")
        fact_cols = ["date_key", "product_key", "customer_key", "country_key", "invoice_no",
                     "source_row_number", "line_fingerprint", "invoice_datetime", "invoice_hour",
                     "quantity", "unit_price", "line_amount", "line_type", "is_product",
                     "is_cancellation", "is_duplicate", "etl_run_id"]
        sql = f"INSERT INTO fact_sales({', '.join(fact_cols)}) VALUES ({', '.join('?' * len(fact_cols))})"
        rows = _records(facts, fact_cols)
        for i in range(0, len(rows), BATCH):
            conn.executemany(sql, rows[i:i + BATCH])

        if fail_after_facts:  # test hook: proves the transaction rolls back
            raise RuntimeError("Simulated failure after fact insert")

        # ---- staging copy of the raw source (text, unchanged)
        conn.execute("DELETE FROM stg_raw_sales")
        raw_cols = ["source_row_number", "InvoiceNo", "StockCode", "Description", "Quantity",
                    "InvoiceDate", "UnitPrice", "CustomerID", "Country"]
        raw_rows = [(*r, run_id) for r in raw[raw_cols].itertuples(index=False, name=None)]
        for i in range(0, len(raw_rows), BATCH):
            conn.executemany(
                f"INSERT INTO stg_raw_sales({', '.join(raw_cols)}, etl_run_id) VALUES ({', '.join('?' * 10)})",
                raw_rows[i:i + BATCH])

        # ---- rejected rows with reasons
        if len(tr.rejected):
            rej_cols = [c for c in tr.rejected.columns if c not in ("reason", "source_row_number")]
            conn.executemany(
                "INSERT INTO etl_rejected_rows(etl_run_id, source_row_number, reason, raw_record_json) "
                "VALUES (?,?,?,?)",
                [(run_id, int(r["source_row_number"]), r["reason"], json.dumps({c: r[c] for c in rej_cols}))
                 for _, r in tr.rejected.iterrows()])

        conn.execute("INSERT OR REPLACE INTO warehouse_meta(key, value) VALUES ('data_version', ?)", (str(run_id),))
        conn.execute("INSERT OR REPLACE INTO warehouse_meta(key, value) VALUES ('loaded_at', ?)", (now_iso(),))
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return int(len(rows))


def table_counts(conn: sqlite3.Connection) -> dict:
    tables = ["dim_date", "dim_product", "dim_customer", "dim_country", "fact_sales",
              "stg_raw_sales", "etl_rejected_rows", "etl_run_log"]
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}


def verify(conn: sqlite3.Connection, expected_facts: int, expected_amount: float) -> dict:
    """Post-load consistency checks: counts, referential integrity, measure totals."""
    fact_count, amount = conn.execute("SELECT COUNT(*), COALESCE(SUM(line_amount), 0) FROM fact_sales").fetchone()
    orphans = {}
    for dim, key in [("dim_date", "date_key"), ("dim_product", "product_key"),
                     ("dim_customer", "customer_key"), ("dim_country", "country_key")]:
        orphans[dim] = conn.execute(
            f"SELECT COUNT(*) FROM fact_sales f LEFT JOIN {dim} d ON f.{key} = d.{key} WHERE d.{key} IS NULL"
        ).fetchone()[0]
    fk_violations = len(conn.execute("PRAGMA foreign_key_check(fact_sales)").fetchall())
    dup_fp = conn.execute(
        "SELECT COUNT(*) FROM (SELECT line_fingerprint FROM fact_sales GROUP BY 1 HAVING COUNT(*) > 1)").fetchone()[0]
    result = {
        "fact_rows": fact_count,
        "expected_fact_rows": expected_facts,
        "row_count_match": fact_count == expected_facts,
        "line_amount_total": round(amount, 2),
        "expected_line_amount_total": round(expected_amount, 2),
        "amount_match": abs(amount - expected_amount) < 0.01,
        "orphan_foreign_keys": orphans,
        "foreign_key_violations": fk_violations,
        "duplicate_fingerprints": dup_fp,
    }
    result["passed"] = (result["row_count_match"] and result["amount_match"] and fk_violations == 0
                        and dup_fp == 0 and not any(orphans.values()))
    return result
