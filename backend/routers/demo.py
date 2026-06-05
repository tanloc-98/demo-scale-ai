"""Demo Control Router — scale pods, launch load test, red-team runner."""
import asyncio
import json
import random
import subprocess
import time
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import StreamingResponse
from backend.db.job_store import update_metrics, get_metrics

# K8s deployment names (must match k8s/agents/ manifests)
_DEPLOYMENT_MAP = {
    "agent-gateway":  "agent-gateway",
    "salary-agent":   "salary-agent",
    "timesheet-agent":"timesheet-agent",
}
_HPA_MAP = {
    "agent-gateway":  "agent-gateway-hpa",
    "salary-agent":   "salary-agent-hpa",
    "timesheet-agent":"timesheet-agent-hpa",
}

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
    """Scale a K8s deployment via kubectl. ArgoCD ignores spec.replicas so this persists."""
    service  = payload.get("service", "")
    replicas = int(payload.get("replicas", 1))

    if service not in _pod_state:
        return {"error": f"Unknown service: {service}. Valid: {list(_pod_state.keys())}"}

    old = _pod_state[service]["desired"]
    deployment = _DEPLOYMENT_MAP.get(service, service)

    # Scale deployment AND update HPA minReplicas to prevent HPA fighting back
    try:
        r1 = subprocess.run(
            ["kubectl", "scale", "deployment", deployment,
             f"--replicas={replicas}", "-n", "hr-ai"],
            capture_output=True, text=True, timeout=10
        )
        if r1.returncode != 0:
            return {"error": r1.stderr.strip(), "service": service}
        # Update HPA minReplicas so HPA doesn't immediately revert the scale
        hpa_name = _HPA_MAP.get(service)
        if hpa_name:
            subprocess.run(
                ["kubectl", "patch", "hpa", hpa_name, "-n", "hr-ai",
                 "--type=merge",
                 f"--patch={{\"spec\":{{\"minReplicas\":{replicas}}}}}"],
                capture_output=True, text=True, timeout=10
            )
    except Exception as e:
        return {"error": str(e), "service": service}

    _pod_state[service]["desired"] = replicas
    update_metrics(pod_counts={svc: s["running"] for svc, s in _pod_state.items()})

    # Track running count as pods spin up
    async def _track_running(svc: str, target: int):
        for _ in range(30):          # poll up to 60s
            await asyncio.sleep(2)
            try:
                r = subprocess.run(
                    ["kubectl", "get", "pods", "-n", "hr-ai",
                     "-l", f"app={deployment}", "--no-headers"],
                    capture_output=True, text=True, timeout=5
                )
                running = sum(1 for l in r.stdout.strip().splitlines()
                              if "Running" in l and "1/1" in l)
                _pod_state[svc]["running"] = running
                update_metrics(pod_counts={s: p["running"] for s, p in _pod_state.items()})
                if running == target:
                    break
            except Exception:
                break

    background_tasks.add_task(_track_running, service, replicas)
    return {
        "service":      service,
        "deployment":   deployment,
        "old_replicas": old,
        "new_replicas": replicas,
        "status":       "scaling",
        "message":      f"kubectl scale {deployment} --replicas={replicas} applied",
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
        from backend.db.job_store import create_salary_job, update_job
        total = rps * 60  # simulate 60 seconds worth
        batch = min(rps, 50)
        for _ in range(total // batch):
            if not _load_test_state["active"]:
                break
            for _ in range(batch):
                emp = f"EMP{random.randint(1,200):03d}"
                payload = {
                    "employee_id": emp, "month": "2026-05",
                    "base_salary": random.randint(10_000_000, 25_000_000),
                    "overtime_hours": random.randint(0, 20),
                    "days_absent": random.randint(0, 2),
                }
                job = create_salary_job(emp, payload)
                # Mark as completed immediately (simulated load, no real processing)
                update_job(job["job_id"], status="completed",
                           result={"net_salary": payload["base_salary"] * 0.85})
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
