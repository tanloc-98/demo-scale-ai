"""
Database module — async SQLAlchemy with PostgreSQL (or SQLite for local dev).
"""
import os
import uuid
import json
from datetime import datetime
from typing import Optional, Any

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import (
    Column, String, Float, Integer, DateTime, Boolean, Text, JSON,
    Index, MetaData, Table
)
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./hrdb.sqlite3"
)

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"
    id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4())[:8])
    employee_id = Column(String, nullable=False)
    job_type    = Column(String, nullable=False)  # salary | timesheet
    status      = Column(String, default="queued")  # queued|processing|completed|failed
    payload     = Column(JSON)
    result      = Column(JSON)
    error       = Column(Text)
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at= Column(DateTime)
    wait_seconds= Column(Float, default=0)
    duration_seconds = Column(Float, default=0)


class SalaryResult(Base):
    __tablename__ = "salary_results"
    id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4())[:8])
    employee_id = Column(String, nullable=False)
    period      = Column(String, nullable=False)
    gross_salary= Column(Float)
    net_salary  = Column(Float)
    data        = Column(JSON)
    created_at  = Column(DateTime, default=datetime.utcnow)


class TimesheetResultDB(Base):
    __tablename__ = "timesheet_results"
    id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4())[:8])
    employee_id = Column(String, nullable=False)
    period      = Column(String, nullable=False)
    days_present= Column(Integer)
    total_hours = Column(Float)
    anomaly_count= Column(Integer)
    data        = Column(JSON)
    created_at  = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    timestamp   = Column(DateTime, default=datetime.utcnow)
    action      = Column(String)
    resource    = Column(String)
    employee_id = Column(String)
    ip_address  = Column(String)
    result      = Column(String)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
