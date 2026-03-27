"""
Abstract base class for research pipeline agents.

Provides timeout handling, structured logging, and LLM cost attribution on
``ResearchState``.
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod

from app.config import Settings
from app.core.exceptions import AgentError, AgentTimeoutError
from app.orchestration.state import AgentCostEntry, ResearchState, utc_now
from app.services.ai.client import LlmCallResult, LlmClient


class BaseAgent(ABC):
    """Abstract base for all research agents."""

    def __init__(self, name: str, llm_client: LlmClient, settings: Settings) -> None:
        self.name = name
        self._llm = llm_client
        self._settings = settings
        self._logger = logging.getLogger(f"agent.{name}")

    async def run(self, state: ResearchState) -> ResearchState:
        """Execute agent with timeout, cost tracking, and error handling."""
        start = time.monotonic()
        try:
            result = await asyncio.wait_for(
                self._execute(state),
                timeout=self._settings.agent_timeout_seconds,
            )
            latency_ms = (time.monotonic() - start) * 1000.0
            self._log_completion(state, latency_ms)
            return result
        except TimeoutError:
            self._logger.error(
                "Agent timed out",
                extra={
                    "agent": self.name,
                    "task_id": str(state.task_id),
                    "timeout_seconds": self._settings.agent_timeout_seconds,
                },
            )
            state.errors.append(
                f"{self.name} timed out after {self._settings.agent_timeout_seconds}s",
            )
            raise AgentTimeoutError(self.name) from None
        except AgentTimeoutError:
            raise
        except AgentError:
            raise
        except Exception as exc:  # noqa: BLE001
            self._logger.error(
                "Agent failed",
                extra={
                    "agent": self.name,
                    "task_id": str(state.task_id),
                    "error": str(exc),
                },
            )
            state.errors.append(f"{self.name} failed: {exc!s}")
            raise AgentError(self.name, str(exc)) from exc

    @abstractmethod
    async def _execute(self, state: ResearchState) -> ResearchState:
        """Implement agent-specific logic. Called by run() with timeout."""
        ...

    def _track_cost(self, state: ResearchState, llm_result: LlmCallResult) -> None:
        """Attribute LLM usage to this agent in orchestration state."""
        previous = state.agent_costs.get(self.name, AgentCostEntry())
        merged = AgentCostEntry(
            total_cost_usd=previous.total_cost_usd + llm_result.cost_usd,
            input_tokens=previous.input_tokens + llm_result.input_tokens,
            output_tokens=previous.output_tokens + llm_result.output_tokens,
        )
        state.agent_costs[self.name] = merged
        state.updated_at = utc_now()

    def _log_completion(self, state: ResearchState, latency_ms: float) -> None:
        """Emit a structured completion log for observability."""
        self._logger.info(
            "Agent step completed",
            extra={
                "agent": self.name,
                "task_id": str(state.task_id),
                "latency_ms": latency_ms,
            },
        )
