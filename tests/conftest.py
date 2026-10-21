# Shared pytest fixtures: every test runs against a small, hand-verified fixture CSV and a
# throw-away warehouse in a temp directory - never the real warehouse or migriga.db writes.
import os
import shutil
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

FIXTURE_CSV = os.path.join(ROOT, "tests", "fixtures", "sample_retail.csv")


@pytest.fixture
def sample_csv(tmp_path):
    """A private copy of the fixture CSV (tests may modify it)."""
    dst = tmp_path / "sample_retail.csv"
    shutil.copy(FIXTURE_CSV, dst)
    return str(dst)


@pytest.fixture
def warehouse_env(tmp_path, sample_csv, monkeypatch):
    """Points the ETL/analytics configuration at a temp warehouse + temp source CSV."""
    wh = str(tmp_path / "warehouse" / "test_warehouse.db")
    monkeypatch.setenv("MIGRIGA_SOURCE_CSV", sample_csv)
    monkeypatch.setenv("MIGRIGA_WAREHOUSE_PATH", wh)
    monkeypatch.setenv("MIGRIGA_MODEL_PATH", str(tmp_path / "processed" / "model.json"))
    return {"csv": sample_csv, "warehouse": wh, "tmp": tmp_path}


@pytest.fixture
def loaded_warehouse(warehouse_env):
    from etl.run_etl import run_etl
    summary = run_etl(triggered_by="pytest")
    assert summary["status"] == "SUCCESS"
    return {**warehouse_env, "summary": summary}


@pytest.fixture
def wh_conn(loaded_warehouse):
    from analytics.warehouse import connect
    conn = connect(loaded_warehouse["warehouse"])
    yield conn
    conn.close()
