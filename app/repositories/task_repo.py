"""
Research task persistence repository.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.research_task import ResearchTask


class TaskRepository:
    """Data access for ``research_tasks`` rows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, task_id: UUID) -> ResearchTask | None:
        """Return a task by primary key, if present."""
        result = await self._session.execute(select(ResearchTask).where(ResearchTask.id == task_id))
        return result.scalar_one_or_none()

    async def create_placeholder(
        self,
        *,
        company_name: str,
        research_brief: str,
        status: str,
        state_json: dict[str, object],
    ) -> ResearchTask:
        """Insert a minimal task row for orchestration bootstrap (Phase 1 stub)."""
        row = ResearchTask(
            id=uuid4(),
            company_name=company_name,
            research_brief=research_brief,
            status=status,
            state_json=state_json,
        )
        self._session.add(row)
        await self._session.flush()
        return row
