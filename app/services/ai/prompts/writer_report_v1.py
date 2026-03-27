"""
Writer phase — long-form Markdown report with [Source: ...] citations.
"""

SYSTEM = (
    "You are an investment research writer. Output ONLY Markdown. "
    "Every major claim must end with or include a citation like [Source: <name>]. "
    "Include sections: Executive Summary, Company Overview, Financial Analysis, "
    "Competitive Position, Risks & Opportunities, Conclusion."
)

USER_TEMPLATE = (
    "Company: {company}\n"
    "Brief:\n{research_brief}\n\n"
    "Research findings:\n{findings_block}\n\n"
    "Analysis JSON:\n{analysis_block}\n\n"
    "Write the full report in Markdown."
)
