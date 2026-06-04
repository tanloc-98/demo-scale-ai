"""Salary API Router"""
import os
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from backend.schemas.payroll import SalaryInput, JobResponse
from backend.agents.salary_agent import SalaryAgent
from backend.db.job_store import create_salary_job, get_job, update_job, process_job_async, get_queue_depth

QUEUE_MAX = int(os.getenv("QUEUE_MAX", "500"))
_RETRY_AFTER_SECONDS = 30

router = APIRouter(prefix="/salary", tags=["salary"])
_agent = SalaryAgent()


async def _run_salary(job_id: str, input_data: dict):
    return await _agent.run(job_id, input_data)


@router.post("/calculate", response_model=JobResponse, status_code=202)
async def calculate_salary(data: SalaryInput, background_tasks: BackgroundTasks):
    """Submit salary calculation job. Returns 202 + job_id immediately.
    Returns 429 with Retry-After header when queue exceeds QUEUE_MAX."""
    depth = get_queue_depth()
    if depth >= QUEUE_MAX:
        return JSONResponse(
            status_code=429,
            content={"error": "Queue full", "queue_depth": depth,
                     "retry_after": _RETRY_AFTER_SECONDS},
            headers={"Retry-After": str(_RETRY_AFTER_SECONDS)},
        )
    job = create_salary_job(data.employee_id, data.to_calc_input())
    background_tasks.add_task(
        process_job_async, job["job_id"], _run_salary, job["job_id"], data.to_calc_input()
    )
    return JobResponse(
        job_id=job["job_id"],
        status="queued",
        position=job.get("position", 1),
        created_at=job["created_at"],
    )


@router.get("/{job_id}", response_model=JobResponse)
async def get_salary_result(job_id: str):
    """Poll salary job result."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return JobResponse(**{k: v for k, v in job.items() if k in JobResponse.model_fields})
