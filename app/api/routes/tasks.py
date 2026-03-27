"""
Task inspection routes (stub).
"""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from fastapi import APIRouter

from app.api.schemas import success_envelope
from app.core.logging_config import get_correlation_id

router = APIRouter(tags=["tasks"])


@router.get("/tasks/{task_id}")
async def get_task_stub(task_id: UUID) -> dict[str, Any]:
    """Placeholder endpoint for fetching a single task."""
    started = time.perf_counter()
    request_id = get_correlation_id() or "unknown"
    return success_envelope(
        data={"task_id": str(task_id), "status": "stub"},
        request_id=request_id,
        started_at=started,
    ).model_dump()
