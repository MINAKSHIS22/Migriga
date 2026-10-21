# OLAP tests: aggregation, roll-up / drill-down, slice, dice, pivot, empty results, validation.
# Expected values are hand-computed from tests/fixtures/sample_retail.csv (see docs/testing.md).
import pytest

from analytics.olap import drill_down_level, roll_up_level, run_query, to_csv_rows
from analytics.warehouse import AnalyticsParamError

GROSS_TOTAL = 177.43        # 13 eligible merchandise SALE lines (duplicate + postage excluded)
CANCELLED = 2.55
NET_TOTAL = 174.88


def by_member(res):
    return {r["member"]: round(r["value"], 2) for r in res["rows"]}


def test_monthly_net_sales(wh_conn):
    r = run_query(wh_conn, {"rows": "month", "measure": "net_sales"})
    assert by_member(r) == {"2009-12": 63.58, "2010-01": 58.62, "2010-03": 52.68}
    assert round(r["grand_total"], 2) == NET_TOTAL


def test_measures(wh_conn):
    def total(m):
        return run_query(wh_conn, {"rows": "year", "measure": m})["grand_total"]
    assert round(total("gross_sales"), 2) == GROSS_TOTAL
    assert round(total("cancelled_value"), 2) == CANCELLED
    assert total("orders") == 6                   # distinct invoices, not lines
    assert total("lines") == 13
    assert total("units_sold") == 49
    assert total("customers") == 3                # anonymous excluded
    assert round(total("avg_order_value"), 4) == round(GROSS_TOTAL / 6, 4)


def test_roll_up_equals_sum_of_children(wh_conn):
    months = run_query(wh_conn, {"rows": "month", "measure": "gross_sales"})
    quarters = run_query(wh_conn, {"rows": "quarter", "measure": "gross_sales"})
    years = run_query(wh_conn, {"rows": "year", "measure": "gross_sales"})
    assert round(sum(r["value"] for r in months["rows"]), 2) == round(sum(r["value"] for r in quarters["rows"]), 2) \
        == round(sum(r["value"] for r in years["rows"]), 2) == GROSS_TOTAL
    assert by_member(years) == {2009: 66.13, 2010: 111.30}


def test_drill_down_with_slice(wh_conn):
    r = run_query(wh_conn, {"rows": "quarter", "measure": "gross_sales", "slices": {"year": "2010"}})
    assert by_member(r) == {"2010-Q1": 111.30}
    r = run_query(wh_conn, {"rows": "month", "measure": "gross_sales", "slices": {"year": "2010", "quarter": "2010-Q1"}})
    assert by_member(r) == {"2010-01": 58.62, "2010-03": 52.68}
    assert r["roll_up_to"] == "quarter" and r["drill_down_to"] == "day"
    assert drill_down_level("year") == "quarter" and roll_up_level("day") == "month"
    assert roll_up_level("year") is None and drill_down_level("day") is None


def test_slice_on_country(wh_conn):
    r = run_query(wh_conn, {"rows": "year", "measure": "gross_sales", "slices": {"country": "France"}})
    assert round(r["grand_total"], 2) == 32.28


def test_dice_multiple_dimensions(wh_conn):
    r = run_query(wh_conn, {"rows": "product", "measure": "units_sold", "filters": {
        "date_from": "2010-01-01", "date_to": "2010-03-31", "countries": ["France", "United Kingdom"],
        "products": ["85123a", "22423"]}})
    got = {m.split(" · ")[0]: v for m, v in by_member(r).items()}
    assert got == {"85123A": 17, "22423": 4}
    assert "DICE" in r["explanation"]


def test_customer_filter(wh_conn):
    r = run_query(wh_conn, {"rows": "year", "measure": "orders", "filters": {"customers": ["17850"]}})
    assert r["grand_total"] == 2


def test_pivot(wh_conn):
    r = run_query(wh_conn, {"rows": "month", "columns": "country", "measure": "gross_sales"})
    assert r["mode"] == "pivot"
    cols = [c["member"] for c in r["columns"]]
    assert set(cols) == {"United Kingdom", "France"}
    fr = cols.index("France")
    cells = {row["member"]: row["cells"][fr] for row in r["rows"]}
    assert round(cells["2010-01"], 2) == 22.95 and cells["2009-12"] is None
    for row in r["rows"]:               # row totals equal the sum of the row's cells
        assert round(sum(c or 0 for c in row["cells"]), 2) == round(row["value"], 2)
    header, body = to_csv_rows(r)
    assert header[0] == "Month" and header[-1] == "Row total" and len(body) == 3


def test_pivot_swap(wh_conn):
    a = run_query(wh_conn, {"rows": "month", "columns": "country", "measure": "gross_sales"})
    b = run_query(wh_conn, {"rows": "country", "columns": "month", "measure": "gross_sales"})
    assert round(a["grand_total"], 2) == round(b["grand_total"], 2)
    assert {r["member"] for r in b["rows"]} == {"United Kingdom", "France"}


def test_empty_result(wh_conn):
    r = run_query(wh_conn, {"rows": "month", "filters": {"countries": ["Atlantis"]}})
    assert r["rows"] == [] and r["total_groups"] == 0 and r["grand_total"] is None


@pytest.mark.parametrize("params,msg", [
    ({"rows": "salary"}, "Unknown row dimension"),
    ({"rows": "month", "columns": "month"}, "must differ"),
    ({"measure": "profit"}, "Unknown measure"),
    ({"limit": 0}, "limit"),
    ({"limit": "abc"}, "integer"),
    ({"slices": {"evil); DROP TABLE fact_sales;--": "x"}}, "unknown dimension"),
    ({"filters": {"date_from": "2010-02-30"}}, "valid calendar date"),
    ({"filters": {"date_from": "2010-03-01", "date_to": "2010-01-01"}}, "on or before"),
])
def test_parameter_validation(wh_conn, params, msg):
    with pytest.raises(AnalyticsParamError, match=msg):
        run_query(wh_conn, params)


def test_user_values_are_bound_parameters(wh_conn):
    evil = "France' OR '1'='1"
    r = run_query(wh_conn, {"rows": "year", "filters": {"countries": [evil]}})
    assert r["rows"] == [] and evil in r["sql_params"] and evil not in r["sql"]
