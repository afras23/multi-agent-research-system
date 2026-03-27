"""
Agent message persistence repository.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_message import AgentMessageRow


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
