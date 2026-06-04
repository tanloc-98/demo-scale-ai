"""
Redis-backed job store — shared across all pods.
Falls back to in-memory when Redis is unavailable (local dev without Docker).
"""
import json
import os
import uuid
from datetime import datetime
from typing import Optional, Dict, Any

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
JOB_TTL   = 86400   # 24 hours

_redis: Any = None
_jobs_fallback: Dict[str, dict] = {}   # fallback when Redis unavailable

# ── Metrics (in-memory per pod, refreshed from Redis periodically) ─────────
_metrics = {
    "throughput_rps": 0.0,
    "p95_latency_ms": 850.0,
    "cache_hit_rate": 0.34,
    "error_rate": 0.001,
    "pod_counts": {"agent-gateway": 2, "salary-agent": 1, "timesheet-agent": 1, "mlx-lm": 1},
    "queue_depth": 0,
    "load_test_active": False,
    "load_test_rps": 0,
    "completed_today": 0,
    "history": [],
}


def _get_redis():
    global _redis
    if _redis is not None:
        return _redis
    try:
        import redis as redis_lib
        r = redis_lib.from_url(REDIS_URL, decode_responses=True, socket_timeout=1)
        r.ping()
        _redis = r
        return _redis
    except Exception:
        return None


# ── Core CRUD ───────────────────────────────────────────────────────────────

def _save_job(job: dict):
    r = _get_redis()
    job_id = job["job_id"]
    if r:
        r.setex(f"job:{job_id}", JOB_TTL, json.dumps(job))
        r.lpush("jobs:index", job_id)
        r.expire("jobs:index", JOB_TTL)
    else:
        _jobs_fallback[job_id] = job


def get_job(job_id: str) -> Optional[dict]:
    r = _get_redis()
    if r:
        raw = r.get(f"job:{job_id}")
        return json.loads(raw) if raw else None
    return _jobs_fallback.get(job_id)


def list_jobs(limit: int = 50) -> list:
    r = _get_redis()
    if r:
        ids = r.lrange("jobs:index", 0, limit - 1)
        jobs = []
        for jid in ids:
            raw = r.get(f"job:{jid}")
            if raw:
                jobs.append(json.loads(raw))
        return jobs
    return sorted(_jobs_fallback.values(), key=lambda j: j["created_at"], reverse=True)[:limit]


def update_job(job_id: str, **kwargs):
    job = get_job(job_id)
    if job is None:
        return
    job.update(kwargs)
    job["updated_at"] = datetime.utcnow().isoformat()
    _save_job(job)
    # Update queue depth metric
    _sync_queue_depth()


def _sync_queue_depth():
    r = _get_redis()
    if r:
        ids = r.lrange("jobs:index", 0, 200)
        depth = 0
        for jid in ids:
            raw = r.get(f"job:{jid}")
            if raw:
                j = json.loads(raw)
                if j.get("status") in ("queued", "processing"):
                    depth += 1
        _metrics["queue_depth"] = depth
    else:
        _metrics["queue_depth"] = len(
            [j for j in _jobs_fallback.values() if j["status"] in ("queued",)]
        )


def _new_job(employee_id: str, job_type: str, payload: dict) -> dict:
    job_id = str(uuid.uuid4())[:8].upper()
    now = datetime.utcnow().isoformat()
    _sync_queue_depth()
    job = {
        "job_id":       job_id,
        "employee_id":  employee_id,
        "job_type":     job_type,
        "status":       "queued",
        "payload":      payload,
        "result":       None,
        "error":        None,
        "created_at":   now,
        "updated_at":   now,
        "completed_at": None,
        "wait_seconds": 0.0,
        "duration_seconds": 0.0,
        "position":     _metrics["queue_depth"] + 1,
    }
    _save_job(job)
    _metrics["queue_depth"] += 1
    return job


def clear_done_jobs():
    r = _get_redis()
    if r:
        ids = r.lrange("jobs:index", 0, -1)
        for jid in ids:
            raw = r.get(f"job:{jid}")
            if raw:
                j = json.loads(raw)
                if j.get("status") in ("completed", "failed"):
                    r.delete(f"job:{jid}")
    else:
        to_del = [jid for jid, j in _jobs_fallback.items() if j["status"] in ("completed", "failed")]
        for jid in to_del:
            del _jobs_fallback[jid]


# ── Public helpers ──────────────────────────────────────────────────────────

def get_metrics() -> dict:
    return dict(_metrics)


def get_queue_depth() -> int:
    return int(_metrics.get("queue_depth", 0))


def update_metrics(**kwargs):
    _metrics.update(kwargs)


def create_salary_job(employee_id: str, payload: dict) -> dict:
    return _new_job(employee_id, "salary", payload)


def create_timesheet_job(employee_id: str, payload: dict) -> dict:
    return _new_job(employee_id, "timesheet", payload)


async def process_job_async(job_id: str, processor_fn, *args):
    """Run a job asynchronously and update status in Redis."""
    import time
    start = time.time()
    update_job(job_id, status="processing")
    try:
        result = await processor_fn(*args)
        duration = time.time() - start
        update_job(
            job_id,
            status="completed",
            result=result,
            completed_at=datetime.utcnow().isoformat(),
            duration_seconds=round(duration, 3),
        )
        _metrics["completed_today"] = _metrics.get("completed_today", 0) + 1
        _metrics["p95_latency_ms"]  = round(duration * 1000, 1)
    except Exception as e:
        update_job(job_id, status="failed", error=str(e))
    finally:
        _sync_queue_depth()


def seed_demo_jobs():
    """Seed initial completed jobs for demo dashboard (idempotent)."""
    r = _get_redis()
    seed_key = "demo:seeded"
    if r and r.get(seed_key):
        return
    for i in range(1, 4):
        emp_id = f"EMP{i:03d}"
        payload = {
            "employee_id": emp_id,
            "month": "2026-05",
            "base_salary": 15_000_000 + (i * 1_000_000),
            "overtime_hours": i * 2,
            "days_absent": 0,
        }
        job = _new_job(emp_id, "salary", payload)
        update_job(
            job["job_id"],
            status="completed",
            result={"net_salary": 12_000_000 + (i * 500_000)},
            completed_at=datetime.utcnow().isoformat(),
            duration_seconds=1.2 + (i * 0.1),
        )
    _metrics["completed_today"] = 3
    _metrics["queue_depth"] = 0
    if r:
        r.set(seed_key, "1", ex=3600)
