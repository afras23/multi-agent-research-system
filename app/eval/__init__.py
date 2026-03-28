"""
Offline evaluation harness: fixtures, grading metrics, and pipeline helpers.
"""

from app.eval.grading import (
    section_completeness_result,
    topic_coverage_ratio,
)
from app.eval.schemas import EvalFailure, EvalTestCase, EvaluationReport

__all__ = [
    "EvalFailure",
    "EvalTestCase",
    "EvaluationReport",
    "section_completeness_result",
    "topic_coverage_ratio",
]
