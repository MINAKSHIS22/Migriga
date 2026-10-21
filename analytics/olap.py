# MIGRIGA Analytics - OLAP engine over the star schema
# Roll-up / drill-down = changing the level of the time hierarchy (year > quarter > month > day)
# Slice = fixing one dimension member; Dice = filtering several dimensions at once
# Pivot = cross-tabulating a row dimension against a column dimension for one measure.
# All SQL is assembled only from the whitelists below; user values are always bound parameters.
from .warehouse import (ELIGIBLE_SALES, IS_CANCEL, IS_SALE, STAR_JOINS, AnalyticsParamError,
                        build_filters, cache, cache_token, freeze)

TIME_HIERARCHY = ["year", "quarter", "month", "day"]

DIMENSIONS = {
    "year":      {"label": "Year", "expr": "d.year", "order": "MIN(d.date_key)"},
    "quarter":   {"label": "Quarter", "expr": "d.year_quarter", "order": "MIN(d.date_key)"},
    "month":     {"label": "Month", "expr": "d.year_month", "order": "MIN(d.date_key)"},
    "day":       {"label": "Day", "expr": "d.full_date", "order": "MIN(d.date_key)"},
    "weekday":   {"label": "Weekday", "expr": "d.weekday_name", "order": "MIN(d.weekday_num)"},
    "hour":      {"label": "Hour of day", "expr": "f.invoice_hour", "order": "MIN(f.invoice_hour)"},
    "country":   {"label": "Country", "expr": "c.country_name", "order": None},
    "product":   {"label": "Product", "expr": "p.stock_code || ' · ' || p.description", "order": None},
    "customer":  {"label": "Customer", "expr": "CASE WHEN cu.customer_key = 0 THEN 'Anonymous' ELSE cu.customer_id END",
                  "order": None},
    "line_type": {"label": "Line type", "expr": "f.line_type", "order": None},
}

MEASURES = {
    "net_sales":       {"label": "Net sales (£)", "sql": "SUM(f.line_amount)", "fmt": "money"},
    "gross_sales":     {"label": "Gross sales (£)", "sql": f"SUM(CASE WHEN {IS_SALE} THEN f.line_amount ELSE 0 END)",
                        "fmt": "money"},
    "cancelled_value": {"label": "Cancelled value (£)",
                        "sql": f"SUM(CASE WHEN {IS_CANCEL} THEN -f.line_amount ELSE 0 END)", "fmt": "money"},
    "units_sold":      {"label": "Units sold", "sql": f"SUM(CASE WHEN {IS_SALE} THEN f.quantity ELSE 0 END)",
                        "fmt": "int"},
    "orders":          {"label": "Orders (invoices)",
                        "sql": f"COUNT(DISTINCT CASE WHEN {IS_SALE} THEN f.invoice_no END)", "fmt": "int"},
    "lines":           {"label": "Invoice lines", "sql": f"SUM(CASE WHEN {IS_SALE} THEN 1 ELSE 0 END)", "fmt": "int"},
    "customers":       {"label": "Identified customers",
                        "sql": f"COUNT(DISTINCT CASE WHEN {IS_SALE} AND f.customer_key <> 0 THEN f.customer_key END)",
                        "fmt": "int"},
    "avg_order_value": {"label": "Avg order value (£)",
                        "sql": f"SUM(CASE WHEN {IS_SALE} THEN f.line_amount ELSE 0 END) * 1.0 / "
                               f"NULLIF(COUNT(DISTINCT CASE WHEN {IS_SALE} THEN f.invoice_no END), 0)",
                        "fmt": "money"},
}

MAX_ROWS = 5000
MAX_PIVOT_COLUMNS = 24


def drill_down_level(level):
    i = TIME_HIERARCHY.index(level)
    return TIME_HIERARCHY[i + 1] if i + 1 < len(TIME_HIERARCHY) else None


def roll_up_level(level):
    i = TIME_HIERARCHY.index(level)
    return TIME_HIERARCHY[i - 1] if i > 0 else None


def _validate(params):
    rows_dim = params.get("rows") or "month"
    cols_dim = params.get("columns") or None
    measure = params.get("measure") or "net_sales"
    if rows_dim not in DIMENSIONS:
        raise AnalyticsParamError(f"Unknown row dimension '{rows_dim}'.")
    if cols_dim is not None and cols_dim not in DIMENSIONS:
        raise AnalyticsParamError(f"Unknown column dimension '{cols_dim}'.")
    if cols_dim == rows_dim:
        raise AnalyticsParamError("Row and column dimensions must differ for a pivot.")
    if measure not in MEASURES:
        raise AnalyticsParamError(f"Unknown measure '{measure}'.")
    sort = params.get("sort") or "natural"
    if sort not in ("natural", "measure_desc", "measure_asc"):
        raise AnalyticsParamError("sort must be natural, measure_desc or measure_asc.")
    try:
        limit = int(500 if params.get("limit") is None else params.get("limit"))
    except (TypeError, ValueError):
        raise AnalyticsParamError("limit must be an integer.")
    if not 1 <= limit <= MAX_ROWS:
        raise AnalyticsParamError(f"limit must be between 1 and {MAX_ROWS}.")
    slices = params.get("slices") or {}
    if not isinstance(slices, dict):
        raise AnalyticsParamError("slices must be an object of {dimension: value}.")
    for dim, val in slices.items():
        if dim not in DIMENSIONS:
            raise AnalyticsParamError(f"Cannot slice on unknown dimension '{dim}'.")
        if val is None or len(str(val)) > 200:
            raise AnalyticsParamError(f"Invalid slice value for '{dim}'.")
    return rows_dim, cols_dim, measure, sort, limit, slices


def _where(params):
    conds, args, normalized = build_filters(params.get("filters") or {})
    slices = params.get("slices") or {}
    for dim, val in slices.items():
        conds.append(f"CAST({DIMENSIONS[dim]['expr']} AS TEXT) = ?")
        args.append(str(val))
    return [ELIGIBLE_SALES] + conds, args, normalized


def run_query(conn, params: dict) -> dict:
    rows_dim, cols_dim, measure, sort, limit, slices = _validate(params)
    key = ("olap", cache_token(conn), freeze(params))
    hit = cache.get(key)
    if hit is not None:
        return hit

    conds, args, normalized = _where(params)
    where_sql = " AND ".join(conds)
    rdef, mdef = DIMENSIONS[rows_dim], MEASURES[measure]
    order_natural = rdef["order"] or "member"
    if sort == "measure_desc":
        order_sql = "value DESC"
    elif sort == "measure_asc":
        order_sql = "value ASC"
    else:
        order_sql = f"{order_natural} ASC" if rdef["order"] else "value DESC"

    totals_sql = f"SELECT {mdef['sql']} AS value, COUNT(*) AS fact_rows {STAR_JOINS} WHERE {where_sql}"
    total_row = conn.execute(totals_sql, args).fetchone()

    if cols_dim is None:
        sql = (f"SELECT {rdef['expr']} AS member, {mdef['sql']} AS value, COUNT(*) AS fact_rows\n"
               f"{STAR_JOINS}\nWHERE {where_sql}\nGROUP BY member\nORDER BY {order_sql}\nLIMIT ?")
        rows = [dict(r) for r in conn.execute(sql, args + [limit]).fetchall()]
        count_sql = f"SELECT COUNT(DISTINCT {rdef['expr']}) {STAR_JOINS} WHERE {where_sql}"
        total_groups = conn.execute(count_sql, args).fetchone()[0]
        result = {
            "mode": "aggregate",
            "rows": [{"member": r["member"], "value": r["value"], "fact_rows": r["fact_rows"]} for r in rows],
            "columns": None,
        }
    else:
        cdef = DIMENSIONS[cols_dim]
        # Column members: natural order for ordered dims, else the top-N by measure.
        col_order = f"{cdef['order']} ASC" if cdef["order"] else "value DESC"
        col_sql = (f"SELECT {cdef['expr']} AS member, {mdef['sql']} AS value {STAR_JOINS} WHERE {where_sql} "
                   f"GROUP BY member ORDER BY {col_order} LIMIT ?")
        col_members = [r["member"] for r in conn.execute(col_sql, args + [MAX_PIVOT_COLUMNS + 1]).fetchall()]
        truncated_cols = len(col_members) > MAX_PIVOT_COLUMNS
        col_members = col_members[:MAX_PIVOT_COLUMNS]

        row_sql = (f"SELECT {rdef['expr']} AS member, {mdef['sql']} AS value {STAR_JOINS} WHERE {where_sql} "
                   f"GROUP BY member ORDER BY {order_sql} LIMIT ?")
        row_list = [dict(r) for r in conn.execute(row_sql, args + [limit]).fetchall()]
        row_members = [r["member"] for r in row_list]
        total_groups = conn.execute(f"SELECT COUNT(DISTINCT {rdef['expr']}) {STAR_JOINS} WHERE {where_sql}",
                                    args).fetchone()[0]

        sql = (f"SELECT {rdef['expr']} AS row_member, {cdef['expr']} AS col_member, {mdef['sql']} AS value\n"
               f"{STAR_JOINS}\nWHERE {where_sql}\nGROUP BY row_member, col_member")
        cells = {}
        if row_members and col_members:
            for r in conn.execute(sql, args).fetchall():
                cells[(r["row_member"], r["col_member"])] = r["value"]
        result = {
            "mode": "pivot",
            "columns": [{"member": m} for m in col_members],
            "columns_truncated": truncated_cols,
            "rows": [{"member": rm, "value": rr["value"],
                      "cells": [cells.get((rm, cm)) for cm in col_members]}
                     for rm, rr in zip(row_members, row_list)],
        }

    result.update({
        "rows_dimension": rows_dim, "columns_dimension": cols_dim, "measure": measure,
        "measure_label": mdef["label"], "measure_format": mdef["fmt"],
        "rows_label": rdef["label"], "columns_label": DIMENSIONS[cols_dim]["label"] if cols_dim else None,
        "grand_total": total_row["value"], "fact_rows_scanned": total_row["fact_rows"],
        "total_groups": total_groups, "returned_groups": len(result["rows"]),
        "truncated": total_groups > len(result["rows"]),
        "filters": normalized, "slices": slices,
        "sql": sql, "sql_params": args,
        "drill_down_to": drill_down_level(rows_dim) if rows_dim in TIME_HIERARCHY else None,
        "roll_up_to": roll_up_level(rows_dim) if rows_dim in TIME_HIERARCHY else None,
        "explanation": explain(rows_dim, cols_dim, measure, normalized, slices),
    })
    cache.put(key, result)
    return result


def explain(rows_dim, cols_dim, measure, filters, slices) -> str:
    parts = [f"{MEASURES[measure]['label']} grouped by {DIMENSIONS[rows_dim]['label'].lower()}"]
    if cols_dim:
        parts[0] += f" (rows) × {DIMENSIONS[cols_dim]['label'].lower()} (columns) — PIVOT"
    if rows_dim in TIME_HIERARCHY:
        parts.append(f"time level = {rows_dim} (roll-up ↑ {roll_up_level(rows_dim) or '—'}, "
                     f"drill-down ↓ {drill_down_level(rows_dim) or '—'})")
    if slices:
        parts.append("SLICE " + ", ".join(f"{DIMENSIONS[d]['label']} = {v}" for d, v in slices.items()))
    dice = []
    if filters.get("date_from") or filters.get("date_to"):
        dice.append(f"date {filters.get('date_from') or '…'} → {filters.get('date_to') or '…'}")
    for k in ("countries", "products", "customers"):
        if filters.get(k):
            dice.append(f"{k} ∈ {{{', '.join(filters[k][:5])}{'…' if len(filters[k]) > 5 else ''}}}")
    if dice:
        parts.append(("DICE " if len(dice) > 1 else "filter ") + "; ".join(dice))
    parts.append("eligible lines only: merchandise SALE + CANCELLATION, duplicates excluded")
    return " · ".join(parts)


def to_csv_rows(result: dict):
    """Flattens an OLAP result into header + rows for CSV export."""
    if result["mode"] == "pivot":
        header = [result["rows_label"]] + [str(c["member"]) for c in result["columns"]] + ["Row total"]
        body = [[r["member"]] + r["cells"] + [r["value"]] for r in result["rows"]]
    else:
        header = [result["rows_label"], result["measure_label"], "Fact rows"]
        body = [[r["member"], r["value"], r["fact_rows"]] for r in result["rows"]]
    return header, body


def metadata() -> dict:
    return {
        "dimensions": [{"id": k, "label": v["label"]} for k, v in DIMENSIONS.items()],
        "measures": [{"id": k, "label": v["label"], "format": v["fmt"]} for k, v in MEASURES.items()],
        "time_hierarchy": TIME_HIERARCHY,
        "max_rows": MAX_ROWS,
    }
