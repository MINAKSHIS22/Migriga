# MIGRIGA Analytics - Background job manager
# Expensive work (ETL, Apriori mining, K-Means segmentation) runs in a small worker pool so
# HTTP requests return immediately. Finished results are cached per (kind, params, data_version);
# an identical request returns the cached job instead of recomputing.
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor

MAX_ACTIVE_JOBS = 4
MAX_KEPT_JOBS = 50


class TooManyJobs(Exception):
    pass


class JobManager:
    def __init__(self, workers: int = 2):
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="migriga-job")
        self._jobs = {}
        self._by_key = {}
        self._lock = threading.Lock()

    def _public(self, job, include_result=True):
        out = {k: v for k, v in job.items() if k not in ("result", "key")}
        if include_result and job["status"] == "done":
            out["result"] = job["result"]
        return out

    def submit(self, kind: str, key, fn, *, user: str = None):
        """fn(progress) -> result. Returns (job_dict, reused_bool)."""
        with self._lock:
            existing_id = self._by_key.get((kind, key))
            if existing_id and existing_id in self._jobs:
                job = self._jobs[existing_id]
                if job["status"] in ("queued", "running", "done"):
                    return self._public(job), True
            active = sum(1 for j in self._jobs.values() if j["status"] in ("queued", "running"))
            if active >= MAX_ACTIVE_JOBS:
                raise TooManyJobs("Too many analysis jobs are running. Please wait for one to finish.")
            job_id = uuid.uuid4().hex[:12]
            job = {"id": job_id, "kind": kind, "status": "queued", "progress": 0, "message": "Queued",
                   "created_at": time.time(), "started_at": None, "finished_at": None, "error": None,
                   "submitted_by": user, "result": None, "key": key}
            self._jobs[job_id] = job
            self._by_key[(kind, key)] = job_id
            self._trim()

        def progress(message, pct):
            job["message"] = message
            job["progress"] = int(max(job["progress"], min(99, pct)))

        def run():
            job["status"], job["started_at"] = "running", time.time()
            try:
                job["result"] = fn(progress)
                job["status"], job["progress"], job["message"] = "done", 100, "Completed"
            except Exception as exc:  # report a safe message; keep the trace in the server log
                job["status"] = "failed"
                job["error"] = _safe_message(exc)
                job["message"] = "Failed"
                traceback.print_exc()
            finally:
                job["finished_at"] = time.time()

        self._pool.submit(run)
        return self._public(job), False

    def get(self, job_id: str, include_result=True):
        job = self._jobs.get(job_id)
        return self._public(job, include_result) if job else None

    def result(self, job_id: str):
        job = self._jobs.get(job_id)
        return job["result"] if job and job["status"] == "done" else None

    def active(self, kind: str):
        with self._lock:
            for j in self._jobs.values():
                if j["kind"] == kind and j["status"] in ("queued", "running"):
                    return self._public(j, include_result=False)
        return None

    def latest(self, kind: str):
        with self._lock:
            done = [j for j in self._jobs.values() if j["kind"] == kind and j["status"] == "done"]
        return max(done, key=lambda j: j["finished_at"]) if done else None

    def clear_results(self, kinds=None):
        """Called after the warehouse changes so stale results are never served."""
        with self._lock:
            for jid in [j for j, job in self._jobs.items()
                        if job["status"] in ("done", "failed") and (kinds is None or job["kind"] in kinds)]:
                self._jobs.pop(jid)
            self._by_key = {k: v for k, v in self._by_key.items() if v in self._jobs}

    def _trim(self):
        finished = sorted((j for j in self._jobs.values() if j["status"] in ("done", "failed")),
                          key=lambda j: j["created_at"])
        for j in finished[:max(0, len(self._jobs) - MAX_KEPT_JOBS)]:
            self._jobs.pop(j["id"], None)
        self._by_key = {k: v for k, v in self._by_key.items() if v in self._jobs}


def _safe_message(exc: Exception) -> str:
    from .warehouse import AnalyticsParamError, WarehouseUnavailable
    if isinstance(exc, (AnalyticsParamError, WarehouseUnavailable)):
        return str(exc)
    return f"The analysis failed ({exc.__class__.__name__}). See the server log for details."


jobs = JobManager()
