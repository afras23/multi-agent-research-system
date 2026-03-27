"""
Tests for ``BaseAgent`` timeout, logging, and cost attribution.
"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock

import pytest
from app.agents.base_agent import BaseAgent
from app.config import Settings
from app.core.exceptions import AgentError, AgentTimeoutError
from app.orchestration.state import ResearchState, utc_now
from app.services.ai.client import LlmCallResult, LlmClient


class _SlowAgent(BaseAgent):
    async def _execute(self, state: ResearchState) -> ResearchState:
        await asyncio.sleep(10.0)
        return state


class _FailingAgent(BaseAgent):
    async def _execute(self, state: ResearchState) -> ResearchState:
        raise ValueError("planned failure")


class _CostAgent(BaseAgent):
    async def _execute(self, state: ResearchState) -> ResearchState:
        sample = LlmCallResult(
            content="x",
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.01,
            latency_ms=1.0,
            model="gpt-4o",
            prompt_version="test",
        )
        self._track_cost(state, sample)
        return state


def _minimal_state() -> ResearchState:
    from uuid import uuid4

    return ResearchState(
        task_id=uuid4(),
        company_name="Acme",
        research_brief="Brief",
        status="pending",
        created_at=utc_now(),
        updated_at=utc_now(),
    )


@pytest.mark.asyncio
async def test_agent_timeout_raises_agent_timeout_error(test_settings: Settings) -> None:
    settings = test_settings.model_copy(update={"agent_timeout_seconds": 1})
    llm = LlmClient(settings, openai_client=AsyncMock())
    agent = _SlowAgent("slow", llm, settings)
    state = _minimal_state()
    with pytest.raises(AgentTimeoutError):
        await agent.run(state)
    assert any("timed out" in err for err in state.errors)


@pytest.mark.asyncio
async def test_agent_failure_logs_error_and_raises(
    test_settings: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.ERROR)
    llm = LlmClient(test_settings, openai_client=AsyncMock())
    agent = _FailingAgent("failing", llm, test_settings)
    state = _minimal_state()
    with pytest.raises(AgentError):
        await agent.run(state)
    assert any("failed" in err for err in state.errors)


@pytest.mark.asyncio
async def test_agent_tracks_cost_to_state(test_settings: Settings) -> None:
    llm = LlmClient(test_settings, openai_client=AsyncMock())
    agent = _CostAgent("cost", llm, test_settings)
    state = _minimal_state()
    out = await agent.run(state)
    entry = out.agent_costs["cost"]
    assert entry.total_cost_usd == pytest.approx(0.01)
    assert entry.input_tokens == 10
    assert entry.output_tokens == 5


@pytest.mark.asyncio
async def test_agent_logs_completion_with_latency(
    test_settings: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    llm = LlmClient(test_settings, openai_client=AsyncMock())

    class _FastAgent(BaseAgent):
        async def _execute(self, state: ResearchState) -> ResearchState:
            return state

    agent = _FastAgent("fast", llm, test_settings)
    state = _minimal_state()
    await agent.run(state)
    assert "Agent step completed" in caplog.text
    assert any(hasattr(record, "latency_ms") for record in caplog.records)
