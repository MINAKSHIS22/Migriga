# Integration tests: analytics API schemas, auth, warehouse-sourced values, real jobs, exports,
# and preservation of the existing Migriga storefront API.
import csv
import io
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient

import server
from backend.deps import require_admin


@pytest.fixture
def client():
    return TestClient(server.app)          # no context manager: startup hooks (seeding, warm-up) do not run


@pytest.fixture
def admin_client(client):
    server.app.dependency_overrides[require_admin] = lambda: {"id": 1, "email": "test-admin@migriga.local", "role": "admin"}
    yield client
    server.app.dependency_overrides.clear()


def wait_job(c, job_id, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        job = c.get(f"/api/analytics/jobs/{job_id}").json()["job"]
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.2)
    raise AssertionError("job timed out")


def test_analytics_requires_admin(client, loaded_warehouse):
    for path in ["/api/analytics/overview", "/api/analytics/dashboard", "/api/analytics/etl/status"]:
        assert client.get(path).status_code == 403
    assert client.post("/api/analytics/etl/run", json={}).status_code == 403
    assert client.get("/api/analytics/dashboard", headers={"Authorization": "Bearer not-a-token"}).status_code == 403


def test_warehouse_missing_returns_503(admin_client, warehouse_env):
    r = admin_client.get("/api/analytics/dashboard")
    assert r.status_code == 503 and r.json()["code"] == "warehouse_unavailable"
    ov = admin_client.get("/api/analytics/overview").json()
    assert ov["initialized"] is False and "Chen, D. (2012)" in ov["dataset"]["citation"]


def test_overview_schema(admin_client, loaded_warehouse):
    ov = admin_client.get("/api/analytics/overview").json()
    assert ov["initialized"] is True
    assert ov["filter_options"]["countries"] == ["France", "United Kingdom"]
    assert {d["id"] for d in ov["olap"]["dimensions"]} >= {"year", "quarter", "month", "day", "country", "product"}


def test_dashboard_values_come_from_warehouse(admin_client, loaded_warehouse):
    d = admin_client.get("/api/analytics/dashboard").json()
    c = sqlite3.connect(loaded_warehouse["warehouse"])
    gross = c.execute("SELECT SUM(line_amount) FROM fact_sales WHERE line_type='SALE' AND is_product=1 "
                      "AND is_duplicate=0").fetchone()[0]
    c.close()
    k = d["kpis"]
    assert k["gross_sales"] == round(gross, 2) == 177.43
    assert k["net_sales"] == 174.88 and k["orders"] == 6 and k["units_sold"] == 49
    assert k["identified_customers"] == 3 and k["repeat_customer_rate"] == pytest.approx(2 / 3)
    assert d["non_product_charges"] == 18.0
    assert {i["id"] for i in d["insights"]} >= {"best_month", "top_product", "top_country", "cancellations"}
    assert d["top_products_value"][0]["stock_code"] == "85123A"


def test_dashboard_filters_change_results(admin_client, loaded_warehouse):
    fr = admin_client.get("/api/analytics/dashboard?countries=France").json()["kpis"]
    assert fr["gross_sales"] == 32.28 and fr["orders"] == 2
    empty = admin_client.get("/api/analytics/dashboard?date_from=2010-02-01&date_to=2010-02-28").json()
    assert empty["kpis"]["orders"] == 0 and empty["insights"][0]["id"] == "empty"
    bad = admin_client.get("/api/analytics/dashboard?date_from=31-12-2010")
    assert bad.status_code == 422 and bad.json()["code"] == "invalid_parameter"


def test_olap_endpoint_and_export(admin_client, loaded_warehouse):
    body = {"rows": "month", "measure": "gross_sales", "filters": {"countries": ["France"]}}
    r = admin_client.post("/api/analytics/olap", json=body).json()
    assert {x["member"]: round(x["value"], 2) for x in r["rows"]} == {"2010-01": 22.95, "2010-03": 9.33}
    assert "?" in r["sql"] and r["sql_params"] == ["France"]
    exp = admin_client.post("/api/analytics/olap/export", json=body)
    assert exp.status_code == 200 and exp.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(exp.text)))
    assert rows[0][0] == "Month" and [x[0] for x in rows[1:]] == ["2010-01", "2010-03"]
    assert admin_client.post("/api/analytics/olap", json={"rows": "nope"}).status_code == 422


def test_basket_job_runs_real_mining(admin_client, loaded_warehouse, monkeypatch):
    from analytics import market_basket
    monkeypatch.setattr(market_basket, "MIN_SUPPORT_BASKETS", 1)
    start = admin_client.post("/api/analytics/basket/jobs", json={"min_support": 0.3, "min_confidence": 0.5,
                                                                  "min_lift": 0}).json()
    job = wait_job(admin_client, start["job"]["id"])
    assert job["status"] == "done" and job["result"]["n_baskets"] == 6 and job["result"]["n_rules"] == 3
    again = admin_client.post("/api/analytics/basket/jobs", json={"min_support": 0.3, "min_confidence": 0.5,
                                                                  "min_lift": 0}).json()
    assert again["cached"] is True and again["job"]["id"] == start["job"]["id"]
    other = admin_client.post("/api/analytics/basket/jobs", json={"min_support": 0.5, "min_confidence": 0.5,
                                                                  "min_lift": 0}).json()
    assert other["job"]["id"] != start["job"]["id"]                     # new params -> new computation
    exp = admin_client.get(f"/api/analytics/basket/{job['id']}/export?kind=rules")
    lines = list(csv.reader(io.StringIO(exp.text)))
    assert lines[0] == ["antecedent", "consequent", "support", "support_count", "confidence", "lift"]
    assert len(lines) == 4
    assert admin_client.post("/api/analytics/basket/jobs", json={"min_support": 5}).status_code == 422


def test_segmentation_job_and_filtered_export(admin_client, loaded_warehouse):
    start = admin_client.post("/api/analytics/segmentation/jobs", json={"k": 2, "seed": 42}).json()
    job = wait_job(admin_client, start["job"]["id"])
    assert job["status"] == "done"
    res = job["result"]
    assert res["customers_included"] == 3 and len(res["clusters"]) == 2
    c1 = [c["customer_id"] for c in res["customers"] if c["cluster"] == 1]
    exp = admin_client.get(f"/api/analytics/segmentation/{job['id']}/export?cluster=1")
    rows = list(csv.reader(io.StringIO(exp.text)))
    assert rows[0][0] == "customer_id" and sorted(r[0] for r in rows[1:]) == sorted(c1)
    bad = admin_client.post("/api/analytics/segmentation/jobs", json={"k": 50})
    assert bad.status_code == 422


def test_failed_job_reports_safe_error(admin_client, loaded_warehouse):
    start = admin_client.post("/api/analytics/segmentation/jobs", json={"k": 6, "seed": 1}).json()
    job = wait_job(admin_client, start["job"]["id"])
    assert job["status"] == "failed" and "eligible customers" in job["error"]


def test_etl_status_and_run_via_api(admin_client, loaded_warehouse):
    st = admin_client.get("/api/analytics/etl/status").json()
    assert st["last_success"]["rows_loaded"] == 19 and st["table_counts"]["fact_sales"] == 19
    assert st["last_success"]["quality"]["rejected_by_reason"] == {
        "invalid_quantity": 1, "invalid_invoice_date": 1, "missing_stock_code": 1}
    job = admin_client.post("/api/analytics/etl/run", json={"force": True}).json()["job"]
    done = wait_job(admin_client, job["id"])
    assert done["status"] == "done" and done["result"]["status"] == "SUCCESS" and done["result"]["rows_loaded"] == 19
    runs = admin_client.get("/api/analytics/etl/status").json()["runs"]
    assert runs[0]["triggered_by"] == "web:test-admin@migriga.local" and runs[0]["status"] == "SUCCESS"
    rej = admin_client.get("/api/analytics/etl/rejected").json()["rejected"]
    assert len(rej) == 3


def test_lab_apriori_demo(admin_client):
    r = admin_client.post("/api/analytics/lab/apriori-demo", json={
        "baskets": [["Bread", "Milk"], ["Bread", "Diapers", "Beer", "Eggs"], ["Milk", "Diapers", "Beer", "Cola"],
                    ["Bread", "Milk", "Diapers", "Beer"], ["Bread", "Milk", "Diapers", "Cola"]],
        "min_support": 0.6, "min_confidence": 0.7}).json()
    assert r["min_support_count"] == 3 and len(r["itemsets"]) == 8 and r["trace"][0]["k"] == 1
    assert admin_client.post("/api/analytics/lab/apriori-demo", json={"baskets": []}).status_code == 422


def test_existing_storefront_api_still_works(client):
    r = client.get("/api/products")
    assert r.status_code == 200 and len(r.json()["products"]) > 0
    pid = r.json()["products"][0]["id"]
    assert client.get(f"/api/products/{pid}").status_code == 200
    assert client.get("/api/products?search=serum").status_code == 200
    assert client.get("/api/recommendations/status").status_code == 200
    assert client.get("/api/admin/stats").status_code == 403         # admin endpoints still protected
    for page in ["/", "/store", "/admin", "/login", "/analytics"]:
        assert client.get(page).status_code == 200
    assert client.get("/js/analytics/core.js").status_code == 200
    assert client.get("/css/analytics.css").status_code == 200
