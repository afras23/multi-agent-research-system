"""
Research phase — extract one structured finding for a single area.
"""

SYSTEM = (
    "You are a research analyst. Reply with ONLY a single JSON object — no markdown fences. "
    "Use keys: topic, summary (2-3 sentences), source (simulated publisher name), "
    "source_url (string or null), confidence (number 0-1)."
)

USER_TEMPLATE = (
    "Company: {company}\n"
    "Brief:\n{research_brief}\n"
    "Information area:\n{area}\n\n"
    "Produce one JSON object for this area. "
    "Simulate a plausible source name; use null for source_url if unknown."
)
