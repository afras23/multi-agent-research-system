"""
Parameterised pipeline coverage for briefs and agent configuration.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from app.agents.research_agent import ResearchAgent
from app.config import Settings
from app.orchestration.state import ResearchState, utc_now
from app.services.ai.client import LlmClient

from tests.conftest import json_response
from tests.unit.openai_client_mocks import mock_openai_client


def _state(brief: str) -> ResearchState:
    return ResearchState(
        task_id=uuid4(),
        company_name="Co",
        research_brief=brief,
        status="pending",
        created_at=utc_now(),
        updated_at=utc_now(),
    )


@pytest.mark.parametrize(
    "research_brief",
    [
        "Short brief.",
        "A longer institutional equity research brief covering multiple geographies.",
        "Regulatory and litigation outlook for the next two fiscal years.",
    ],
)
@pytest.mark.asyncio
async def test_research_agent_across_brief_lengths(research_brief: str) -> None:
    create = AsyncMock(
        side_effect=[
            json_response('["One"]', 3, 3),
            json_response(
                '{"topic":"One","summary":"S.","source":"SRC","source_url":null,"confidence":0.5}',
                3,
                3,
            ),
        ],
    )
    settings = Settings(
        database_url="postgresql+asyncpg://t:t@localhost:5432/t",
        openai_api_key="k",
    )
    llm = LlmClient(settings, openai_client=mock_openai_client(create))
    agent = ResearchAgent(llm, settings)
    out = await agent.run(_state(research_brief))
    assert len(out.research_findings) == 1
    user = create.await_args_list[0].kwargs["messages"][1]["content"]
    assert research_brief in user


@pytest.mark.parametrize(
    ("max_parallel", "subtask_timeout"),
    [
        (1, 120),
        (3, 60),
        (5, 30),
    ],
)
@pytest.mark.asyncio
async def test_research_agent_respects_agent_configuration(
    max_parallel: int,
    subtask_timeout: int,
) -> None:
    create = AsyncMock(
        side_effect=[
            json_response('["A","B"]', 2, 2),
            json_response(
                '{"topic":"A","summary":"S.","source":"S","source_url":null,"confidence":0.5}',
                2,
                2,
            ),
            json_response(
                '{"topic":"B","summary":"S.","source":"S","source_url":null,"confidence":0.5}',
                2,
                2,
            ),
        ],
    )
    settings = Settings(
        database_url="postgresql+asyncpg://t:t@localhost:5432/t",
        openai_api_key="k",
        max_parallel_agents=max_parallel,
        research_subtask_timeout_seconds=subtask_timeout,
    )
    llm = LlmClient(settings, openai_client=mock_openai_client(create))
    agent = ResearchAgent(llm, settings)
    out = await agent.run(_state("Brief"))
    assert len(out.research_findings) == 2
    assert settings.max_parallel_agents == max_parallel
