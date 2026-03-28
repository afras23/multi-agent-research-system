"""
State persistence, serialisation, and concurrent update safety.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.orchestration.checkpoints import CheckpointManager
from app.orchestration.state import AnalysisResult, ResearchFinding, ResearchState, utc_now
from app.repositories.task_repo import TaskRepository


def _state() -> ResearchState:
    return ResearchState(
        task_id=uuid4(),
        company_name="Co",
        research_brief="B",
        status="researching",
        created_at=utc_now(),
        updated_at=utc_now(),
    )


@pytest.mark.asyncio
async def test_state_persisted_after_each_agent() -> None:
    snapshots: list[dict[str, object]] = []

    async def save_side(task_id, st: ResearchState) -> None:
        snapshots.append(st.model_dump(mode="json"))

    repo = MagicMock(spec=TaskRepository)
    repo.save_state = AsyncMock(side_effect=save_side)

    st = _state()
    st.research_findings = [
        ResearchFinding(
            topic="A",
            summary="s",
            source="S",
            source_url=None,
            confidence=0.5,
            raw_text="r",
        ),
    ]
    await repo.save_state(st.task_id, st)
    st.analysis_result = AnalysisResult(
        key_themes=["k"],
        competitive_position="c",
        financial_outlook="f",
    )
    await repo.save_state(st.task_id, st)
    assert len(snapshots) == 2
    assert snapshots[0].get("analysis_result") is None
    assert snapshots[1].get("analysis_result") is not None


@pytest.mark.asyncio
async def test_state_resumable_after_checkpoint() -> None:
    repo = MagicMock(spec=TaskRepository)
    st = _state()
    st.status = "awaiting_approval"
    st.checkpoint_status = "pending"
    repo.load_state = AsyncMock(return_value=st.model_copy(deep=True))
    repo.save_state = AsyncMock()
    cm = CheckpointManager(repo)
    approved = await cm.process_approval(st.task_id, True, "reviewer@example.com")
    assert approved.checkpoint_status == "approved"
    assert approved.status == "writing"
    loaded = await repo.load_state(st.task_id)
    assert loaded.checkpoint_reviewer == "reviewer@example.com"


def test_state_serialization_roundtrip() -> None:
    original = _state()
    original.research_findings = [
        ResearchFinding(
            topic="T",
            summary="S",
            source="SRC",
            source_url=None,
            confidence=0.7,
            raw_text="{}",
        ),
    ]
    payload = original.model_dump(mode="json")
    restored = ResearchState.model_validate(payload)
    assert restored.task_id == original.task_id
    assert restored.research_findings[0].topic == "T"


@pytest.mark.asyncio
async def test_concurrent_state_updates_no_corruption() -> None:
    lock = asyncio.Lock()
    merged: dict[str, float] = {"research_agent": 0.0}

    async def worker(agent: str, amount: float) -> None:
        for _ in range(20):
            async with lock:
                merged[agent] = merged.get(agent, 0.0) + amount
            await asyncio.sleep(0)

    await asyncio.gather(
        worker("research_agent", 0.01),
        worker("analysis_agent", 0.02),
    )
    assert abs(merged["research_agent"] - 0.2) < 0.001
    assert abs(merged["analysis_agent"] - 0.4) < 0.001
