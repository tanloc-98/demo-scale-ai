"""
Data Retention Policy — HR AI Agents
Theo luật kế toán VN (Luật 88/2015/QH13) và NĐ 13/2023/NĐ-CP.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

# ---------------------------------------------------------------------------
# Retention constants
# ---------------------------------------------------------------------------

# Redis TTL (seconds)
REDIS_TTL_CACHE_RESULT   = 3600       # 1 giờ — kết quả tính lương cached
REDIS_TTL_JOB_RESULT     = 86400      # 24 giờ — job result
REDIS_TTL_QUEUE_JOB      = 1800       # 30 phút — job trong queue nếu chưa xử lý
REDIS_QUEUE_MAX_MEMORY   = "2gb"      # maxmemory Redis
REDIS_EVICTION_POLICY    = "allkeys-lru"

# Database retention (days)
DB_RETAIN_AUDIT_LOG_DAYS    = 365 * 5     # 5 năm (luật kế toán)
DB_RETAIN_SALARY_RESULT_DAYS = 365 * 10  # 10 năm (hồ sơ lương)
DB_RETAIN_JOB_DAYS          = 30         # 30 ngày — job history
DB_RETAIN_TIMESHEET_DAYS    = 365 * 5    # 5 năm

# LLM log retention (Loki)
LOKI_RETAIN_LLM_REQUESTS    = 90         # 90 ngày
LOKI_RETAIN_AUDIT_LOGS      = 365 * 5    # 5 năm
# Raw PII: không bao giờ được log (retention = 0)
LOKI_RETAIN_PII_RAW         = 0


# ---------------------------------------------------------------------------
# Cleanup functions (gọi từ K8s CronJob hoặc CLI)
# ---------------------------------------------------------------------------

async def cleanup_expired_jobs(session) -> int:
    """
    Xóa jobs đã hoàn thành/thất bại cũ hơn DB_RETAIN_JOB_DAYS ngày.
    Returns: số records đã xóa.
    """
    from sqlalchemy import delete, and_
    from backend.db.database import Job

    cutoff = datetime.now(timezone.utc) - timedelta(days=DB_RETAIN_JOB_DAYS)
    result = await session.execute(
        delete(Job).where(
            and_(
                Job.status.in_(["completed", "failed"]),
                Job.created_at < cutoff,
            )
        )
    )
    await session.commit()
    return result.rowcount


async def cleanup_old_audit_logs(session) -> int:
    """
    Xóa audit_log records cũ hơn DB_RETAIN_AUDIT_LOG_DAYS (5 năm).
    Returns: số records đã xóa.
    """
    from sqlalchemy import delete
    from backend.db.database import AuditLog

    cutoff = datetime.now(timezone.utc) - timedelta(days=DB_RETAIN_AUDIT_LOG_DAYS)
    result = await session.execute(
        delete(AuditLog).where(AuditLog.timestamp < cutoff)
    )
    await session.commit()
    return result.rowcount


async def cleanup_old_salary_results(session) -> int:
    """
    Xóa salary_results cũ hơn DB_RETAIN_SALARY_RESULT_DAYS (10 năm).
    Returns: số records đã xóa.
    """
    from sqlalchemy import delete
    from backend.db.database import SalaryResult

    cutoff = datetime.now(timezone.utc) - timedelta(days=DB_RETAIN_SALARY_RESULT_DAYS)
    result = await session.execute(
        delete(SalaryResult).where(SalaryResult.created_at < cutoff)
    )
    await session.commit()
    return result.rowcount


async def run_all_cleanup(session) -> dict:
    """
    Chạy toàn bộ cleanup — dùng trong K8s CronJob hàng ngày.
    Returns summary dict.
    """
    jobs_deleted     = await cleanup_expired_jobs(session)
    audit_deleted    = await cleanup_old_audit_logs(session)
    salary_deleted   = await cleanup_old_salary_results(session)
    return {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "jobs_deleted": jobs_deleted,
        "audit_logs_deleted": audit_deleted,
        "salary_results_deleted": salary_deleted,
    }


async def get_retention_stats(session) -> dict:
    """
    Trả về thống kê số records theo bảng — dùng cho monitoring.
    """
    from sqlalchemy import select, func
    from backend.db.database import Job, AuditLog, SalaryResult

    job_count   = (await session.execute(select(func.count()).select_from(Job))).scalar()
    audit_count = (await session.execute(select(func.count()).select_from(AuditLog))).scalar()
    salary_count= (await session.execute(select(func.count()).select_from(SalaryResult))).scalar()

    return {
        "jobs":           job_count,
        "audit_logs":     audit_count,
        "salary_results": salary_count,
        "retention_policy": {
            "jobs_days":          DB_RETAIN_JOB_DAYS,
            "audit_logs_days":    DB_RETAIN_AUDIT_LOG_DAYS,
            "salary_results_days": DB_RETAIN_SALARY_RESULT_DAYS,
        },
    }
