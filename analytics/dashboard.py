# MIGRIGA Analytics - Dashboard KPIs, chart series and evidence-based insights
# All figures use the shared policy in analytics/warehouse.py (merchandise SALE and
# CANCELLATION lines, flagged duplicates excluded). Currency is the source currency (GBP).
import calendar
from concurrent.futures import ThreadPoolExecutor

from .warehouse import (ELIGIBLE_SALES, IS_CANCEL, IS_SALE, STAR_JOINS, build_filters, cache, cache_token,
                        connect, data_version, freeze)

GROSS = f"SUM(CASE WHEN {IS_SALE} THEN f.line_amount ELSE 0 END)"
CANCELLED = f"SUM(CASE WHEN {IS_CANCEL} THEN -f.line_amount ELSE 0 END)"
UNITS = f"SUM(CASE WHEN {IS_SALE} THEN f.quantity ELSE 0 END)"
ORDERS = f"COUNT(DISTINCT CASE WHEN {IS_SALE} THEN f.invoice_no END)"


def _where(filters):
    conds, args, normalized = build_filters(filters)
    return " AND ".join([ELIGIBLE_SALES] + conds), args, normalized


def _db_path(conn) -> str:
    return conn.execute("PRAGMA database_list").fetchone()["file"]


def _run_parallel(path: str, queries: dict) -> dict:
    """Runs independent read-only aggregations concurrently (SQLite releases the GIL while
    executing), each on its own connection. Returns {name: [row dicts]}."""
    def run(item):
        name, (sql, args) = item
        c = connect(path)
        try:
            return name, [dict(r) for r in c.execute(sql, args).fetchall()]
        finally:
            c.close()
    with ThreadPoolExecutor(max_workers=min(6, len(queries))) as pool:
        return dict(pool.map(run, queries.items()))


def get_dashboard(conn, filters: dict) -> dict:
    where, args, normalized = _where(filters)
    key = ("dashboard", cache_token(conn), freeze(normalized))
    hit = cache.get(key)
    if hit is not None:
        return hit
    per_customer = (f"SELECT f.customer_key, COUNT(DISTINCT f.invoice_no) AS inv {STAR_JOINS} "
                    f"WHERE {where} AND {IS_SALE} AND f.customer_key <> 0 GROUP BY f.customer_key")
    # Non-merchandise charges (postage, fees, manual lines) are outside product sales; shown for transparency.
    conds, fargs, _ = build_filters(filters)
    extra = (" AND " + " AND ".join(conds)) if conds else ""
    queries = {
        "kpi": (f"""SELECT {GROSS} AS gross, {CANCELLED} AS cancelled, SUM(f.line_amount) AS net, {UNITS} AS units,
              {ORDERS} AS orders, SUM(CASE WHEN {IS_SALE} THEN 1 ELSE 0 END) AS sale_lines,
              COUNT(DISTINCT CASE WHEN {IS_CANCEL} THEN f.invoice_no END) AS cancel_invoices,
              SUM(CASE WHEN {IS_CANCEL} THEN -f.quantity ELSE 0 END) AS cancelled_units,
              COUNT(DISTINCT CASE WHEN {IS_SALE} AND f.customer_key <> 0 THEN f.customer_key END) AS customers,
              COUNT(DISTINCT CASE WHEN {IS_SALE} THEN f.product_key END) AS products,
              COUNT(DISTINCT CASE WHEN {IS_SALE} THEN f.country_key END) AS countries,
              SUM(CASE WHEN {IS_SALE} AND f.customer_key = 0 THEN f.line_amount ELSE 0 END) AS anon_gross,
              MIN(d.full_date) AS first_day, MAX(d.full_date) AS last_day
              {STAR_JOINS} WHERE {where}""", args),
        "repeat": (f"SELECT COUNT(*) AS n, SUM(CASE WHEN inv >= 2 THEN 1 ELSE 0 END) AS repeaters "
                   f"FROM ({per_customer})", args),
        "monthly": (f"""SELECT d.year_month AS month, {GROSS} AS gross, {CANCELLED} AS cancelled,
            SUM(f.line_amount) AS net, {ORDERS} AS orders, {UNITS} AS units, COUNT(DISTINCT d.full_date) AS active_days,
            MIN(d.full_date) AS first_day, MAX(d.full_date) AS last_day
            {STAR_JOINS} WHERE {where} GROUP BY d.year_month ORDER BY d.year_month""", args),
        "yearly": (f"""SELECT d.year AS year, {GROSS} AS gross, SUM(f.line_amount) AS net, {ORDERS} AS orders
            {STAR_JOINS} WHERE {where} GROUP BY d.year ORDER BY d.year""", args),
        "top_value": (f"""SELECT p.stock_code, p.description, {GROSS} AS gross, {UNITS} AS units
            {STAR_JOINS} WHERE {where} GROUP BY p.product_key ORDER BY gross DESC LIMIT 10""", args),
        "top_qty": (f"""SELECT p.stock_code, p.description, {UNITS} AS units, {GROSS} AS gross
            {STAR_JOINS} WHERE {where} GROUP BY p.product_key ORDER BY units DESC LIMIT 10""", args),
        "countries": (f"""SELECT c.country_name AS country, {GROSS} AS gross, SUM(f.line_amount) AS net,
            {ORDERS} AS orders {STAR_JOINS} WHERE {where} GROUP BY c.country_key ORDER BY net DESC""", args),
        "weekday": (f"""SELECT d.weekday_num, d.weekday_name AS weekday, {GROSS} AS gross, {ORDERS} AS orders
            {STAR_JOINS} WHERE {where} GROUP BY d.weekday_num ORDER BY d.weekday_num""", args),
        "hourly": (f"""SELECT f.invoice_hour AS hour, {GROSS} AS gross, {ORDERS} AS orders
            {STAR_JOINS} WHERE {where} GROUP BY f.invoice_hour ORDER BY f.invoice_hour""", args),
        "dist": (f"""SELECT CASE WHEN inv = 1 THEN '1' WHEN inv = 2 THEN '2' WHEN inv <= 5 THEN '3–5'
            WHEN inv <= 10 THEN '6–10' WHEN inv <= 20 THEN '11–20' ELSE '21+' END AS bucket,
            MIN(inv) AS lo, COUNT(*) AS customers FROM ({per_customer}) GROUP BY bucket ORDER BY lo""", args),
        "fees": (f"""SELECT COALESCE(SUM(f.line_amount), 0) AS fees {STAR_JOINS}
            WHERE f.is_duplicate = 0 AND f.is_product = 0 AND {IS_SALE}{extra}""", fargs),
    }
    r = _run_parallel(_db_path(conn), queries)
    k, repeat = r["kpi"][0], r["repeat"][0]

    gross, orders = k["gross"] or 0, k["orders"] or 0
    kpis = {
        "orders": orders,
        "sale_lines": k["sale_lines"] or 0,
        "units_sold": k["units"] or 0,
        "gross_sales": round(gross, 2),
        "cancelled_value": round(k["cancelled"] or 0, 2),
        "cancelled_units": k["cancelled_units"] or 0,
        "cancellation_invoices": k["cancel_invoices"] or 0,
        "net_sales": round(k["net"] or 0, 2),
        "avg_order_value": round(gross / orders, 2) if orders else None,
        "identified_customers": k["customers"] or 0,
        "anonymous_gross_share": (k["anon_gross"] / gross) if gross else None,
        "products_sold": k["products"] or 0,
        "active_countries": k["countries"] or 0,
        "repeat_customer_rate": (repeat["repeaters"] / repeat["n"]) if repeat["n"] else None,
        "first_day": k["first_day"], "last_day": k["last_day"],
    }
    top10_share = (sum(p["gross"] or 0 for p in r["top_value"]) / gross) if gross else None

    result = {
        "filters": normalized, "data_version": data_version(conn), "currency": "GBP",
        "kpis": kpis, "monthly": r["monthly"], "yearly": r["yearly"], "top_products_value": r["top_value"],
        "top_products_quantity": r["top_qty"], "countries": r["countries"], "weekday": r["weekday"],
        "hourly": r["hourly"], "customer_order_distribution": r["dist"], "top10_product_share": top10_share,
        "non_product_charges": round(r["fees"][0]["fees"], 2),
    }
    result["insights"] = build_insights(result)
    cache.put(key, result)
    return result


def _money(v):
    return f"£{v:,.0f}"


def _month_label(ym):
    y, m = ym.split("-")
    return f"{calendar.month_name[int(m)]} {y}"


def _is_partial(month: str, period_first: str, period_last: str) -> bool:
    """True when the analysed period starts after the 1st or ends before the last day of this
    calendar month (days without trading inside the period do not make a month partial)."""
    y, mo = map(int, month.split("-"))
    last = f"{month}-{calendar.monthrange(y, mo)[1]:02d}"
    return period_first > f"{month}-01" or period_last < last


def build_insights(d: dict) -> list:
    """Each insight is computed from the query results above and carries its supporting numbers."""
    out = []
    k = d["kpis"]
    if not k["orders"]:
        return [{"id": "empty", "text": "No eligible sales match the current filters.", "evidence": {}}]

    months = [m for m in d["monthly"] if m["net"] is not None]
    if months:
        best = max(months, key=lambda m: m["net"])
        total = sum(m["net"] for m in months)
        first, last = d["kpis"]["first_day"], d["kpis"]["last_day"]
        partial = _is_partial(best["month"], first, last)
        text = (f"{_month_label(best['month'])} had the highest net sales in the selected period: "
                f"{_money(best['net'])} ({best['net'] / total:.1%} of the period total).")
        if partial:
            text += f" Note: the period covers only {max(first, best['month'] + '-01')} to {min(last, best['last_day'])} of that month."
        out.append({"id": "best_month", "text": text,
                    "evidence": {"month": best["month"], "net_sales": round(best["net"], 2),
                                 "period_net_sales": round(total, 2)}})
        partial_months = [m["month"] for m in months if _is_partial(m["month"], first, last)]
        if partial_months and len(months) > 1:
            out.append({"id": "partial_months",
                        "text": "Months only partly inside the analysed period (compare totals with care): "
                                + ", ".join(_month_label(m) for m in partial_months) + ".",
                        "evidence": {"months": partial_months}})

    if d["top_products_value"]:
        tp = d["top_products_value"][0]
        out.append({"id": "top_product",
                    "text": f"Top product by gross sales value: {tp['description']} ({tp['stock_code']}) with "
                            f"{_money(tp['gross'])}, {tp['gross'] / k['gross_sales']:.1%} of gross sales.",
                    "evidence": {"stock_code": tp["stock_code"], "gross_sales": round(tp["gross"], 2)}})
    if d["top10_product_share"] is not None and k["products_sold"] > 10:
        out.append({"id": "concentration",
                    "text": f"The 10 best-selling products contribute {d['top10_product_share']:.1%} of gross sales "
                            f"across {k['products_sold']:,} products sold.",
                    "evidence": {"top10_share": round(d["top10_product_share"], 4), "products_sold": k["products_sold"]}})
    if d["countries"]:
        c0 = d["countries"][0]
        net_total = sum(c["net"] for c in d["countries"])
        if net_total:
            out.append({"id": "top_country",
                        "text": f"{c0['country']} leads eligible sales with {_money(c0['net'])} net "
                                f"({c0['net'] / net_total:.1%}) across {len(d['countries'])} active countries.",
                        "evidence": {"country": c0["country"], "net_sales": round(c0["net"], 2)}})
    if k["gross_sales"]:
        rate = k["cancelled_value"] / k["gross_sales"]
        out.append({"id": "cancellations",
                    "text": f"Cancellations equal {rate:.1%} of gross sales value ({_money(k['cancelled_value'])} on "
                            f"{k['cancellation_invoices']:,} cancellation invoices).",
                    "evidence": {"cancelled_value": k["cancelled_value"], "gross_sales": k["gross_sales"]}})
    if k["repeat_customer_rate"] is not None:
        out.append({"id": "repeat_rate",
                    "text": f"{k['repeat_customer_rate']:.1%} of {k['identified_customers']:,} identified customers placed "
                            f"two or more orders in the selected period.",
                    "evidence": {"repeat_rate": round(k["repeat_customer_rate"], 4),
                                 "identified_customers": k["identified_customers"]}})
    if k["anonymous_gross_share"]:
        out.append({"id": "anonymous",
                    "text": f"{k['anonymous_gross_share']:.1%} of gross sales came from purchases without a CustomerID; "
                            "they count in sales totals but not in customer metrics.",
                    "evidence": {"anonymous_share": round(k["anonymous_gross_share"], 4)}})
    return out


def filter_options(conn) -> dict:
    key = ("filter_options", cache_token(conn))
    hit = cache.get(key)
    if hit is not None:
        return hit
    countries = [r[0] for r in conn.execute(
        "SELECT c.country_name FROM dim_country c ORDER BY c.country_name").fetchall()]
    dmin, dmax = conn.execute(f"SELECT MIN(d.full_date), MAX(d.full_date) FROM fact_sales f "
                              f"JOIN dim_date d ON d.date_key = f.date_key").fetchone()
    years = [r[0] for r in conn.execute("SELECT DISTINCT year FROM dim_date ORDER BY year").fetchall()]
    res = {"countries": countries, "date_min": dmin, "date_max": dmax, "years": years}
    cache.put(key, res)
    return res


def search_products(conn, term: str, limit: int = 20) -> list:
    term = (term or "").strip()
    if len(term) > 100:
        term = term[:100]
    like = f"%{term.upper()}%"
    rows = conn.execute(
        "SELECT stock_code, description FROM dim_product WHERE is_product = 1 AND "
        "(UPPER(stock_code) LIKE ? OR UPPER(description) LIKE ?) ORDER BY "
        "CASE WHEN UPPER(stock_code) = ? THEN 0 ELSE 1 END, description LIMIT ?",
        (like, like, term.upper(), max(1, min(limit, 50)))).fetchall()
    return [dict(r) for r in rows]
