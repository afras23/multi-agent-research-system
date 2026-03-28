"""
Shared pytest fixtures.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key-for-ci")

from app.config import Settings
from app.orchestration.state import ResearchState, utc_now
from app.services.ai.client import LlmClient

from tests.unit.openai_client_mocks import mock_openai_client


@pytest.fixture
def test_settings() -> Settings:
    """Minimal settings safe for unit tests (no network)."""
    return Settings(
        database_url="postgresql+asyncpg://test:test@localhost:5432/test_db",
        openai_api_key="test-openai-key",
        ai_model="gpt-4o",
        max_daily_cost_usd=10.0,
        max_request_cost_usd=2.0,
        agent_timeout_seconds=120,
        max_parallel_agents=3,
        research_subtask_timeout_seconds=60,
    )


@pytest.fixture
def minimal_research_state(test_settings: Settings) -> ResearchState:
    """Bare :class:`ResearchState` for agent unit tests."""
    from uuid import uuid4

    return ResearchState(
        task_id=uuid4(),
        company_name="TestCo",
        research_brief="Brief",
        status="pending",
        created_at=utc_now(),
        updated_at=utc_now(),
    )


@pytest.fixture
def llm_client_factory(test_settings: Settings):
    """Build an :class:`LlmClient` with a shaped async OpenAI mock."""

    def _make(completions_create: AsyncMock) -> LlmClient:
        return LlmClient(test_settings, openai_client=mock_openai_client(completions_create))

    return _make


def json_response(content: str, prompt_tokens: int = 10, completion_tokens: int = 10) -> MagicMock:
    """Build a fake OpenAI chat completion response."""
    return MagicMock(
        choices=[MagicMock(message=MagicMock(content=content))],
        usage=MagicMock(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )
