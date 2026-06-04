"""
Seed 200 demo employees — chạy 1 lần trước khi demo.
Tạo jobs salary + timesheet đã completed để /jobs và /observability có data.
Usage: python3 backend/seed_demo_data.py
"""
import asyncio
import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.db.job_store import (
    _jobs, _metrics,
    create_salary_job, create_timesheet_job,
    update_job,
)
from backend.tools.salary_calculator import calculate_net_salary
from backend.tools.timesheet_processor import process_timesheet

random.seed(42)

DEPARTMENTS = ["Engineering", "HR", "Finance", "Operations", "Sales", "Marketing"]
SALARY_BANDS = {
    "Engineering": (20_000_000, 50_000_000),
    "Finance":     (18_000_000, 40_000_000),
    "HR":          (15_000_000, 30_000_000),
    "Operations":  (12_000_000, 25_000_000),
    "Sales":       (15_000_000, 35_000_000),
    "Marketing":   (15_000_000, 30_000_000),
}

SCHEDULE = {"start": "08:00", "end": "17:30", "break_minutes": 60}

WORK_DAYS_JUNE = [
    f"2026-06-{d:02d}" for d in range(1, 31)
    if __import__("datetime").date(2026, 6, d).weekday() < 5
]  # 22 working days


def make_salary_input(emp_id: str, dept: str) -> dict:
    lo, hi = SALARY_BANDS[dept]
    base = random.randrange(lo, hi, 500_000)
    ot = random.choice([0, 0, 4, 8, 12])
    absent = random.choice([0, 0, 0, 1])
    return {
        "employee_id": emp_id, "month": "2026-05",
        "base_salary": base, "total_work_days": 22,
        "days_worked": 22 - absent, "days_absent": absent,
        "overtime_hours": ot, "overtime_hours_weekend": random.choice([0, 4]),
        "overtime_hours_holiday": 0,
        "allowances": {"lunch": 800_000, "transport": 500_000},
        "deductions": {"social_insurance": True, "health_insurance": True, "union_fee": True},
        "dependents": random.choice([0, 0, 1]),
    }


def make_timesheet_records(n_days: int = 22) -> list:
    records = []
    for d_str in WORK_DAYS_JUNE[:n_days]:
        if random.random() < 0.04:
            records.append({"date": d_str, "check_in": None, "check_out": None})
            continue
        late = random.randint(6, 20) if random.random() < 0.08 else random.randint(-4, 4)
        ci_min = 8 * 60 + late
        co_min = 17 * 60 + 30 + (random.randint(60, 120) if random.random() < 0.10 else 0)
        records.append({
            "date": d_str,
            "check_in":  f"{ci_min//60:02d}:{ci_min%60:02d}",
            "check_out": f"{co_min//60:02d}:{co_min%60:02d}",
        })
    return records


def seed_jobs(n: int = 30):
    """Seed n completed salary + n completed timesheet jobs."""
    print(f"Seeding {n} salary + {n} timesheet jobs...")
    for i in range(1, n + 1):
        emp_id = f"EMP{random.randint(1, 200):03d}"
        dept   = random.choice(DEPARTMENTS)

        # Salary job
        sal_input = make_salary_input(emp_id, dept)
        sal_job   = create_salary_job(emp_id, sal_input)
        sal_result = calculate_net_salary(sal_input)
        sal_result["summary"] = (
            f"Nhân viên {emp_id} tháng 2026-05: "
            f"lương gross {sal_result['gross_salary']:,.0f} VNĐ, "
            f"thực nhận {sal_result['net_salary']:,.0f} VNĐ."
        )
        update_job(sal_job["job_id"], status="completed", result=sal_result,
                   duration_seconds=round(random.uniform(0.4, 1.2), 3))

        # Timesheet job
        records   = make_timesheet_records()
        ts_input  = {"employee_id": emp_id, "month": "2026-06",
                     "records": records, "work_schedule": SCHEDULE}
        ts_job    = create_timesheet_job(emp_id, ts_input)
        ts_result = process_timesheet(records, SCHEDULE, "2026-06")
        ts_result["employee_id"] = emp_id
        ts_result["period"]      = "2026-06"
        ts_result["summary"]     = (
            f"Nhân viên {emp_id} tháng 6/2026: "
            f"đi làm {ts_result['days_present']}/22 ngày, "
            f"tổng {ts_result['total_hours']:.1f}h."
        )
        update_job(ts_job["job_id"], status="completed", result=ts_result,
                   duration_seconds=round(random.uniform(0.3, 0.9), 3))

    _metrics["completed_today"] = n * 2
    print(f"✅ Seeded {n*2} completed jobs into in-memory store.")


if __name__ == "__main__":
    seed_jobs(30)
    print("Demo data ready. Start the server and open http://localhost:3000")
