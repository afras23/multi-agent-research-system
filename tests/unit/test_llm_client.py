"""
Tests for ``LlmClient`` retries, pricing, and cost limits.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.config import Settings
from app.core.exceptions import CostLimitExceeded, RetryableError
from app.services.ai.client import LlmClient
from openai import APITimeoutError


def _settings(**overrides: object) -> Settings:
    base = Settings(
        database_url="postgresql+asyncpg://test:test@localhost:5432/test_db",
        openai_api_key="k",
    )
    return base.model_copy(update=overrides) if overrides else base


def _mock_completion(content: str, prompt_tokens: int, completion_tokens: int) -> MagicMock:
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=content))]
    response.usage = MagicMock(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
    return response


def _openai_mock_with_completion(response: MagicMock) -> MagicMock:
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=response)
    return client


@pytest.mark.asyncio
async def test_returns_llm_call_result() -> None:
    settings = _settings()
    mock_client = _openai_mock_with_completion(_mock_completion("ok", 100, 50))
    llm = LlmClient(settings, openai_client=mock_client)
    result = await llm.complete(system_prompt="s", user_prompt="u", prompt_version="pv")
    assert result.content == "ok"
    assert result.input_tokens == 100
    assert result.output_tokens == 50
    assert result.model == "gpt-4o"
    assert result.prompt_version == "pv"


@pytest.mark.asyncio
async def test_cost_tracking_per_call() -> None:
    settings = _settings()
    mock_client = _openai_mock_with_completion(_mock_completion("a", 100_000, 0))
    llm = LlmClient(settings, openai_client=mock_client)
    before = llm.daily_cost_usd
    await llm.complete(system_prompt="s", user_prompt="u", prompt_version="pv")
    after = llm.daily_cost_usd
    assert after > before


@pytest.mark.asyncio
async def test_daily_cost_limit_enforced() -> None:
    settings = _settings(max_daily_cost_usd=0.0)
    mock_client = _openai_mock_with_completion(_mock_completion("x", 10, 10))
    llm = LlmClient(settings, openai_client=mock_client)
    with pytest.raises(CostLimitExceeded):
        await llm.complete(system_prompt="s", user_prompt="u", prompt_version="pv")


@pytest.mark.asyncio
async def test_retry_on_timeout() -> None:
    settings = _settings()
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=[
            APITimeoutError("timeout"),
            _mock_completion("recovered", 5, 5),
        ],
    )
    llm = LlmClient(settings, openai_client=mock_client)
    result = await llm.complete(system_prompt="s", user_prompt="u", prompt_version="pv")
    assert result.content == "recovered"
    assert mock_client.chat.completions.create.await_count == 2


@pytest.mark.asyncio
async def test_retry_exhausted_raises_retryable() -> None:
    settings = _settings()
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=APITimeoutError("timeout"))
    llm = LlmClient(settings, openai_client=mock_client)
    with pytest.raises(RetryableError):
        await llm.complete(system_prompt="s", user_prompt="u", prompt_version="pv")
