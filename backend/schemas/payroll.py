"""Pydantic schemas for employee, payroll, timesheet."""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date


class AllowancesInput(BaseModel):
    lunch: Optional[float] = 800_000
    transport: Optional[float] = 500_000


class DeductionFlags(BaseModel):
    social_insurance: bool = True
    health_insurance: bool = True
    union_fee: bool = True


class SalaryInput(BaseModel):
    employee_id: str = Field(..., example="EMP001")
    month: str = Field(..., example="2026-05")
    base_salary: float = Field(..., gt=0, example=15_000_000)
    total_work_days: int = Field(22, ge=1, le=31)
    days_worked: Optional[int] = None
    days_absent: int = Field(0, ge=0)
    overtime_hours: float = Field(0.0, ge=0)
    overtime_hours_weekend: float = Field(0.0, ge=0)
    overtime_hours_holiday: float = Field(0.0, ge=0)
    allowances: Optional[AllowancesInput] = None
    deductions: Optional[DeductionFlags] = None
    dependents: int = Field(0, ge=0)

    def to_calc_input(self) -> dict:
        d = self.model_dump()
        if d.get("allowances"):
            d["allowances"] = {k: v for k, v in d["allowances"].items() if v}
        if d.get("deductions"):
            d["deductions"] = d["deductions"]
        # days_worked default
        if d.get("days_worked") is None:
            d["days_worked"] = d["total_work_days"] - d["days_absent"]
        return d


class DeductionsResult(BaseModel):
    social_insurance: float
    health_insurance: float
    union_fee: float
    personal_income_tax: float
    total: float


class SalaryResult(BaseModel):
    employee_id: str
    period: str
    base_salary: float
    days_worked: int
    total_work_days: int
    overtime_hours_weekday: float
    overtime_hours_weekend: float
    overtime_hours_holiday: float
    allowances: dict
    gross_salary: float
    deductions: DeductionsResult
    net_salary: float
    summary: Optional[str] = None


class JobResponse(BaseModel):
    job_id: str
    status: str  # queued | processing | completed | failed
    position: Optional[int] = None
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


class TimesheetRecord(BaseModel):
    date: str = Field(..., example="2026-05-01")
    check_in: Optional[str] = Field(None, example="08:02")
    check_out: Optional[str] = Field(None, example="17:35")


class WorkSchedule(BaseModel):
    start: str = Field("08:00", example="08:00")
    end: str = Field("17:30", example="17:30")
    break_minutes: int = Field(60, ge=0)


class TimesheetInput(BaseModel):
    employee_id: str = Field(..., example="EMP001")
    month: str = Field(..., example="2026-05")
    records: list[TimesheetRecord]
    work_schedule: Optional[WorkSchedule] = None


class TimesheetResult(BaseModel):
    employee_id: str
    period: str
    total_working_days: int
    days_present: int
    days_absent: int
    total_hours: float
    overtime_hours: float
    late_arrivals: int
    early_leaves: int
    anomalies: list[str]
    records: list[dict]
    approved: bool
    summary: Optional[str] = None
