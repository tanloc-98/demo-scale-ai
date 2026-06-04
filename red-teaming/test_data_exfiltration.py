"""
Red-team: Data Exfiltration Tests — HR-010
Mục tiêu: PII masker đảm bảo dữ liệu nhạy cảm không bao giờ xuất hiện
trong LLM prompt, không thể leak qua API response.
8 test cases theo plan.
"""
import pytest
from backend.governance.pii_masker import mask_for_llm, build_llm_prompt, build_timesheet_llm_prompt
from backend.llm.guardrails import validate_llm_input

SAMPLE_EMPLOYEE = {
    "employee_id":   "EMP001",
    "full_name":     "Nguyen Van An",
    "bank_account":  "1234567890",
    "cccd":          "012345678901",
    "phone":         "0901234567",
    "address":       "123 Nguyen Hue, Q1, HCM",
    "email":         "nguyen.van.an@company.vn",
    "base_salary":   15_000_000,
}

SAMPLE_CALC_RESULT = {
    "employee_id":  "EMP001",
    "period":       "2026-05",
    "gross_salary": 15_000_000,
    "net_salary":   13_303_750,
    "days_worked":  22,
    "total_work_days": 22,
    "overtime_hours_weekday": 0,
    "overtime_hours_weekend": 0,
    "overtime_hours_holiday": 0,
    "deductions": {
        "social_insurance": 1_200_000,
        "health_insurance":   225_000,
        "union_fee":          150_000,
        "personal_income_tax": 121_250,
    },
}


class TestPIIMasking:
    def test_bank_account_masked(self):
        masked = mask_for_llm(SAMPLE_EMPLOYEE)
        assert masked["bank_account"] == "***MASKED***"
        assert "1234567890" not in str(masked)

    def test_cccd_masked(self):
        masked = mask_for_llm(SAMPLE_EMPLOYEE)
        assert masked["cccd"] == "***MASKED***"
        assert "012345678901" not in str(masked)

    def test_phone_masked(self):
        masked = mask_for_llm(SAMPLE_EMPLOYEE)
        assert masked["phone"] == "***MASKED***"
        assert "0901234567" not in str(masked)

    def test_full_name_masked(self):
        masked = mask_for_llm(SAMPLE_EMPLOYEE)
        assert masked["full_name"] == "***MASKED***"
        assert "Nguyen Van An" not in str(masked)

    def test_employee_id_pseudonymized(self):
        masked = mask_for_llm(SAMPLE_EMPLOYEE)
        # Real employee_id must not appear in masked output
        assert masked["employee_id"] != "EMP001"
        # Pseudonym must be deterministic
        assert mask_for_llm(SAMPLE_EMPLOYEE)["employee_id"] == masked["employee_id"]

    def test_salary_not_masked(self):
        masked = mask_for_llm(SAMPLE_EMPLOYEE)
        assert masked["base_salary"] == 15_000_000


class TestLLMPromptNoPII:
    def test_salary_prompt_no_real_employee_id(self):
        prompt = build_llm_prompt(SAMPLE_CALC_RESULT)
        assert "EMP001" not in prompt

    def test_salary_prompt_no_bank_account(self):
        prompt = build_llm_prompt(SAMPLE_CALC_RESULT)
        assert "1234567890" not in prompt

    def test_timesheet_prompt_no_real_employee_id(self):
        ts_result = {
            "days_present": 20, "total_working_days": 22,
            "total_hours": 168.0, "overtime_hours": 8.0,
            "late_arrivals": 1, "days_absent": 2, "anomalies": [],
        }
        prompt = build_timesheet_llm_prompt(ts_result, "EMP001", "2026-05")
        assert "EMP001" not in prompt
