"""
Pydantic models for evaluation fixtures and aggregated reports.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EvalTestCase(BaseModel):
    """One row from ``eval/test_set.jsonl``."""

    company_name: str
    research_brief: str
    expected_sections: list[str]
    expected_topics: list[str]
    category: Literal["standard", "complex", "edge_case"]
    expected_quality_score_min: float = Field(ge=0.0, le=100.0)


class EvalFailure(BaseModel):
    """A single failed case with a human-readable reason."""

    company: str
    reason: str


class EvaluationReport(BaseModel):
    """Aggregated evaluation output written to ``eval/results/eval_YYYY-MM-DD.json``."""

    timestamp: str
    model: str
    test_cases: int
    pass_rate: float
    avg_quality_score: float
    avg_sections_present: float
    avg_topic_coverage: float
    avg_citation_count: float
    avg_cost_per_task_usd: float
    avg_latency_ms: float
    cost_by_agent: dict[str, float]
    failures: list[EvalFailure]
