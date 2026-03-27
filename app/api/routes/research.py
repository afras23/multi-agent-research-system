"""
Research task API — create, inspect, approve, reject, and fetch reports.
"""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import success_envelope
from app.api.schemas.research import (
    ApprovalRequest,
    RejectionRequest,
    ResearchRequest,
)
from app.core.logging_config import get_correlation_id
from app.dependencies import get_db, get_research_service
from app.services.research_service import ResearchService

router = APIRouter(prefix="/research", tags=["research"])


@router.post("", status_code=202)
async def create_research(
    body: ResearchRequest,
    service: ResearchService = Depends(get_research_service),
    session: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Create a task and run the graph until the checkpoint or completion."""
    started = time.perf_counter()
    correlation_id = get_correlation_id() or "unknown"
    result = await service.start_research(body)
    await session.commit()
    payload = success_envelope(
        data=result.model_dump(mode="json"),
        correlation_id=correlation_id,
        started_at=started,
    )
    return JSONResponse(status_code=202, content=payload.model_dump())


@router.get("/{task_id}/report", name="get_research_report")
async def get_research_report(
    task_id: UUID,
    service: ResearchService = Depends(get_research_service),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return the final Markdown report when the task completed successfully."""
    started = time.perf_counter()
    correlation_id = get_correlation_id() or "unknown"
    report = await service.get_report(task_id)
    await session.commit()
    return success_envelope(
        data=report.model_dump(mode="json"),
        correlation_id=correlation_id,
        started_at=started,
    ).model_dump()


@router.get("")
async def list_research_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None, description="Filter by task status"),
    service: ResearchService = Depends(get_research_service),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Paginated list of research tasks."""
    started = time.perf_counter()
    correlation_id = get_correlation_id() or "unknown"
    listing = await service.list_tasks(page=page, page_size=page_size, status_filter=status)
    await session.commit()
    return success_envelope(
        data=listing.model_dump(mode="json"),
        correlation_id=correlation_id,
        started_at=started,
    ).model_dump()


@router.get("/{task_id}")
async def get_research_task(
    task_id: UUID,
    service: ResearchService = Depends(get_research_service),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return orchestration snapshot and persisted agent messages."""
    started = time.perf_counter()
    correlation_id = get_correlation_id() or "unknown"
    detail = await service.get_task(task_id)
    await session.commit()
    return success_envelope(
        data=detail.model_dump(mode="json"),
        correlation_id=correlation_id,
        started_at=started,
    ).model_dump()


@router.post("/{task_id}/approve")
async def approve_research_checkpoint(
    task_id: UUID,
    body: ApprovalRequest,
    service: ResearchService = Depends(get_research_service),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Approve analysis and resume drafting."""
    started = time.perf_counter()
    correlation_id = get_correlation_id() or "unknown"
    result = await service.approve_checkpoint(task_id, body)
    await session.commit()
    return success_envelope(
        data=result.model_dump(mode="json"),
        correlation_id=correlation_id,
        started_at=started,
    ).model_dump()


@router.post("/{task_id}/reject")
async def reject_research_checkpoint(
    task_id: UUID,
    body: RejectionRequest,
    service: ResearchService = Depends(get_research_service),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Reject at the checkpoint and end the run."""
    started = time.perf_counter()
    correlation_id = get_correlation_id() or "unknown"
    result = await service.reject_checkpoint(task_id, body)
    await session.commit()
    return success_envelope(
        data=result.model_dump(mode="json"),
        correlation_id=correlation_id,
        started_at=started,
    ).model_dump()
