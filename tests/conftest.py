"""
Shared pytest fixtures.
"""

from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key-for-ci")

import pytest
from app.config import Settings


@pytest.fixture
def test_settings() -> Settings:
    """Minimal settings safe for unit tests (no network)."""
    return Settings(
        database_url="postgresql+asyncpg://test:test@localhost:5432/test_db",
        openai_api_key="test-openai-key",
        ai_model="gpt-4o",
        max_daily_cost_usd=10.0,
        max_request_cost_usd=2.0,
        agent_timeout_seconds=120,
    )
