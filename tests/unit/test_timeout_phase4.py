"""
Timeout behaviour for agents and orchestrated runs.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.agents.base_agent import BaseAgent
from app.config import Settings
from app.core.exceptions import AgentTimeoutError
from app.orchestration.state import ResearchState, utc_now
from app.services.ai.client import LlmClient
from openai import AsyncOpenAI

from tests.unit.openai_client_mocks import mock_openai_client


def _settings(**kwargs: object) -> Settings:
    base = {
        "database_url": "postgresql+asyncpg://t:t@localhost:5432/t",
        "openai_api_key": "k",
        "agent_timeout_seconds": 1,
    }
    base.update(kwargs)
    return Settings(**base)  # type: ignore[arg-type]


class _SlowAgent(BaseAgent):
    async def _execute(self, state: ResearchState) -> ResearchState:
        await asyncio.sleep(3.0)
        return state


@pytest.mark.asyncio
async def test_agent_timeout_raises_correctly() -> None:
    settings = _settings(agent_timeout_seconds=1)
    llm = LlmClient(settings, openai_client=MagicMock(spec=AsyncOpenAI))
    agent = _SlowAgent("slow", llm, settings)
    state = ResearchState(
        task_id=uuid4(),
        company_name="C",
        research_brief="B",
        status="pending",
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    with pytest.raises(AgentTimeoutError):
        await agent.run(state)


@pytest.mark.asyncio
async def test_parallel_subtask_timeout_partial_results() -> None:
    """Duplicate scenario name: parallel research yields placeholders on subtask timeout."""
    from app.agents.research_agent import ResearchAgent

    areas_json = '["OnlySlow"]'
    finding_json = (
        '{"topic":"OnlySlow","summary":"Ok.","source":"S","source_url":null,"confidence":0.5}'
    )
    lock = asyncio.Lock()
    n = 0

    async def chain(*_a: object, **_k: object) -> MagicMock:
        nonlocal n
        async with lock:
            n += 1
            cur = n
        if cur == 1:
            return MagicMock(
                choices=[MagicMock(message=MagicMock(content=areas_json))],
                usage=MagicMock(prompt_tokens=1, completion_tokens=1),
            )
        await asyncio.sleep(2.0)
        return MagicMock(
            choices=[MagicMock(message=MagicMock(content=finding_json))],
            usage=MagicMock(prompt_tokens=1, completion_tokens=1),
        )

    client = mock_openai_client(AsyncMock(side_effect=chain))
    s = _settings(agent_timeout_seconds=120, research_subtask_timeout_seconds=1)
    llm = LlmClient(s, openai_client=client)
    agent = ResearchAgent(llm, s)
    state = ResearchState(
        task_id=uuid4(),
        company_name="Co",
        research_brief="B",
        status="pending",
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    out = await agent.run(state)
    assert len(out.research_findings) == 1
    assert "timed out" in out.research_findings[0].summary.lower()


@pytest.mark.asyncio
async def test_overall_task_timeout_if_all_agents_slow() -> None:
    settings = _settings(agent_timeout_seconds=1)
    llm = LlmClient(settings, openai_client=MagicMock(spec=AsyncOpenAI))
    agent = _SlowAgent("slow", llm, settings)
    state = ResearchState(
        task_id=uuid4(),
        company_name="C",
        research_brief="B",
        status="pending",
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(agent.run(state), timeout=0.01)
