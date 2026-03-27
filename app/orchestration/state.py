"""
LangGraph orchestration state models.

Typed state shared across agents; serialised to JSON for persistence in later
phases.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(UTC)


class ResearchFinding(BaseModel):
    """A single sourced research snippet."""

    title: str
    summary: str
    source_url: str | None = None


class AnalysisResult(BaseModel):
    """Structured output from the analysis step."""

    executive_summary: str
    key_themes: list[str] = Field(default_factory=list)
    key_risks: list[str] = Field(default_factory=list)


class QualityScore(BaseModel):
    """Scores from the quality review step."""

    overall: float = Field(ge=0.0, le=1.0)
    citation_coverage: float = Field(ge=0.0, le=1.0)
    notes: str | None = None


class AgentCostEntry(BaseModel):
    """Cumulative LLM usage attributed to one agent."""

    total_cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0


class AgentMessage(BaseModel):
    """Inter-agent or agent-to-orchestrator message for the in-memory log."""

    message_id: UUID = Field(default_factory=uuid4)
    agent_name: str
    message_type: Literal["input", "output", "error"]
    content: str


class ResearchState(BaseModel):
    """Typed state object shared by all agents via LangGraph."""

    task_id: UUID
    company_name: str
    research_brief: str
    status: Literal[
        "pending",
        "researching",
        "analyzing",
        "awaiting_approval",
        "writing",
        "quality_check",
        "completed",
        "failed",
    ]

    research_findings: list[ResearchFinding] = Field(default_factory=list)
    analysis_result: AnalysisResult | None = None
    report_draft: str | None = None
    quality_score: QualityScore | None = None

    agent_costs: dict[str, AgentCostEntry] = Field(default_factory=dict)
    agent_messages: list[AgentMessage] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    checkpoint_status: Literal["not_reached", "pending", "approved", "rejected"] = "not_reached"
    checkpoint_reviewer: str | None = None

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    model_config = {"frozen": False}
