"""
Quality agent — scores draft reports against a rubric and lists issues.
"""

from __future__ import annotations

import logging

from pydantic import ValidationError

from app.agents.base_agent import BaseAgent
from app.config import Settings
from app.orchestration.state import QualityScore, ResearchState
from app.services.ai.client import LlmClient
from app.services.ai.json_utils import parse_json_object
from app.services.ai.prompt_loader import get_prompt

logger = logging.getLogger(__name__)


def _findings_summary(state: ResearchState) -> str:
    return "\n".join(f"- {f.topic}: {f.summary}" for f in state.research_findings)


class QualityAgent(BaseAgent):
    """Evaluates draft quality and recommends next action."""

    def __init__(self, llm_client: LlmClient, settings: Settings) -> None:
        super().__init__(name="quality_agent", llm_client=llm_client, settings=settings)

    async def _execute(self, state: ResearchState) -> ResearchState:
        state.status = "quality_check"
        report_body = state.report_draft or ""
        sys_p, usr_p, pv = get_prompt(
            "quality_rubric",
            "v1",
            report_body=report_body,
            findings_block=_findings_summary(state) or "(none)",
        )
        llm = await self._llm.complete(
            system_prompt=sys_p,
            user_prompt=usr_p,
            prompt_version=pv,
        )
        self._track_cost(state, llm)
        payload = parse_json_object(llm.content)
        try:
            state.quality_score = QualityScore.model_validate(payload)
        except ValidationError:
            logger.warning(
                "Quality JSON validation failed, using minimal score",
                extra={"task_id": str(state.task_id), "preview": llm.content[:200]},
            )
            state.quality_score = QualityScore(
                overall_score=0.0,
                source_coverage=0.0,
                completeness=0.0,
                accuracy=0.0,
                coherence=0.0,
                issues=[],
                recommendation="revise",
            )
        score = state.quality_score.overall_score
        issues_n = len(state.quality_score.issues)
        msg = f"Quality check: score={score}, issues={issues_n}"
        self._logger.info(
            msg,
            extra={
                "task_id": str(state.task_id),
                "overall_score": score,
                "issues_count": issues_n,
            },
        )
        self._append_agent_message(state, msg)
        return state
