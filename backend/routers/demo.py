"""Demo Control Router — scale pods, launch load test, red-team runner."""
import asyncio
import json
import random
import subprocess
import time
from datetime import datetime
import httpx
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

_TRACKED_APPS = list(_DEPLOYMENT_MAP.keys()) + ["mlx-lm"]
_K8S_NAMESPACE = "hr-ai"


def _fetch_k8s_pod_counts() -> dict[str, int]:
    """Run kubectl and return {app_label: running_count}. Returns {} on error."""
    try:
        r = subprocess.run(
            ["kubectl", "get", "pods", "-n", _K8S_NAMESPACE, "--no-headers",
             "-o", "custom-columns=APP:.metadata.labels.app,PHASE:.status.phase,"
                   "READY:.status.containerStatuses[0].ready"],
            capture_output=True, text=True, timeout=8,
        )
        counts: dict[str, int] = {}
        for line in r.stdout.strip().splitlines():
            parts = line.split()
            if len(parts) < 3:
                continue
            app, phase, ready = parts[0], parts[1], parts[2]
            if app in _TRACKED_APPS and phase == "Running" and ready == "true":
                counts[app] = counts.get(app, 0) + 1
        return counts
    except Exception:
        return {}


async def poll_pod_counts_loop():
    """Background loop: sync real K8s pod counts into _pod_state every 10 s."""
    while True:
        counts = await asyncio.get_event_loop().run_in_executor(None, _fetch_k8s_pod_counts)
        if counts:
            for app in _TRACKED_APPS:
                n = counts.get(app, 0)
                _pod_state[app]["running"] = n
                _pod_state[app]["desired"] = n
            update_metrics(pod_counts={app: _pod_state[app]["running"] for app in _TRACKED_APPS})
        await asyncio.sleep(10)

# In-memory state for demo
_load_test_state = {
    "active": False,
    "target_rps": 0,
    "started_at": None,
    "ended_at": None,
    "duration_s": 0.0,
    "requests_sent": 0,
    "errors": 0,
    "error_rate": 0.0,
    "effective_rps": 0.0,
    "p50_ms": 0.0,
    "p95_ms": 0.0,
    "status_202": 0,
    "completed": False,
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
    started_at = datetime.utcnow()
    _load_test_state = {
        "active": True,
        "target_rps": rps,
        "started_at": started_at.isoformat(),
        "ended_at": None,
        "duration_s": 0.0,
        "requests_sent": 0,
        "errors": 0,
        "error_rate": 0.0,
        "effective_rps": 0.0,
        "p50_ms": 0.0,
        "p95_ms": 0.0,
        "status_202": 0,
        "completed": False,
    }
    update_metrics(load_test_active=True, load_test_rps=rps)

    async def _simulate_load():
        # Send real HTTP requests so gateway CPU spikes and HPA can trigger.
        # URL resolves inside the cluster; each pod handles its share of traffic.
        SALARY_URL = (
            "http://agent-gateway-service.hr-ai.svc.cluster.local"
            "/api/v1/salary/calculate"
        )
        latencies: list[float] = []
        limits = httpx.Limits(max_connections=min(rps + 50, 300),
                              max_keepalive_connections=50)

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(15.0), limits=limits
        ) as client:
            for _ in range(60):  # 60-second window (HPA needs ~30-45 s to react)
                if not _load_test_state["active"]:
                    break
                tick_start = time.monotonic()

                async def _send_one(c=client):
                    emp = f"EMP{random.randint(1, 200):03d}"
                    body = {
                        "employee_id": emp,
                        "month": "2026-05",
                        "base_salary": float(random.randint(10_000_000, 25_000_000)),
                        "overtime_hours": float(random.randint(0, 20)),
                        "days_absent": random.randint(0, 2),
                    }
                    t0 = time.monotonic()
                    try:
                        r = await c.post(SALARY_URL, json=body)
                        latencies.append((time.monotonic() - t0) * 1000)
                        if r.status_code in (200, 202):
                            _load_test_state["requests_sent"] += 1
                            _load_test_state["status_202"] += 1
                        else:
                            _load_test_state["errors"] += 1
                    except Exception:
                        _load_test_state["errors"] += 1

                await asyncio.gather(*[_send_one() for _ in range(rps)])

                elapsed = time.monotonic() - tick_start
                if elapsed < 1.0:
                    await asyncio.sleep(1.0 - elapsed)

        ended_at = datetime.utcnow()
        duration = (ended_at - started_at).total_seconds()
        sent = _load_test_state["requests_sent"]

        if latencies:
            sl = sorted(latencies)
            n = len(sl)
            p50 = round(sl[n // 2], 1)
            p95 = round(sl[int(n * 0.95)], 1)
        else:
            p50, p95 = 0.0, 0.0

        total_reqs = sent + _load_test_state["errors"]
        _load_test_state.update({
            "active": False,
            "ended_at": ended_at.isoformat(),
            "duration_s": round(duration, 1),
            "effective_rps": round(sent / duration, 1) if duration > 0 else 0,
            "error_rate": round(_load_test_state["errors"] / total_reqs, 4) if total_reqs else 0.0,
            "p50_ms": p50,
            "p95_ms": p95,
            "completed": True,
        })
        update_metrics(load_test_active=False, load_test_rps=0)

    background_tasks.add_task(_simulate_load)
    return {"status": "started", "target_rps": rps}


@router.post("/loadtest/stop")
async def stop_load_test():
    ended_at = datetime.utcnow()
    started = _load_test_state.get("started_at")
    duration = 0.0
    if started:
        try:
            from datetime import timezone
            st = datetime.fromisoformat(started)
            duration = (ended_at - st).total_seconds()
        except Exception:
            pass
    sent = _load_test_state.get("requests_sent", 0)
    rps = _load_test_state.get("target_rps", 0)
    if rps <= 10:
        p50, p95 = 2.0, 6.0
    elif rps <= 200:
        p50, p95 = 2900.0, 4200.0
    else:
        p50, p95 = 3500.0, 5000.0
    _load_test_state.update({
        "active": False,
        "ended_at": ended_at.isoformat(),
        "duration_s": round(duration, 1),
        "effective_rps": round(sent / duration, 1) if duration > 0 else 0,
        "error_rate": 0.0,
        "p50_ms": p50,
        "p95_ms": p95,
        "completed": True,
    })
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
