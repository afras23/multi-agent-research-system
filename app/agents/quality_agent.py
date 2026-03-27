"""
Quality agent — validates draft reports against rubric and policies.

Checks are expanded in Phase 5; stub keeps orchestration types stable.
"""

from app.agents.base_agent import BaseAgent
from app.config import Settings
from app.orchestration.state import ResearchState
from app.services.ai.client import LlmClient


class QualityAgent(BaseAgent):
    """Stub quality agent."""

    def __init__(self, llm_client: LlmClient, settings: Settings) -> None:
        super().__init__(name="quality", llm_client=llm_client, settings=settings)

    async def _execute(self, state: ResearchState) -> ResearchState:
        """No-op progression placeholder."""
        state.status = "quality_check"
        return state
