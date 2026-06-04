import os
import asyncio
from celery import Celery
from backend.tools.salary_calculator import calculate_net_salary as calculate_salary
from backend.tools.timesheet_processor import process_timesheet
from backend.llm.client import llm_client
from backend.db.job_store import update_job, _metrics
from datetime import datetime

# Initialize Celery
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
app = Celery("llm_worker", broker=redis_url, backend=redis_url)

@app.task(name="salary")
def process_salary_job(job_id: str, data: dict):
    # Run async code in sync wrapper
    return asyncio.run(_run_salary_async(job_id, data))

async def _run_salary_async(job_id: str, data: dict):
    import time
    start = time.time()
    update_job(job_id, status="processing")
    try:
        # 1. Pure Python calculation
        result = calculate_salary(data)
        
        # 2. LLM formatting
        summary = await llm_client.format_salary_summary(result)
        result["summary"] = summary
        
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
        return result
    except Exception as e:
        update_job(job_id, status="failed", error=str(e))
        raise e

@app.task(name="timesheet")
def process_timesheet_job(job_id: str, data: dict):
    return asyncio.run(_run_timesheet_async(job_id, data))

async def _run_timesheet_async(job_id: str, data: dict):
    import time
    start = time.time()
    update_job(job_id, status="processing")
    try:
        records = data["records"]
        schedule = data.get("work_schedule")
        month = data["month"]
        result = process_timesheet(records, schedule, month)
        result["employee_id"] = data["employee_id"]
        result["period"] = month
        
        summary = await llm_client.format_timesheet_summary(result, data["employee_id"], month)
        result["summary"] = summary
        
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
        return result
    except Exception as e:
        update_job(job_id, status="failed", error=str(e))
        raise e
