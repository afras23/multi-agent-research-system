"""
Run a single evaluation case through the real agent stack with a mocked OpenAI client.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.agents.analysis_agent import AnalysisAgent
from app.agents.quality_agent import QualityAgent
from app.agents.research_agent import ResearchAgent
from app.agents.writer_agent import WriterAgent
from app.config import Settings
from app.eval.checkpoint import EvaluationCheckpointManager
from app.eval.grading import section_completeness_result, topic_coverage_ratio
from app.eval.openai_mock import build_mock_openai_client
from app.eval.schemas import EvalTestCase
from app.orchestration.graph import GraphDependencies, build_research_graph
from app.orchestration.state import ResearchState, utc_now
from app.services.ai.client import LlmClient

logger = logging.getLogger(__name__)

EVAL_QUALITY_FAIL_COMPANY = "EvalQualityGateFail"
EVAL_SECTION_OMIT_COMPANY = "EvalSectionOmitCo"


def load_test_cases(test_set_path: Path) -> list[EvalTestCase]:
    """
    Load evaluation cases from a JSONL file.

    Args:
        test_set_path: Path to ``test_set.jsonl``.

    Returns:
        Parsed test cases in file order.

    Raises:
        ValueError: When the file is empty or a line is invalid JSON.
    """
    lines = test_set_path.read_text(encoding="utf-8").strip().splitlines()
    if not lines:
        msg = "test set file is empty"
        raise ValueError(msg)
    cases: list[EvalTestCase] = []
    for line in lines:
        row = json.loads(line)
        cases.append(EvalTestCase.model_validate(row))
    return cases


def _target_quality_score(case: EvalTestCase) -> float:
    if case.company_name == EVAL_QUALITY_FAIL_COMPANY:
        return 50.0
    return float(max(case.expected_quality_score_min + 5.0, 65.0))


def build_mock_completion_contents(case: EvalTestCase) -> list[str]:
    """
    Build deterministic LLM reply strings for one evaluation case.

    Shapes match ``ResearchAgent``, ``AnalysisAgent``, ``WriterAgent``, and
    ``QualityAgent`` JSON / Markdown expectations.
    """
    topics = case.expected_topics
    if not topics:
        topics = ["market context"]
    areas = ["Strategic overview", "Market dynamics", "Financial signals"]
    contents: list[str] = [json.dumps(areas)]
    for idx, area in enumerate(areas):
        t = topics[idx % len(topics)]
        finding = {
            "topic": area,
            "summary": f"Analysis of {t} for {case.company_name}.",
            "source": f"Source-{idx + 1}",
            "source_url": None,
            "confidence": 0.75,
            "raw_text": "",
        }
        contents.append(json.dumps(finding))

    analysis = {
        "key_themes": topics[: min(4, len(topics))],
        "risks": [
            {
                "description": "Sample competitive risk",
                "severity": "medium",
                "source": areas[0],
            },
        ],
        "opportunities": [
            {
                "description": "Growth opportunity",
                "rationale": f"Linked to {topics[0]}",
            },
        ],
        "competitive_position": f"Discusses {topics[0]} and peers.",
        "financial_outlook": f"Discusses revenue and {topics[-1] if topics else 'outlook'}.",
        "gaps_identified": [],
        "contradictions": [],
    }
    contents.append(json.dumps(analysis))

    sections_for_report = list(case.expected_sections)
    if case.company_name == EVAL_SECTION_OMIT_COMPANY and sections_for_report:
        sections_for_report = sections_for_report[:-1]

    report_parts = [
        f"# Research Report: {case.company_name}",
        "## Executive Summary",
        f"This report covers {', '.join(topics)}. [Source: 1]",
    ]
    for sec in sections_for_report:
        tref = topics[0] if topics else "market"
        report_parts.append(f"## {sec}\nDetails on {tref} and operations. [Source: 2]")
    report_md = "\n\n".join(report_parts)
    contents.append(report_md)

    q = _target_quality_score(case)
    quality_payload = {
        "overall_score": q,
        "source_coverage": min(100.0, q + 5.0),
        "completeness": min(100.0, q + 3.0),
        "accuracy": min(100.0, q + 2.0),
        "coherence": min(100.0, q + 4.0),
        "issues": [],
        "recommendation": "approve",
    }
    contents.append(json.dumps(quality_payload))
    return contents


def _mock_openai_for_contents(contents: list[str]) -> MagicMock:
    responses = [
        MagicMock(
            choices=[MagicMock(message=MagicMock(content=c))],
            usage=MagicMock(prompt_tokens=20, completion_tokens=20),
        )
        for c in contents
    ]
    return build_mock_openai_client(AsyncMock(side_effect=responses))


def _eval_settings() -> Settings:
    """Settings tuned for sequential, cost-tolerant offline runs."""
    return Settings(
        database_url="postgresql+asyncpg://eval:eval@127.0.0.1:5432/eval",
        openai_api_key="eval-mock",
        max_parallel_agents=1,
        max_daily_cost_usd=10_000.0,
        max_request_cost_usd=500.0,
    )


def _mock_task_store(initial: ResearchState) -> tuple[dict[str, ResearchState], MagicMock]:
    store: dict[str, ResearchState] = {str(initial.task_id): initial.model_copy(deep=True)}

    async def load_state(task_id: object) -> ResearchState:
        return store[str(task_id)].model_copy(deep=True)

    async def save_state(task_id: object, st: ResearchState) -> None:
        store[str(task_id)] = st.model_copy(deep=True)

    repo = MagicMock()
    repo.load_state = AsyncMock(side_effect=load_state)
    repo.save_state = AsyncMock(side_effect=save_state)
    return store, repo


def grade_case(case: EvalTestCase, state: ResearchState) -> tuple[bool, list[str]]:
    """
    Apply pass/fail rules: quality floor, all sections, >=80% topic coverage.

    Returns:
        (passed, failure reasons).
    """
    reasons: list[str] = []
    report = state.report_draft or ""
    qs = state.quality_score.overall_score if state.quality_score else 0.0
    if qs < case.expected_quality_score_min:
        reasons.append(
            f"quality score {qs:.1f} below minimum {case.expected_quality_score_min:.1f}",
        )
    complete, _, missing = section_completeness_result(report, case.expected_sections)
    if not complete and missing:
        reasons.append(f"missing section: {missing[0]}")
    ratio = topic_coverage_ratio(report, case.expected_topics)
    if ratio < 0.8:
        reasons.append(f"topic coverage {ratio:.2f} below 0.80")
    return (len(reasons) == 0, reasons)


async def run_single_eval_case(
    case: EvalTestCase,
    *,
    settings: Settings | None = None,
) -> tuple[ResearchState, list[str], float]:
    """
    Execute the LangGraph pipeline once with a mocked provider.

    Args:
        case: Input brief and expectations.
        settings: Optional settings; defaults to evaluation-friendly values.

    Returns:
        Final orchestration state, failure reasons (empty if pass), and wall-clock
        latency for the full graph run in milliseconds.
    """
    cfg_settings = settings or _eval_settings()
    contents = build_mock_completion_contents(case)
    llm = LlmClient(cfg_settings, openai_client=_mock_openai_for_contents(contents))
    llm.reset_daily_cost_for_tests()

    task_id = uuid4()
    initial = ResearchState(
        task_id=task_id,
        company_name=case.company_name,
        research_brief=case.research_brief,
        status="pending",
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    _, repo = _mock_task_store(initial)
    deps = GraphDependencies(
        research_agent=ResearchAgent(llm, cfg_settings),
        analysis_agent=AnalysisAgent(llm, cfg_settings),
        writer_agent=WriterAgent(llm, cfg_settings),
        quality_agent=QualityAgent(llm, cfg_settings),
        checkpoint_manager=EvaluationCheckpointManager(repo),
    )
    graph = build_research_graph(deps)
    invoke_cfg = {"configurable": {"thread_id": str(task_id)}}
    payload = {"research_state": initial.model_dump(mode="json")}

    t0 = time.perf_counter()
    out = await graph.ainvoke(payload, invoke_cfg)
    latency_ms = (time.perf_counter() - t0) * 1000.0

    state = ResearchState.model_validate(out["research_state"])
    _, reasons = grade_case(case, state)

    if reasons:
        logger.warning(
            "Evaluation case did not pass",
            extra={
                "company": case.company_name,
                "reasons": reasons,
            },
        )
    return (state, reasons, latency_ms)


def per_agent_costs(state: ResearchState) -> dict[str, float]:
    """Return USD totals per agent name."""
    return {k: round(v.total_cost_usd, 6) for k, v in state.agent_costs.items()}


def total_cost_usd(state: ResearchState) -> float:
    """Sum of per-agent USD costs."""
    return round(sum(per_agent_costs(state).values()), 6)
