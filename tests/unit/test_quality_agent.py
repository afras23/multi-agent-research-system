"""
Tests for ``QualityAgent``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.agents.quality_agent import QualityAgent
from app.config import Settings
from app.orchestration.state import ResearchFinding, ResearchState, utc_now
from app.services.ai.client import LlmClient

from tests.unit.openai_client_mocks import mock_openai_client


def _settings() -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://t:t@localhost:5432/t",
        openai_api_key="k",
    )


def _state() -> ResearchState:
    return ResearchState(
        task_id=uuid4(),
        company_name="Co",
        research_brief="B",
        status="quality_check",
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
        report_draft="Claim [Source: SRC].",
        created_at=utc_now(),
        updated_at=utc_now(),
    )


@pytest.mark.asyncio
async def test_scores_report_quality() -> None:
    payload = (
        '{"source_coverage":80,"completeness":75,"accuracy":85,"coherence":90,'
        '"overall_score":82.5,"issues":[],"recommendation":"approve"}'
    )
    client = mock_openai_client(
        AsyncMock(
            return_value=MagicMock(
                choices=[MagicMock(message=MagicMock(content=payload))],
                usage=MagicMock(prompt_tokens=30, completion_tokens=60),
            ),
        ),
    )
    llm = LlmClient(_settings(), openai_client=client)
    agent = QualityAgent(llm, _settings())
    state = _state()
    out = await agent.run(state)
    assert out.quality_score is not None
    assert out.quality_score.overall_score == pytest.approx(82.5)


@pytest.mark.asyncio
async def test_identifies_issues() -> None:
    payload = (
        '{"source_coverage":40,"completeness":50,"accuracy":45,"coherence":60,'
        '"overall_score":48.75,'
        '"issues":[{"description":"Missing cite","severity":"high","location_in_report":"§2"}],'
        '"recommendation":"revise"}'
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
    agent = QualityAgent(llm, _settings())
    state = _state()
    out = await agent.run(state)
    assert out.quality_score is not None
    assert len(out.quality_score.issues) >= 1
