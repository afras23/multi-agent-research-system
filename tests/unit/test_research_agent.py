"""
Tests for ``ResearchAgent``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.agents.research_agent import ResearchAgent
from app.config import Settings
from app.orchestration.state import ResearchState, utc_now
from app.services.ai.client import LlmClient

from tests.unit.openai_client_mocks import mock_openai_client


def _settings() -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://t:t@localhost:5432/t",
        openai_api_key="k",
    )


def _minimal_state() -> ResearchState:
    return ResearchState(
        task_id=uuid4(),
        company_name="Acme",
        research_brief="Market position",
        status="pending",
        created_at=utc_now(),
        updated_at=utc_now(),
    )


def _openai_chain_responses(*contents: str) -> MagicMock:
    responses = [
        MagicMock(
            choices=[MagicMock(message=MagicMock(content=c))],
            usage=MagicMock(prompt_tokens=10, completion_tokens=10),
        )
        for c in contents
    ]
    return mock_openai_client(AsyncMock(side_effect=responses))


@pytest.mark.asyncio
async def test_produces_findings_from_brief() -> None:
    areas_json = '["Competition", "Regulation"]'
    finding_json = (
        '{"topic":"Competition","summary":"Peers are active.","source":"Trade press",'
        '"source_url":null,"confidence":0.7}'
    )
    llm = LlmClient(
        _settings(),
        openai_client=_openai_chain_responses(areas_json, finding_json, finding_json),
    )
    agent = ResearchAgent(llm, _settings())
    state = _minimal_state()
    out = await agent.run(state)
    assert len(out.research_findings) == 2
    assert out.research_findings[0].topic == "Competition"


@pytest.mark.asyncio
async def test_tracks_cost_attribution() -> None:
    areas_json = '["One area"]'
    finding_json = (
        '{"topic":"One area","summary":"S.","source":"SRC","source_url":null,"confidence":0.5}'
    )
    llm = LlmClient(_settings(), openai_client=_openai_chain_responses(areas_json, finding_json))
    agent = ResearchAgent(llm, _settings())
    state = _minimal_state()
    out = await agent.run(state)
    assert "research_agent" in out.agent_costs
    assert out.agent_costs["research_agent"].total_cost_usd >= 0.0


@pytest.mark.asyncio
async def test_handles_empty_llm_response() -> None:
    empty = MagicMock(
        choices=[MagicMock(message=MagicMock(content=""))],
        usage=MagicMock(prompt_tokens=1, completion_tokens=0),
    )
    client = mock_openai_client(AsyncMock(side_effect=[empty, empty, empty, empty]))
    llm = LlmClient(_settings(), openai_client=client)
    agent = ResearchAgent(llm, _settings())
    state = _minimal_state()
    out = await agent.run(state)
    assert len(out.research_findings) >= 1
