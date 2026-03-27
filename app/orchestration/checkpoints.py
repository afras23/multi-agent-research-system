"""
Checkpoint persistence helpers (stub).

PostgreSQL-backed checkpointing arrives in Phase 2/3.
"""

from __future__ import annotations

import logging
from uuid import UUID

logger = logging.getLogger(__name__)


async def save_checkpoint_stub(task_id: UUID) -> None:
    """Persist graph checkpoint — no-op in Phase 1."""
    logger.info(
        "Checkpoint save requested (stub)",
        extra={"task_id": str(task_id)},
    )
