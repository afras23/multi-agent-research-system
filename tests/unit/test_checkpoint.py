"""
Tests for ``CheckpointManager`` and task persistence hooks.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.orchestration.checkpoints import CheckpointManager
from app.orchestration.state import ResearchState, utc_now


def _state() -> ResearchState:
    return ResearchState(
        task_id=uuid4(),
        company_name="Co",
        research_brief="B",
        status="analyzing",
        created_at=utc_now(),
        updated_at=utc_now(),
    )


@pytest.mark.asyncio
async def test_pause_sets_awaiting_approval() -> None:
    store: dict[str, ResearchState] = {}

    async def save_state(tid, st: ResearchState) -> None:
        store[str(tid)] = st

    repo = MagicMock()
    repo.save_state = AsyncMock(side_effect=save_state)
    cm = CheckpointManager(repo)
    st = _state()
    out = await cm.pause_for_approval(st)
    assert out.checkpoint_status == "pending"
    assert out.status == "awaiting_approval"
    repo.save_state.assert_awaited()


@pytest.mark.asyncio
async def test_approve_resumes_pipeline() -> None:
    tid = uuid4()
    base = _state()
    base.task_id = tid
    store = {str(tid): base}

    async def load_state(task_id):
        return store[str(task_id)].model_copy(deep=True)

    async def save_state(task_id, st: ResearchState) -> None:
        store[str(task_id)] = st

    repo = MagicMock()
    repo.load_state = AsyncMock(side_effect=load_state)
    repo.save_state = AsyncMock(side_effect=save_state)
    cm = CheckpointManager(repo)
    out = await cm.process_approval(tid, approved=True, reviewer="alice")
    assert out.checkpoint_status == "approved"
    assert out.status == "writing"
    assert out.checkpoint_reviewer == "alice"


@pytest.mark.asyncio
async def test_reject_sets_rejected_status() -> None:
    tid = uuid4()
    base = _state()
    base.task_id = tid
    store = {str(tid): base}

    async def load_state(task_id):
        return store[str(task_id)].model_copy(deep=True)

    async def save_state(task_id, st: ResearchState) -> None:
        store[str(task_id)] = st

    repo = MagicMock()
    repo.load_state = AsyncMock(side_effect=load_state)
    repo.save_state = AsyncMock(side_effect=save_state)
    cm = CheckpointManager(repo)
    out = await cm.process_approval(tid, approved=False, reviewer="bob")
    assert out.checkpoint_status == "rejected"
    assert out.status == "rejected"
