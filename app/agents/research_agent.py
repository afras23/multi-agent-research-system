"""
Research agent — plans areas and extracts structured findings via the LLM.
"""

from __future__ import annotations

import asyncio
import logging

from pydantic import ValidationError

from app.agents.base_agent import BaseAgent
from app.config import Settings
from app.orchestration.state import ResearchFinding, ResearchState
from app.services.ai.client import LlmCallResult, LlmClient
from app.services.ai.json_utils import parse_json_array, parse_json_object
from app.services.ai.prompt_loader import get_prompt

logger = logging.getLogger(__name__)


def _default_areas() -> list[str]:
    return ["Strategic overview", "Competitive landscape", "Financial outlook"]


def _parse_area_strings(raw: str) -> list[str]:
    areas = [str(a).strip() for a in parse_json_array(raw) if str(a).strip()]
    return areas if areas else _default_areas()


def _industry_line(state: ResearchState) -> str:
    if state.industry_context and state.industry_context.strip():
        return state.industry_context.strip()
    return "Not specified."


def _build_finding(area: str, raw: str) -> ResearchFinding | None:
    payload = parse_json_object(raw)
    if not payload:
        return None
    payload.setdefault("topic", area)
    payload.setdefault("summary", "No summary returned by the model.")
    payload.setdefault("source", "Simulated industry database")
    payload.setdefault("confidence", 0.5)
    payload.setdefault("raw_text", raw)
    try:
        return ResearchFinding.model_validate(payload)
    except ValidationError:
        logger.warning(
            "Research finding validation failed",
            extra={"area": area, "preview": raw[:200]},
        )
        return None


class ResearchAgent(BaseAgent):
    """Plans research areas and extracts structured findings per area."""

    def __init__(self, llm_client: LlmClient, settings: Settings) -> None:
        super().__init__(name="research_agent", llm_client=llm_client, settings=settings)

    async def _one_area(
        self,
        state: ResearchState,
        area: str,
    ) -> tuple[ResearchFinding, LlmCallResult | None]:
        sys_f, usr_f, pv_f = get_prompt(
            "research_finding",
            "v1",
            company=state.company_name,
            research_brief=state.research_brief,
            industry_context=_industry_line(state),
            area=area,
        )
        finding_llm = await self._llm.complete(
            system_prompt=sys_f,
            user_prompt=usr_f,
            prompt_version=pv_f,
        )
        finding = _build_finding(area, finding_llm.content)
        if finding is None:
            finding = ResearchFinding(
                topic=area,
                summary="Insufficient structured output; placeholder summary.",
                source="Simulated fallback source",
                source_url=None,
                confidence=0.3,
                raw_text=finding_llm.content or "",
            )
        return finding, finding_llm

    async def _bounded_area(
        self,
        state: ResearchState,
        area: str,
        semaphore: asyncio.Semaphore,
    ) -> tuple[ResearchFinding, LlmCallResult | None]:
        async with semaphore:
            try:
                return await asyncio.wait_for(
                    self._one_area(state, area),
                    timeout=float(self._settings.research_subtask_timeout_seconds),
                )
            except TimeoutError:
                logger.warning(
                    "Research subtask timed out",
                    extra={
                        "task_id": str(state.task_id),
                        "area": area,
                        "timeout_seconds": self._settings.research_subtask_timeout_seconds,
                    },
                )
                placeholder = ResearchFinding(
                    topic=area,
                    summary=(
                        "This information area timed out before the model returned a full result."
                    ),
                    source="Simulated timeout placeholder",
                    source_url=None,
                    confidence=0.2,
                    raw_text="",
                )
                return placeholder, None

    async def _execute(self, state: ResearchState) -> ResearchState:
        state.status = "researching"
        state.research_findings = []
        sys_a, usr_a, pv_a = get_prompt(
            "research_areas",
            "v1",
            company=state.company_name,
            research_brief=state.research_brief,
            industry_context=_industry_line(state),
        )
        areas_llm = await self._llm.complete(
            system_prompt=sys_a,
            user_prompt=usr_a,
            prompt_version=pv_a,
        )
        self._track_cost(state, areas_llm)
        areas = _parse_area_strings(areas_llm.content)
        if not areas:
            areas = _default_areas()

        semaphore = asyncio.Semaphore(self._settings.max_parallel_agents)
        tasks = [self._bounded_area(state, area, semaphore) for area in areas]
        gathered = await asyncio.gather(*tasks, return_exceptions=True)
        for entry in gathered:
            if isinstance(entry, tuple):
                finding, llm_res = entry
            else:
                logger.error(
                    "Research subtask failed",
                    extra={
                        "task_id": str(state.task_id),
                        "error": repr(entry),
                    },
                )
                state.research_findings.append(
                    ResearchFinding(
                        topic="unknown",
                        summary="Subtask failed; placeholder summary.",
                        source="Simulated error fallback",
                        source_url=None,
                        confidence=0.1,
                        raw_text="",
                    ),
                )
                continue
            if llm_res is not None:
                self._track_cost(state, llm_res)
            state.research_findings.append(finding)

        msg = (
            f"Research completed: {len(state.research_findings)} findings on {state.company_name}"
        )
        self._logger.info(
            msg,
            extra={
                "task_id": str(state.task_id),
                "findings_count": len(state.research_findings),
            },
        )
        self._append_agent_message(state, msg)
        return state
