"""
Agent message persistence repository.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_message import AgentMessageRow
from app.orchestration.state import AgentMessage


class MessageRepository:
    """Data access for ``agent_messages`` rows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append_message(
        self,
        *,
        task_id: UUID,
        agent_name: str,
        message_type: str,
        content: str,
        tokens_used: int,
        cost_usd: float,
        latency_ms: float,
    ) -> AgentMessageRow:
        """Persist a single agent message row."""
        row = AgentMessageRow(
            id=uuid4(),
            task_id=task_id,
            agent_name=agent_name,
            message_type=message_type,
            content=content,
            tokens_used=tokens_used,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def log_messages(self, task_id: UUID, messages: list[AgentMessage]) -> None:
        """Persist a batch of orchestration ``AgentMessage`` records."""
        for msg in messages:
            await self.append_message(
                task_id=task_id,
                agent_name=msg.agent_name,
                message_type=msg.message_type,
                content=msg.content,
                tokens_used=0,
                cost_usd=0.0,
                latency_ms=0.0,
            )

    async def get_messages(self, task_id: UUID) -> list[AgentMessage]:
        """Load all messages for a task ordered by creation time."""
        stmt = (
            select(AgentMessageRow)
            .where(AgentMessageRow.task_id == task_id)
            .order_by(AgentMessageRow.created_at.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        result: list[AgentMessage] = []
        for row in rows:
            result.append(
                AgentMessage.model_validate(
                    {
                        "message_id": row.id,
                        "agent_name": row.agent_name,
                        "message_type": row.message_type,
                        "content": row.content,
                    },
                ),
            )
        return result
