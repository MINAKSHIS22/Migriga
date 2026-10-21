# Consistency checks on the real warehouse built from data/raw/online_retail_09_10.csv.
# Skipped automatically when the warehouse has not been built (python -m etl.run_etl).
import os
import sqlite3

import pytest

from etl import config

WH = config.DEFAULT_WAREHOUSE_PATH
pytestmark = pytest.mark.skipif(not os.path.isfile(WH), reason="real warehouse not built")


@pytest.fixture(scope="module")
def conn():
    c = sqlite3.connect(f"file:{WH}?mode=ro", uri=True)
    yield c
    c.close()


def one(conn, sql):
    return conn.execute(sql).fetchone()[0]


def test_every_raw_record_is_loaded_or_rejected(conn):
    last = conn.execute("SELECT run_id, rows_read, rows_accepted, rows_rejected, rows_loaded FROM etl_run_log "
                        "WHERE status='SUCCESS' ORDER BY run_id DESC LIMIT 1").fetchone()
    run_id, read, accepted, rejected, loaded = last
    assert one(conn, "SELECT COUNT(*) FROM stg_raw_sales") == read
    assert accepted + rejected == read
    assert one(conn, "SELECT COUNT(*) FROM fact_sales") == loaded == accepted
    assert one(conn, f"SELECT COUNT(*) FROM etl_rejected_rows WHERE etl_run_id = {run_id}") == rejected


def test_star_schema_integrity(conn):
    assert conn.execute("PRAGMA foreign_key_check(fact_sales)").fetchall() == []
    assert one(conn, "SELECT COUNT(*) FROM (SELECT line_fingerprint FROM fact_sales GROUP BY 1 HAVING COUNT(*) > 1)") == 0
    assert one(conn, "SELECT COUNT(*) FROM dim_customer WHERE customer_key = 0 AND is_anonymous = 1") == 1


def test_classification_is_consistent(conn):
    assert one(conn, "SELECT COUNT(*) FROM fact_sales WHERE line_type='SALE' AND (quantity <= 0 OR unit_price <= 0)") == 0
    assert one(conn, "SELECT COUNT(*) FROM fact_sales WHERE line_type='CANCELLATION' AND invoice_no NOT LIKE 'C%'") == 0
    assert one(conn, "SELECT COUNT(*) FROM fact_sales WHERE ABS(line_amount - quantity * unit_price) > 0.01") == 0


def test_net_equals_gross_minus_cancelled(conn):
    base = "FROM fact_sales WHERE is_duplicate = 0 AND is_product = 1"
    gross = one(conn, f"SELECT SUM(line_amount) {base} AND line_type = 'SALE'")
    cancelled = -one(conn, f"SELECT SUM(line_amount) {base} AND line_type = 'CANCELLATION'")
    net = one(conn, f"SELECT SUM(line_amount) {base} AND line_type IN ('SALE', 'CANCELLATION')")
    assert abs(net - (gross - cancelled)) < 0.01
