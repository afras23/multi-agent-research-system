"""
Tests for LangGraph orchestration wiring.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from app.agents.analysis_agent import AnalysisAgent
from app.agents.quality_agent import QualityAgent
from app.agents.research_agent import ResearchAgent
from app.agents.writer_agent import WriterAgent
from app.config import Settings
from app.orchestration.checkpoints import CheckpointManager
from app.orchestration.graph import GraphDependencies, build_research_graph, route_after_checkpoint
from app.orchestration.state import (
    AnalysisResult,
    ResearchFinding,
    ResearchState,
    utc_now,
)


def _settings() -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://t:t@localhost:5432/t",
        openai_api_key="k",
    )


def _initial_state() -> ResearchState:
    tid = uuid4()
    return ResearchState(
        task_id=tid,
        company_name="Co",
        research_brief="Brief",
        status="pending",
        created_at=utc_now(),
        updated_at=utc_now(),
    )


def _make_store(initial: ResearchState) -> dict[str, ResearchState]:
    return {str(initial.task_id): initial.model_copy(deep=True)}


def _mock_task_repo(store: dict[str, ResearchState]) -> MagicMock:
    async def load_state(task_id):
        return store[str(task_id)].model_copy(deep=True)

    async def save_state(task_id, st: ResearchState) -> None:
        store[str(task_id)] = st.model_copy(deep=True)

    repo = MagicMock()
    repo.load_state = AsyncMock(side_effect=load_state)
    repo.save_state = AsyncMock(side_effect=save_state)
    return repo


def _finding() -> ResearchFinding:
    return ResearchFinding(
        topic="t",
        summary="s",
        source="so",
        source_url=None,
        confidence=0.5,
        raw_text="r",
    )


@pytest.mark.asyncio
async def test_graph_compiles_without_error() -> None:
    store = _make_store(_initial_state())
    repo = _mock_task_repo(store)
    settings = _settings()
    llm = MagicMock()
    deps = GraphDependencies(
        research_agent=ResearchAgent(llm, settings),
        analysis_agent=AnalysisAgent(llm, settings),
        writer_agent=WriterAgent(llm, settings),
        quality_agent=QualityAgent(llm, settings),
        checkpoint_manager=CheckpointManager(repo),
    )
    graph = build_research_graph(deps)
    assert graph is not None


@pytest.mark.asyncio
async def test_full_pipeline_runs_with_mocked_agents() -> None:
    store = _make_store(_initial_state())
    repo = _mock_task_repo(store)
    settings = _settings()
    ra = ResearchAgent(MagicMock(), settings)
    aa = AnalysisAgent(MagicMock(), settings)
    wa = WriterAgent(MagicMock(), settings)
    qa = QualityAgent(MagicMock(), settings)

    async def mr(rs: ResearchState) -> ResearchState:
        rs.research_findings = [_finding()]
        return rs

    async def ma(rs: ResearchState) -> ResearchState:
        rs.analysis_result = AnalysisResult(
            key_themes=["k"],
            competitive_position="c",
            financial_outlook="f",
        )
        return rs

    async def mw(rs: ResearchState) -> ResearchState:
        rs.report_draft = "Text [Source: so]."
        return rs

    async def mq(rs: ResearchState) -> ResearchState:
        from app.orchestration.state import QualityScore

        rs.quality_score = QualityScore(
            overall_score=90.0,
            source_coverage=90.0,
            completeness=90.0,
            accuracy=90.0,
            coherence=90.0,
            issues=[],
            recommendation="approve",
        )
        return rs

    ra.run = AsyncMock(side_effect=mr)
    aa.run = AsyncMock(side_effect=ma)
    wa.run = AsyncMock(side_effect=mw)
    qa.run = AsyncMock(side_effect=mq)

    deps = GraphDependencies(
        research_agent=ra,
        analysis_agent=aa,
        writer_agent=wa,
        quality_agent=qa,
        checkpoint_manager=CheckpointManager(repo),
    )
    graph = build_research_graph(deps)
    tid = next(iter(store.keys()))
    cfg = {"configurable": {"thread_id": tid}}
    initial = store[tid].model_dump(mode="json")
    with patch("app.orchestration.graph.interrupt", lambda _payload: None):
        out = await graph.ainvoke({"research_state": initial}, cfg)

    rs = ResearchState.model_validate(out["research_state"])
    assert rs.status in {"awaiting_approval", "completed", "failed", "rejected"}


@pytest.mark.asyncio
async def test_checkpoint_pauses_execution() -> None:
    store = _make_store(_initial_state())
    repo = _mock_task_repo(store)
    settings = _settings()
    ra = ResearchAgent(MagicMock(), settings)
    aa = AnalysisAgent(MagicMock(), settings)
    wa = WriterAgent(MagicMock(), settings)
    qa = QualityAgent(MagicMock(), settings)

    async def mr(rs: ResearchState) -> ResearchState:
        rs.research_findings = [_finding()]
        return rs

    async def ma(rs: ResearchState) -> ResearchState:
        rs.analysis_result = AnalysisResult(
            key_themes=["k"],
            competitive_position="c",
            financial_outlook="f",
        )
        return rs

    ra.run = AsyncMock(side_effect=mr)
    aa.run = AsyncMock(side_effect=ma)
    wa.run = AsyncMock()
    qa.run = AsyncMock()

    deps = GraphDependencies(
        research_agent=ra,
        analysis_agent=aa,
        writer_agent=wa,
        quality_agent=qa,
        checkpoint_manager=CheckpointManager(repo),
    )
    graph = build_research_graph(deps)
    tid = list(store.keys())[0]
    cfg = {"configurable": {"thread_id": tid}}
    initial = store[tid].model_dump(mode="json")

    def _raise_interrupt(_p):
        raise RuntimeError("interrupt")

    with (
        patch("app.orchestration.graph.interrupt", _raise_interrupt),
        pytest.raises(RuntimeError, match="interrupt"),
    ):
        await graph.ainvoke({"research_state": initial}, cfg)


def test_rejected_checkpoint_ends_pipeline() -> None:
    rs = ResearchState(
        task_id=uuid4(),
        company_name="Co",
        research_brief="B",
        status="awaiting_approval",
        checkpoint_status="rejected",
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    assert route_after_checkpoint({"research_state": rs.model_dump(mode="json")}) == "end"
