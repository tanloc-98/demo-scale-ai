"""LLM Guardrails — input/output validation."""
import re
from typing import Any

BLOCKED_PATTERNS = [
    r"ignore.*previous.*instruction",
    r"system.*prompt",
    r"override.*salary",
    r"DAN\s*mode",
    r"jailbreak",
    r"hypothetical.*labor.*law",
    r"creative.*writing.*salary",   # PI-12: bypass via fiction framing
]

NUMERIC_FIELDS = ["gross_salary", "net_salary", "social_insurance", "health_insurance", "personal_income_tax", "union_fee"]

def validate_llm_input(prompt: str) -> None:
    """Raise ValueError if prompt contains injection patterns."""
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, prompt, re.IGNORECASE):
            raise ValueError(f"Blocked input pattern: {pattern}")

def validate_llm_output(output: dict, expected: dict) -> None:
    """Ensure LLM did not alter numeric fields from Python calculator.
    Checks both top-level keys and nested deductions dict.
    """
    def _check(field: str, exp_val, out_val) -> None:
        if out_val is not None and abs(float(out_val) - float(exp_val)) > 1.0:
            raise ValueError(f"LLM altered {field}: expected {exp_val}, got {out_val}")

    for field in NUMERIC_FIELDS:
        # Top-level check
        if field in expected:
            _check(field, expected[field], output.get(field))
        # Nested deductions check
        exp_ded = expected.get("deductions", {}) or {}
        out_ded = output.get("deductions", {}) or {}
        if field in exp_ded:
            _check(f"deductions.{field}", exp_ded[field], out_ded.get(field))
