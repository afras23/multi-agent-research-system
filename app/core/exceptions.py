"""
Application exception hierarchy.

Maps domain failures to HTTP-friendly codes and stable error_code values for
clients and observability.
"""

from __future__ import annotations

from typing import Any


class BaseAppError(Exception):
    """Base error with HTTP status, machine code, and structured context."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 500,
        error_code: str = "INTERNAL_ERROR",
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.context = context or {}


class AgentError(BaseAppError):
    """An agent step failed after retries or validation."""

    def __init__(self, agent_name: str, detail: str) -> None:
        super().__init__(
            message=f"Agent {agent_name} failed: {detail}",
            status_code=500,
            error_code="AGENT_FAILED",
            context={"agent_name": agent_name, "detail": detail},
        )
        self.agent_name = agent_name


class AgentTimeoutError(BaseAppError):
    """An agent exceeded its execution time budget."""

    def __init__(self, agent_name: str) -> None:
        super().__init__(
            message=f"Agent {agent_name} timed out",
            status_code=504,
            error_code="AGENT_TIMEOUT",
            context={"agent_name": agent_name},
        )
        self.agent_name = agent_name


class OrchestrationError(BaseAppError):
    """The LangGraph orchestration layer failed."""

    def __init__(self, detail: str) -> None:
        super().__init__(
            message=f"Orchestration failed: {detail}",
            status_code=500,
            error_code="ORCHESTRATION_FAILED",
            context={"detail": detail},
        )


class CheckpointError(BaseAppError):
    """Checkpoint persistence or restore failed."""

    def __init__(self, detail: str) -> None:
        super().__init__(
            message=f"Checkpoint error: {detail}",
            status_code=500,
            error_code="CHECKPOINT_FAILED",
            context={"detail": detail},
        )


class CostLimitExceeded(BaseAppError):
    """Daily or per-request LLM cost limit was exceeded."""

    def __init__(self, current_cost_usd: float, limit_usd: float, *, scope: str) -> None:
        super().__init__(
            message="Cost limit exceeded",
            status_code=503,
            error_code="COST_LIMIT",
            context={
                "current_cost_usd": current_cost_usd,
                "limit_usd": limit_usd,
                "scope": scope,
            },
        )


class RateLimitExceeded(BaseAppError):
    """Upstream provider rate limit."""

    def __init__(self, retry_after_seconds: float | None) -> None:
        super().__init__(
            message="Upstream rate limit exceeded",
            status_code=429,
            error_code="RATE_LIMITED",
            context={"retry_after_seconds": retry_after_seconds},
        )


class RetryableError(BaseAppError):
    """Transient failure that may succeed on retry."""

    def __init__(self, detail: str) -> None:
        super().__init__(
            message=detail,
            status_code=503,
            error_code="RETRYABLE",
            context={"detail": detail},
        )


class TaskNotFoundError(BaseAppError):
    """Requested research task does not exist."""

    def __init__(self, task_id: str) -> None:
        super().__init__(
            message="Research task not found",
            status_code=404,
            error_code="TASK_NOT_FOUND",
            context={"task_id": task_id},
        )


class ReportNotReadyError(BaseAppError):
    """Report is not available yet (pipeline still running)."""

    def __init__(self, task_id: str, *, detail: str) -> None:
        super().__init__(
            message=detail,
            status_code=409,
            error_code="REPORT_NOT_READY",
            context={"task_id": task_id},
        )


class ReportNotFoundError(BaseAppError):
    """No final report exists for this task (failed, rejected, or not finished)."""

    def __init__(self, task_id: str) -> None:
        super().__init__(
            message="Report not available for this task",
            status_code=404,
            error_code="REPORT_NOT_FOUND",
            context={"task_id": task_id},
        )
