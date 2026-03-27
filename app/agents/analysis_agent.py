"""
Analysis agent — synthesises themes and risks from research artefacts.

Implementation arrives in later phases; the class is wired for orchestration.
"""

from app.agents.base_agent import BaseAgent
from app.config import Settings
from app.orchestration.state import ResearchState
from app.services.ai.client import LlmClient


class AnalysisAgent(BaseAgent):
    """Stub analysis agent."""

    def __init__(self, llm_client: LlmClient, settings: Settings) -> None:
        super().__init__(name="analysis", llm_client=llm_client, settings=settings)

    async def _execute(self, state: ResearchState) -> ResearchState:
        """No-op progression placeholder."""
        state.status = "analyzing"
        return state
