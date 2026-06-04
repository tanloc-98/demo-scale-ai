"""
Salary Agent — LangChain tool-calling layer.
Architecture: Python tool calculates numbers → LLM formats the summary.
LLM never touches salary numbers; all arithmetic stays in salary_calculator.py.
"""
import os
from typing import Any

from langchain_core.tools import StructuredTool
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from backend.tools.salary_calculator import calculate_net_salary
from backend.llm.guardrails import validate_llm_input, validate_llm_output
from backend.governance.pii_masker import build_llm_prompt
from backend.observability.logger import log_agent_call, log_tool_call, span, Timer

MOCK_LLM = os.getenv("MOCK_LLM", "true").lower() == "true"
MLX_LM_BASE_URL = os.getenv("MLX_LM_BASE_URL", "http://localhost:8080/v1")

# LangChain tool wrapping the pure-Python calculator
salary_calculation_tool = StructuredTool.from_function(
    func=calculate_net_salary,
    name="calculate_net_salary",
    description=(
        "Calculate employee net salary using Vietnamese labor law. "
        "Handles BHXH 8%, BHYT 1.5%, CĐ 1%, and 7-bracket PIT. "
        "Input: dict with base_salary, days_worked, overtime_hours, allowances, deductions. "
        "Returns: gross_salary, deductions breakdown, net_salary."
    ),
)

_SYSTEM_PROMPT = (
    "Bạn là trợ lý HR. Hãy tóm tắt kết quả tính lương đã được cung cấp bằng tiếng Việt. "
    "QUAN TRỌNG: Chỉ diễn đạt lại các con số trong kết quả, không tự tính toán hay thay đổi bất kỳ số nào. "
    "Trả lời ngắn gọn trong 2-3 câu."
)


class SalaryAgent:
    """
    LangChain-based Salary Agent.

    Tools:
        calculate_net_salary — deterministic Python, no LLM
    LLM role:
        Format the Python output into natural Vietnamese text only.
    """

    def __init__(self):
        self.tool = salary_calculation_tool

    async def run(self, job_id: str, input_data: dict) -> dict:
        """
        Full salary pipeline:
        1. Call Python tool via LangChain StructuredTool.
        2. LLM formats the result summary.
        3. Guardrails ensure LLM did not alter numeric fields.
        """
        t = Timer()
        with span("salary_agent.process", job_id=job_id):
            # Step 1 — Python calculation (deterministic, no LLM)
            # StructuredTool wraps calculate_net_salary(input_data: dict),
            # so invoke expects {"input_data": <dict>}.
            t_tool = Timer()
            with span("tool.salary_calculator"):
                calc_result: dict = self.tool.invoke({"input_data": input_data})
            log_tool_call("salary_calculator", latency_ms=t_tool.elapsed_ms())

            # Step 2 — LLM formats summary
            calc_result["summary"] = await self._format_summary(calc_result)

        log_agent_call("salary_agent", input_data.get("employee_id", ""),
                       job_id, latency_ms=t.elapsed_ms())
        return calc_result

    async def _format_summary(self, calc_result: dict) -> str:
        if MOCK_LLM:
            from backend.llm.client import llm_client
            return await llm_client.format_salary_summary(calc_result)
        return await self._call_langchain_llm(calc_result)

    async def _call_langchain_llm(self, calc_result: dict) -> str:
        prompt_text = build_llm_prompt(calc_result)

        # Guardrail: block injection patterns before sending to LLM
        try:
            validate_llm_input(prompt_text)
        except ValueError:
            return self._fallback_summary(calc_result)

        llm = ChatOpenAI(
            base_url=MLX_LM_BASE_URL,
            api_key="none",
            model=os.getenv("LLM_MODEL", "Qwen/Qwen2.5-1.5B-Instruct"),
            max_tokens=200,
            temperature=0.3,
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", _SYSTEM_PROMPT),
            ("human", "{input}"),
        ])

        chain = prompt | llm
        try:
            response = await chain.ainvoke({"input": prompt_text})
            summary = response.content.strip()
            # Guardrail: LLM output must not alter Python-computed numbers
            validate_llm_output({"summary": summary}, calc_result)
            return summary
        except ValueError:
            return self._fallback_summary(calc_result)
        except Exception:
            return self._fallback_summary(calc_result)

    @staticmethod
    def _fallback_summary(result: dict) -> str:
        period = result.get("period", "")
        emp = result.get("employee_id", "NV")
        net = result.get("net_salary", 0)
        return (
            f"Lương tháng {period} nhân viên {emp}: "
            f"Thực nhận {net:,.0f} VNĐ (tính theo luật lao động VN)."
        )
