"""
Research task persistence repository.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
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
        task_id: UUID | None = None,
        company_name: str,
        research_brief: str,
        status: str,
        state_json: dict[str, object],
    ) -> ResearchTask:
        """Insert a minimal task row for orchestration bootstrap (Phase 1 stub)."""
        row = ResearchTask(
            id=task_id or uuid4(),
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
        row.total_latency_ms = state.total_pipeline_latency_ms
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

    async def aggregate_operational_metrics(
        self,
        *,
        utc_day_start: datetime,
        cost_limit_usd: float,
    ) -> dict[str, Any]:
        """
        Aggregate dashboard metrics for tasks created on or after ``utc_day_start`` (UTC).

        Args:
            utc_day_start: Inclusive start of the reporting window (UTC).
            cost_limit_usd: Configured daily cost cap (for response payload).

        Returns:
            Metrics fields for ``/api/v1/metrics``.
        """
        base = select(ResearchTask).where(ResearchTask.created_at >= utc_day_start)
        rows = (await self._session.execute(base)).scalars().all()

        tasks_today = len(rows)
        tasks_completed = sum(1 for r in rows if r.status == "completed")
        tasks_failed = sum(1 for r in rows if r.status == "failed")

        completed_latencies = [r.total_latency_ms for r in rows if r.status == "completed"]
        avg_latency_ms = (
            sum(completed_latencies) / len(completed_latencies) if completed_latencies else 0.0
        )

        cost_today_usd = sum(r.total_cost_usd for r in rows)

        agent_keys = (
            "research_agent",
            "analysis_agent",
            "writer_agent",
            "quality_agent",
        )
        cost_per_agent: dict[str, float] = {k: 0.0 for k in agent_keys}
        quality_scores: list[float] = []
        for row in rows:
            payload = row.state_json or {}
            costs = payload.get("agent_costs") or {}
            if isinstance(costs, dict):
                for key in agent_keys:
                    entry = costs.get(key)
                    if isinstance(entry, dict) and "total_cost_usd" in entry:
                        cost_per_agent[key] += float(entry["total_cost_usd"])
            qs = payload.get("quality_score")
            if isinstance(qs, dict) and "overall_score" in qs:
                quality_scores.append(float(qs["overall_score"]))

        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0

        return {
            "tasks_today": tasks_today,
            "tasks_completed": tasks_completed,
            "tasks_failed": tasks_failed,
            "avg_latency_ms": round(avg_latency_ms, 2),
            "cost_today_usd": round(cost_today_usd, 4),
            "cost_limit_usd": cost_limit_usd,
            "cost_per_agent": {k: round(v, 4) for k, v in cost_per_agent.items()},
            "avg_quality_score": round(avg_quality, 2),
        }


def utc_start_of_today() -> datetime:
    """Return UTC midnight for the current calendar day."""
    now = datetime.now(UTC)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)
