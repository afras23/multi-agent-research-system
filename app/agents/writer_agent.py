"""
Writer agent — produces a Markdown report with explicit source citations.
"""

from __future__ import annotations

import re

from app.agents.base_agent import BaseAgent
from app.config import Settings
from app.orchestration.state import ResearchState
from app.services.ai.client import LlmClient
from app.services.ai.prompt_loader import get_prompt


def _word_count(text: str) -> int:
    return len([w for w in text.split() if w])


def _citation_count(text: str) -> int:
    return len(re.findall(r"\[Source:", text, flags=re.IGNORECASE))


class WriterAgent(BaseAgent):
    """Drafts a structured Markdown report from research and analysis."""

    def __init__(self, llm_client: LlmClient, settings: Settings) -> None:
        super().__init__(name="writer_agent", llm_client=llm_client, settings=settings)

    async def _execute(self, state: ResearchState) -> ResearchState:
        state.status = "writing"
        findings_lines = "\n".join(
            f"- {f.topic}: {f.summary} [{f.source}]" for f in state.research_findings
        )
        analysis_block = (
            state.analysis_result.model_dump_json(indent=2) if state.analysis_result else "{}"
        )
        sys_p, usr_p, pv = get_prompt(
            "writer_report",
            "v1",
            company=state.company_name,
            research_brief=state.research_brief,
            findings_block=findings_lines or "(none)",
            analysis_block=analysis_block,
        )
        llm = await self._llm.complete(
            system_prompt=sys_p,
            user_prompt=usr_p,
            prompt_version=pv,
        )
        self._track_cost(state, llm)
        state.report_draft = llm.content or ""
        words = _word_count(state.report_draft)
        cites = _citation_count(state.report_draft)
        msg = f"Report drafted: {words} words, {cites} citations"
        self._logger.info(
            msg,
            extra={
                "task_id": str(state.task_id),
                "word_count": words,
                "citation_count": cites,
            },
        )
        self._append_agent_message(state, msg)
        return state
