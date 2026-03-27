"""
Shared API response envelope models.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ResponseMetadata(BaseModel):
    """Standard metadata block for successful responses."""

    request_id: str = Field(description="Correlation identifier for the request")
    timestamp: str = Field(description="UTC ISO-8601 timestamp")
    processing_time_ms: float = Field(ge=0.0, description="Server processing time in milliseconds")


class SuccessEnvelope(BaseModel):
    """Portfolio-standard success payload wrapper."""

    status: Literal["success"] = "success"
    data: dict[str, Any]
    metadata: ResponseMetadata


class ErrorDetail(BaseModel):
    """Structured error body."""

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    """Portfolio-standard error payload wrapper."""

    status: Literal["error"] = "error"
    error: ErrorDetail
    metadata: ResponseMetadata


def utc_timestamp() -> str:
    """Return current UTC time as an ISO-8601 string."""
    return datetime.now(UTC).isoformat()


def success_envelope(
    *,
    data: dict[str, Any],
    request_id: str,
    started_at: float,
) -> SuccessEnvelope:
    """Build a success envelope with timing metadata."""
    import time

    elapsed_ms = (time.perf_counter() - started_at) * 1000.0
    return SuccessEnvelope(
        data=data,
        metadata=ResponseMetadata(
            request_id=request_id,
            timestamp=utc_timestamp(),
            processing_time_ms=elapsed_ms,
        ),
    )
