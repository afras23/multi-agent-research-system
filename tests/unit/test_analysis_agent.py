"""
Tests for ``AnalysisAgent``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.agents.analysis_agent import AnalysisAgent
from app.config import Settings
from app.orchestration.state import ResearchFinding, ResearchState, utc_now
from app.services.ai.client import LlmClient

from tests.unit.openai_client_mocks import mock_openai_client


def _settings() -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://t:t@localhost:5432/t",
        openai_api_key="k",
    )


def _state_with_findings() -> ResearchState:
    return ResearchState(
        task_id=uuid4(),
        company_name="Acme",
        research_brief="Test",
        status="analyzing",
        research_findings=[
            ResearchFinding(
                topic="T1",
                summary="S1",
                source="SRC",
                source_url=None,
                confidence=0.8,
                raw_text="{}",
            ),
        ],
        created_at=utc_now(),
        updated_at=utc_now(),
    )


@pytest.mark.asyncio
async def test_synthesises_findings_into_analysis() -> None:
    payload = (
        '{"key_themes":["scale"],"risks":[{"description":"R","severity":"high","source":"T1"}],'
        '"opportunities":[{"description":"O","rationale":"X"}],'
        '"competitive_position":"Strong.","financial_outlook":"Stable.",'
        '"gaps_identified":[],"contradictions":[]}'
    )
    client = mock_openai_client(
        AsyncMock(
            return_value=MagicMock(
                choices=[MagicMock(message=MagicMock(content=payload))],
                usage=MagicMock(prompt_tokens=20, completion_tokens=40),
            ),
        ),
    )
    llm = LlmClient(_settings(), openai_client=client)
    agent = AnalysisAgent(llm, _settings())
    state = _state_with_findings()
    out = await agent.run(state)
    assert out.analysis_result is not None
    assert "scale" in out.analysis_result.key_themes


@pytest.mark.asyncio
async def test_identifies_gaps_in_research() -> None:
    payload = (
        '{"key_themes":[],"risks":[],"opportunities":[],"competitive_position":"?",'
        '"financial_outlook":"?","gaps_identified":["No primary data"],'
        '"contradictions":[]}'
    )
    client = mock_openai_client(
        AsyncMock(
            return_value=MagicMock(
                choices=[MagicMock(message=MagicMock(content=payload))],
                usage=MagicMock(prompt_tokens=10, completion_tokens=20),
            ),
        ),
    )
    llm = LlmClient(_settings(), openai_client=client)
    agent = AnalysisAgent(llm, _settings())
    state = _state_with_findings()
    out = await agent.run(state)
    assert out.analysis_result is not None
    assert "No primary data" in out.analysis_result.gaps_identified


@pytest.mark.asyncio
async def test_handles_contradictory_findings() -> None:
    payload = (
        '{"key_themes":["t"],"risks":[],"opportunities":[],"competitive_position":"?",'
        '"financial_outlook":"?","gaps_identified":[],"contradictions":["A vs B"]}'
    )
    client = mock_openai_client(
        AsyncMock(
            return_value=MagicMock(
                choices=[MagicMock(message=MagicMock(content=payload))],
                usage=MagicMock(prompt_tokens=10, completion_tokens=20),
            ),
        ),
    )
    llm = LlmClient(_settings(), openai_client=client)
    agent = AnalysisAgent(llm, _settings())
    state = _state_with_findings()
    out = await agent.run(state)
    assert out.analysis_result is not None
    assert "A vs B" in out.analysis_result.contradictions
