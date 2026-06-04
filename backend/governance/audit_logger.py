"""
Audit Logger — FastAPI middleware ghi mọi request/response vào audit_log.
Compliant với NĐ 13/2023/NĐ-CP: mọi truy cập dữ liệu nhân sự phải được ghi log.
"""
import json
import re
import time
from datetime import datetime
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from backend.db.database import AsyncSessionLocal, AuditLog

# Paths cần audit — chỉ log các API nghiệp vụ, bỏ qua health/docs/stream
_AUDIT_PATHS = re.compile(
    r"^/api/v1/(salary|timesheet|jobs|demo/scale|demo/redteam)"
)

# Map path pattern → action name
_ACTION_MAP = [
    (re.compile(r"/salary/calculate"),        "salary.calculate"),
    (re.compile(r"/salary/"),                 "salary.get"),
    (re.compile(r"/timesheet/process"),       "timesheet.process"),
    (re.compile(r"/timesheet/"),              "timesheet.get"),
    (re.compile(r"/jobs$"),                   "jobs.list"),
    (re.compile(r"/jobs/"),                   "jobs.get"),
    (re.compile(r"/demo/scale"),              "demo.scale"),
    (re.compile(r"/demo/redteam/run"),        "demo.redteam_run"),
]


def _map_action(path: str, method: str) -> str:
    for pattern, action in _ACTION_MAP:
        if pattern.search(path):
            return action
    return f"{method.lower()}.{path.split('/')[-1]}"


async def _extract_employee_id(request: Request) -> Optional[str]:
    """Try to extract employee_id from request body without consuming the stream."""
    try:
        body = await request.body()
        if body:
            data = json.loads(body)
            return data.get("employee_id")
    except Exception:
        pass
    return None


async def _write_audit(
    action: str,
    resource: str,
    employee_id: Optional[str],
    ip_address: str,
    result: str,
) -> None:
    """Fire-and-forget: write one audit record to DB."""
    try:
        async with AsyncSessionLocal() as session:
            entry = AuditLog(
                timestamp=datetime.utcnow(),
                action=action,
                resource=resource,
                employee_id=employee_id,
                ip_address=ip_address,
                result=result,
            )
            session.add(entry)
            await session.commit()
    except Exception:
        pass  # never let audit failure break the main request


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware: intercept API requests, log action + outcome to audit_log.
    Only logs paths matching _AUDIT_PATHS.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not _AUDIT_PATHS.match(path):
            return await call_next(request)

        action      = _map_action(path, request.method)
        ip_address  = request.client.host if request.client else "unknown"
        employee_id = await _extract_employee_id(request)

        start = time.monotonic()
        response: Response = await call_next(request)
        duration_ms = int((time.monotonic() - start) * 1000)

        result = "success" if response.status_code < 400 else (
            "denied" if response.status_code == 403 else "error"
        )

        # Background write — do not await to avoid blocking response
        import asyncio
        asyncio.ensure_future(
            _write_audit(action, path, employee_id, ip_address, result)
        )

        return response
