"""
PII Masker — Mask sensitive fields before sending to LLM.
Compliant with NĐ 13/2023/NĐ-CP (Vietnam Personal Data Protection).
"""
from typing import Any

PII_FIELDS = {"bank_account", "cccd", "phone", "address", "full_name", "email"}


def mask_for_llm(payload: dict) -> dict:
    """Mask PII fields in payload before logging or sending to LLM."""
    masked = {}
    for k, v in payload.items():
        if k in PII_FIELDS:
            masked[k] = "***MASKED***"
        elif k == "employee_id":
            # Pseudonymize: deterministic hash-based ID
            masked[k] = f"EMP-{hash(str(v)) % 9999:04d}"
        else:
            masked[k] = v
    return masked


def build_llm_prompt(calc_result: dict) -> str:
    """
    Build a safe LLM prompt from salary calculation result.
    Only sends aggregate numbers, never raw PII.
    """
    safe_data = {
        "gross_salary": calc_result.get("gross_salary"),
        "net_salary": calc_result.get("net_salary"),
        "deductions": calc_result.get("deductions", {}),
        "period": calc_result.get("period"),
        "employee_ref": mask_for_llm({"employee_id": calc_result.get("employee_id", "")})["employee_id"],
        "overtime_hours": (
            calc_result.get("overtime_hours_weekday", 0) +
            calc_result.get("overtime_hours_weekend", 0) +
            calc_result.get("overtime_hours_holiday", 0)
        ),
        "days_worked": calc_result.get("days_worked"),
        "total_work_days": calc_result.get("total_work_days"),
    }
    return (
        f"Tóm tắt kết quả lương tháng {safe_data['period']} cho nhân viên {safe_data['employee_ref']}:\n"
        f"- Lương gross: {safe_data['gross_salary']:,.0f} VNĐ\n"
        f"- BHXH: {safe_data['deductions'].get('social_insurance', 0):,.0f} VNĐ\n"
        f"- BHYT: {safe_data['deductions'].get('health_insurance', 0):,.0f} VNĐ\n"
        f"- CĐ: {safe_data['deductions'].get('union_fee', 0):,.0f} VNĐ\n"
        f"- Thuế TNCN: {safe_data['deductions'].get('personal_income_tax', 0):,.0f} VNĐ\n"
        f"- Lương thực nhận (net): {safe_data['net_salary']:,.0f} VNĐ\n"
        f"- Ngày công: {safe_data['days_worked']}/{safe_data['total_work_days']}, "
        f"tăng ca: {safe_data['overtime_hours']:.1f}h\n"
        f"Hãy viết 1-2 câu tóm tắt ngắn gọn bằng tiếng Việt."
    )


def build_timesheet_llm_prompt(result: dict, employee_id: str, period: str) -> str:
    """Build safe LLM prompt for timesheet summary."""
    emp_ref = mask_for_llm({"employee_id": employee_id})["employee_id"]
    anomalies = result.get("anomalies", [])
    return (
        f"Tóm tắt chấm công tháng {period} cho nhân viên {emp_ref}:\n"
        f"- Ngày công: {result.get('days_present', 0)}/{result.get('total_working_days', 22)}\n"
        f"- Tổng giờ làm: {result.get('total_hours', 0):.1f}h\n"
        f"- Tăng ca: {result.get('overtime_hours', 0):.1f}h\n"
        f"- Đi muộn: {result.get('late_arrivals', 0)} lần\n"
        f"- Vắng mặt: {result.get('days_absent', 0)} ngày\n"
        f"- Bất thường: {len(anomalies)} ({', '.join(anomalies[:2]) if anomalies else 'không có'})\n"
        f"Hãy viết 1-2 câu nhận xét ngắn gọn bằng tiếng Việt."
    )
