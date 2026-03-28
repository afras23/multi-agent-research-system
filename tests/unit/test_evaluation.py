"""
Unit tests for evaluation grading helpers and report schema.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.eval.grading import section_completeness_result, topic_coverage_ratio
from app.eval.schemas import EvalFailure, EvaluationReport


def test_section_completeness_check() -> None:
    """Expected Markdown headers are detected case-insensitively."""
    md = """# Research Report

## Executive Summary
Intro.

## Company Overview
Details.
"""
    expected = ["Executive Summary", "Company Overview", "Missing Section"]
    ok, present_n, missing = section_completeness_result(md, expected)
    assert ok is False
    assert present_n == 2
    assert missing == ["Missing Section"]


def test_topic_coverage_calculation() -> None:
    """Topic coverage counts substring mentions in the report body."""
    text = "Market share is stable; revenue growth accelerated."
    topics = ["market share", "revenue growth", "margin expansion"]
    ratio = topic_coverage_ratio(text, topics)
    assert ratio == pytest.approx(2 / 3)


def test_evaluation_report_schema_valid() -> None:
    """Aggregated JSON shape matches :class:`EvaluationReport`."""
    raw = EvaluationReport(
        timestamp=datetime.now(UTC).isoformat(),
        model="gpt-4o",
        test_cases=20,
        pass_rate=0.85,
        avg_quality_score=74.5,
        avg_sections_present=5.8,
        avg_topic_coverage=0.88,
        avg_citation_count=12.3,
        avg_cost_per_task_usd=1.45,
        avg_latency_ms=35000.0,
        cost_by_agent={
            "research": 0.65,
            "analysis": 0.30,
            "writer": 0.35,
            "quality": 0.15,
        },
        failures=[
            EvalFailure(company="ExampleCo", reason="missing section: Financial Analysis"),
        ],
    )
    roundtrip = EvaluationReport.model_validate_json(raw.model_dump_json())
    assert roundtrip.pass_rate == 0.85
    assert roundtrip.failures[0].company == "ExampleCo"
