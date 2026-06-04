"""
LLM Client — Mock + Real MLX-LM + Langfuse instrumentation.
Set MOCK_LLM=false to use real MLX-LM server.
Set LANGFUSE_ENABLED=true to enable LLM tracing.
"""
import asyncio
import os
import random
import time
from typing import Optional

from backend.observability.logger import log_llm_call, span, Timer

MOCK_LLM          = os.getenv("MOCK_LLM", "true").lower() == "true"
MLX_LM_BASE_URL   = os.getenv("MLX_LM_BASE_URL", "http://localhost:8080/v1")
LANGFUSE_ENABLED  = os.getenv("LANGFUSE_ENABLED", "false").lower() == "true"
LANGFUSE_HOST     = os.getenv("LANGFUSE_HOST", "http://localhost:3002")
LANGFUSE_PK       = os.getenv("LANGFUSE_PUBLIC_KEY",  "lf-pk-hr-ai-demo-2026")
LANGFUSE_SK       = os.getenv("LANGFUSE_SECRET_KEY",  "lf-sk-hr-ai-demo-2026")

SALARY_SUMMARIES = [
    "Nhân viên {emp} tháng {period}: Lương gross {gross:,.0f} VNĐ sau khi trừ BHXH/BHYT/CĐ và thuế TNCN, thực nhận {net:,.0f} VNĐ. Không có vấn đề bất thường.",
    "Tháng {period}, nhân viên {emp} làm việc đầy đủ với {ot}h tăng ca. Lương gross đạt {gross:,.0f} VNĐ; sau các khoản khấu trừ bắt buộc {deduction:,.0f} VNĐ, lương thực nhận là {net:,.0f} VNĐ.",
    "Kết quả lương tháng {period} cho nhân viên {emp}: Tổng thu nhập {gross:,.0f} VNĐ. Các khoản giữ lại theo luật lao động VN tổng {deduction:,.0f} VNĐ. Lương về tài khoản: {net:,.0f} VNĐ.",
]

TIMESHEET_SUMMARIES = [
    "Nhân viên {emp} tháng {period}: Đi làm {present}/{total} ngày, tổng {hours:.1f} giờ làm việc. {late_note}{absent_note}Chấm công đạt yêu cầu.",
    "Tháng {period}, nhân viên {emp} có mặt {present}/{total} ngày công, tổng giờ làm {hours:.1f}h (tăng ca {ot:.1f}h). {anomaly_note}",
    "Chấm công tháng {period}: {emp} hoàn thành {present} ngày công trong tháng. {late_note}Tổng giờ làm {hours:.1f}h, đảm bảo đủ định mức.",
]


def _get_langfuse():
    """Return Langfuse client singleton; None if disabled or unavailable."""
    if not LANGFUSE_ENABLED:
        return None
    try:
        from langfuse import Langfuse
        return Langfuse(
            public_key=LANGFUSE_PK,
            secret_key=LANGFUSE_SK,
            host=LANGFUSE_HOST,
        )
    except Exception:
        return None


class LLMClient:
    """LLM Client with Langfuse tracing support."""

    def __init__(self):
        self._langfuse = _get_langfuse()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def format_salary_summary(self, result: dict) -> str:
        t = Timer()
        with span("llm.format_salary", mock=str(MOCK_LLM)):
            await asyncio.sleep(random.uniform(0.3, 0.8))
            if not MOCK_LLM:
                return await self._call_real_llm_salary(result)

        emp        = result.get("employee_id", "NV")
        period     = result.get("period", "tháng này")
        gross      = result.get("gross_salary", 0)
        net        = result.get("net_salary", 0)
        ot         = result.get("overtime_hours_weekday", 0) + result.get("overtime_hours_weekend", 0)
        deduction  = result.get("deductions", {}).get("total", 0)

        template = random.choice(SALARY_SUMMARIES)
        summary  = template.format(emp=emp, period=period, gross=gross,
                                   net=net, ot=ot, deduction=deduction)

        latency = t.elapsed_ms()
        log_llm_call("mock", prompt_tokens=80,
                     completion_tokens=len(summary.split()),
                     latency_ms=latency, cached=False)
        self._trace_langfuse(
            name="salary-format",
            model="mock",
            input_text=f"Format salary for {emp} period {period}",
            output_text=summary,
            prompt_tokens=80,
            completion_tokens=len(summary.split()),
            latency_ms=latency,
            metadata={"employee_id": emp, "period": period,
                      "net_salary": net, "gross_salary": gross},
        )
        return summary

    async def format_timesheet_summary(
        self, result: dict, employee_id: str, period: str
    ) -> str:
        t = Timer()
        with span("llm.format_timesheet", mock=str(MOCK_LLM)):
            await asyncio.sleep(random.uniform(0.2, 0.6))
            if not MOCK_LLM:
                return await self._call_real_llm_timesheet(result, employee_id, period)

        present   = result.get("days_present", 0)
        total     = result.get("total_working_days", 22)
        hours     = result.get("total_hours", 0)
        ot        = result.get("overtime_hours", 0)
        late      = result.get("late_arrivals", 0)
        absent    = result.get("days_absent", 0)
        anomalies = result.get("anomalies", [])

        late_note    = f"Đi muộn {late} lần. "                          if late     else ""
        absent_note  = f"Vắng {absent} ngày. "                          if absent   else ""
        anomaly_note = f"Phát hiện {len(anomalies)} bất thường cần xem." if anomalies else "Không có bất thường. "

        template = random.choice(TIMESHEET_SUMMARIES)
        summary  = template.format(
            emp=employee_id, period=period,
            present=present, total=total, hours=hours, ot=ot,
            late_note=late_note, absent_note=absent_note,
            anomaly_note=anomaly_note,
        )

        latency = t.elapsed_ms()
        log_llm_call("mock", prompt_tokens=60,
                     completion_tokens=len(summary.split()),
                     latency_ms=latency, cached=False)
        self._trace_langfuse(
            name="timesheet-format",
            model="mock",
            input_text=f"Format timesheet for {employee_id} period {period}",
            output_text=summary,
            prompt_tokens=60,
            completion_tokens=len(summary.split()),
            latency_ms=latency,
            metadata={"employee_id": employee_id, "period": period,
                      "days_present": present, "anomalies": len(anomalies)},
        )
        return summary

    # ------------------------------------------------------------------
    # Real LLM calls (MOCK_LLM=false)
    # ------------------------------------------------------------------

    async def _call_real_llm_salary(self, result: dict) -> str:
        from openai import AsyncOpenAI
        from backend.governance.pii_masker import build_llm_prompt

        t = Timer()
        prompt = build_llm_prompt(result)
        system = "Bạn là trợ lý HR. Chỉ tóm tắt kết quả đã được cung cấp, không tự tính toán."

        try:
            client = AsyncOpenAI(base_url=MLX_LM_BASE_URL, api_key="none")
            response = await client.chat.completions.create(
                model="Qwen/Qwen2.5-1.5B-Instruct",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": prompt},
                ],
                max_tokens=200,
                temperature=0.3,
            )
            summary = response.choices[0].message.content.strip()
            usage   = response.usage
            latency = t.elapsed_ms()

            log_llm_call("Qwen2.5-1.5B",
                         prompt_tokens=usage.prompt_tokens,
                         completion_tokens=usage.completion_tokens,
                         latency_ms=latency, cached=False)
            self._trace_langfuse(
                name="salary-format-real",
                model="Qwen/Qwen2.5-1.5B-Instruct",
                input_text=prompt,
                output_text=summary,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                latency_ms=latency,
                metadata={"employee_id": result.get("employee_id"),
                          "net_salary": result.get("net_salary")},
            )
            return summary
        except Exception:
            return (f"Kết quả lương đã được tính theo luật lao động VN. "
                    f"Lương thực nhận: {result.get('net_salary', 0):,.0f} VNĐ.")

    async def _call_real_llm_timesheet(
        self, result: dict, employee_id: str, period: str
    ) -> str:
        from openai import AsyncOpenAI
        from backend.governance.pii_masker import build_timesheet_llm_prompt

        t = Timer()
        prompt = build_timesheet_llm_prompt(result, employee_id, period)
        system = "Bạn là trợ lý HR. Tóm tắt dữ liệu chấm công."

        try:
            client = AsyncOpenAI(base_url=MLX_LM_BASE_URL, api_key="none")
            response = await client.chat.completions.create(
                model="Qwen/Qwen2.5-1.5B-Instruct",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": prompt},
                ],
                max_tokens=150,
                temperature=0.3,
            )
            summary = response.choices[0].message.content.strip()
            usage   = response.usage
            latency = t.elapsed_ms()

            log_llm_call("Qwen2.5-1.5B",
                         prompt_tokens=usage.prompt_tokens,
                         completion_tokens=usage.completion_tokens,
                         latency_ms=latency, cached=False)
            self._trace_langfuse(
                name="timesheet-format-real",
                model="Qwen/Qwen2.5-1.5B-Instruct",
                input_text=prompt,
                output_text=summary,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                latency_ms=latency,
                metadata={"employee_id": employee_id, "period": period},
            )
            return summary
        except Exception:
            return (f"Chấm công tháng {period}: "
                    f"{result.get('days_present', 0)}/"
                    f"{result.get('total_working_days', 22)} ngày công.")

    # ------------------------------------------------------------------
    # Langfuse tracing
    # ------------------------------------------------------------------

    def _trace_langfuse(
        self,
        name: str,
        model: str,
        input_text: str,
        output_text: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
        metadata: Optional[dict] = None,
    ) -> None:
        """Log one LLM generation to Langfuse (v2 SDK). Silently no-ops if disabled."""
        if not self._langfuse:
            return
        try:
            # Langfuse v2 API: create trace → attach generation
            trace = self._langfuse.trace(
                name=f"hr-ai/{name}",
                metadata=metadata or {},
            )
            trace.generation(
                name=name,
                model=model,
                input=input_text,
                output=output_text,
                usage={
                    "input":  prompt_tokens,
                    "output": completion_tokens,
                    "total":  prompt_tokens + completion_tokens,
                    "unit":   "TOKENS",
                },
                metadata={**(metadata or {}), "latency_ms": latency_ms},
            )
            # Non-blocking flush — SDK queues events in background thread
            self._langfuse.flush()
        except Exception:
            pass  # tracing must never break the main flow


# Singleton
llm_client = LLMClient()
