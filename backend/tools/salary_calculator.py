"""
Salary Calculator — Pure Python, No LLM
Implements Vietnamese labor law salary calculation.
"""
from datetime import date, datetime
from typing import Optional
from backend.governance.compliance_rules import (
    SOCIAL_INSURANCE_RATE, HEALTH_INSURANCE_RATE, UNION_FEE_RATE,
    OVERTIME_RATE_WEEKDAY, OVERTIME_RATE_WEEKEND, OVERTIME_RATE_HOLIDAY,
    PERSONAL_DEDUCTION, DEPENDENT_DEDUCTION, TAX_BRACKETS,
    STANDARD_WORK_DAYS_PER_MONTH
)


def calculate_gross_salary(
    base_salary: float,
    days_worked: int,
    total_work_days: int = STANDARD_WORK_DAYS_PER_MONTH,
    overtime_hours_weekday: float = 0.0,
    overtime_hours_weekend: float = 0.0,
    overtime_hours_holiday: float = 0.0,
    allowances: Optional[dict] = None,
) -> float:
    """
    Calculate gross salary based on actual days worked and overtime.
    
    Args:
        base_salary: Monthly base salary (VND)
        days_worked: Actual days worked this month
        total_work_days: Total working days in month (default 22)
        overtime_hours_weekday: OT hours on normal weekdays (×1.5)
        overtime_hours_weekend: OT hours on weekends (×2.0)
        overtime_hours_holiday: OT hours on holidays (×3.0)
        allowances: Dict of allowances {'lunch': 800000, 'transport': 500000}
    
    Returns:
        Gross salary (VND)
    """
    if total_work_days <= 0:
        raise ValueError("total_work_days must be > 0")
    if days_worked < 0 or days_worked > total_work_days:
        raise ValueError(f"days_worked must be between 0 and {total_work_days}")

    # Daily rate
    daily_rate = base_salary / total_work_days
    
    # Base salary proportional to days worked
    proportional_salary = daily_rate * days_worked
    
    # Hourly rate (8 hours/day)
    hourly_rate = daily_rate / 8
    
    # Overtime pay
    ot_weekday  = overtime_hours_weekday  * hourly_rate * OVERTIME_RATE_WEEKDAY
    ot_weekend  = overtime_hours_weekend  * hourly_rate * OVERTIME_RATE_WEEKEND
    ot_holiday  = overtime_hours_holiday  * hourly_rate * OVERTIME_RATE_HOLIDAY
    
    # Allowances (not subject to insurance)
    total_allowances = sum((allowances or {}).values())
    
    gross = proportional_salary + ot_weekday + ot_weekend + ot_holiday + total_allowances
    return round(gross, 0)


def calculate_insurance(gross_salary_before_allowances: float) -> dict:
    """
    Calculate employee insurance deductions.
    Insurance is calculated on base salary (before allowances).
    
    Returns dict: {social_insurance, health_insurance, union_fee, total}
    """
    bhxh = round(gross_salary_before_allowances * SOCIAL_INSURANCE_RATE, 0)
    bhyt = round(gross_salary_before_allowances * HEALTH_INSURANCE_RATE, 0)
    cd   = round(gross_salary_before_allowances * UNION_FEE_RATE, 0)
    return {
        "social_insurance": bhxh,
        "health_insurance": bhyt,
        "union_fee": cd,
        "total": bhxh + bhyt + cd,
    }


def calculate_personal_income_tax(
    taxable_income: float,
    dependents: int = 0
) -> float:
    """
    Calculate personal income tax using progressive brackets (Vietnam).
    
    Args:
        taxable_income: Income after insurance deductions
        dependents: Number of dependents (each reduces taxable income by 4.4M/month)
    
    Returns:
        Tax amount (VND)
    """
    # Apply personal deductions
    deductible = PERSONAL_DEDUCTION + (dependents * DEPENDENT_DEDUCTION)
    assessable_income = max(0, taxable_income - deductible)
    
    if assessable_income <= 0:
        return 0.0
    
    # Progressive tax calculation
    tax = 0.0
    prev_bracket = 0.0
    for bracket_limit, rate in TAX_BRACKETS:
        if assessable_income <= prev_bracket:
            break
        taxable_in_bracket = min(assessable_income, bracket_limit) - prev_bracket
        tax += taxable_in_bracket * rate
        prev_bracket = bracket_limit
    
    return round(max(0, tax), 0)


def calculate_net_salary(input_data: dict) -> dict:
    """
    Full salary calculation pipeline.
    
    Input:
        employee_id, month, base_salary, days_worked, total_work_days,
        overtime_hours (total on weekdays by default, or breakdown),
        days_absent, allowances {lunch, transport},
        deductions {social_insurance, health_insurance, union_fee},
        dependents
    
    Returns full payroll result dict.
    """
    base_salary         = float(input_data.get("base_salary", 0))
    days_worked         = int(input_data.get("days_worked", input_data.get("total_work_days", STANDARD_WORK_DAYS_PER_MONTH) - input_data.get("days_absent", 0)))
    total_work_days     = int(input_data.get("total_work_days", STANDARD_WORK_DAYS_PER_MONTH))
    ot_weekday          = float(input_data.get("overtime_hours", 0) or input_data.get("overtime_hours_weekday", 0))
    ot_weekend          = float(input_data.get("overtime_hours_weekend", 0))
    ot_holiday          = float(input_data.get("overtime_hours_holiday", 0))
    allowances          = input_data.get("allowances", {}) or {}
    dependents          = int(input_data.get("dependents", 0))
    deduction_flags     = input_data.get("deductions", {}) or {}
    apply_bhxh          = deduction_flags.get("social_insurance", True)
    apply_bhyt          = deduction_flags.get("health_insurance", True)
    apply_cd            = deduction_flags.get("union_fee", True)

    # Ensure allowances are numeric
    clean_allowances = {k: float(v) for k, v in allowances.items() if v}

    # Step 1: Gross salary
    gross = calculate_gross_salary(
        base_salary=base_salary,
        days_worked=days_worked,
        total_work_days=total_work_days,
        overtime_hours_weekday=ot_weekday,
        overtime_hours_weekend=ot_weekend,
        overtime_hours_holiday=ot_holiday,
        allowances=clean_allowances,
    )

    # Step 2: Insurance (on salary part only, not allowances)
    salary_for_insurance = (base_salary / total_work_days * days_worked) + \
                           (base_salary / total_work_days / 8 * ot_weekday * OVERTIME_RATE_WEEKDAY) + \
                           (base_salary / total_work_days / 8 * ot_weekend * OVERTIME_RATE_WEEKEND) + \
                           (base_salary / total_work_days / 8 * ot_holiday * OVERTIME_RATE_HOLIDAY)
    
    raw_insurance = calculate_insurance(salary_for_insurance)
    deductions_insurance = {
        "social_insurance": raw_insurance["social_insurance"] if apply_bhxh else 0,
        "health_insurance": raw_insurance["health_insurance"] if apply_bhyt else 0,
        "union_fee": raw_insurance["union_fee"] if apply_cd else 0,
    }
    total_insurance = sum(deductions_insurance.values())

    # Step 3: PIT
    taxable_income = gross - sum(clean_allowances.values()) - total_insurance
    pit = calculate_personal_income_tax(taxable_income, dependents)

    # Step 4: Net salary
    total_deductions = total_insurance + pit
    net_salary = gross - total_deductions

    return {
        "employee_id": input_data.get("employee_id", ""),
        "period": input_data.get("month", ""),
        "base_salary": base_salary,
        "days_worked": days_worked,
        "total_work_days": total_work_days,
        "overtime_hours_weekday": ot_weekday,
        "overtime_hours_weekend": ot_weekend,
        "overtime_hours_holiday": ot_holiday,
        "allowances": clean_allowances,
        "gross_salary": gross,
        "deductions": {
            **deductions_insurance,
            "personal_income_tax": pit,
            "total": total_deductions,
        },
        "net_salary": net_salary,
        "summary": None,  # Will be filled by LLM
    }
