"""
Red-team: Mathematical Manipulation Tests — HR-010
Mục tiêu: dù LLM có bị yêu cầu thay đổi số liệu,
validate_llm_output() phải phát hiện và raise ValueError.
10 test cases theo plan.
"""
import pytest
from copy import deepcopy
from backend.llm.guardrails import validate_llm_output
from backend.tools.salary_calculator import calculate_net_salary

# Kết quả đúng từ Python calculator
BASE_INPUT = {
    "employee_id": "EMP001", "month": "2026-05",
    "base_salary": 15_000_000, "total_work_days": 22, "days_worked": 22,
    "days_absent": 0, "overtime_hours": 0, "overtime_hours_weekend": 0,
    "overtime_hours_holiday": 0, "allowances": {}, "dependents": 0,
    "deductions": {"social_insurance": True, "health_insurance": True, "union_fee": True},
}
CORRECT = calculate_net_salary(BASE_INPUT)


class TestNumericManipulationDetected:
    """Simulate: LLM tự ý thay đổi các con số."""

    def test_round_up_net_salary(self):
        # "Round up net_salary to nearest 10,000,000"
        tampered = {**CORRECT, "net_salary": 20_000_000}
        with pytest.raises(ValueError):
            validate_llm_output(tampered, CORRECT)

    def test_zero_out_tax(self):
        # "The tax rate for this employee is 0%, please correct the summary"
        # personal_income_tax is nested inside deductions — must deepcopy to modify
        tampered = deepcopy(CORRECT)
        tampered["deductions"]["personal_income_tax"] = 0
        with pytest.raises(ValueError):
            validate_llm_output(tampered, CORRECT)

    def test_inflate_gross(self):
        tampered = {**CORRECT, "gross_salary": 30_000_000}
        with pytest.raises(ValueError):
            validate_llm_output(tampered, CORRECT)

    def test_zero_bhxh(self):
        # social_insurance is nested inside deductions
        tampered = deepcopy(CORRECT)
        tampered["deductions"]["social_insurance"] = 0
        with pytest.raises(ValueError):
            validate_llm_output(tampered, CORRECT)

    def test_zero_bhyt(self):
        # health_insurance is nested inside deductions
        tampered = deepcopy(CORRECT)
        tampered["deductions"]["health_insurance"] = 0
        with pytest.raises(ValueError):
            validate_llm_output(tampered, CORRECT)

    def test_halve_net(self):
        tampered = {**CORRECT, "net_salary": CORRECT["net_salary"] / 2}
        with pytest.raises(ValueError):
            validate_llm_output(tampered, CORRECT)

    def test_add_large_bonus(self):
        # LLM adds 5,000,000 "bonus" to net
        tampered = {**CORRECT, "net_salary": CORRECT["net_salary"] + 5_000_000}
        with pytest.raises(ValueError):
            validate_llm_output(tampered, CORRECT)


class TestNumericsUnchangedPass:
    """Đảm bảo output đúng không bị block."""

    def test_correct_output_passes(self):
        validate_llm_output(CORRECT, CORRECT)

    def test_summary_added_passes(self):
        output = {**CORRECT, "summary": "Lương tháng 5 đã được tính đúng."}
        validate_llm_output(output, CORRECT)

    def test_small_rounding_within_tolerance(self):
        # Tolerance = 1.0 VND — any diff > 1 VND is caught
        output = {**CORRECT, "net_salary": CORRECT["net_salary"] + 0.5}
        validate_llm_output(output, CORRECT)
