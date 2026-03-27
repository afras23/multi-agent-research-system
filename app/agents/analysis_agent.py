"""
Analysis agent — synthesises themes, risks, and gaps from research findings.
"""

from __future__ import annotations

import logging

from pydantic import ValidationError

from app.agents.base_agent import BaseAgent
from app.config import Settings
from app.orchestration.state import AnalysisResult, ResearchState
from app.services.ai.client import LlmClient
from app.services.ai.json_utils import parse_json_object
from app.services.ai.prompt_loader import get_prompt

logger = logging.getLogger(__name__)


def _findings_block(state: ResearchState) -> str:
    lines: list[str] = []
    for finding in state.research_findings:
        lines.append(
            f"- {finding.topic}: {finding.summary} (source: {finding.source}, "
            f"confidence={finding.confidence})",
        )
    return "\n".join(lines) if lines else "(no findings)"


class AnalysisAgent(BaseAgent):
    """Structured synthesis from research findings."""

    def __init__(self, llm_client: LlmClient, settings: Settings) -> None:
        super().__init__(name="analysis_agent", llm_client=llm_client, settings=settings)

    async def _execute(self, state: ResearchState) -> ResearchState:
        state.status = "analyzing"
        block = _findings_block(state)
        sys_p, usr_p, pv = get_prompt(
            "analysis_structured",
            "v1",
            company=state.company_name,
            findings_block=block,
        )
        llm = await self._llm.complete(
            system_prompt=sys_p,
            user_prompt=usr_p,
            prompt_version=pv,
        )
        self._track_cost(state, llm)
        payload = parse_json_object(llm.content)
        try:
            state.analysis_result = AnalysisResult.model_validate(payload)
        except ValidationError:
            logger.warning(
                "Analysis JSON validation failed, using minimal result",
                extra={"task_id": str(state.task_id), "preview": llm.content[:200]},
            )
            state.analysis_result = AnalysisResult(
                key_themes=["Analysis parsing failed — manual review required."],
                competitive_position="Unable to synthesise competitive position from model output.",
                financial_outlook="Unable to synthesise financial outlook from model output.",
                gaps_identified=["Model output did not match the expected schema."],
            )
        themes_n = len(state.analysis_result.key_themes)
        risks_n = len(state.analysis_result.risks)
        msg = f"Analysis completed: {themes_n} themes, {risks_n} risks identified"
        self._logger.info(
            msg,
            extra={
                "task_id": str(state.task_id),
                "themes": themes_n,
                "risks": risks_n,
            },
        )
        self._append_agent_message(state, msg)
        return state
