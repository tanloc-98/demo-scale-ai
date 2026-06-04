"""Demo Control Router — scale pods, launch load test, red-team runner."""
import asyncio
import json
import random
import time
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import StreamingResponse
from backend.db.job_store import update_metrics, get_metrics

router = APIRouter(prefix="/demo", tags=["demo"])

# In-memory state for demo
_load_test_state = {
    "active": False,
    "target_rps": 0,
    "started_at": None,
    "requests_sent": 0,
    "errors": 0,
}

_pod_state = {
    "agent-gateway": {"desired": 2, "running": 2},
    "salary-agent":   {"desired": 1, "running": 1},
    "timesheet-agent":{"desired": 1, "running": 1},
    "mlx-lm":         {"desired": 1, "running": 1},
}

# Red-team test suite results (simulated)
_REDTEAM_SUITES = {
    "prompt_injection": {
        "label": "Prompt Injection",
        "cases": 12,
        "passed": 12,
        "risk": "LOW",
        "failures": [],
    },
    "data_exfiltration": {
        "label": "Data Exfiltration",
        "cases": 8,
        "passed": 8,
        "risk": "LOW",
        "failures": [],
    },
    "math_manipulation": {
        "label": "Math Manipulation",
        "cases": 10,
        "passed": 10,
        "risk": "LOW",
        "failures": [],
    },
    "jailbreak": {
        "label": "Jailbreak / Policy Bypass",
        "cases": 6,
        "passed": 6,
        "risk": "LOW",
        "failures": [],
    },
}


@router.post("/scale")
async def scale_service(payload: dict, background_tasks: BackgroundTasks):
    """Scale a service's replica count (simulated ArgoCD apply)."""
    service = payload.get("service", "")
    replicas = int(payload.get("replicas", 1))

    if service not in _pod_state:
        return {"error": f"Unknown service: {service}"}

    old = _pod_state[service]["desired"]
    _pod_state[service]["desired"] = replicas
    update_metrics(pod_counts={svc: s["running"] for svc, s in _pod_state.items()})

    # Simulate gradual pod spin-up in background
    async def _ramp(svc: str, target: int, current: int):
        step = 1 if target > current else -1
        for r in range(current, target, step):
            await asyncio.sleep(3)
            _pod_state[svc]["running"] = r + step
            update_metrics(pod_counts={s: p["running"] for s, p in _pod_state.items()})

    background_tasks.add_task(_ramp, service, replicas, old)
    return {
        "service": service,
        "old_replicas": old,
        "new_replicas": replicas,
        "status": "syncing",
        "message": f"ArgoCD syncing {service} → {replicas} replicas",
    }


@router.get("/pods")
async def get_pods():
    """Return current pod state."""
    pods = []
    for svc, state in _pod_state.items():
        for i in range(max(state["desired"], state["running"])):
            status = "running" if i < state["running"] else "pending"
            pods.append({
                "name": f"{svc}-{i+1}",
                "service": svc,
                "status": status,
                "ready": status == "running",
            })
    return {"pods": pods, "pod_state": _pod_state}


@router.post("/loadtest/start")
async def start_load_test(payload: dict, background_tasks: BackgroundTasks):
    """Start simulated load test."""
    global _load_test_state
    rps = int(payload.get("target_rps", 10))
    _load_test_state = {
        "active": True,
        "target_rps": rps,
        "started_at": datetime.utcnow().isoformat(),
        "requests_sent": 0,
        "errors": 0,
    }
    update_metrics(load_test_active=True, load_test_rps=rps)

    async def _simulate_load():
        from backend.db.job_store import _jobs, _new_job, update_job
        import uuid
        total = rps * 60  # simulate 60 seconds worth
        batch = min(rps, 50)
        for _ in range(total // batch):
            if not _load_test_state["active"]:
                break
            for _ in range(batch):
                emp = f"EMP{random.randint(1,200):03d}"
                job = _new_job(emp, "salary", {
                    "employee_id": emp, "month": "2026-05",
                    "base_salary": random.randint(10_000_000, 25_000_000),
                    "overtime_hours": random.randint(0, 20),
                    "days_absent": random.randint(0, 2),
                })
                _load_test_state["requests_sent"] += 1
            await asyncio.sleep(1)
        _load_test_state["active"] = False
        update_metrics(load_test_active=False, load_test_rps=0)

    background_tasks.add_task(_simulate_load)
    return {"status": "started", "target_rps": rps}


@router.post("/loadtest/stop")
async def stop_load_test():
    _load_test_state["active"] = False
    update_metrics(load_test_active=False, load_test_rps=0)
    return {"status": "stopped"}


@router.get("/loadtest/status")
async def load_test_status():
    return _load_test_state


@router.post("/redteam/run")
async def run_redteam(payload: dict, background_tasks: BackgroundTasks):
    """Run selected red-team test suites."""
    selected = payload.get("suites", list(_REDTEAM_SUITES.keys()))
    results = {}
    for suite_id in selected:
        if suite_id in _REDTEAM_SUITES:
            s = _REDTEAM_SUITES[suite_id]
            # Simulate test run delay
            results[suite_id] = {
                **s,
                "run_at": datetime.utcnow().isoformat(),
                "duration_s": round(random.uniform(3, 12), 1),
            }
    total = sum(s["cases"] for s in results.values())
    passed = sum(s["passed"] for s in results.values())
    return {
        "results": results,
        "summary": {
            "total_cases": total,
            "passed": passed,
            "failed": total - passed,
            "overall_risk": "MEDIUM" if any(s["risk"] == "MEDIUM" for s in results.values()) else "LOW",
            "run_at": datetime.utcnow().isoformat(),
        },
    }


@router.get("/redteam/suites")
async def get_redteam_suites():
    return {"suites": _REDTEAM_SUITES}
