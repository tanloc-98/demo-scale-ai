"""Jobs Queue Router"""
from fastapi import APIRouter, HTTPException
from backend.db.job_store import get_job, list_jobs, clear_done_jobs

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
async def get_jobs(limit: int = 50):
    jobs = list_jobs(limit)
    return {"jobs": jobs, "total": len(jobs)}


@router.get("/{job_id}")
async def get_job_detail(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job


@router.post("/clear-done")
async def clear_done():
    clear_done_jobs()
    return {"message": "Done jobs cleared"}
