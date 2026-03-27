"""
Research phase — identify information areas (JSON array of strings).
"""

SYSTEM = (
    "You are a research planner. Reply with ONLY valid JSON — no prose outside JSON. "
    "The JSON must be an array of 3 to 6 short strings naming distinct information areas."
)

USER_TEMPLATE = (
    "Company: {company}\n"
    "Research brief:\n{research_brief}\n\n"
    "Return a JSON array of strings, each naming one information area to investigate."
)
