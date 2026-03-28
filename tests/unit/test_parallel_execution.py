"""
Tests for parallel research subtasks (concurrency and partial results on timeout).
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.agents.research_agent import ResearchAgent
from app.config import Settings
from app.orchestration.state import ResearchState, utc_now
from app.services.ai.client import LlmClient

from tests.unit.openai_client_mocks import mock_openai_client


def _settings(**overrides: object) -> Settings:
    base = {
        "database_url": "postgresql+asyncpg://t:t@localhost:5432/t",
        "openai_api_key": "k",
        "max_parallel_agents": 3,
        "research_subtask_timeout_seconds": 300,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _state() -> ResearchState:
    return ResearchState(
        task_id=uuid4(),
        company_name="Co",
        research_brief="Brief",
        status="pending",
        created_at=utc_now(),
        updated_at=utc_now(),
    )


def _resp(content: str) -> MagicMock:
    return MagicMock(
        choices=[MagicMock(message=MagicMock(content=content))],
        usage=MagicMock(prompt_tokens=1, completion_tokens=1),
    )


@pytest.mark.asyncio
async def test_parallel_research_subtasks_run_concurrently() -> None:
    areas_json = '["A", "B", "C"]'
    finding_json = '{"topic":"X","summary":"S.","source":"SRC","source_url":null,"confidence":0.5}'
    starts: list[float] = []
    lock = asyncio.Lock()
    call_idx = 0

    async def chain(*_a: object, **_k: object) -> MagicMock:
        nonlocal call_idx
        async with lock:
            call_idx += 1
            cur = call_idx
        if cur == 1:
            return _resp(areas_json)
        starts.append(asyncio.get_running_loop().time())
        await asyncio.sleep(0.06)
        return _resp(finding_json)

    client = mock_openai_client(AsyncMock(side_effect=chain))
    llm = LlmClient(_settings(), openai_client=client)
    agent = ResearchAgent(llm, _settings())
    out = await agent.run(_state())
    assert len(out.research_findings) == 3
    assert len(starts) == 3
    spread = max(starts) - min(starts)
    assert spread < 0.05


@pytest.mark.asyncio
async def test_subtask_timeout_returns_partial_results() -> None:
    areas_json = '["Fast", "Slow"]'
    finding_json = (
        '{"topic":"Fast","summary":"Ok.","source":"S","source_url":null,"confidence":0.5}'
    )
    lock = asyncio.Lock()
    call_idx = 0

    async def chain(*_a: object, **_k: object) -> MagicMock:
        nonlocal call_idx
        async with lock:
            call_idx += 1
            cur = call_idx
        if cur == 1:
            return _resp(areas_json)
        if cur == 2:
            return _resp(finding_json)
        await asyncio.sleep(2.0)
        return _resp(finding_json)

    client = mock_openai_client(AsyncMock(side_effect=chain))
    llm = LlmClient(
        _settings(research_subtask_timeout_seconds=1),
        openai_client=client,
    )
    agent = ResearchAgent(llm, _settings(research_subtask_timeout_seconds=1))
    out = await agent.run(_state())
    assert len(out.research_findings) == 2
    assert any("timed out" in f.summary.lower() for f in out.research_findings)
