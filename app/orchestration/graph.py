"""
LangGraph orchestration for the multi-agent research pipeline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from typing_extensions import TypedDict

from app.agents.analysis_agent import AnalysisAgent
from app.agents.quality_agent import QualityAgent
from app.agents.research_agent import ResearchAgent
from app.agents.writer_agent import WriterAgent
from app.core.exceptions import AgentError, AgentTimeoutError
from app.orchestration.checkpoints import CheckpointManager
from app.orchestration.state import ResearchState, utc_now

logger = logging.getLogger(__name__)


def merge_research_state(
    left: dict[str, Any] | None,
    right: dict[str, Any] | None,
) -> dict[str, Any]:
    """Reducer: latest node output replaces orchestration state."""
    if right is not None:
        return right
    return left or {}


class ResearchGraphState(TypedDict):
    """LangGraph carrier for serialised ``ResearchState``."""

    research_state: Annotated[dict[str, Any], merge_research_state]


@dataclass(frozen=True, slots=True)
class GraphDependencies:
    """Injectable agents and checkpoint manager for graph construction."""

    research_agent: ResearchAgent
    analysis_agent: AnalysisAgent
    writer_agent: WriterAgent
    quality_agent: QualityAgent
    checkpoint_manager: CheckpointManager


def _serialise(rs: ResearchState) -> dict[str, Any]:
    return rs.model_dump(mode="json")


def route_if_failed(state: ResearchGraphState) -> Literal["next", "end"]:
    """Route to the next agent or terminate after a hard failure."""
    rs = ResearchState.model_validate(state["research_state"])
    if rs.status == "failed":
        return "end"
    return "next"


def route_after_checkpoint(state: ResearchGraphState) -> Literal["writing", "end"]:
    """Route after the human gate."""
    rs = ResearchState.model_validate(state["research_state"])
    if rs.status == "failed":
        return "end"
    if rs.checkpoint_status == "approved":
        return "writing"
    return "end"


def build_research_graph(deps: GraphDependencies) -> Any:
    """
    Compile the LangGraph workflow for research → analysis → checkpoint → write → quality.

    Returns:
        A compiled LangGraph runnable with an in-memory checkpointer.
    """

    async def research_node(state: ResearchGraphState) -> ResearchGraphState:
        rs = ResearchState.model_validate(state["research_state"])
        try:
            rs = await deps.research_agent.run(rs)
        except AgentTimeoutError as exc:
            rs.status = "failed"
            rs.failure_reason = f"Agent {exc.agent_name} timed out"
            rs.updated_at = utc_now()
        except AgentError as exc:
            rs.status = "failed"
            rs.failure_reason = exc.message
            rs.updated_at = utc_now()
        return {"research_state": _serialise(rs)}

    async def analysis_node(state: ResearchGraphState) -> ResearchGraphState:
        rs = ResearchState.model_validate(state["research_state"])
        try:
            rs = await deps.analysis_agent.run(rs)
        except AgentTimeoutError as exc:
            rs.status = "failed"
            rs.failure_reason = f"Agent {exc.agent_name} timed out"
            rs.updated_at = utc_now()
        except AgentError as exc:
            rs.status = "failed"
            rs.failure_reason = exc.message
            rs.updated_at = utc_now()
        return {"research_state": _serialise(rs)}

    async def checkpoint_node(state: ResearchGraphState) -> ResearchGraphState:
        rs = ResearchState.model_validate(state["research_state"])
        tid = rs.task_id
        persisted = await deps.checkpoint_manager.refresh(tid)
        if persisted.checkpoint_status == "rejected":
            rs = persisted
            rs.status = "rejected"
            rs.updated_at = utc_now()
            await deps.checkpoint_manager.save_research_state(rs)
            return {"research_state": _serialise(rs)}
        if persisted.checkpoint_status == "approved":
            rs = persisted
            rs.status = "writing"
            rs.updated_at = utc_now()
            await deps.checkpoint_manager.save_research_state(rs)
            return {"research_state": _serialise(rs)}
        if rs.checkpoint_status == "not_reached":
            rs = await deps.checkpoint_manager.pause_for_approval(rs)
        if rs.checkpoint_status == "pending":
            interrupt({"task_id": str(rs.task_id), "status": "awaiting_approval"})
        return {"research_state": _serialise(rs)}

    async def writing_node(state: ResearchGraphState) -> ResearchGraphState:
        rs = ResearchState.model_validate(state["research_state"])
        try:
            rs = await deps.writer_agent.run(rs)
        except AgentTimeoutError as exc:
            rs.status = "failed"
            rs.failure_reason = f"Agent {exc.agent_name} timed out"
            rs.updated_at = utc_now()
        except AgentError as exc:
            rs.status = "failed"
            rs.failure_reason = exc.message
            rs.updated_at = utc_now()
        return {"research_state": _serialise(rs)}

    async def quality_node(state: ResearchGraphState) -> ResearchGraphState:
        rs = ResearchState.model_validate(state["research_state"])
        try:
            rs = await deps.quality_agent.run(rs)
            rs.status = "completed"
            rs.updated_at = utc_now()
        except AgentTimeoutError as exc:
            rs.status = "failed"
            rs.failure_reason = f"Agent {exc.agent_name} timed out"
            rs.updated_at = utc_now()
        except AgentError as exc:
            rs.status = "failed"
            rs.failure_reason = exc.message
            rs.updated_at = utc_now()
        return {"research_state": _serialise(rs)}

    builder = StateGraph(ResearchGraphState)
    builder.add_node("research", research_node)
    builder.add_node("analysis", analysis_node)
    builder.add_node("checkpoint", checkpoint_node)
    builder.add_node("writing", writing_node)
    builder.add_node("quality", quality_node)

    builder.add_edge(START, "research")

    builder.add_conditional_edges(
        "research",
        route_if_failed,
        {"next": "analysis", "end": END},
    )

    builder.add_conditional_edges(
        "analysis",
        route_if_failed,
        {"next": "checkpoint", "end": END},
    )

    builder.add_conditional_edges(
        "checkpoint",
        route_after_checkpoint,
        {"writing": "writing", "end": END},
    )

    builder.add_conditional_edges(
        "writing",
        route_if_failed,
        {"next": "quality", "end": END},
    )

    builder.add_edge("quality", END)

    compiled = builder.compile(checkpointer=MemorySaver())
    logger.info("Research LangGraph compiled", extra={"nodes": 5})
    return compiled
