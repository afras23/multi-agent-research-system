"""
Integration-style tests for research HTTP routes (dependency overrides).
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from app.api.schemas.research import (
    ApprovalRequest,
    ReportResponse,
    ResearchRequest,
    ResearchTaskDetail,
    ResearchTaskResponse,
)
from app.dependencies import get_db, get_research_service
from app.main import create_app
from fastapi.testclient import TestClient


async def _mock_db_session() -> object:
    session = MagicMock()
    session.commit = AsyncMock()
    yield session


@pytest.fixture
def client() -> TestClient:
    """ASGI client with a mocked :class:`ResearchService`."""
    app = create_app()
    app.dependency_overrides[get_db] = _mock_db_session

    class _FakeResearchService:
        async def start_research(self, request: ResearchRequest) -> ResearchTaskResponse:
            return ResearchTaskResponse(task_id=uuid4(), status="researching")

        async def get_task(self, task_id: UUID) -> ResearchTaskDetail:
            from app.api.schemas.research import AgentMessageOut, ResearchStateSummary

            return ResearchTaskDetail(
                task_id=task_id,
                company_name="Co",
                research_brief="B",
                industry_context=None,
                status="analyzing",
                checkpoint_status="not_reached",
                checkpoint_reviewer=None,
                rejection_reason=None,
                failure_reason=None,
                agent_costs={},
                agent_messages=[
                    AgentMessageOut(
                        agent_name="research_agent",
                        message_type="output",
                        content="x",
                    ),
                ],
                errors=[],
                state_summary=ResearchStateSummary(
                    findings_count=2,
                    has_analysis=False,
                    has_report_draft=False,
                    has_quality_score=False,
                    checkpoint_status="not_reached",
                ),
                total_pipeline_latency_ms=100.0,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )

        async def approve_checkpoint(
            self,
            task_id: UUID,
            body: ApprovalRequest,
        ) -> ResearchTaskResponse:
            return ResearchTaskResponse(task_id=task_id, status="writing")

        async def reject_checkpoint(self, task_id: UUID, body: MagicMock) -> ResearchTaskResponse:
            return ResearchTaskResponse(task_id=task_id, status="rejected")

        async def get_report(self, task_id: UUID) -> ReportResponse:
            from app.api.schemas.research import AgentCostBreakdown, QualityScoreOut

            return ReportResponse(
                task_id=task_id,
                report_markdown="# Report",
                quality_score=QualityScoreOut(
                    overall_score=80.0,
                    source_coverage=80.0,
                    completeness=80.0,
                    accuracy=80.0,
                    coherence=80.0,
                    recommendation="approve",
                ),
                agent_costs={"research_agent": AgentCostBreakdown()},
                total_cost_usd=1.0,
            )

        async def list_tasks(self, **kwargs: object) -> MagicMock:
            m = MagicMock()
            m.model_dump = lambda mode="json": {"items": [], "page": 1, "page_size": 20, "total": 0}
            return m

    fake = _FakeResearchService()
    app.dependency_overrides[get_research_service] = lambda: fake

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_create_research_task_returns_202(client: TestClient) -> None:
    response = client.post(
        "/api/v1/research",
        json={
            "company_name": "Acme",
            "research_brief": "Test brief",
            "industry_context": "Tech",
        },
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["status"] == "researching"
    assert "task_id" in body["data"]


def test_get_task_returns_current_state(client: TestClient) -> None:
    tid = str(uuid4())
    response = client.get(f"/api/v1/research/{tid}")
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["task_id"] == tid
    assert body["data"]["state_summary"]["findings_count"] == 2


def test_approve_checkpoint_resumes_pipeline(client: TestClient) -> None:
    tid = str(uuid4())
    response = client.post(
        f"/api/v1/research/{tid}/approve",
        json={"reviewer": "alice@example.com"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "writing"


def test_get_report_after_completion(client: TestClient) -> None:
    tid = str(uuid4())
    response = client.get(f"/api/v1/research/{tid}/report")
    assert response.status_code == 200
    report_md = response.json()["data"]["report_markdown"]
    assert "Executive" in report_md or "# Report" in report_md
