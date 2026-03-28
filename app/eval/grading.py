"""
Deterministic grading helpers for evaluation reports (no LLM calls).
"""

from __future__ import annotations

import re
from re import Pattern


def _section_header_pattern(section_title: str) -> Pattern[str]:
    """Build a regex that matches Markdown H1/H2 headers for ``section_title``."""
    escaped = re.escape(section_title.strip())
    return re.compile(rf"^#{{1,2}}\s*{escaped}\s*$", re.MULTILINE | re.IGNORECASE)


def section_completeness_result(
    report_markdown: str,
    expected_sections: list[str],
) -> tuple[bool, int, list[str]]:
    """
    Check whether expected section headings appear in the report.

    Args:
        report_markdown: Full Markdown report body.
        expected_sections: Section titles expected as ``## Title`` (or ``#``).

    Returns:
        Tuple of (all present, count present, missing titles).
    """
    missing: list[str] = []
    present_n = 0
    for title in expected_sections:
        if _section_header_pattern(title).search(report_markdown):
            present_n += 1
        else:
            missing.append(title)
    return (len(missing) == 0, present_n, missing)


def topic_coverage_ratio(report_markdown: str, expected_topics: list[str]) -> float:
    """
    Return the fraction of expected topics mentioned in the report (case-insensitive).

    Args:
        report_markdown: Full Markdown report body.
        expected_topics: Phrases that should appear literally (case-insensitive).

    Returns:
        Ratio in ``[0.0, 1.0]``. Returns ``1.0`` when there are zero expected topics.
    """
    if not expected_topics:
        return 1.0
    lower = report_markdown.lower()
    hits = 0
    for topic in expected_topics:
        if topic.strip().lower() in lower:
            hits += 1
    return hits / len(expected_topics)


def citation_count(report_markdown: str) -> int:
    """Count ``[Source:`` markers (matches writer agent heuristic)."""
    return len(re.findall(r"\[Source:", report_markdown, flags=re.IGNORECASE))
