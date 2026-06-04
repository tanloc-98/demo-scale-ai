"""
In-memory job store + Redis fallback for job queue management.
"""
import asyncio
import json
import os
import uuid
from datetime import datetime
from typing import Optional, Dict, Any

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# In-memory store (works without Redis for local demo)
_jobs: Dict[str, dict] = {}
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
    "history": [],  # for charts
}

def _new_job(employee_id: str, job_type: str, payload: dict) -> dict:
    job_id = str(uuid.uuid4())[:8].upper()
    now = datetime.utcnow().isoformat()
    job = {
        "job_id": job_id,
        "employee_id": employee_id,
        "job_type": job_type,
        "status": "queued",
        "payload": payload,
        "result": None,
        "error": None,
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
        "wait_seconds": 0.0,
        "duration_seconds": 0.0,
        "position": len([j for j in _jobs.values() if j["status"] == "queued"]) + 1,
    }
    _jobs[job_id] = job
    _metrics["queue_depth"] = len([j for j in _jobs.values() if j["status"] == "queued"])
    return job


def get_job(job_id: str) -> Optional[dict]:
    return _jobs.get(job_id)


def list_jobs(limit: int = 50) -> list:
    jobs = sorted(_jobs.values(), key=lambda j: j["created_at"], reverse=True)
    return jobs[:limit]


def update_job(job_id: str, **kwargs):
    if job_id in _jobs:
        _jobs[job_id].update(kwargs)
        _jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()
        _metrics["queue_depth"] = len([j for j in _jobs.values() if j["status"] == "queued"])


def clear_done_jobs():
    to_del = [jid for jid, j in _jobs.items() if j["status"] in ("completed", "failed")]
    for jid in to_del:
        del _jobs[jid]


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
    """Run a job asynchronously and update status."""
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
        _metrics["p95_latency_ms"] = round(duration * 1000, 1)
    except Exception as e:
        update_job(job_id, status="failed", error=str(e))
        _metrics["queue_depth"] = len([j for j in _jobs.values() if j["status"] == "queued"])

def seed_demo_jobs():
    """Seed initial completed jobs for the demo dashboard."""
    if len(_jobs) > 0:
        return
        
    for i in range(1, 4):
        emp_id = f"EMP{i:03d}"
        payload = {
            "employee_id": emp_id,
            "month": "2026-05",
            "base_salary": 15000000 + (i * 1000000),
            "overtime_hours": i * 2,
            "days_absent": 0,
        }
        job = _new_job(emp_id, "salary", payload)
        
        # Simulate completed job
        update_job(
            job["job_id"],
            status="completed",
            result={"net_salary": 12000000 + (i * 500000)},
            completed_at=datetime.utcnow().isoformat(),
            duration_seconds=1.2 + (i * 0.1)
        )
        
    _metrics["completed_today"] = 3
    _metrics["queue_depth"] = 0

