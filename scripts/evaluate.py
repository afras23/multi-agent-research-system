#!/usr/bin/env python3
"""
Offline evaluation harness: runs the research pipeline with a mocked LLM.

Usage::

    python scripts/evaluate.py
    python scripts/evaluate.py --test-set eval/test_set.jsonl --output eval/results/eval_run.json
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from app.config import Settings
from app.eval.grading import citation_count, section_completeness_result, topic_coverage_ratio
from app.eval.pipeline import (
    load_test_cases,
    run_single_eval_case,
    total_cost_usd,
)
from app.eval.schemas import EvalFailure, EvaluationReport

logger = logging.getLogger(__name__)

_AGENT_SHORT = {
    "research_agent": "research",
    "analysis_agent": "analysis",
    "writer_agent": "writer",
    "quality_agent": "quality",
}


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _default_output_path(root: Path) -> Path:
    day = datetime.now(UTC).date().isoformat()
    out_dir = root / "eval" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"eval_{day}.json"


async def run_evaluation(test_set_path: Path, output_path: Path) -> EvaluationReport:
    """
    Run all evaluation cases and write the aggregated JSON report.

    Args:
        test_set_path: Path to ``test_set.jsonl``.
        output_path: Destination JSON file (parent directory is created if needed).

    Returns:
        Parsed :class:`EvaluationReport` matching the written file.
    """
    cases = load_test_cases(test_set_path)
    settings = Settings(
        database_url="postgresql+asyncpg://eval:eval@127.0.0.1:5432/eval",
        openai_api_key="eval-mock",
        max_parallel_agents=1,
        max_daily_cost_usd=10_000.0,
        max_request_cost_usd=500.0,
    )

    n = len(cases)
    quality_scores: list[float] = []
    section_counts: list[float] = []
    topic_ratios: list[float] = []
    citation_counts: list[float] = []
    task_costs: list[float] = []
    latencies: list[float] = []
    failures: list[EvalFailure] = []
    passed_n = 0

    per_agent_cost_lists: dict[str, list[float]] = defaultdict(list)

    for case in cases:
        state, reasons, latency_ms = await run_single_eval_case(case, settings=settings)
        report = state.report_draft or ""

        qs = state.quality_score.overall_score if state.quality_score else 0.0
        quality_scores.append(qs)

        _, present_n, _ = section_completeness_result(report, case.expected_sections)
        section_counts.append(float(present_n))

        tr = topic_coverage_ratio(report, case.expected_topics)
        topic_ratios.append(tr)

        citation_counts.append(float(citation_count(report)))

        tc = total_cost_usd(state)
        task_costs.append(tc)
        latencies.append(latency_ms)

        for raw_name, entry in state.agent_costs.items():
            short = _AGENT_SHORT.get(raw_name, raw_name)
            per_agent_cost_lists[short].append(entry.total_cost_usd)

        if reasons:
            failures.append(
                EvalFailure(company=case.company_name, reason="; ".join(reasons)),
            )
        else:
            passed_n += 1

    pass_rate = passed_n / n if n else 0.0

    def _avg(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    cost_by_agent = {
        name: round(sum(vals) / len(vals), 6) for name, vals in per_agent_cost_lists.items()
    }

    report_model = EvaluationReport(
        timestamp=datetime.now(UTC).isoformat(),
        model=settings.ai_model,
        test_cases=n,
        pass_rate=round(pass_rate, 4),
        avg_quality_score=round(_avg(quality_scores), 2),
        avg_sections_present=round(_avg(section_counts), 2),
        avg_topic_coverage=round(_avg(topic_ratios), 4),
        avg_citation_count=round(_avg(citation_counts), 2),
        avg_cost_per_task_usd=round(_avg(task_costs), 4),
        avg_latency_ms=round(_avg(latencies), 2),
        cost_by_agent=cost_by_agent,
        failures=failures,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        report_model.model_dump_json(indent=2),
        encoding="utf-8",
    )
    logger.info(
        "Evaluation finished",
        extra={
            "output_path": str(output_path),
            "test_cases": n,
            "pass_rate": report_model.pass_rate,
        },
    )
    return report_model


def main() -> None:
    """CLI entrypoint for ``make evaluate``."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for noisy in ("app", "agent", "httpx", "httpcore", "openai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    logging.getLogger("app.eval.pipeline").setLevel(logging.ERROR)

    root = _project_root()
    default_ts = root / "eval" / "test_set.jsonl"
    parser = argparse.ArgumentParser(description="Run multi-agent research evaluation harness.")
    parser.add_argument(
        "--test-set",
        type=Path,
        default=default_ts,
        help="Path to test_set.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON path (default: eval/results/eval_YYYY-MM-DD.json)",
    )
    args = parser.parse_args()
    out = args.output if args.output is not None else _default_output_path(root)

    asyncio.run(run_evaluation(args.test_set.resolve(), out.resolve()))


if __name__ == "__main__":
    main()
