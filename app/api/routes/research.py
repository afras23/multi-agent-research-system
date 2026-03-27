"""
Research task routes (stub until Phase 3 graph wiring).
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends

from app.api.schemas import success_envelope
from app.core.logging_config import get_correlation_id
from app.dependencies import get_research_service
from app.services.research_service import ResearchService

router = APIRouter(prefix="/research", tags=["research"])


@router.post("/tasks")
async def create_research_task_stub(
    service: ResearchService = Depends(get_research_service),
) -> dict[str, Any]:
    """Placeholder endpoint for enqueueing research work."""
    started = time.perf_counter()
    request_id = get_correlation_id() or "unknown"
    description = await service.describe_stub()
    return success_envelope(
        data={"status": "stub", "service": description},
        request_id=request_id,
        started_at=started,
    ).model_dump()
