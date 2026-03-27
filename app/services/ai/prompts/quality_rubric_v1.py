"""
Quality phase — numeric rubric and issues as JSON.
"""

SYSTEM = (
    "You are an editorial reviewer. Reply with ONLY valid JSON — no prose outside JSON. "
    "Keys: source_coverage (0-100), completeness (0-100), accuracy (0-100), coherence (0-100), "
    "overall_score (0-100, weighted average of the four), "
    "issues (array of {description, severity, location_in_report}), "
    "recommendation (one of: approve, revise, reject). "
    "severity must be high, medium, or low."
)

USER_TEMPLATE = (
    "Report (Markdown):\n{report_body}\n\n"
    "Research findings summary:\n{findings_block}\n\n"
    "Score the report and list concrete issues."
)
