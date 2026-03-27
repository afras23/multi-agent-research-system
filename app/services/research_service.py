"""
Research orchestration service.

Coordinates repositories, LangGraph, and the LLM client for HTTP API flows.
"""

from __future__ import annotations

import logging
import time
from typing import Any, cast
from uuid import UUID, uuid4

from langgraph.types import Command

from app.api.schemas.research import (
    AgentCostBreakdown,
    AgentMessageOut,
    ApprovalRequest,
    QualityScoreOut,
    RejectionRequest,
    ReportResponse,
    ResearchRequest,
    ResearchStateSummary,
    ResearchTaskDetail,
    ResearchTaskListItem,
    ResearchTaskListResponse,
    ResearchTaskResponse,
)
from app.core.exceptions import ReportNotFoundError, ReportNotReadyError, TaskNotFoundError
from app.core.task_repo_context import reset_current_task_repo, set_current_task_repo
from app.orchestration.checkpoints import CheckpointManager
from app.orchestration.state import (
    AgentCostEntry,
    AgentMessage,
    QualityScore,
    ResearchState,
    utc_now,
)
from app.repositories.message_repo import MessageRepository
from app.repositories.task_repo import TaskRepository

logger = logging.getLogger(__name__)

_ACTIVE_STATUSES = frozenset(
    {
        "pending",
        "researching",
        "analyzing",
        "awaiting_approval",
        "writing",
        "quality_check",
    },
)


def _cost_breakdown(costs: dict[str, AgentCostEntry]) -> dict[str, AgentCostBreakdown]:
    return {name: AgentCostBreakdown(**entry.model_dump()) for name, entry in costs.items()}


def _messages_out(rows: list[AgentMessage]) -> list[AgentMessageOut]:
    return [AgentMessageOut(**m.model_dump(exclude={"message_id"})) for m in rows]


def _state_summary(state: ResearchState) -> ResearchStateSummary:
    return ResearchStateSummary(
        findings_count=len(state.research_findings),
        has_analysis=state.analysis_result is not None,
        has_report_draft=bool(state.report_draft),
        has_quality_score=state.quality_score is not None,
        checkpoint_status=state.checkpoint_status,
    )


def _quality_out(score: QualityScore | None) -> QualityScoreOut | None:
    if score is None:
        return None
    return QualityScoreOut(
        overall_score=score.overall_score,
        source_coverage=score.source_coverage,
        completeness=score.completeness,
        accuracy=score.accuracy,
        coherence=score.coherence,
        recommendation=score.recommendation,
    )


class ResearchService:
    """Orchestrates a full research task from input to output."""

    def __init__(
        self,
        graph: Any,
        task_repo: TaskRepository,
        message_repo: MessageRepository,
    ) -> None:
        self._graph = graph
        self._tasks = task_repo
        self._messages = message_repo

    def _thread_config(self, task_id: UUID) -> dict[str, Any]:
        return {"configurable": {"thread_id": str(task_id)}}

    async def _run_graph(
        self,
        task_id: UUID,
        *,
        initial: dict[str, Any] | None,
        resume: bool,
    ) -> dict[str, Any]:
        token = set_current_task_repo(self._tasks)
        try:
            cfg = self._thread_config(task_id)
            if resume:
                out = await self._graph.ainvoke(Command(resume=True), cfg)
                return cast(dict[str, Any], out)
            if initial is None:
                msg = "initial payload required when resume is false"
                raise ValueError(msg)
            out = await self._graph.ainvoke(initial, cfg)
            return cast(dict[str, Any], out)
        finally:
            reset_current_task_repo(token)

    async def _persist_state_and_messages(self, task_id: UUID, state: ResearchState) -> None:
        await self._tasks.save_state(task_id, state)
        await self._messages.replace_task_messages(task_id, state.agent_messages)

    async def start_research(self, request: ResearchRequest) -> ResearchTaskResponse:
        """Create task, initialise state, run the graph until interrupt or completion."""
        task_id = uuid4()
        state = ResearchState(
            task_id=task_id,
            company_name=request.company_name,
            research_brief=request.research_brief,
            industry_context=request.industry_context,
            status="pending",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        await self._tasks.create_placeholder(
            task_id=task_id,
            company_name=state.company_name,
            research_brief=state.research_brief,
            status=state.status,
            state_json=state.model_dump(mode="json"),
        )
        t0 = time.monotonic()
        initial = {"research_state": state.model_dump(mode="json")}
        out = await self._run_graph(task_id, initial=initial, resume=False)
        rs = ResearchState.model_validate(out["research_state"])
        segment_ms = (time.monotonic() - t0) * 1000.0
        rs.total_pipeline_latency_ms = rs.total_pipeline_latency_ms + segment_ms
        await self._persist_state_and_messages(task_id, rs)
        logger.info(
            "Research segment finished",
            extra={
                "task_id": str(task_id),
                "status": rs.status,
                "latency_ms": segment_ms,
            },
        )
        return ResearchTaskResponse(task_id=task_id, status=rs.status)

    async def get_task(self, task_id: UUID) -> ResearchTaskDetail:
        """Return task detail with persisted messages and orchestration snapshot."""
        row = await self._tasks.get_by_id(task_id)
        if row is None:
            raise TaskNotFoundError(str(task_id))
        state = ResearchState.model_validate(row.state_json)
        msgs = await self._messages.get_messages(task_id)
        return ResearchTaskDetail(
            task_id=state.task_id,
            company_name=state.company_name,
            research_brief=state.research_brief,
            industry_context=state.industry_context,
            status=state.status,
            checkpoint_status=state.checkpoint_status,
            checkpoint_reviewer=state.checkpoint_reviewer,
            rejection_reason=state.rejection_reason,
            failure_reason=state.failure_reason,
            agent_costs=_cost_breakdown(state.agent_costs),
            agent_messages=_messages_out(msgs),
            errors=list(state.errors),
            state_summary=_state_summary(state),
            total_pipeline_latency_ms=state.total_pipeline_latency_ms,
            created_at=state.created_at,
            updated_at=state.updated_at,
        )

    async def approve_checkpoint(
        self,
        task_id: UUID,
        body: ApprovalRequest,
    ) -> ResearchTaskResponse:
        """Approve the human gate and resume the LangGraph run."""
        row = await self._tasks.get_by_id(task_id)
        if row is None:
            raise TaskNotFoundError(str(task_id))
        cm = CheckpointManager(self._tasks)
        await cm.process_approval(task_id, True, body.reviewer)
        prior = await self._tasks.load_state(task_id)
        t0 = time.monotonic()
        out = await self._run_graph(task_id, initial=None, resume=True)
        rs = ResearchState.model_validate(out["research_state"])
        segment_ms = (time.monotonic() - t0) * 1000.0
        rs.total_pipeline_latency_ms = prior.total_pipeline_latency_ms + segment_ms
        await self._persist_state_and_messages(task_id, rs)
        logger.info(
            "Checkpoint approved; pipeline resumed",
            extra={"task_id": str(task_id), "latency_ms": segment_ms},
        )
        return ResearchTaskResponse(task_id=task_id, status=rs.status)

    async def reject_checkpoint(
        self,
        task_id: UUID,
        body: RejectionRequest,
    ) -> ResearchTaskResponse:
        """Reject at the checkpoint and persist terminal state (no graph resume)."""
        row = await self._tasks.get_by_id(task_id)
        if row is None:
            raise TaskNotFoundError(str(task_id))
        cm = CheckpointManager(self._tasks)
        await cm.process_approval(
            task_id,
            False,
            body.reviewer,
            rejection_reason=body.reason,
        )
        state = await self._tasks.load_state(task_id)
        await self._messages.replace_task_messages(task_id, state.agent_messages)
        logger.info(
            "Checkpoint rejected",
            extra={"task_id": str(task_id), "reviewer": body.reviewer},
        )
        return ResearchTaskResponse(task_id=task_id, status=state.status)

    async def get_report(self, task_id: UUID) -> ReportResponse:
        """Return the final Markdown report for a completed task."""
        row = await self._tasks.get_by_id(task_id)
        if row is None:
            raise TaskNotFoundError(str(task_id))
        state = ResearchState.model_validate(row.state_json)
        if state.status == "completed":
            total = sum(entry.total_cost_usd for entry in state.agent_costs.values())
            return ReportResponse(
                task_id=state.task_id,
                report_markdown=state.report_draft or "",
                quality_score=_quality_out(state.quality_score),
                agent_costs=_cost_breakdown(state.agent_costs),
                total_cost_usd=round(total, 6),
            )
        if state.status in _ACTIVE_STATUSES:
            raise ReportNotReadyError(
                str(task_id),
                detail="Report is not ready; pipeline still in progress",
            )
        raise ReportNotFoundError(str(task_id))

    async def list_tasks(
        self,
        *,
        page: int,
        page_size: int,
        status_filter: str | None,
    ) -> ResearchTaskListResponse:
        """Paginated task index with optional status filter."""
        rows, total = await self._tasks.list_tasks(
            page=page,
            page_size=page_size,
            status_filter=status_filter,
        )
        items = [
            ResearchTaskListItem(
                task_id=r.id,
                company_name=r.company_name,
                status=r.status,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in rows
        ]
        return ResearchTaskListResponse(
            items=items,
            page=max(page, 1),
            page_size=max(page_size, 1),
            total=total,
        )
