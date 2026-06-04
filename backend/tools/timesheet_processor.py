"""
Timesheet Processor — Pure Python, No LLM
Processes check-in/out records and detects anomalies.
"""
from datetime import date, datetime, time, timedelta
from typing import Optional
from backend.governance.compliance_rules import (
    GRACE_PERIOD_MINUTES, WORK_START_TIME, WORK_END_TIME,
    LUNCH_BREAK_MINUTES, VN_HOLIDAYS_2026,
    OVERTIME_RATE_WEEKDAY, OVERTIME_RATE_WEEKEND, OVERTIME_RATE_HOLIDAY,
)
import calendar


def _parse_time(t_str: Optional[str]) -> Optional[time]:
    if not t_str:
        return None
    try:
        return datetime.strptime(t_str, "%H:%M").time()
    except ValueError:
        return None


def _parse_date(d_str: str) -> date:
    return datetime.strptime(d_str, "%Y-%m-%d").date()


def _is_holiday(d: date) -> bool:
    return d in VN_HOLIDAYS_2026


def _is_weekend(d: date) -> bool:
    return d.weekday() >= 5  # Saturday=5, Sunday=6


def _minutes_between(t1: time, t2: time) -> float:
    """Return minutes from t1 to t2 (t2 >= t1)."""
    dt1 = datetime.combine(date.today(), t1)
    dt2 = datetime.combine(date.today(), t2)
    return (dt2 - dt1).total_seconds() / 60


def process_timesheet(
    records: list[dict],
    work_schedule: Optional[dict] = None,
    month: Optional[str] = None,
) -> dict:
    """
    Process timesheet records for a month.

    Args:
        records: List of {date, check_in, check_out} dicts
        work_schedule: {start, end, break_minutes}
        month: "YYYY-MM" string

    Returns:
        Full timesheet summary dict with anomalies.
    """
    schedule = work_schedule or {}
    start_str  = schedule.get("start", WORK_START_TIME)
    end_str    = schedule.get("end", WORK_END_TIME)
    break_min  = int(schedule.get("break_minutes", LUNCH_BREAK_MINUTES))
    grace      = GRACE_PERIOD_MINUTES

    work_start = _parse_time(start_str)
    work_end   = _parse_time(end_str)

    # Determine expected work days in month
    if month:
        year, mon = int(month.split("-")[0]), int(month.split("-")[1])
        _, days_in_month = calendar.monthrange(year, mon)
        all_dates = [date(year, mon, d) for d in range(1, days_in_month + 1)]
    else:
        all_dates = []

    expected_work_dates = {
        d for d in all_dates
        if not _is_weekend(d) and not _is_holiday(d)
    }
    total_work_days = len(expected_work_dates)

    # Index records by date string
    record_map = {r["date"]: r for r in records}

    days_present = 0
    days_absent  = 0
    days_holiday = 0
    days_weekend = 0
    total_minutes_worked = 0.0
    overtime_minutes = 0.0
    late_arrivals = 0
    early_leaves  = 0
    anomalies: list[str] = []
    processed_records: list[dict] = []

    for d in (all_dates if all_dates else [_parse_date(r["date"]) for r in records]):
        d_str = d.strftime("%Y-%m-%d")
        is_hol = _is_holiday(d)
        is_wkd = _is_weekend(d)

        if is_hol:
            days_holiday += 1
        elif is_wkd:
            days_weekend += 1

        record = record_map.get(d_str)

        if not record:
            # Expected work day but no record
            if not is_hol and not is_wkd:
                days_absent += 1
                anomalies.append(f"{d_str}: Không có dữ liệu chấm công")
            processed_records.append({"date": d_str, "status": "holiday" if is_hol else ("weekend" if is_wkd else "absent")})
            continue

        check_in  = _parse_time(record.get("check_in"))
        check_out = _parse_time(record.get("check_out"))

        # Missing both
        if check_in is None and check_out is None:
            if not is_hol and not is_wkd:
                days_absent += 1
                anomalies.append(f"{d_str}: Quên chấm công (không có check-in và check-out)")
            processed_records.append({"date": d_str, "check_in": None, "check_out": None, "status": "absent"})
            continue

        # Missing one
        if check_in is None:
            anomalies.append(f"{d_str}: Thiếu dữ liệu check-in")
        if check_out is None:
            anomalies.append(f"{d_str}: Thiếu dữ liệu check-out")

        # Late arrival check
        is_late = False
        if check_in and work_start:
            late_threshold = (datetime.combine(date.today(), work_start) + timedelta(minutes=grace)).time()
            if check_in > late_threshold:
                is_late = True
                late_min = _minutes_between(work_start, check_in) - grace
                late_arrivals += 1
                anomalies.append(f"{d_str}: Đi muộn {int(late_min)} phút (check-in lúc {check_in.strftime('%H:%M')})")

        # Early leave check
        is_early = False
        if check_out and work_end:
            early_threshold = (datetime.combine(date.today(), work_end) - timedelta(minutes=grace)).time()
            if check_out < early_threshold:
                is_early = True
                early_min = _minutes_between(check_out, work_end) - grace
                early_leaves += 1
                anomalies.append(f"{d_str}: Về sớm {int(early_min)} phút (check-out lúc {check_out.strftime('%H:%M')})")

        # Calculate worked minutes
        if check_in and check_out:
            raw_minutes = _minutes_between(check_in, check_out)
            # Subtract lunch break if worked full day
            worked = max(0, raw_minutes - break_min) if raw_minutes > (break_min + 60) else raw_minutes
        else:
            worked = 0

        # Overtime: minutes beyond standard work hours
        standard_minutes = _minutes_between(work_start, work_end) - break_min if work_start and work_end else 480
        ot_minutes = max(0, worked - standard_minutes)

        total_minutes_worked += worked
        overtime_minutes     += ot_minutes

        # Day type for OT rate
        if is_hol:
            ot_rate_label = "holiday"
        elif is_wkd:
            ot_rate_label = "weekend"
        else:
            ot_rate_label = "weekday"

        status = "holiday" if is_hol else ("weekend" if is_wkd else ("late" if is_late else ("early_leave" if is_early else "present")))

        if not is_hol and not is_wkd:
            days_present += 1

        processed_records.append({
            "date": d_str,
            "check_in": check_in.strftime("%H:%M") if check_in else None,
            "check_out": check_out.strftime("%H:%M") if check_out else None,
            "hours_worked": round(worked / 60, 2),
            "overtime_hours": round(ot_minutes / 60, 2),
            "ot_type": ot_rate_label,
            "is_late": is_late,
            "is_early_leave": is_early,
            "status": status,
        })

    total_hours = round(total_minutes_worked / 60, 2)
    overtime_hours = round(overtime_minutes / 60, 2)

    return {
        "total_working_days": total_work_days,
        "days_present": days_present,
        "days_absent": days_absent,
        "days_holiday": days_holiday,
        "days_weekend": days_weekend,
        "total_hours": total_hours,
        "overtime_hours": overtime_hours,
        "late_arrivals": late_arrivals,
        "early_leaves": early_leaves,
        "anomalies": anomalies,
        "records": processed_records,
        "approved": False,
        "summary": None,  # Will be filled by LLM
    }
