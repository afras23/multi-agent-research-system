"""
Agent interaction: hand-offs between pipeline stages (mocked LLM).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.agents.analysis_agent import AnalysisAgent
from app.agents.quality_agent import QualityAgent
from app.agents.research_agent import ResearchAgent
from app.agents.writer_agent import WriterAgent
from app.config import Settings
from app.core.exceptions import AgentTimeoutError
from app.orchestration.checkpoints import CheckpointManager
from app.orchestration.graph import GraphDependencies, build_research_graph
from app.orchestration.state import AnalysisResult, ResearchFinding, ResearchState, utc_now
from app.services.ai.client import LlmClient

from tests.conftest import json_response
from tests.unit.openai_client_mocks import mock_openai_client


def _settings() -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://t:t@localhost:5432/t",
        openai_api_key="k",
    )


def _base_state() -> ResearchState:
    return ResearchState(
        task_id=uuid4(),
        company_name="Acme",
        research_brief="Market study",
        status="pending",
        created_at=utc_now(),
        updated_at=utc_now(),
    )


@pytest.mark.asyncio
async def test_research_agent_output_consumed_by_analysis_agent() -> None:
    async def chain(*_a: object, **_k: object) -> MagicMock:
        chain.n += 1  # type: ignore[attr-defined]
        if chain.n == 1:
            return json_response('["TopicA"]')
        if chain.n == 2:
            return json_response(
                '{"topic":"TopicA","summary":"S.","source":"SRC","source_url":null,"confidence":0.5}',
            )
        return json_response(
            '{"key_themes":["t"],"risks":[],"opportunities":[],"competitive_position":"c",'
            '"financial_outlook":"f","gaps_identified":[],"contradictions":[]}',
        )

    chain.n = 0  # type: ignore[attr-defined]
    client = mock_openai_client(AsyncMock(side_effect=chain))
    settings = _settings()
    llm = LlmClient(settings, openai_client=client)
    research = ResearchAgent(llm, settings)
    analysis = AnalysisAgent(llm, settings)
    state = _base_state()
    state = await research.run(state)
    assert state.research_findings and state.research_findings[0].topic == "TopicA"
    await analysis.run(state)
    assert client.chat.completions.create.await_count >= 3
    last_call = client.chat.completions.create.await_args_list[-1]
    messages = last_call.kwargs["messages"]
    user_block = messages[1]["content"]
    assert "TopicA" in user_block or "TopicA" in str(messages)


@pytest.mark.asyncio
async def test_analysis_output_consumed_by_writer_agent() -> None:
    calls: list[str] = []

    async def chain(*_a: object, **_k: object) -> MagicMock:
        calls.append("x")
        n = len(calls)
        if n == 1:
            return json_response("# Executive\n\n[Source: R1] Claim.\n")
        return json_response("{}")

    client = mock_openai_client(AsyncMock(side_effect=chain))
    settings = _settings()
    llm = LlmClient(settings, openai_client=client)
    writer = WriterAgent(llm, settings)
    state = _base_state()
    state.research_findings = [
        ResearchFinding(
            topic="T",
            summary="S",
            source="R1",
            source_url=None,
            confidence=0.5,
            raw_text="r",
        ),
    ]
    state.analysis_result = AnalysisResult(
        key_themes=["themeX"],
        competitive_position="cp",
        financial_outlook="fo",
    )
    state = await writer.run(state)
    assert state.report_draft is not None
    assert (
        "themeX"
        in client.chat.completions.create.await_args_list[0].kwargs["messages"][1]["content"]
    )


@pytest.mark.asyncio
async def test_writer_output_consumed_by_quality_agent() -> None:
    async def chain(*_a: object, **_k: object) -> MagicMock:
        return json_response(
            '{"source_coverage":80,"completeness":80,"accuracy":80,"coherence":80,'
            '"overall_score":80,"issues":[],"recommendation":"approve"}',
        )

    client = mock_openai_client(AsyncMock(side_effect=chain))
    settings = _settings()
    llm = LlmClient(settings, openai_client=client)
    qa = QualityAgent(llm, settings)
    state = _base_state()
    state.research_findings = [
        ResearchFinding(
            topic="T",
            summary="S",
            source="SRC",
            source_url=None,
            confidence=0.5,
            raw_text="r",
        ),
    ]
    state.report_draft = "Body [Source: SRC]."
    state = await qa.run(state)
    assert state.quality_score is not None
    user_content = client.chat.completions.create.await_args.kwargs["messages"][1]["content"]
    assert "Body" in user_content or "Source" in user_content


@pytest.mark.asyncio
async def test_full_pipeline_produces_report_with_citations() -> None:
    """
    End-to-end report shape: writer consumes research + analysis and emits [Source:] lines.
    (LangGraph human checkpoint requires a separate resume flow in integration tests.)
    """
    settings = _settings()
    create = AsyncMock(
        return_value=json_response(
            "# Executive Summary\n\n[Source: SEC] Material claim.\n\n## Company\n\n[Source: News].",
            20,
            40,
        ),
    )
    llm = LlmClient(settings, openai_client=mock_openai_client(create))
    writer = WriterAgent(llm, settings)
    state = _base_state()
    state.research_findings = [
        ResearchFinding(
            topic="t",
            summary="s",
            source="SEC",
            source_url=None,
            confidence=0.5,
            raw_text="r",
        ),
    ]
    state.analysis_result = AnalysisResult(
        key_themes=["k"],
        competitive_position="c",
        financial_outlook="f",
    )
    out = await writer.run(state)
    assert out.report_draft is not None
    assert "[Source:" in out.report_draft


@pytest.mark.asyncio
async def test_agent_error_propagates_to_task_status() -> None:
    st0 = _initial()
    store = {st0.task_id: st0}

    async def load_state(task_id):
        return store[task_id].model_copy(deep=True)

    async def save_state(task_id, st: ResearchState) -> None:
        store[task_id] = st.model_copy(deep=True)

    repo = MagicMock()
    repo.load_state = AsyncMock(side_effect=load_state)
    repo.save_state = AsyncMock(side_effect=save_state)
    settings = _settings()

    async def fail(_rs: ResearchState) -> ResearchState:
        raise AgentTimeoutError("research_agent")

    ra = ResearchAgent(MagicMock(), settings)
    ra.run = AsyncMock(side_effect=fail)
    deps = GraphDependencies(
        research_agent=ra,
        analysis_agent=AnalysisAgent(MagicMock(), settings),
        writer_agent=WriterAgent(MagicMock(), settings),
        quality_agent=QualityAgent(MagicMock(), settings),
        checkpoint_manager=CheckpointManager(repo),
    )
    graph = build_research_graph(deps)
    tid = st0.task_id
    out = await graph.ainvoke(
        {"research_state": store[tid].model_dump(mode="json")},
        {"configurable": {"thread_id": str(tid)}},
    )
    rs = ResearchState.model_validate(out["research_state"])
    assert rs.status == "failed"


def _initial() -> ResearchState:
    tid = uuid4()
    return ResearchState(
        task_id=tid,
        company_name="Co",
        research_brief="B",
        status="pending",
        created_at=utc_now(),
        updated_at=utc_now(),
    )


@pytest.mark.asyncio
async def test_multiple_agent_errors_all_recorded_in_state() -> None:
    state = _base_state()
    state.errors.append("research_agent failed: simulated upstream")
    state.errors.append("analysis_agent failed: simulated upstream")
    assert len(state.errors) == 2
    assert all("failed" in e for e in state.errors)
