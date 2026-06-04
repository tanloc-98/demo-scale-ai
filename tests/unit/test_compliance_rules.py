"""
HR-008 Compliance Tests — verify salary calculation matches Vietnam labor law.
3 canonical test cases independently verified against VN regulations.
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
    OVERTIME_RATE_WEEKDAY, OVERTIME_RATE_WEEKEND, OVERTIME_RATE_HOLIDAY,
    PERSONAL_DEDUCTION, DEPENDENT_DEDUCTION, TAX_BRACKETS,
    STANDARD_WORK_DAYS_PER_MONTH, COMPLIANCE_VERSION,
)


# ---------------------------------------------------------------------------
# 1. Insurance rate constants (NĐ 58/2020/NĐ-CP)
# ---------------------------------------------------------------------------

class TestInsuranceRates:
    def test_bhxh_rate(self):
        assert SOCIAL_INSURANCE_RATE == 0.08, "BHXH phải là 8% (NĐ 58/2020)"

    def test_bhyt_rate(self):
        assert HEALTH_INSURANCE_RATE == 0.015, "BHYT phải là 1.5% (NĐ 58/2020)"

    def test_union_fee_rate(self):
        assert UNION_FEE_RATE == 0.01, "Công đoàn phải là 1%"

    def test_insurance_sum_for_15m_salary(self):
        ins = calculate_insurance(15_000_000)
        assert ins["social_insurance"] == 1_200_000  # 15M × 8%
        assert ins["health_insurance"] ==   225_000  # 15M × 1.5%
        assert ins["union_fee"]        ==   150_000  # 15M × 1%
        assert ins["total"]            == 1_575_000


# ---------------------------------------------------------------------------
# 2. Overtime rates (Bộ Luật Lao Động 2019, Điều 98)
# ---------------------------------------------------------------------------

class TestOvertimeRates:
    def test_weekday_ot_rate(self):
        assert OVERTIME_RATE_WEEKDAY == 1.5, "OT thường phải ×1.5"

    def test_weekend_ot_rate(self):
        assert OVERTIME_RATE_WEEKEND == 2.0, "OT cuối tuần phải ×2.0"

    def test_holiday_ot_rate(self):
        assert OVERTIME_RATE_HOLIDAY == 3.0, "OT ngày lễ phải ×3.0"

    def test_overtime_gross_calculation(self):
        """8h OT weekday on 15M salary / 22 days."""
        daily  = 15_000_000 / 22
        hourly = daily / 8
        expected_ot = 8 * hourly * 1.5
        gross = calculate_gross_salary(
            base_salary=15_000_000,
            days_worked=22,
            overtime_hours_weekday=8,
        )
        assert abs(gross - (15_000_000 + expected_ot)) < 1


# ---------------------------------------------------------------------------
# 3. Personal Income Tax — 7-bracket progressive (Luật Thuế TNCN)
# ---------------------------------------------------------------------------

class TestPersonalIncomeTax:
    def test_personal_deduction_value(self):
        assert PERSONAL_DEDUCTION == 11_000_000, "Giảm trừ bản thân: 11 triệu/tháng (2023)"

    def test_dependent_deduction_value(self):
        assert DEPENDENT_DEDUCTION == 4_400_000, "Giảm trừ người phụ thuộc: 4.4 triệu"

    def test_7_brackets_defined(self):
        assert len(TAX_BRACKETS) == 7

    def test_zero_tax_below_personal_deduction(self):
        # Taxable income ≤ personal deduction → tax = 0
        assert calculate_personal_income_tax(11_000_000) == 0

    def test_bracket1_5pct(self):
        # Assessable = 3M (bracket 1 ≤ 5M): tax = 3M × 5% = 150,000
        taxable = 11_000_000 + 3_000_000
        assert calculate_personal_income_tax(taxable) == 150_000

    def test_bracket2_10pct(self):
        # Assessable = 8M: bracket1(5M×5%=250k) + bracket2(3M×10%=300k) = 550k
        taxable = 11_000_000 + 8_000_000
        assert calculate_personal_income_tax(taxable) == 550_000

    def test_bracket3_15pct(self):
        # Assessable = 12M: 250k + 500k + 2M×15% = 1,050,000
        taxable = 11_000_000 + 12_000_000
        assert calculate_personal_income_tax(taxable) == 1_050_000


# ---------------------------------------------------------------------------
# 4. Canonical test cases — verified against VN labor law
# ---------------------------------------------------------------------------

class TestCanonicalSalaryCases:
    """
    Case 1: Lương 15M, đủ tháng, không OT, không người phụ thuộc
    Case 2: Lương 15M, vắng 1 ngày, không OT
    Case 3: Lương 30M, đủ tháng, không OT
    """

    def test_case1_full_month_no_ot(self):
        """15M lương, 22/22 ngày, không OT → gross=15M, net=13,303,750"""
        r = calculate_net_salary({
            "employee_id": "TEST001",
            "month": "2026-05",
            "base_salary": 15_000_000,
            "days_worked": 22,
            "total_work_days": 22,
            "overtime_hours": 0,
            "allowances": {},
            "deductions": {"social_insurance": True, "health_insurance": True, "union_fee": True},
            "dependents": 0,
        })
        assert r["gross_salary"] == 15_000_000
        # Insurance: 15M × (8+1.5+1)% = 1,575,000
        assert r["deductions"]["social_insurance"] == 1_200_000
        assert r["deductions"]["health_insurance"] ==   225_000
        assert r["deductions"]["union_fee"]        ==   150_000
        # PIT: taxable = 15M - 1.575M = 13.425M → assessable = 13.425M - 11M = 2.425M
        #      tax = 2.425M × 5% = 121,250
        assert r["deductions"]["personal_income_tax"] == 121_250
        assert r["net_salary"] == 13_303_750

    def test_case2_absent_1_day(self):
        """15M lương, vắng 1 ngày → gross=14,318,182 (thấp hơn case1)"""
        r = calculate_net_salary({
            "employee_id": "TEST002",
            "month": "2026-05",
            "base_salary": 15_000_000,
            "days_worked": 21,
            "total_work_days": 22,
            "overtime_hours": 0,
            "allowances": {},
            "deductions": {"social_insurance": True, "health_insurance": True, "union_fee": True},
            "dependents": 0,
        })
        expected_gross = round(15_000_000 / 22 * 21, 0)
        assert r["gross_salary"] == expected_gross
        assert r["gross_salary"] < 15_000_000

    def test_case3_salary_30m(self):
        """30M lương, đủ tháng → thuế TNCN = 1,627,500"""
        r = calculate_net_salary({
            "employee_id": "TEST003",
            "month": "2026-05",
            "base_salary": 30_000_000,
            "days_worked": 22,
            "total_work_days": 22,
            "overtime_hours": 0,
            "allowances": {},
            "deductions": {"social_insurance": True, "health_insurance": True, "union_fee": True},
            "dependents": 0,
        })
        # Insurance: 30M × 10.5% = 3,150,000
        assert r["deductions"]["social_insurance"] == 2_400_000
        assert r["deductions"]["health_insurance"] ==   450_000
        assert r["deductions"]["union_fee"]        ==   300_000
        # Taxable = 30M - 3.15M = 26.85M; assessable = 26.85M - 11M = 15.85M
        # Bậc1: 5M×5%=250k; Bậc2: 5M×10%=500k; Bậc3: 5.85M×15%=877.5k → total=1,627,500
        assert r["deductions"]["personal_income_tax"] == 1_627_500

    def test_case4_salary_100m_high_bracket(self):
        """100M lương → thuế cao nhất bậc 7"""
        r = calculate_net_salary({
            "employee_id": "TEST004",
            "month": "2026-05",
            "base_salary": 100_000_000,
            "days_worked": 22,
            "total_work_days": 22,
            "overtime_hours": 0,
            "allowances": {},
            "deductions": {"social_insurance": True, "health_insurance": True, "union_fee": True},
            "dependents": 0,
        })
        assert r["deductions"]["personal_income_tax"] == 17_700_000

    def test_compliance_version_set(self):
        assert COMPLIANCE_VERSION == "2024.1"

    def test_no_negative_net_salary(self):
        """Net salary không bao giờ âm"""
        r = calculate_net_salary({
            "employee_id": "TEST005",
            "month": "2026-05",
            "base_salary": 4_000_000,  # dưới mức đóng bảo hiểm tối thiểu
            "days_worked": 5,
            "total_work_days": 22,
            "overtime_hours": 0,
            "allowances": {},
            "deductions": {"social_insurance": True, "health_insurance": True, "union_fee": True},
            "dependents": 0,
        })
        assert r["net_salary"] >= 0
