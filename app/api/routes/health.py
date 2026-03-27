"""
Health, readiness, and metrics routes.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import success_envelope
from app.core.logging_config import get_correlation_id
from app.dependencies import get_db, get_llm_client
from app.services.ai.client import LlmClient

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, Any]:
    """Liveness probe."""
    started = time.perf_counter()
    request_id = get_correlation_id() or "unknown"
    payload = success_envelope(
        data={"status": "healthy"},
        request_id=request_id,
        started_at=started,
    )
    return payload.model_dump()


@router.get("/health/ready")
async def health_ready(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Readiness probe including database connectivity."""
    started = time.perf_counter()
    request_id = get_correlation_id() or "unknown"
    await db.execute(text("SELECT 1"))
    payload = success_envelope(
        data={"status": "ready", "database": "ok"},
        request_id=request_id,
        started_at=started,
    )
    return payload.model_dump()


@router.get("/metrics")
async def metrics(llm_client: LlmClient = Depends(get_llm_client)) -> dict[str, Any]:
    """Operational metrics stub (expanded in later phases)."""
    started = time.perf_counter()
    request_id = get_correlation_id() or "unknown"
    payload = success_envelope(
        data={
            "daily_cost_usd": llm_client.daily_cost_usd,
            "cost_limit_usd": llm_client.max_daily_cost_usd,
        },
        request_id=request_id,
        started_at=started,
    )
    return payload.model_dump()
