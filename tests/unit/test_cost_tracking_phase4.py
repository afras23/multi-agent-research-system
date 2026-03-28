"""
Cost attribution, limits, and metrics aggregation (mocked persistence).
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.config import Settings
from app.core.exceptions import CostLimitExceeded
from app.dependencies import get_settings, get_task_repository
from app.main import create_app
from app.orchestration.state import ResearchFinding, ResearchState, utc_now
from app.repositories.task_repo import TaskRepository, utc_start_of_today
from app.services.ai.client import LlmClient
from fastapi.testclient import TestClient

from tests.conftest import json_response
from tests.unit.openai_client_mocks import mock_openai_client


def _settings(**kwargs: object) -> Settings:
    base = {
        "database_url": "postgresql+asyncpg://t:t@localhost:5432/t",
        "openai_api_key": "k",
        "max_daily_cost_usd": 10.0,
        "max_request_cost_usd": 2.0,
    }
    base.update(kwargs)
    return Settings(**base)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_cost_attributed_to_correct_agent() -> None:
    settings = _settings()
    client = mock_openai_client(
        AsyncMock(
            return_value=json_response("{}", prompt_tokens=100, completion_tokens=50),
        ),
    )
    llm = LlmClient(settings, openai_client=client)
    from app.agents.analysis_agent import AnalysisAgent

    agent = AnalysisAgent(llm, settings)
    state = ResearchState(
        task_id=uuid4(),
        company_name="Co",
        research_brief="B",
        status="analyzing",
        research_findings=[
            ResearchFinding(
                topic="T",
                summary="S",
                source="SRC",
                source_url=None,
                confidence=0.5,
                raw_text="r",
            ),
        ],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    await agent.run(state)
    assert "analysis_agent" in state.agent_costs
    assert state.agent_costs["analysis_agent"].total_cost_usd >= 0.0


@pytest.mark.asyncio
async def test_daily_cost_aggregation_across_tasks() -> None:
    settings = _settings()
    mock_client = mock_openai_client(
        AsyncMock(return_value=json_response("ok", prompt_tokens=50_000, completion_tokens=10)),
    )
    llm = LlmClient(settings, openai_client=mock_client)
    before = llm.daily_cost_usd
    await llm.complete(system_prompt="s", user_prompt="a", prompt_version="pv")
    mid = llm.daily_cost_usd
    await llm.complete(system_prompt="s", user_prompt="b", prompt_version="pv")
    after = llm.daily_cost_usd
    assert mid > before
    assert after > mid


@pytest.mark.asyncio
async def test_cost_limit_stops_new_tasks() -> None:
    settings = _settings(max_daily_cost_usd=0.0)
    mock_client = mock_openai_client(
        AsyncMock(return_value=json_response("x", prompt_tokens=10, completion_tokens=10)),
    )
    llm = LlmClient(settings, openai_client=mock_client)
    with pytest.raises(CostLimitExceeded):
        await llm.complete(system_prompt="s", user_prompt="u", prompt_version="pv")


def test_cost_breakdown_in_metrics_endpoint() -> None:
    app = create_app()

    async def fake_metrics(*_a: object, **_k: object) -> dict[str, object]:
        return {
            "tasks_today": 2,
            "tasks_completed": 1,
            "tasks_failed": 0,
            "avg_latency_ms": 100.0,
            "cost_today_usd": 1.5,
            "cost_limit_usd": 10.0,
            "cost_per_agent": {
                "research_agent": 1.0,
                "analysis_agent": 0.25,
                "writer_agent": 0.25,
                "quality_agent": 0.0,
            },
            "avg_quality_score": 80.0,
        }

    repo = MagicMock(spec=TaskRepository)
    repo.aggregate_operational_metrics = AsyncMock(side_effect=fake_metrics)

    app.dependency_overrides[get_task_repository] = lambda: repo
    app.dependency_overrides[get_settings] = lambda: _settings()

    with TestClient(app) as client:
        r = client.get("/api/v1/metrics")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["cost_per_agent"]["research_agent"] == 1.0
    assert data["cost_today_usd"] == 1.5
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_task_repo_aggregate_cost_per_agent() -> None:
    """Repository aggregates per-agent spend from ``state_json`` payloads."""
    row = MagicMock()
    row.status = "completed"
    row.total_cost_usd = 2.0
    row.total_latency_ms = 50.0
    row.state_json = {
        "agent_costs": {
            "research_agent": {"total_cost_usd": 1.0},
            "analysis_agent": {"total_cost_usd": 0.5},
            "writer_agent": {"total_cost_usd": 0.5},
            "quality_agent": {"total_cost_usd": 0.0},
        },
        "quality_score": {"overall_score": 88.0},
    }
    row.created_at = datetime.now(UTC)

    session = MagicMock()

    class _Result:
        def scalars(self) -> object:
            return self

        def all(self) -> list[object]:
            return [row]

    async def execute(_stmt: object) -> _Result:
        return _Result()

    session.execute = AsyncMock(side_effect=execute)
    repo = TaskRepository(session)
    out = await repo.aggregate_operational_metrics(
        utc_day_start=utc_start_of_today(),
        cost_limit_usd=10.0,
    )
    assert out["cost_per_agent"]["research_agent"] >= 1.0
    assert out["avg_quality_score"] >= 88.0
