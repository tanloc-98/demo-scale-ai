"""Timesheet API Router"""
import os
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from backend.schemas.payroll import TimesheetInput, JobResponse
from backend.agents.timesheet_agent import TimesheetAgent
from backend.db.job_store import create_timesheet_job, get_job, process_job_async, get_queue_depth

QUEUE_MAX = int(os.getenv("QUEUE_MAX", "500"))
_RETRY_AFTER_SECONDS = 30

router = APIRouter(prefix="/timesheet", tags=["timesheet"])
_agent = TimesheetAgent()


async def _run_timesheet(job_id: str, data: dict):
    return await _agent.run(job_id, data)


@router.post("/process", response_model=JobResponse, status_code=202)
async def process_timesheet_api(data: TimesheetInput, background_tasks: BackgroundTasks):
    """Submit timesheet processing job. Returns 429 + Retry-After when queue full."""
    depth = get_queue_depth()
    if depth >= QUEUE_MAX:
        return JSONResponse(
            status_code=429,
            content={"error": "Queue full", "queue_depth": depth,
                     "retry_after": _RETRY_AFTER_SECONDS},
            headers={"Retry-After": str(_RETRY_AFTER_SECONDS)},
        )
    payload = data.model_dump()
    job = create_timesheet_job(data.employee_id, payload)
    background_tasks.add_task(
        process_job_async, job["job_id"], _run_timesheet, job["job_id"], payload
    )
    return JobResponse(
        job_id=job["job_id"],
        status="queued",
        position=job.get("position", 1),
        created_at=job["created_at"],
    )


@router.get("/{job_id}", response_model=JobResponse)
async def get_timesheet_result(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return JobResponse(**{k: v for k, v in job.items() if k in JobResponse.model_fields})
