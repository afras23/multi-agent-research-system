"""
Minimal AsyncOpenAI-shaped mock for offline evaluation (no test framework imports).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock


def build_mock_openai_client(completions_create: AsyncMock) -> MagicMock:
    """
    Return a mock client whose ``chat.completions.create`` is ``completions_create``.

    Args:
        completions_create: Async mock returning OpenAI-shaped completion objects.

    Returns:
        MagicMock shaped like ``AsyncOpenAI``.
    """
    client = MagicMock()
    chat = MagicMock()
    completions = MagicMock()
    completions.create = completions_create
    chat.completions = completions
    client.chat = chat
    return client
