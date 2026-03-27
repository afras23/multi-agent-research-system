"""
Research orchestration service.

Coordinates repositories and the LLM client; full LangGraph wiring lands in
Phase 3.
"""

from __future__ import annotations

import logging
from uuid import UUID

from app.orchestration.state import ResearchState
from app.repositories.task_repo import TaskRepository
from app.services.ai.client import LlmClient

logger = logging.getLogger(__name__)


class ResearchService:
    """Application service for research task lifecycle (Phase 1 stub)."""

    def __init__(
        self,
        task_repo: TaskRepository,
        llm_client: LlmClient,
    ) -> None:
        self._tasks = task_repo
        self._llm = llm_client

    async def describe_stub(self) -> str:
        """Return a static description for health/diagnostics."""
        return "research_service_stub"

    async def persist_initial_state(self, state: ResearchState) -> UUID:
        """
        Persist a serialised snapshot for a new task (stub for later pipeline).

        Args:
            state: In-memory orchestration state.

        Returns:
            Database identifier for the created task row.
        """
        row = await self._tasks.create_placeholder(
            company_name=state.company_name,
            research_brief=state.research_brief,
            status=state.status,
            state_json=state.model_dump(mode="json"),
        )
        logger.info(
            "Persisted initial research task placeholder",
            extra={"task_id": str(row.id), "status": state.status},
        )
        return row.id
