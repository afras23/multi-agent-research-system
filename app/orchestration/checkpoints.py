"""
Human checkpoint handling and state persistence hooks.
"""

from __future__ import annotations

import logging
from uuid import UUID

from app.orchestration.state import ResearchState, utc_now
from app.repositories.task_repo import TaskRepository

logger = logging.getLogger(__name__)


class CheckpointManager:
    """Coordinates human approval gates with persisted orchestration state."""

    def __init__(self, task_repo: TaskRepository | None = None) -> None:
        self._task_repo = task_repo

    def _repo(self) -> TaskRepository:
        """Return the bound repository or the request-scoped context repository."""
        if self._task_repo is not None:
            return self._task_repo
        from app.core.task_repo_context import get_current_task_repo

        return get_current_task_repo()

    async def refresh(self, task_id: UUID) -> ResearchState:
        """Load the latest persisted state for a task."""
        return await self._repo().load_state(task_id)

    async def pause_for_approval(self, state: ResearchState) -> ResearchState:
        """Set checkpoint to pending and persist."""
        state.checkpoint_status = "pending"
        state.status = "awaiting_approval"
        state.updated_at = utc_now()
        await self._repo().save_state(state.task_id, state)
        logger.info(
            "Checkpoint awaiting human approval",
            extra={"task_id": str(state.task_id)},
        )
        return state

    async def process_approval(
        self,
        task_id: UUID,
        approved: bool,
        reviewer: str,
        *,
        rejection_reason: str | None = None,
    ) -> ResearchState:
        """Apply an approval decision and persist."""
        state = await self._repo().load_state(task_id)
        state.checkpoint_reviewer = reviewer
        state.updated_at = utc_now()
        if approved:
            state.checkpoint_status = "approved"
            state.status = "writing"
            state.rejection_reason = None
        else:
            state.checkpoint_status = "rejected"
            state.status = "rejected"
            state.rejection_reason = rejection_reason
        await self._repo().save_state(task_id, state)
        logger.info(
            "Checkpoint decision recorded",
            extra={
                "task_id": str(task_id),
                "approved": approved,
                "reviewer": reviewer,
            },
        )
        return state

    async def save_research_state(self, state: ResearchState) -> None:
        """Persist the full orchestration snapshot for a task."""
        await self._repo().save_state(state.task_id, state)
