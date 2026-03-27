"""
Research task persistence repository.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import TaskNotFoundError
from app.models.research_task import ResearchTask
from app.orchestration.state import ResearchState


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

    async def save_state(self, task_id: UUID, state: ResearchState) -> None:
        """Serialise orchestration state to ``state_json`` and update status."""
        row = await self.get_by_id(task_id)
        if row is None:
            raise TaskNotFoundError(str(task_id))
        row.state_json = state.model_dump(mode="json")
        row.status = state.status
        total_cost = sum(entry.total_cost_usd for entry in state.agent_costs.values())
        row.total_cost_usd = total_cost
        await self._session.flush()

    async def load_state(self, task_id: UUID) -> ResearchState:
        """Load and deserialise ``ResearchState`` from persisted JSON."""
        row = await self.get_by_id(task_id)
        if row is None:
            raise TaskNotFoundError(str(task_id))
        return ResearchState.model_validate(row.state_json)

    async def update_status(self, task_id: UUID, status: str) -> None:
        """Update only the task status column."""
        row = await self.get_by_id(task_id)
        if row is None:
            raise TaskNotFoundError(str(task_id))
        row.status = status
        await self._session.flush()

    async def list_tasks(
        self,
        *,
        page: int,
        page_size: int,
        status_filter: str | None = None,
    ) -> tuple[list[ResearchTask], int]:
        """Return a page of tasks and total count (for pagination)."""
        page = max(page, 1)
        page_size = max(page_size, 1)
        base = select(ResearchTask)
        count_stmt = select(func.count()).select_from(ResearchTask)
        if status_filter is not None:
            base = base.where(ResearchTask.status == status_filter)
            count_stmt = select(func.count()).select_from(ResearchTask).where(
                ResearchTask.status == status_filter,
            )
        total = int((await self._session.execute(count_stmt)).scalar_one())
        offset = (page - 1) * page_size
        stmt = base.order_by(ResearchTask.created_at.desc()).offset(offset).limit(page_size)
        rows = (await self._session.execute(stmt)).scalars().all()
        return list(rows), total
