"""
Writer agent — produces draft narrative from approved inputs.

Real prompting is introduced in Phase 5; this stub preserves interfaces.
"""

from app.agents.base_agent import BaseAgent
from app.config import Settings
from app.orchestration.state import ResearchState
from app.services.ai.client import LlmClient


class WriterAgent(BaseAgent):
    """Stub writer agent."""

    def __init__(self, llm_client: LlmClient, settings: Settings) -> None:
        super().__init__(name="writer", llm_client=llm_client, settings=settings)

    async def _execute(self, state: ResearchState) -> ResearchState:
        """No-op progression placeholder."""
        state.status = "writing"
        return state
