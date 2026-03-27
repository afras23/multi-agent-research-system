"""
LangGraph orchestration state models.

Typed state shared across agents; serialised to JSON for persistence.
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
    """A single structured research finding with simulated provenance."""

    topic: str
    summary: str = Field(description="Two to three sentences")
    source: str = Field(description="Simulated source label")
    source_url: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    raw_text: str = Field(description="Raw LLM output for this finding")


class RiskItem(BaseModel):
    """A risk identified during analysis."""

    description: str
    severity: Literal["high", "medium", "low"]
    source: str = Field(description="Supporting finding topic or note")


class OpportunityItem(BaseModel):
    """An opportunity identified during analysis."""

    description: str
    rationale: str = Field(default="", description="Why this is an opportunity")


class AnalysisResult(BaseModel):
    """Structured synthesis from the analysis step."""

    key_themes: list[str] = Field(default_factory=list)
    risks: list[RiskItem] = Field(default_factory=list)
    opportunities: list[OpportunityItem] = Field(default_factory=list)
    competitive_position: str = Field(description="Two to three sentences")
    financial_outlook: str = Field(description="Two to three sentences")
    gaps_identified: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)


class QualityIssue(BaseModel):
    """A concrete issue flagged by the quality agent."""

    description: str
    severity: Literal["high", "medium", "low"]
    location_in_report: str | None = None


class QualityScore(BaseModel):
    """Structured quality review scores (0–100 scale)."""

    overall_score: float = Field(ge=0.0, le=100.0)
    source_coverage: float = Field(ge=0.0, le=100.0)
    completeness: float = Field(ge=0.0, le=100.0)
    accuracy: float = Field(ge=0.0, le=100.0)
    coherence: float = Field(ge=0.0, le=100.0)
    issues: list[QualityIssue] = Field(default_factory=list)
    recommendation: Literal["approve", "revise", "reject"]


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
    industry_context: str | None = None
    status: Literal[
        "pending",
        "researching",
        "analyzing",
        "awaiting_approval",
        "writing",
        "quality_check",
        "completed",
        "failed",
        "rejected",
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
    rejection_reason: str | None = None

    total_pipeline_latency_ms: float = Field(
        default=0.0,
        description="Wall-clock latency for the orchestrated run segments",
    )
    failure_reason: str | None = Field(
        default=None,
        description="Set when status is failed (e.g. timeout)",
    )

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    model_config = {"frozen": False}
