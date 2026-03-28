"""
Request and response models for research HTTP API.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ResearchRequest(BaseModel):
    """Payload to start a new multi-agent research run."""

    company_name: str = Field(description="Legal or trade name of the company under review")
    research_brief: str = Field(description="Goals and questions for the research pass")
    industry_context: str | None = Field(
        default=None,
        description="Optional sector, geography, or regulatory context",
    )

    @field_validator("company_name", "research_brief", mode="before")
    @classmethod
    def strip_outer_whitespace(cls, value: object) -> object:
        """Remove leading/trailing whitespace from user-supplied text fields."""
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("company_name", mode="after")
    @classmethod
    def strip_html_angle_brackets(cls, value: str) -> str:
        """Remove common HTML/script fragments from user-supplied company names."""
        without_script = re.sub(
            r"<script[^>]*>.*?</script>",
            "",
            value,
            flags=re.DOTALL | re.IGNORECASE,
        )
        without_tags = re.sub(r"<[^>]*>", "", without_script)
        return without_tags.strip()

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "company_name": "Acme Corp",
                    "research_brief": "Assess competitive threats and margin outlook.",
                    "industry_context": "Industrial automation, North America",
                },
            ],
        },
    }


class ResearchTaskResponse(BaseModel):
    """Minimal task reference returned after create or checkpoint actions."""

    task_id: UUID = Field(description="Primary key of the research task")
    status: str = Field(description="Current orchestration status")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"task_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6", "status": "researching"},
            ],
        },
    }


class AgentCostBreakdown(BaseModel):
    """Aggregated LLM cost for one agent."""

    total_cost_usd: float = Field(default=0.0, ge=0.0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)


class ResearchStateSummary(BaseModel):
    """Lightweight view of orchestration progress for polling clients."""

    findings_count: int = Field(ge=0)
    has_analysis: bool
    has_report_draft: bool
    has_quality_score: bool
    checkpoint_status: Literal["not_reached", "pending", "approved", "rejected"]


class AgentMessageOut(BaseModel):
    """One persisted inter-agent message."""

    agent_name: str
    message_type: Literal["input", "output", "error"]
    content: str


class ResearchTaskDetail(BaseModel):
    """Full task snapshot including costs and messages."""

    task_id: UUID
    company_name: str
    research_brief: str
    industry_context: str | None
    status: str
    checkpoint_status: str
    checkpoint_reviewer: str | None
    rejection_reason: str | None
    failure_reason: str | None
    agent_costs: dict[str, AgentCostBreakdown]
    agent_messages: list[AgentMessageOut]
    errors: list[str]
    state_summary: ResearchStateSummary
    total_pipeline_latency_ms: float
    created_at: datetime
    updated_at: datetime

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "task_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "company_name": "Acme Corp",
                    "research_brief": "Margin outlook",
                    "industry_context": "SaaS",
                    "status": "awaiting_approval",
                    "checkpoint_status": "pending",
                    "checkpoint_reviewer": None,
                    "rejection_reason": None,
                    "failure_reason": None,
                    "agent_costs": {},
                    "agent_messages": [],
                    "errors": [],
                    "state_summary": {
                        "findings_count": 4,
                        "has_analysis": True,
                        "has_report_draft": False,
                        "has_quality_score": False,
                        "checkpoint_status": "pending",
                    },
                    "total_pipeline_latency_ms": 12000.0,
                    "created_at": "2026-03-27T12:00:00+00:00",
                    "updated_at": "2026-03-27T12:00:30+00:00",
                },
            ],
        },
    }


class ApprovalRequest(BaseModel):
    """Human approval for the checkpoint after analysis."""

    reviewer: str = Field(description="Identifier of the approver")

    model_config = {"json_schema_extra": {"examples": [{"reviewer": "alice@example.com"}]}}


class RejectionRequest(BaseModel):
    """Human rejection at the checkpoint."""

    reviewer: str = Field(description="Identifier of the reviewer")
    reason: str = Field(description="Why the draft pipeline was rejected")

    model_config = {
        "json_schema_extra": {
            "examples": [{"reviewer": "bob@example.com", "reason": "Insufficient sources."}],
        },
    }


class QualityScoreOut(BaseModel):
    """Quality rubric scores exposed to API clients."""

    overall_score: float
    source_coverage: float
    completeness: float
    accuracy: float
    coherence: float
    recommendation: Literal["approve", "revise", "reject"]


class ReportResponse(BaseModel):
    """Final report payload for a completed task."""

    task_id: UUID
    report_markdown: str
    quality_score: QualityScoreOut | None
    agent_costs: dict[str, AgentCostBreakdown]
    total_cost_usd: float

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "task_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "report_markdown": "# Executive Summary\n...",
                    "quality_score": {
                        "overall_score": 82.5,
                        "source_coverage": 80.0,
                        "completeness": 75.0,
                        "accuracy": 85.0,
                        "coherence": 90.0,
                        "recommendation": "approve",
                    },
                    "agent_costs": {},
                    "total_cost_usd": 1.25,
                },
            ],
        },
    }


class ResearchTaskListItem(BaseModel):
    """One row in the paginated task list."""

    task_id: UUID
    company_name: str
    status: str
    created_at: datetime
    updated_at: datetime


class ResearchTaskListResponse(BaseModel):
    """Paginated list wrapper."""

    items: list[ResearchTaskListItem]
    page: int
    page_size: int
    total: int
