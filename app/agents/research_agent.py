"""
Research agent — gathers and structures source-facing notes.

Full retrieval integration is implemented in a later phase; this module
currently exposes the agent interface for orchestration wiring.
"""

from app.agents.base_agent import BaseAgent
from app.config import Settings
from app.orchestration.state import ResearchState
from app.services.ai.client import LlmClient


class ResearchAgent(BaseAgent):
    """Stub research agent until Phase 2/3 implementation."""

    def __init__(self, llm_client: LlmClient, settings: Settings) -> None:
        super().__init__(name="research", llm_client=llm_client, settings=settings)

    async def _execute(self, state: ResearchState) -> ResearchState:
        """No-op progression placeholder."""
        state.status = "researching"
        return state
