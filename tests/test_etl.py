# ETL tests: loading, rerun safety, changed sources, rollback, locking, rejected rows, integrity
import sqlite3

import pytest

from etl.extract import SourceValidationError
from etl.lock import ETLAlreadyRunning, ETLLock
from etl.run_etl import run_etl


def q(path, sql, args=()):
    c = sqlite3.connect(path)
    try:
        return c.execute(sql, args).fetchall()
    finally:
        c.close()


def test_initial_load_counts(loaded_warehouse):
    s = loaded_warehouse["summary"]
    assert (s["rows_read"], s["rows_accepted"], s["rows_rejected"], s["rows_loaded"]) == (22, 19, 3, 19)
    tc = s["table_counts"]
    assert tc["fact_sales"] == 19
    assert tc["stg_raw_sales"] == 22                      # raw copy keeps every record, incl. rejected
    assert tc["etl_rejected_rows"] == 3
    assert tc["dim_customer"] == 4                        # 3 customers + anonymous member (key 0)
    assert tc["dim_country"] == 2
    assert s["quality"]["verification"]["passed"] is True


def test_referential_integrity(loaded_warehouse):
    wh = loaded_warehouse["warehouse"]
    assert q(wh, "PRAGMA foreign_key_check(fact_sales)") == []
    for dim, key in [("dim_date", "date_key"), ("dim_product", "product_key"),
                     ("dim_customer", "customer_key"), ("dim_country", "country_key")]:
        orphans = q(wh, f"SELECT COUNT(*) FROM fact_sales f LEFT JOIN {dim} d USING({key}) WHERE d.{key} IS NULL")
        assert orphans[0][0] == 0
    assert q(wh, "SELECT customer_id, is_anonymous FROM dim_customer WHERE customer_key = 0") == [("__ANONYMOUS__", 1)]
    assert q(wh, "SELECT COUNT(*) FROM fact_sales WHERE customer_key = 0")[0][0] == 4


def test_rerun_unchanged_source_is_skipped(loaded_warehouse):
    s = run_etl()
    assert s["status"] == "SKIPPED_UNCHANGED"
    assert s["table_counts"]["fact_sales"] == 19


def test_forced_rerun_does_not_duplicate_facts(loaded_warehouse):
    wh = loaded_warehouse["warehouse"]
    keys_before = dict(q(wh, "SELECT stock_code, product_key FROM dim_product"))
    s = run_etl(force=True)
    assert s["status"] == "SUCCESS" and s["table_counts"]["fact_sales"] == 19
    assert q(wh, "SELECT COUNT(DISTINCT line_fingerprint) FROM fact_sales")[0][0] == 19
    assert dict(q(wh, "SELECT stock_code, product_key FROM dim_product")) == keys_before   # stable surrogate keys


def test_unique_fingerprint_constraint_blocks_duplicate_fact(loaded_warehouse):
    wh = loaded_warehouse["warehouse"]
    c = sqlite3.connect(wh)
    with pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO fact_sales(date_key, product_key, customer_key, country_key, invoice_no, "
                  "source_row_number, line_fingerprint, invoice_datetime, invoice_hour, quantity, unit_price, "
                  "line_amount, line_type, is_product, is_cancellation, is_duplicate, etl_run_id) "
                  "SELECT date_key, product_key, customer_key, country_key, invoice_no, source_row_number, "
                  "line_fingerprint, invoice_datetime, invoice_hour, quantity, unit_price, line_amount, line_type, "
                  "is_product, is_cancellation, is_duplicate, etl_run_id FROM fact_sales LIMIT 1")
    c.close()


def test_changed_source_is_fully_refreshed(loaded_warehouse):
    with open(loaded_warehouse["csv"], "a") as f:
        f.write("100014,71053,WHITE METAL LANTERN,5,3/3/2010 9:00,3.39,13047,United Kingdom\n")
    s = run_etl()
    assert s["status"] == "SUCCESS"
    assert s["rows_read"] == 23 and s["table_counts"]["fact_sales"] == 20
    assert q(loaded_warehouse["warehouse"], "SELECT COUNT(*) FROM fact_sales WHERE invoice_no='100014'")[0][0] == 1


def test_failed_load_rolls_back(loaded_warehouse):
    wh = loaded_warehouse["warehouse"]
    before = q(wh, "SELECT COUNT(*), SUM(line_amount) FROM fact_sales")
    with open(loaded_warehouse["csv"], "a") as f:
        f.write("100015,71053,WHITE METAL LANTERN,5,3/3/2010 9:00,3.39,13047,United Kingdom\n")
    with pytest.raises(RuntimeError, match="Simulated failure"):
        run_etl(_fail_after_facts=True)
    assert q(wh, "SELECT COUNT(*), SUM(line_amount) FROM fact_sales") == before
    assert q(wh, "SELECT status FROM etl_run_log ORDER BY run_id DESC LIMIT 1")[0][0] == "FAILED"
    assert q(wh, "SELECT value FROM warehouse_meta WHERE key='data_version'")[0][0] == \
        str(loaded_warehouse["summary"]["run_id"])


def test_missing_source_is_logged_as_failed(warehouse_env, monkeypatch, tmp_path):
    monkeypatch.setenv("MIGRIGA_SOURCE_CSV", str(tmp_path / "missing.csv"))
    with pytest.raises(SourceValidationError):
        run_etl()
    row = q(warehouse_env["warehouse"], "SELECT status, error_message FROM etl_run_log ORDER BY run_id DESC LIMIT 1")[0]
    assert row[0] == "FAILED" and "not found" in row[1]


def test_rejected_rows_are_logged_with_raw_record(loaded_warehouse):
    rows = q(loaded_warehouse["warehouse"],
             "SELECT source_row_number, reason, raw_record_json FROM etl_rejected_rows ORDER BY source_row_number")
    assert [(r[0], r[1]) for r in rows] == [(16, "invalid_quantity"), (17, "invalid_invoice_date"),
                                            (18, "missing_stock_code")]
    assert '"Quantity": "abc"' in rows[0][2]


def test_concurrent_runs_are_prevented(warehouse_env):
    with ETLLock(warehouse_env["warehouse"]):
        with pytest.raises(ETLAlreadyRunning):
            run_etl()


def test_stale_lock_from_dead_process_is_recovered(warehouse_env):
    lock = warehouse_env["warehouse"] + ".etl.lock"
    import os
    os.makedirs(os.path.dirname(lock), exist_ok=True)
    with open(lock, "w") as f:
        f.write("999999")          # pid that does not exist
    assert run_etl()["status"] == "SUCCESS"


def test_interrupted_run_is_marked(loaded_warehouse):
    wh = loaded_warehouse["warehouse"]
    c = sqlite3.connect(wh)
    c.execute("INSERT INTO etl_run_log(started_at, status) VALUES ('2020-01-01T00:00:00', 'RUNNING')")
    c.commit(); c.close()
    run_etl()
    assert q(wh, "SELECT COUNT(*) FROM etl_run_log WHERE status = 'RUNNING'")[0][0] == 0
    assert q(wh, "SELECT COUNT(*) FROM etl_run_log WHERE status = 'INTERRUPTED'")[0][0] == 1
