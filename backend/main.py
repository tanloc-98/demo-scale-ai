"""
HR AI Agents — FastAPI Application Entry Point
Scale AI Demo — Mac M2 Studio + MLX-LM
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.governance.audit_logger import AuditMiddleware
from backend.routers.salary import router as salary_router
from backend.routers.timesheet import router as timesheet_router
from backend.routers.jobs import router as jobs_router
from backend.routers.metrics import router as stream_router, obs_router
from backend.routers.demo import router as demo_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown events."""
    # Create DB tables (audit_log, jobs, salary_results, timesheet_results)
    from backend.db.database import init_db
    await init_db()
    # Seed demo data
    from backend.db.job_store import seed_demo_jobs
    seed_demo_jobs()
    yield


app = FastAPI(
    title="HR AI Agents",
    description="Scale AI Demo — Salary & Timesheet Agents on Mac M2 Studio",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Audit every business API request to audit_log table
app.add_middleware(AuditMiddleware)

# Mount routers
API_PREFIX = "/api/v1"
app.include_router(salary_router,    prefix=API_PREFIX)
app.include_router(timesheet_router, prefix=API_PREFIX)
app.include_router(jobs_router,      prefix=API_PREFIX)
app.include_router(stream_router,    prefix=API_PREFIX)
app.include_router(obs_router,       prefix=API_PREFIX)
app.include_router(demo_router,      prefix=API_PREFIX)


@app.get("/")
async def root():
    return {
        "service": "HR AI Agents",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
