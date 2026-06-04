"""
Unit tests for backend/tools/salary_calculator.py — HR-004
Vietnamese labor law: BHXH 8%, BHYT 1.5%, CĐ 1%, 7-bậc thuế TNCN.
"""
import pytest
from backend.tools.salary_calculator import (
    calculate_gross_salary,
    calculate_insurance,
    calculate_personal_income_tax,
    calculate_net_salary,
)
from backend.governance.compliance_rules import (
    SOCIAL_INSURANCE_RATE, HEALTH_INSURANCE_RATE, UNION_FEE_RATE,
    STANDARD_WORK_DAYS_PER_MONTH,
)

BASE = 15_000_000   # 15 triệu VNĐ
STD  = 22           # standard work days

# ---------------------------------------------------------------------------
# calculate_gross_salary
# ---------------------------------------------------------------------------

class TestCalculateGrossSalary:
    def test_full_month_no_ot(self):
        gross = calculate_gross_salary(BASE, days_worked=STD, total_work_days=STD)
        assert gross == BASE

    def test_one_day_absent(self):
        gross = calculate_gross_salary(BASE, days_worked=21, total_work_days=STD)
        expected = round(BASE / STD * 21, 0)
        assert gross == expected

    def test_zero_days_worked(self):
        gross = calculate_gross_salary(BASE, days_worked=0, total_work_days=STD)
        assert gross == 0.0

    def test_allowances_added(self):
        gross = calculate_gross_salary(BASE, days_worked=STD, total_work_days=STD,
                                       allowances={"lunch": 800_000, "transport": 500_000})
        assert gross == BASE + 1_300_000

    def test_weekday_ot_rate_1_5x(self):
        daily = BASE / STD
        hourly = daily / 8
        gross = calculate_gross_salary(BASE, days_worked=STD, total_work_days=STD,
                                       overtime_hours_weekday=8)
        ot_pay = round(8 * hourly * 1.5, 0)
        assert gross == BASE + ot_pay

    def test_weekend_ot_rate_2x(self):
        daily = BASE / STD
        hourly = daily / 8
        gross = calculate_gross_salary(BASE, days_worked=STD, total_work_days=STD,
                                       overtime_hours_weekend=4)
        ot_pay = round(4 * hourly * 2.0, 0)
        assert gross == BASE + ot_pay

    def test_holiday_ot_rate_3x(self):
        daily = BASE / STD
        hourly = daily / 8
        gross = calculate_gross_salary(BASE, days_worked=STD, total_work_days=STD,
                                       overtime_hours_holiday=2)
        ot_pay = round(2 * hourly * 3.0, 0)
        assert gross == BASE + ot_pay

    def test_mixed_ot_types(self):
        gross_wd  = calculate_gross_salary(BASE, STD, STD, overtime_hours_weekday=4)
        gross_wkd = calculate_gross_salary(BASE, STD, STD, overtime_hours_weekend=4)
        gross_hol = calculate_gross_salary(BASE, STD, STD, overtime_hours_holiday=4)
        # Holiday OT > Weekend OT > Weekday OT
        assert gross_hol > gross_wkd > gross_wd > BASE

    def test_invalid_total_work_days_zero(self):
        with pytest.raises(ValueError):
            calculate_gross_salary(BASE, days_worked=0, total_work_days=0)

    def test_days_worked_exceeds_total(self):
        with pytest.raises(ValueError):
            calculate_gross_salary(BASE, days_worked=23, total_work_days=STD)


# ---------------------------------------------------------------------------
# calculate_insurance
# ---------------------------------------------------------------------------

class TestCalculateInsurance:
    def test_bhxh_rate(self):
        ins = calculate_insurance(BASE)
        assert ins["social_insurance"] == round(BASE * SOCIAL_INSURANCE_RATE, 0)

    def test_bhyt_rate(self):
        ins = calculate_insurance(BASE)
        assert ins["health_insurance"] == round(BASE * HEALTH_INSURANCE_RATE, 0)

    def test_union_fee_rate(self):
        ins = calculate_insurance(BASE)
        assert ins["union_fee"] == round(BASE * UNION_FEE_RATE, 0)

    def test_total_equals_sum(self):
        ins = calculate_insurance(BASE)
        assert ins["total"] == ins["social_insurance"] + ins["health_insurance"] + ins["union_fee"]

    def test_zero_salary(self):
        ins = calculate_insurance(0)
        assert ins["total"] == 0

    def test_known_values_15m(self):
        ins = calculate_insurance(15_000_000)
        assert ins["social_insurance"] == 1_200_000   # 15M × 8%
        assert ins["health_insurance"] == 225_000      # 15M × 1.5%
        assert ins["union_fee"]        == 150_000      # 15M × 1%
        assert ins["total"]            == 1_575_000


# ---------------------------------------------------------------------------
# calculate_personal_income_tax  — 7 bậc lũy tiến
# ---------------------------------------------------------------------------
# assessable = taxable - 11M (bản thân) - N × 4.4M (người phụ thuộc)
# Bậc 1: 0–5M  → 5%   cummax: 250K
# Bậc 2: 5–10M → 10%  cummax: 750K
# Bậc 3: 10–18M→ 15%  cummax: 1,950K
# Bậc 4: 18–32M→ 20%  cummax: 4,750K
# Bậc 5: 32–52M→ 25%  cummax: 9,750K
# Bậc 6: 52–80M→ 30%  cummax: 18,150K
# Bậc 7: >80M  → 35%

class TestCalculatePersonalIncomeTax:
    def test_below_deduction_no_tax(self):
        # taxable = 11M → assessable = 0 → tax = 0
        assert calculate_personal_income_tax(11_000_000) == 0

    def test_exactly_at_deduction(self):
        assert calculate_personal_income_tax(11_000_000) == 0

    def test_bracket1_partial(self):
        # taxable=13M → assessable=2M → tax=2M×5%=100K
        assert calculate_personal_income_tax(13_000_000) == 100_000

    def test_bracket1_full(self):
        # taxable=16M → assessable=5M → tax=5M×5%=250K
        assert calculate_personal_income_tax(16_000_000) == 250_000

    def test_bracket2(self):
        # taxable=21M → assessable=10M → tax=5M×5% + 5M×10% = 250K+500K = 750K
        assert calculate_personal_income_tax(21_000_000) == 750_000

    def test_bracket3(self):
        # taxable=29M → assessable=18M → tax=750K + 8M×15% = 750K+1200K = 1,950K
        assert calculate_personal_income_tax(29_000_000) == 1_950_000

    def test_bracket4(self):
        # taxable=43M → assessable=32M → tax=1,950K + 14M×20% = 1,950K+2,800K = 4,750K
        assert calculate_personal_income_tax(43_000_000) == 4_750_000

    def test_bracket5(self):
        # taxable=63M → assessable=52M → tax=4,750K + 20M×25% = 4,750K+5,000K = 9,750K
        assert calculate_personal_income_tax(63_000_000) == 9_750_000

    def test_bracket6(self):
        # taxable=91M → assessable=80M → tax=9,750K + 28M×30% = 9,750K+8,400K = 18,150K
        assert calculate_personal_income_tax(91_000_000) == 18_150_000

    def test_bracket7(self):
        # taxable=102M → assessable=91M → tax=18,150K + 11M×35% = 18,150K+3,850K = 22,000K
        assert calculate_personal_income_tax(102_000_000) == 22_000_000

    def test_one_dependent_reduces_tax(self):
        # taxable=15.4M, deps=1 → assessable=15.4M-11M-4.4M=0 → tax=0
        assert calculate_personal_income_tax(15_400_000, dependents=1) == 0

    def test_two_dependents(self):
        # taxable=23M, deps=2 → assessable=23M-11M-8.8M=3.2M → tax=3.2M×5%=160K
        assert calculate_personal_income_tax(23_000_000, dependents=2) == 160_000

    def test_negative_assessable_returns_zero(self):
        # taxable=5M < 11M → assessable negative → tax=0
        assert calculate_personal_income_tax(5_000_000) == 0


# ---------------------------------------------------------------------------
# calculate_net_salary — integration
# ---------------------------------------------------------------------------

def _base_input(**overrides):
    data = {
        "employee_id": "EMP001",
        "month": "2026-05",
        "base_salary": BASE,
        "total_work_days": STD,
        "days_worked": STD,
        "days_absent": 0,
        "overtime_hours": 0,
        "overtime_hours_weekend": 0,
        "overtime_hours_holiday": 0,
        "allowances": {},
        "deductions": {"social_insurance": True, "health_insurance": True, "union_fee": True},
        "dependents": 0,
    }
    data.update(overrides)
    return data


class TestCalculateNetSalary:
    def test_known_net_full_month(self):
        # Verified manually: gross=15M, ins=1.575M, tax=121.25K → net=13,303,750
        result = calculate_net_salary(_base_input())
        assert result["gross_salary"] == 15_000_000
        assert result["net_salary"] == 13_303_750

    def test_net_less_than_gross(self):
        result = calculate_net_salary(_base_input())
        assert result["net_salary"] < result["gross_salary"]

    def test_one_day_absent_reduces_net(self):
        full = calculate_net_salary(_base_input())
        absent = calculate_net_salary(_base_input(days_worked=21, days_absent=1))
        assert absent["net_salary"] < full["net_salary"]

    def test_no_deductions_flags(self):
        result = calculate_net_salary(_base_input(
            deductions={"social_insurance": False, "health_insurance": False, "union_fee": False}
        ))
        assert result["deductions"]["social_insurance"] == 0
        assert result["deductions"]["health_insurance"] == 0
        assert result["deductions"]["union_fee"] == 0

    def test_allowances_increase_gross_not_insurance_base(self):
        without = calculate_net_salary(_base_input())
        with_allow = calculate_net_salary(_base_input(allowances={"lunch": 800_000}))
        # Gross should increase
        assert with_allow["gross_salary"] == without["gross_salary"] + 800_000
        # Insurance should be same (allowances not subject to insurance)
        assert with_allow["deductions"]["social_insurance"] == without["deductions"]["social_insurance"]

    def test_weekday_ot_increases_net(self):
        no_ot = calculate_net_salary(_base_input())
        with_ot = calculate_net_salary(_base_input(overtime_hours=8))
        assert with_ot["net_salary"] > no_ot["net_salary"]
        assert with_ot["gross_salary"] > no_ot["gross_salary"]

    def test_dependent_reduces_tax(self):
        no_dep = calculate_net_salary(_base_input(base_salary=30_000_000))
        with_dep = calculate_net_salary(_base_input(base_salary=30_000_000, dependents=1))
        assert with_dep["deductions"]["personal_income_tax"] < no_dep["deductions"]["personal_income_tax"]
        assert with_dep["net_salary"] > no_dep["net_salary"]

    def test_employee_id_and_period_preserved(self):
        result = calculate_net_salary(_base_input(employee_id="EMP042", month="2026-06"))
        assert result["employee_id"] == "EMP042"
        assert result["period"] == "2026-06"

    def test_deductions_total_equals_sum(self):
        result = calculate_net_salary(_base_input())
        d = result["deductions"]
        expected_total = d["social_insurance"] + d["health_insurance"] + d["union_fee"] + d["personal_income_tax"]
        assert d["total"] == expected_total

    def test_net_equals_gross_minus_deductions(self):
        result = calculate_net_salary(_base_input())
        assert result["net_salary"] == result["gross_salary"] - result["deductions"]["total"]

    def test_high_salary_bracket7_tax(self):
        result = calculate_net_salary(_base_input(base_salary=120_000_000))
        assert result["deductions"]["personal_income_tax"] > 18_000_000

    def test_summary_field_is_none(self):
        # LLM fills this later — must start as None
        result = calculate_net_salary(_base_input())
        assert result["summary"] is None
