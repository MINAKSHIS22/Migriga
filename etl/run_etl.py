# MIGRIGA Analytics - ETL orchestrator
# Usage:  python -m etl.run_etl [--source PATH] [--warehouse PATH] [--force]
import argparse
import os
import json
import sys
import time

from . import config
from .extract import SourceValidationError, extract
from .load import (connect, finish_run, init_schema, last_successful_run, load,
                   mark_interrupted_runs, start_run, table_counts, verify)
from .lock import ETLLock
from .transform import transform


def run_etl(source: str = None, warehouse: str = None, force: bool = False,
            triggered_by: str = "cli", progress=None, _fail_after_facts: bool = False) -> dict:
    """Runs Extract -> Transform -> Load -> Verify. Returns the run summary dict.

    If the source file is byte-identical (sha256) to the last successful load and
    force is False, the run is logged as SKIPPED_UNCHANGED and the warehouse is untouched.
    """
    source = source or config.source_csv_path()
    warehouse = warehouse or config.warehouse_path()
    report = progress or (lambda stage, pct: None)
    t0 = time.time()

    with ETLLock(warehouse):
        conn = connect(warehouse)
        try:
            init_schema(conn)
            mark_interrupted_runs(conn)
            run_id = start_run(conn, triggered_by, os.path.basename(source))
            try:
                report("extract", 5)
                ex = extract(source)
                prev = last_successful_run(conn)
                if prev and prev["source_sha256"] == ex.meta["source_sha256"] and not force:
                    finish_run(conn, run_id, "SKIPPED_UNCHANGED",
                               source_sha256=ex.meta["source_sha256"], source_size=ex.meta["source_size_bytes"],
                               rows_read=ex.meta["rows_read"], rows_accepted=0, rows_rejected=0, rows_loaded=0,
                               elapsed_seconds=round(time.time() - t0, 2),
                               warnings_json=[f"Source unchanged since run #{prev['run_id']}; nothing reloaded. "
                                              "Use force to rebuild."])
                    report("done", 100)
                    return _summary(conn, run_id)

                report("transform", 25)
                tr = transform(ex.raw)
                report("load", 55)
                loaded = load(conn, run_id, ex.raw, tr, fail_after_facts=_fail_after_facts)
                report("verify", 90)
                check = verify(conn, len(tr.facts), float(tr.facts["line_amount"].sum()))
                quality = {**tr.quality, "extract": ex.meta, "verification": check}
                warnings = list(tr.warnings)
                if not check["passed"]:
                    warnings.append("Post-load verification reported inconsistencies; see quality.verification.")
                finish_run(conn, run_id, "SUCCESS",
                           source_sha256=ex.meta["source_sha256"], source_size=ex.meta["source_size_bytes"],
                           rows_read=ex.meta["rows_read"], rows_accepted=tr.quality["rows_accepted"],
                           rows_rejected=tr.quality["rows_rejected"], rows_loaded=loaded,
                           elapsed_seconds=round(time.time() - t0, 2),
                           quality_json=quality, warnings_json=warnings)
                report("done", 100)
                return _summary(conn, run_id)
            except Exception as exc:
                msg = str(exc) if isinstance(exc, SourceValidationError) else f"{exc.__class__.__name__}: {exc}"
                finish_run(conn, run_id, "FAILED", elapsed_seconds=round(time.time() - t0, 2),
                           error_message=msg[:1000])
                raise
        finally:
            conn.close()


def _summary(conn, run_id: int) -> dict:
    row = dict(conn.execute("SELECT * FROM etl_run_log WHERE run_id = ?", (run_id,)).fetchone())
    for k in ("quality_json", "warnings_json"):
        row[k.replace("_json", "")] = json.loads(row.pop(k)) if row.get(k) else ([] if "warn" in k else {})
    row["table_counts"] = table_counts(conn)
    return row


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Run the Migriga Analytics ETL pipeline.")
    p.add_argument("--source", help="Path to the retail CSV (default: data/raw/online_retail_09_10.csv)")
    p.add_argument("--warehouse", help="Path to the SQLite warehouse (default: data/warehouse/migriga_warehouse.db)")
    p.add_argument("--force", action="store_true", help="Reload even if the source file is unchanged")
    args = p.parse_args(argv)

    def show(stage, pct):
        print(f"[{pct:3d}%] {stage}", flush=True)

    try:
        s = run_etl(args.source, args.warehouse, force=args.force, progress=show)
    except Exception as exc:
        print(f"ETL FAILED: {exc}", file=sys.stderr)
        return 1
    q = s.get("quality", {})
    print(f"\nRun #{s['run_id']} {s['status']} in {s['elapsed_seconds']}s")
    print(f"  rows read     : {s['rows_read']}")
    print(f"  rows accepted : {s['rows_accepted']}")
    print(f"  rows rejected : {s['rows_rejected']}")
    print(f"  rows loaded   : {s['rows_loaded']}")
    if q.get("lines_by_type"):
        print(f"  lines by type : {q['lines_by_type']}")
        print(f"  duplicates    : {q['duplicate_lines_flagged']} flagged")
        print(f"  verification  : {'PASSED' if q['verification']['passed'] else 'FAILED'}")
    for w in s.get("warnings", []):
        print(f"  warning: {w}")
    print(f"  tables        : {s['table_counts']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
