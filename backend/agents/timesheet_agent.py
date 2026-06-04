"""
Timesheet Agent — LangChain tool-calling layer.
Architecture: Python tool processes check-in/out records → LLM formats explanation.
LLM never changes attendance numbers; all logic stays in timesheet_processor.py.
"""
import os

from langchain_core.tools import StructuredTool
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from backend.tools.timesheet_processor import process_timesheet
from backend.llm.guardrails import validate_llm_input
from backend.governance.pii_masker import build_timesheet_llm_prompt
from backend.observability.logger import log_agent_call, log_tool_call, span, Timer

MOCK_LLM = os.getenv("MOCK_LLM", "true").lower() == "true"
MLX_LM_BASE_URL = os.getenv("MLX_LM_BASE_URL", "http://localhost:8080/v1")


def _process_timesheet_tool(records: list, work_schedule: dict | None, month: str) -> dict:
    """Wrapper so StructuredTool can accept positional args from LangChain."""
    return process_timesheet(records, work_schedule, month)


timesheet_processing_tool = StructuredTool.from_function(
    func=_process_timesheet_tool,
    name="process_timesheet",
    description=(
        "Process employee check-in/out records for a month. "
        "Detects late arrivals, early leaves, missing punches, and overtime. "
        "Input: records (list of {date, check_in, check_out}), work_schedule, month (YYYY-MM). "
        "Returns: days_present, total_hours, overtime_hours, anomalies list."
    ),
)

_SYSTEM_PROMPT = (
    "Bạn là trợ lý HR. Hãy tóm tắt dữ liệu chấm công đã được cung cấp bằng tiếng Việt. "
    "Chỉ diễn đạt lại thông tin trong kết quả, không suy diễn thêm. "
    "Nêu rõ số ngày công, giờ làm việc, và các bất thường (nếu có). Trả lời ngắn gọn."
)


class TimesheetAgent:
    """
    LangChain-based Timesheet Agent.

    Tools:
        process_timesheet — deterministic Python rule engine, no LLM
    LLM role:
        Explain attendance summary and anomalies in natural Vietnamese.
    """

    def __init__(self):
        self.tool = timesheet_processing_tool

    async def run(self, job_id: str, data: dict) -> dict:
        """
        Full timesheet pipeline:
        1. Call Python tool via LangChain StructuredTool.
        2. LLM formats explanation of attendance summary.
        """
        t = Timer()
        with span("timesheet_agent.process", job_id=job_id):
            records = data["records"]
            schedule = data.get("work_schedule")
            month = data["month"]

            # Step 1 — Python processing (no LLM)
            t_tool = Timer()
            with span("tool.timesheet_processor"):
                result: dict = self.tool.invoke({
                    "records": records,
                    "work_schedule": schedule,
                    "month": month,
                })
            log_tool_call("timesheet_processor", latency_ms=t_tool.elapsed_ms())

            result["employee_id"] = data["employee_id"]
            result["period"] = month

            # Step 2 — LLM formats summary
            result["summary"] = await self._format_summary(
                result, data["employee_id"], month
            )

        log_agent_call("timesheet_agent", data["employee_id"],
                       job_id, latency_ms=t.elapsed_ms())
        return result

    async def _format_summary(
        self, result: dict, employee_id: str, period: str
    ) -> str:
        if MOCK_LLM:
            from backend.llm.client import llm_client
            return await llm_client.format_timesheet_summary(result, employee_id, period)
        return await self._call_langchain_llm(result, employee_id, period)

    async def _call_langchain_llm(
        self, result: dict, employee_id: str, period: str
    ) -> str:
        prompt_text = build_timesheet_llm_prompt(result, employee_id, period)

        try:
            validate_llm_input(prompt_text)
        except ValueError:
            return self._fallback_summary(result, employee_id, period)

        llm = ChatOpenAI(
            base_url=MLX_LM_BASE_URL,
            api_key="none",
            model=os.getenv("LLM_MODEL", "Qwen/Qwen2.5-1.5B-Instruct"),
            max_tokens=150,
            temperature=0.3,
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", _SYSTEM_PROMPT),
            ("human", "{input}"),
        ])

        chain = prompt | llm
        try:
            response = await chain.ainvoke({"input": prompt_text})
            return response.content.strip()
        except Exception:
            return self._fallback_summary(result, employee_id, period)

    @staticmethod
    def _fallback_summary(result: dict, employee_id: str, period: str) -> str:
        present = result.get("days_present", 0)
        total = result.get("total_working_days", 22)
        hours = result.get("total_hours", 0)
        anomalies = result.get("anomalies", [])
        note = f" Phát hiện {len(anomalies)} bất thường." if anomalies else ""
        return (
            f"Chấm công tháng {period}: {employee_id} có mặt {present}/{total} ngày, "
            f"tổng {hours:.1f} giờ làm việc.{note}"
        )
