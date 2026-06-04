"""SSE Metrics Stream + Demo Observability Router"""
import asyncio
import json
import random
import time
from datetime import datetime
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from backend.db.job_store import get_metrics, update_metrics, list_jobs

router = APIRouter(prefix="/stream", tags=["stream"])

# Simulated trace store
_traces = []


def _generate_trace(job: dict) -> dict:
    base_ms = random.uniform(800, 1400)
    return {
        "trace_id": f"trace-{job['job_id']}",
        "job_id": job["job_id"],
        "employee_id": job.get("employee_id", ""),
        "job_type": job.get("job_type", "salary"),
        "status": job.get("status", "completed"),
        "total_ms": round(base_ms),
        "timestamp": job.get("completed_at") or job.get("created_at"),
        "spans": [
            {"name": "agent_gateway.route",       "ms": round(random.uniform(1, 5)),   "status": "ok"},
            {"name": "redis.cache_lookup",         "ms": round(random.uniform(1, 3)),   "status": "miss"},
            {"name": f"{job.get('job_type','salary')}_agent.process", "ms": round(base_ms - 50), "status": "ok"},
            {"name": "tool.calculator",            "ms": round(random.uniform(3, 8)),   "status": "ok"},
            {"name": "llm.format_response",        "ms": round(random.uniform(300, 800)), "status": "ok",
             "prompt_tokens": random.randint(150, 220),
             "completion_tokens": random.randint(80, 150)},
            {"name": "redis.cache_write",          "ms": round(random.uniform(1, 2)),   "status": "ok"},
        ],
    }


def _get_live_metrics() -> dict:
    metrics = get_metrics()
    jobs = list_jobs(100)
    processing = [j for j in jobs if j["status"] == "processing"]
    queued = [j for j in jobs if j["status"] == "queued"]
    completed = [j for j in jobs if j["status"] == "completed"]

    # Update traces from completed jobs
    for job in completed[-5:]:
        exists = any(t["job_id"] == job["job_id"] for t in _traces)
        if not exists:
            _traces.append(_generate_trace(job))

    # Simulate realistic fluctuating metrics
    pod_counts = metrics.get("pod_counts", {})
    total_pods = sum(pod_counts.values())

    return {
        "queue_depth": len(queued),
        "processing": len(processing),
        "completed_today": len(completed),
        "pod_counts": pod_counts,
        "total_pods": total_pods,
        "throughput_rps": round(random.uniform(0.8, 2.1) if processing else random.uniform(0.0, 0.5), 2),
        "p95_latency_ms": metrics.get("p95_latency_ms", 850),
        "cache_hit_rate": round(random.uniform(0.28, 0.42), 2),
        "error_rate": round(random.uniform(0.0, 0.003), 4),
        "mlx_lm_status": "online",
        "load_test_active": metrics.get("load_test_active", False),
        "load_test_rps": metrics.get("load_test_rps", 0),
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/metrics")
async def stream_metrics():
    """SSE endpoint — push metrics every 2 seconds."""
    async def generator():
        while True:
            data = _get_live_metrics()
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


# Observability
obs_router = APIRouter(prefix="/traces", tags=["observability"])

@obs_router.get("")
async def get_traces(limit: int = 20):
    jobs = list_jobs(50)
    traces = []
    for job in jobs:
        if job.get("status") in ("completed", "processing"):
            traces.append(_generate_trace(job))
    return {"traces": traces[-limit:], "total": len(traces)}


@obs_router.get("/{trace_id}")
async def get_trace(trace_id: str):
    jobs = list_jobs(200)
    for job in jobs:
        if f"trace-{job['job_id']}" == trace_id:
            return _generate_trace(job)
    # Return a sample trace
    return {
        "trace_id": trace_id,
        "error": "Trace not found, showing sample",
        "spans": [],
    }
