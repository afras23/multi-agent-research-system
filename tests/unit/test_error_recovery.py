"""
LLM retries, circuit breaker, and infrastructure failure handling.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from app.config import Settings
from app.core.exceptions import RetryableError
from app.dependencies import get_db
from app.main import create_app
from app.services.ai.client import LlmClient
from openai import APITimeoutError
from sqlalchemy.exc import OperationalError

from tests.conftest import json_response
from tests.unit.openai_client_mocks import mock_openai_client


def _settings(**kwargs: object) -> Settings:
    base = {
        "database_url": "postgresql+asyncpg://t:t@localhost:5432/t",
        "openai_api_key": "k",
    }
    base.update(kwargs)
    return Settings(**base)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_llm_failure_retries_then_fails_gracefully() -> None:
    create = AsyncMock(
        side_effect=[
            APITimeoutError("t"),
            APITimeoutError("t"),
            json_response("recovered", 5, 5),
        ],
    )
    llm = LlmClient(_settings(), openai_client=mock_openai_client(create))
    result = await llm.complete(system_prompt="s", user_prompt="u", prompt_version="pv")
    assert result.content == "recovered"
    assert create.await_count == 3


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_failures() -> None:
    create = AsyncMock(side_effect=APITimeoutError("t"))
    llm = LlmClient(_settings(), openai_client=mock_openai_client(create))
    for _ in range(2):
        with pytest.raises(RetryableError):
            await llm.complete(system_prompt="s", user_prompt="u", prompt_version="pv")
    with pytest.raises(RetryableError) as exc:
        await llm.complete(system_prompt="s", user_prompt="u", prompt_version="pv")
    assert "circuit" in str(exc.value).lower()
    assert create.await_count == 6


def test_database_unavailable_returns_503() -> None:
    app = create_app()

    async def failing_db() -> object:
        raise OperationalError("SELECT 1", {}, None)
        yield  # pragma: no cover

    app.dependency_overrides[get_db] = failing_db
    try:
        from fastapi.testclient import TestClient

        with TestClient(app) as client:
            response = client.get("/api/v1/health/ready")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
