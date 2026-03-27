"""
Test helpers: build ``AsyncOpenAI``-shaped mocks with ``chat.completions.create``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock


def mock_openai_client(completions_create: AsyncMock) -> MagicMock:
    """Return a mock client whose ``chat.completions.create`` is ``completions_create``."""
    client = MagicMock()
    chat = MagicMock()
    completions = MagicMock()
    completions.create = completions_create
    chat.completions = completions
    client.chat = chat
    return client
