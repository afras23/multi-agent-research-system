"""
Research agent — plans areas and extracts structured findings via the LLM.
"""

from __future__ import annotations

import logging

from pydantic import ValidationError

from app.agents.base_agent import BaseAgent
from app.config import Settings
from app.orchestration.state import ResearchFinding, ResearchState
from app.services.ai.client import LlmClient
from app.services.ai.json_utils import parse_json_array, parse_json_object
from app.services.ai.prompt_loader import get_prompt

logger = logging.getLogger(__name__)


def _default_areas() -> list[str]:
    return ["Strategic overview", "Competitive landscape", "Financial outlook"]


def _parse_area_strings(raw: str) -> list[str]:
    areas = [str(a).strip() for a in parse_json_array(raw) if str(a).strip()]
    return areas if areas else _default_areas()


def _build_finding(area: str, raw: str, company_name: str) -> ResearchFinding | None:
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

    async def _execute(self, state: ResearchState) -> ResearchState:
        state.status = "researching"
        state.research_findings = []
        sys_a, usr_a, pv_a = get_prompt(
            "research_areas",
            "v1",
            company=state.company_name,
            research_brief=state.research_brief,
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
        for area in areas:
            sys_f, usr_f, pv_f = get_prompt(
                "research_finding",
                "v1",
                company=state.company_name,
                research_brief=state.research_brief,
                area=area,
            )
            finding_llm = await self._llm.complete(
                system_prompt=sys_f,
                user_prompt=usr_f,
                prompt_version=pv_f,
            )
            self._track_cost(state, finding_llm)
            finding = _build_finding(area, finding_llm.content, state.company_name)
            if finding is None:
                finding = ResearchFinding(
                    topic=area,
                    summary="Insufficient structured output; placeholder summary.",
                    source="Simulated fallback source",
                    source_url=None,
                    confidence=0.3,
                    raw_text=finding_llm.content or "",
                )
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
