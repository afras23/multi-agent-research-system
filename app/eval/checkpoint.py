"""
Checkpoint behaviour for offline evaluation (no human interrupt).
"""

from __future__ import annotations

import logging

from app.orchestration.checkpoints import CheckpointManager
from app.orchestration.state import ResearchState, utc_now
from app.repositories.task_repo import TaskRepository

logger = logging.getLogger(__name__)


class EvaluationCheckpointManager(CheckpointManager):
    """
    Auto-approves the human gate so the LangGraph run can finish in one ``ainvoke``.

    Production uses :class:`CheckpointManager` with real interrupts; evaluation
    records a synthetic reviewer and routes straight to writing.
    """

    def __init__(self, task_repo: TaskRepository | None = None) -> None:
        super().__init__(task_repo)

    async def pause_for_approval(self, state: ResearchState) -> ResearchState:
        """Mark checkpoint approved and advance status to writing without blocking."""
        state.checkpoint_status = "approved"
        state.status = "writing"
        state.checkpoint_reviewer = "evaluation_harness"
        state.updated_at = utc_now()
        await self._repo().save_state(state.task_id, state)
        logger.info(
            "Evaluation checkpoint auto-approved",
            extra={"task_id": str(state.task_id)},
        )
        return state
