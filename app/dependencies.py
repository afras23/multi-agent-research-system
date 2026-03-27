"""
FastAPI dependency injection providers.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from functools import lru_cache
from typing import cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.session import get_db_session
from app.repositories.message_repo import MessageRepository
from app.repositories.task_repo import TaskRepository
from app.services.ai.client import LlmClient
from app.services.research_service import ResearchService


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()  # type: ignore[call-arg]


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a request-scoped async database session."""
    async for session in get_db_session():
        yield session


def get_llm_client(request: Request) -> LlmClient:
    """Return the shared LLM client from application state."""
    return cast(LlmClient, request.app.state.llm_client)


def get_task_repository(session: AsyncSession = Depends(get_db)) -> TaskRepository:
    """Build a task repository for the current session."""
    return TaskRepository(session)


def get_message_repository(session: AsyncSession = Depends(get_db)) -> MessageRepository:
    """Build a message repository for the current session."""
    return MessageRepository(session)


def get_research_service(
    task_repo: TaskRepository = Depends(get_task_repository),
    llm_client: LlmClient = Depends(get_llm_client),
) -> ResearchService:
    """Compose the research orchestration service."""
    return ResearchService(task_repo=task_repo, llm_client=llm_client)
