# MIGRIGA Analytics API - /api/analytics/*
# Exposes the data warehouse, ETL pipeline, OLAP engine, Apriori market basket analysis and
# RFM/K-Means segmentation. Every endpoint requires an authenticated admin session.
import csv
import io
import json
import logging
import math
import os
import sqlite3
import threading
import uuid
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from analytics import customer_segmentation, dashboard, market_basket, olap
from analytics.jobs import TooManyJobs, jobs
from analytics.warehouse import (AnalyticsParamError, WarehouseUnavailable, cache, cache_token, connect,
                                 data_version, freeze)
from backend.deps import require_admin
from etl import config
from etl.lock import ETLAlreadyRunning

log = logging.getLogger("migriga.analytics")
router = APIRouter(prefix="/api/analytics", tags=["analytics"], dependencies=[Depends(require_admin)])


# ------------------------------------------------------------------ errors
def register_error_handlers(app):
    @app.exception_handler(WarehouseUnavailable)
    async def _warehouse_unavailable(request: Request, exc: WarehouseUnavailable):
        return JSONResponse(status_code=503, content={"detail": str(exc), "code": "warehouse_unavailable"})

    @app.exception_handler(AnalyticsParamError)
    async def _bad_param(request: Request, exc: AnalyticsParamError):
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "invalid_parameter"})

    @app.exception_handler(TooManyJobs)
    async def _too_many(request: Request, exc: TooManyJobs):
        return JSONResponse(status_code=429, content={"detail": str(exc), "code": "too_many_jobs"})

    @app.exception_handler(ETLAlreadyRunning)
    async def _etl_running(request: Request, exc: ETLAlreadyRunning):
        return JSONResponse(status_code=409, content={"detail": str(exc), "code": "etl_running"})

    @app.exception_handler(sqlite3.Error)
    async def _db_error(request: Request, exc: sqlite3.Error):
        log.exception("Warehouse query failed")
        return JSONResponse(status_code=500, content={"detail": "A warehouse query failed. See the server log.",
                                                      "code": "warehouse_error"})


class _Conn:
    """Context manager for a read-only warehouse connection."""
    def __enter__(self):
        self.conn = connect()
        return self.conn

    def __exit__(self, *exc):
        self.conn.close()


# ------------------------------------------------------------------ CSV helper
def _csv_cell(v):
    # Neutralise spreadsheet formula injection in text cells
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + v
    return v


def _csv_response(filename: str, header: list, rows: list):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    for r in rows:
        w.writerow([_csv_cell(v) for v in r])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# ------------------------------------------------------------------ overview & filters
def _dataset_info():
    return {"citation": config.DATASET_CITATION, "license": config.DATASET_LICENSE, "note": config.DATASET_NOTE,
            "source_file": os.path.basename(config.source_csv_path()),
            "source_present": os.path.isfile(config.source_csv_path())}


@router.get("/overview")
def overview():
    info = {"dataset": _dataset_info(), "initialized": False}
    try:
        with _Conn() as conn:
            info["initialized"] = True
            info["data_version"] = data_version(conn)
            info["loaded_at"] = (conn.execute("SELECT value FROM warehouse_meta WHERE key='loaded_at'").fetchone()
                                 or [None])[0]
            info["filter_options"] = dashboard.filter_options(conn)
    except WarehouseUnavailable as exc:
        info["message"] = str(exc)
    info["olap"] = olap.metadata()
    info["etl_running"] = jobs.active("etl") is not None
    return info


@router.get("/products/search")
def product_search(q: str = Query("", max_length=100), limit: int = Query(20, ge=1, le=50)):
    with _Conn() as conn:
        return {"products": dashboard.search_products(conn, q, limit)}


# ------------------------------------------------------------------ dashboard
def _filters_from_query(date_from, date_to, countries, products):
    return {"date_from": date_from, "date_to": date_to, "countries": countries, "products": products}


@router.get("/dashboard")
def get_dashboard(date_from: Optional[str] = None, date_to: Optional[str] = None,
                  countries: Optional[str] = Query(None, max_length=2000),
                  products: Optional[str] = Query(None, max_length=2000)):
    with _Conn() as conn:
        return dashboard.get_dashboard(conn, _filters_from_query(date_from, date_to, countries, products))


# ------------------------------------------------------------------ OLAP
class OLAPRequest(BaseModel):
    rows: str = "month"
    columns: Optional[str] = None
    measure: str = "net_sales"
    sort: str = "natural"
    limit: int = 500
    filters: Dict = Field(default_factory=dict)
    slices: Dict[str, str] = Field(default_factory=dict)


@router.post("/olap")
def olap_query(req: OLAPRequest):
    with _Conn() as conn:
        return olap.run_query(conn, req.model_dump())


@router.post("/olap/export")
def olap_export(req: OLAPRequest):
    with _Conn() as conn:
        result = olap.run_query(conn, {**req.model_dump(), "limit": olap.MAX_ROWS})
    header, rows = olap.to_csv_rows(result)
    return _csv_response(f"migriga_olap_{result['rows_dimension']}_{result['measure']}.csv", header, rows)


# ------------------------------------------------------------------ ETL
class ETLRunRequest(BaseModel):
    force: bool = False


def _etl_status_payload():
    path = config.warehouse_path()
    status = {"warehouse_exists": os.path.isfile(path), "dataset": _dataset_info(),
              "running_job": jobs.active("etl"), "runs": [], "last_success": None, "table_counts": {}}
    if not status["warehouse_exists"]:
        return status
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        try:
            runs = [dict(r) for r in conn.execute(
                "SELECT run_id, started_at, finished_at, status, triggered_by, source_file, rows_read, rows_accepted, "
                "rows_rejected, rows_loaded, elapsed_seconds, warnings_json, error_message "
                "FROM etl_run_log ORDER BY run_id DESC LIMIT 15").fetchall()]
        except sqlite3.OperationalError:
            return status
        for r in runs:
            r["warnings"] = json.loads(r.pop("warnings_json") or "[]")
        status["runs"] = runs
        last = conn.execute("SELECT * FROM etl_run_log WHERE status='SUCCESS' ORDER BY run_id DESC LIMIT 1").fetchone()
        if last:
            last = dict(last)
            last["quality"] = json.loads(last.pop("quality_json") or "{}")
            last["warnings"] = json.loads(last.pop("warnings_json") or "[]")
            last["quality"].get("extract", {}).pop("source_path", None)
            status["last_success"] = last
        for t in ["dim_date", "dim_product", "dim_customer", "dim_country", "fact_sales", "stg_raw_sales",
                  "etl_rejected_rows", "etl_run_log"]:
            status["table_counts"][t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        status["line_type_counts"] = {r[0]: r[1] for r in conn.execute(
            "SELECT line_type, COUNT(*) FROM fact_sales GROUP BY line_type ORDER BY 2 DESC")}
    finally:
        conn.close()
    return status


@router.get("/etl/status")
def etl_status():
    return _etl_status_payload()


@router.post("/etl/run")
def etl_run(req: ETLRunRequest, admin: dict = Depends(require_admin)):
    from etl.run_etl import run_etl
    if jobs.active("etl"):
        raise ETLAlreadyRunning("An ETL run is already in progress.")

    def work(progress):
        summary = run_etl(force=req.force, triggered_by=f"web:{admin.get('email')}",
                          progress=lambda stage, pct: progress(stage, pct))
        if summary["status"] == "SUCCESS":
            cache.clear()
            jobs.clear_results(kinds=("basket", "segmentation"))
        return {"run_id": summary["run_id"], "status": summary["status"], "rows_loaded": summary["rows_loaded"]}

    job, _ = jobs.submit("etl", uuid.uuid4().hex, work, user=admin.get("email"))
    return {"job": job}


@router.get("/etl/rejected")
def etl_rejected(limit: int = Query(50, ge=1, le=500)):
    with _Conn() as conn:
        rows = conn.execute(
            "SELECT etl_run_id, source_row_number, reason, raw_record_json FROM etl_rejected_rows "
            "WHERE etl_run_id = (SELECT MAX(etl_run_id) FROM etl_rejected_rows) "
            "ORDER BY source_row_number LIMIT ?", (limit,)).fetchall()
        return {"rejected": [{**dict(r), "raw_record": json.loads(r["raw_record_json"])} for r in rows]}


# ------------------------------------------------------------------ jobs (shared)
@router.get("/jobs/{job_id}")
def job_status(job_id: str, include_result: bool = True):
    job = jobs.get(job_id, include_result=include_result)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found (it may have expired after a warehouse reload).")
    return {"job": job}


def _done_result(job_id: str, kind: str):
    job = jobs.get(job_id, include_result=False)
    if not job or job["kind"] != kind:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job["status"] != "done":
        raise HTTPException(status_code=409, detail=f"Job is {job['status']}; results are not available yet.")
    return jobs.result(job_id)


# ------------------------------------------------------------------ Market basket (Apriori)
class BasketRequest(BaseModel):
    min_support: float = market_basket.DEFAULTS["min_support"]
    min_confidence: float = market_basket.DEFAULTS["min_confidence"]
    min_lift: float = market_basket.DEFAULTS["min_lift"]
    max_len: int = market_basket.DEFAULTS["max_len"]
    country: Optional[str] = None


@router.post("/basket/jobs")
def basket_job(req: BasketRequest, admin: dict = Depends(require_admin)):
    params = market_basket.validate_params(req.model_dump())
    with _Conn() as conn:
        version = cache_token(conn)

    def work(progress):
        with _Conn() as conn:
            return market_basket.mine(conn, params, progress=progress)

    job, reused = jobs.submit("basket", (version, freeze(params)), work, user=admin.get("email"))
    return {"job": job, "cached": reused}


@router.get("/basket/{job_id}/export")
def basket_export(job_id: str, kind: str = Query("rules", pattern="^(rules|itemsets)$")):
    res = _done_result(job_id, "basket")
    desc = res.get("descriptions", {})
    name = lambda codes: " + ".join(f"{c} {desc.get(c, '')}".strip() for c in codes)
    if kind == "rules":
        header = ["antecedent", "consequent", "support", "support_count", "confidence", "lift"]
        rows = [[name(r["antecedent"]), name(r["consequent"]), round(r["support"], 6), r["support_count"],
                 round(r["confidence"], 6), round(r["lift"], 6)] for r in res["rules"]]
    else:
        header = ["itemset", "size", "support", "support_count"]
        rows = [[name(i["items"]), i["size"], round(i["support"], 6), i["support_count"]] for i in res["itemsets"]]
    return _csv_response(f"migriga_apriori_{kind}.csv", header, rows)


# ------------------------------------------------------------------ Segmentation (RFM + K-Means)
class SegmentationRequest(BaseModel):
    k: int = customer_segmentation.DEFAULT_K
    seed: int = customer_segmentation.DEFAULT_SEED


@router.post("/segmentation/jobs")
def segmentation_job(req: SegmentationRequest, admin: dict = Depends(require_admin)):
    params = customer_segmentation.validate_params(req.model_dump())
    with _Conn() as conn:
        version = cache_token(conn)

    def work(progress):
        with _Conn() as conn:
            return customer_segmentation.segment(conn, params, progress=progress)

    job, reused = jobs.submit("segmentation", (version, freeze(params)), work, user=admin.get("email"))
    return {"job": job, "cached": reused}


@router.get("/segmentation/{job_id}/export")
def segmentation_export(job_id: str, cluster: Optional[int] = Query(None, ge=1, le=10)):
    res = _done_result(job_id, "segmentation")
    rows = [c for c in res["customers"] if cluster is None or c["cluster"] == cluster]
    header = ["customer_id", "country", "recency_days", "frequency", "monetary_gbp", "cluster"]
    body = [[c["customer_id"], c["country"], c["recency_days"], c["frequency"], c["monetary"], c["cluster"]]
            for c in rows]
    suffix = f"_cluster{cluster}" if cluster else ""
    return _csv_response(f"migriga_rfm_segments_k{res['params']['k']}{suffix}.csv", header, body)


# ------------------------------------------------------------------ DWM Lab: Apriori on a small editable dataset
class LabAprioriRequest(BaseModel):
    baskets: List[List[str]]
    min_support: float = 0.4
    min_confidence: float = 0.6


@router.post("/lab/apriori-demo")
def lab_apriori(req: LabAprioriRequest):
    if not 1 <= len(req.baskets) <= 30:
        raise AnalyticsParamError("Provide between 1 and 30 baskets.")
    baskets = []
    for b in req.baskets:
        items = {str(i).strip()[:40] for i in b if str(i).strip()}
        if len(items) > 15:
            raise AnalyticsParamError("Each demo basket may contain at most 15 items.")
        if items:
            baskets.append(items)
    if not baskets:
        raise AnalyticsParamError("All baskets are empty.")
    if not 0.05 <= req.min_support <= 1 or not 0.0 <= req.min_confidence <= 1:
        raise AnalyticsParamError("min_support must be 0.05-1 and min_confidence 0-1.")
    trace = []
    freq = market_basket.apriori(baskets, req.min_support, max_len=4, trace=trace)
    rules = market_basket.association_rules(freq, len(baskets), req.min_confidence, 0.0)
    return {
        "n_baskets": len(baskets),
        "min_support_count": max(1, math.ceil(req.min_support * len(baskets) - 1e-9)),
        "trace": trace,
        "itemsets": sorted(({"items": sorted(s), "support_count": c, "support": c / len(baskets)}
                            for s, c in freq.items()), key=lambda x: (len(x["items"]), x["items"])),
        "rules": rules,
    }


# ------------------------------------------------------------------ startup warm-up
def warm_cache():
    """Precomputes the default dashboard and segmentation in the background (if the warehouse exists)."""
    def run():
        try:
            with _Conn() as conn:
                dashboard.filter_options(conn)
                dashboard.get_dashboard(conn, {})
                version = cache_token(conn)
            params = customer_segmentation.validate_params({})

            def seg(progress):
                with _Conn() as c:
                    return customer_segmentation.segment(c, params, progress=progress)
            jobs.submit("segmentation", (version, freeze(params)), seg, user="startup")
        except WarehouseUnavailable:
            log.info("Analytics warehouse not initialised yet; skipping warm-up.")
        except Exception:
            log.exception("Analytics warm-up failed")
    threading.Thread(target=run, name="migriga-warmup", daemon=True).start()
