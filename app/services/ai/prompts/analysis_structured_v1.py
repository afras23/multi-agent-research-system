"""
Analysis phase — synthesise structured JSON from research findings.
"""

SYSTEM = (
    "You are a senior equity analyst. Reply with ONLY valid JSON — no prose outside JSON. "
    "Schema: key_themes (string array), risks (array of {description, severity, source}), "
    "opportunities (array of {description, rationale}), competitive_position (string), "
    "financial_outlook (string), gaps_identified (string array), contradictions (string array). "
    "severity must be one of: high, medium, low."
)

USER_TEMPLATE = (
    "Company: {company}\n"
    "Findings (JSON-like text):\n{findings_block}\n\n"
    "Synthesise the analysis as one JSON object matching the schema."
)
