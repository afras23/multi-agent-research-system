"""
Tests for ``WriterAgent``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.agents.writer_agent import WriterAgent
from app.config import Settings
from app.orchestration.state import AnalysisResult, ResearchFinding, ResearchState, utc_now
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
        status="writing",
        research_findings=[
            ResearchFinding(
                topic="T",
                summary="S",
                source="SRC",
                source_url=None,
                confidence=0.9,
                raw_text="x",
            ),
        ],
        analysis_result=AnalysisResult(
            key_themes=["k"],
            competitive_position="cp",
            financial_outlook="fo",
        ),
        created_at=utc_now(),
        updated_at=utc_now(),
    )


@pytest.mark.asyncio
async def test_produces_structured_report() -> None:
    md = "# Executive Summary\n\n[Source: SRC] Claim.\n\n## Company Overview\n\nText."
    client = mock_openai_client(
        AsyncMock(
            return_value=MagicMock(
                choices=[MagicMock(message=MagicMock(content=md))],
                usage=MagicMock(prompt_tokens=50, completion_tokens=100),
            ),
        ),
    )
    llm = LlmClient(_settings(), openai_client=client)
    agent = WriterAgent(llm, _settings())
    state = _state()
    out = await agent.run(state)
    assert out.report_draft is not None
    assert "Executive Summary" in out.report_draft


@pytest.mark.asyncio
async def test_includes_citations() -> None:
    md = "Line [Source: Annual Report]. Another [Source: News]."
    client = mock_openai_client(
        AsyncMock(
            return_value=MagicMock(
                choices=[MagicMock(message=MagicMock(content=md))],
                usage=MagicMock(prompt_tokens=10, completion_tokens=20),
            ),
        ),
    )
    llm = LlmClient(_settings(), openai_client=client)
    agent = WriterAgent(llm, _settings())
    state = _state()
    out = await agent.run(state)
    assert "[Source:" in (out.report_draft or "")
