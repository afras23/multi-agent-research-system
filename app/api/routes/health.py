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
from app.config import Settings
from app.core.logging_config import get_correlation_id
from app.dependencies import get_db, get_settings, get_task_repository
from app.repositories.task_repo import TaskRepository, utc_start_of_today

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, Any]:
    """Liveness probe."""
    started = time.perf_counter()
    correlation_id = get_correlation_id() or "unknown"
    payload = success_envelope(
        data={"status": "healthy"},
        correlation_id=correlation_id,
        started_at=started,
    )
    return payload.model_dump()


@router.get("/health/ready")
async def health_ready(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Readiness probe including database connectivity."""
    started = time.perf_counter()
    correlation_id = get_correlation_id() or "unknown"
    await db.execute(text("SELECT 1"))
    payload = success_envelope(
        data={"status": "ready", "database": "ok"},
        correlation_id=correlation_id,
        started_at=started,
    )
    return payload.model_dump()


@router.get("/metrics")
async def metrics(
    task_repo: TaskRepository = Depends(get_task_repository),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Operational metrics derived from persisted tasks (UTC day window)."""
    started = time.perf_counter()
    correlation_id = get_correlation_id() or "unknown"
    day_start = utc_start_of_today()
    agg = await task_repo.aggregate_operational_metrics(
        utc_day_start=day_start,
        cost_limit_usd=settings.max_daily_cost_usd,
    )
    payload = success_envelope(
        data=agg,
        correlation_id=correlation_id,
        started_at=started,
    )
    return payload.model_dump()
