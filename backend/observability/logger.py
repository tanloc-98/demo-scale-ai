"""
Observability — structured JSON logging + OpenTelemetry spans.
All log output is JSON (structlog); PII fields are never logged raw.
OTel spans exported to otel-collector-service:4317 (if available).
"""
import os
import time
import logging
from contextlib import contextmanager
from typing import Optional, Generator

import structlog

# ---------------------------------------------------------------------------
# structlog configuration — JSON output, PII-safe
# ---------------------------------------------------------------------------

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

log = structlog.get_logger("hr-ai")

# ---------------------------------------------------------------------------
# OpenTelemetry — optional, graceful fallback if SDK not installed
# ---------------------------------------------------------------------------

_OTEL_ENABLED = False
_tracer = None

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

    _otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector-service:4317")
    _provider = TracerProvider()
    _exporter = OTLPSpanExporter(endpoint=_otel_endpoint, insecure=True)
    _provider.add_span_processor(BatchSpanProcessor(_exporter))
    trace.set_tracer_provider(_provider)
    _tracer = trace.get_tracer("hr-ai-agents")
    _OTEL_ENABLED = True
except Exception:
    pass  # OTel not installed or endpoint unreachable — degrade gracefully


@contextmanager
def span(name: str, **attrs) -> Generator:
    """Context manager: creates OTel span if available, otherwise no-op."""
    if _OTEL_ENABLED and _tracer:
        with _tracer.start_as_current_span(name) as s:
            for k, v in attrs.items():
                s.set_attribute(k, str(v))
            yield s
    else:
        yield None


# ---------------------------------------------------------------------------
# Structured log helpers — used by routers, workers, LLM client
# ---------------------------------------------------------------------------

def log_agent_call(
    agent_name: str,
    employee_id: str,
    job_id: str,
    latency_ms: float,
    status: str = "ok",
) -> None:
    """Log one agent invocation. Never logs salary amounts or raw PII."""
    log.info(
        "agent_call",
        agent=agent_name,
        job_id=job_id,
        # pseudonymize employee_id so we can correlate without raw PII in logs
        employee_ref=f"EMP-{hash(employee_id) % 9999:04d}",
        latency_ms=round(latency_ms, 1),
        status=status,
    )


def log_llm_call(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: float,
    cached: bool = False,
) -> None:
    log.info(
        "llm_call",
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        latency_ms=round(latency_ms, 1),
        cached=cached,
    )


def log_tool_call(
    tool_name: str,
    latency_ms: float,
    success: bool = True,
    error: Optional[str] = None,
) -> None:
    log.info(
        "tool_call",
        tool=tool_name,
        latency_ms=round(latency_ms, 1),
        success=success,
        error=error,
    )


def log_cache_event(hit: bool, key_prefix: str) -> None:
    log.debug("cache_event", hit=hit, key_prefix=key_prefix)


# ---------------------------------------------------------------------------
# Timing helper
# ---------------------------------------------------------------------------

class Timer:
    """Simple elapsed-ms timer."""
    def __init__(self):
        self._start = time.monotonic()

    def elapsed_ms(self) -> float:
        return (time.monotonic() - self._start) * 1000
