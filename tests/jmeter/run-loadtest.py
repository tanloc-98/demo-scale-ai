#!/usr/bin/env python3
"""
HR AI Agents Load Test — Python async version.
Thay thế JMeter khi jp@gc plugin chưa cài.
Usage:
    python run-loadtest.py --rps 10 --duration 30 --host localhost --port 8000
"""
import asyncio, argparse, json, time, random, csv, os
from pathlib import Path

try:
    import httpx
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx", "-q"])
    import httpx

BASE_DIR = Path(__file__).parent


def load_employees(n=20) -> list[dict]:
    csv_path = BASE_DIR / "test-data" / "employees_200.csv"
    rows = []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return (rows * 10)[:n]


async def send_salary(client: httpx.AsyncClient, host: str, port: int, emp: dict) -> dict:
    url = f"http://{host}:{port}/api/v1/salary/calculate"
    payload = {
        "employee_id": emp["employee_id"],
        "month": "2026-05",
        "base_salary": float(emp["base_salary"]),
        "total_work_days": 22,
        "days_absent": int(emp.get("days_absent", 0)),
        "overtime_hours": float(emp.get("overtime_hours", 0)),
        "overtime_hours_weekend": float(emp.get("overtime_hours_weekend", 0)),
        "overtime_hours_holiday": 0,
        "allowances": {"lunch": 800000, "transport": 500000},
        "deductions": {"social_insurance": True, "health_insurance": True, "union_fee": True},
        "dependents": int(emp.get("dependents", 0)),
    }
    t0 = time.monotonic()
    try:
        r = await client.post(url, json=payload, timeout=10.0)
        latency = (time.monotonic() - t0) * 1000
        # 202=queued, 200=sync OK, 429=queue full (expected when QUEUE_MAX hit)
        return {"ok": r.status_code in (200, 202, 429), "status": r.status_code, "latency_ms": latency}
    except Exception as e:
        return {"ok": False, "status": 0, "latency_ms": (time.monotonic() - t0) * 1000, "error": str(e)}


async def send_timesheet(client: httpx.AsyncClient, host: str, port: int, emp_id: str) -> dict:
    url = f"http://{host}:{port}/api/v1/timesheet/process"
    payload = {
        "employee_id": emp_id,
        "month": "2026-05",
        "records": [
            {"date": "2026-05-01", "check_in": "08:02", "check_out": "17:35"},
            {"date": "2026-05-02", "check_in": "07:55", "check_out": "20:10"},
            {"date": "2026-05-05", "check_in": None,    "check_out": None},
        ],
        "work_schedule": {"start": "08:00", "end": "17:30", "break_minutes": 60},
    }
    t0 = time.monotonic()
    try:
        r = await client.post(url, json=payload, timeout=10.0)
        latency = (time.monotonic() - t0) * 1000
        return {"ok": r.status_code in (200, 202, 429), "status": r.status_code, "latency_ms": latency}
    except Exception as e:
        return {"ok": False, "status": 0, "latency_ms": (time.monotonic() - t0) * 1000, "error": str(e)}


async def run_test(host: str, port: int, target_rps: int, duration: int):
    employees = load_employees(50)
    results = []
    interval = 1.0 / target_rps
    deadline = time.monotonic() + duration

    async with httpx.AsyncClient() as client:
        tasks = []
        while time.monotonic() < deadline:
            t_send = time.monotonic()
            emp = random.choice(employees)
            if random.random() < 0.6:
                task = asyncio.create_task(send_salary(client, host, port, emp))
            else:
                task = asyncio.create_task(send_timesheet(client, host, port, emp["employee_id"]))
            tasks.append(task)

            # pace
            elapsed = time.monotonic() - t_send
            sleep_time = max(0, interval - elapsed)
            await asyncio.sleep(sleep_time)

        results = await asyncio.gather(*tasks)

    return results


def print_report(results: list[dict], target_rps: int, duration: int):
    total = len(results)
    ok = sum(1 for r in results if r["ok"])
    errors = total - ok
    latencies = sorted(r["latency_ms"] for r in results if r["latency_ms"] > 0)

    def pct(p):
        if not latencies: return 0
        idx = int(len(latencies) * p / 100)
        return latencies[min(idx, len(latencies)-1)]

    actual_rps = total / duration if duration else 0
    error_rate = (errors / total * 100) if total else 0

    print("\n" + "="*60)
    print(f"  HR AI Agents Load Test Results — {target_rps} req/s target")
    print("="*60)
    print(f"  Total requests   : {total}")
    print(f"  Successful       : {ok}  ({100-error_rate:.1f}%)")
    print(f"  Errors           : {errors}  ({error_rate:.1f}%)")
    print(f"  Actual throughput: {actual_rps:.1f} req/s")
    print(f"  P50 latency      : {pct(50):.0f} ms")
    print(f"  P95 latency      : {pct(95):.0f} ms")
    print(f"  P99 latency      : {pct(99):.0f} ms")
    print(f"  Min latency      : {latencies[0]:.0f} ms" if latencies else "")
    print(f"  Max latency      : {latencies[-1]:.0f} ms" if latencies else "")

    status_counts = {}
    for r in results:
        s = r.get("status", 0)
        status_counts[s] = status_counts.get(s, 0) + 1
    print(f"\n  Status codes     : {dict(sorted(status_counts.items()))}")

    # Save JSON report
    report_dir = Path(__file__).parent / "reports" / f"{target_rps}rps"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "result.json"
    with open(report_path, "w") as f:
        json.dump({
            "target_rps": target_rps, "duration": duration,
            "total": total, "ok": ok, "errors": errors,
            "actual_rps": actual_rps, "error_rate_pct": error_rate,
            "p50_ms": pct(50), "p95_ms": pct(95), "p99_ms": pct(99),
            "status_codes": status_counts,
        }, f, indent=2)
    print(f"\n  Report saved to: {report_path}")
    print("="*60)
    return error_rate


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rps",      type=int, default=10)
    parser.add_argument("--duration", type=int, default=30)
    parser.add_argument("--host",     default="localhost")
    parser.add_argument("--port",     type=int, default=8000)
    args = parser.parse_args()

    print(f"Starting load test: {args.rps} req/s for {args.duration}s → {args.host}:{args.port}")
    results = asyncio.run(run_test(args.host, args.port, args.rps, args.duration))
    error_rate = print_report(results, args.rps, args.duration)
    exit(0 if error_rate < 5.0 else 1)
