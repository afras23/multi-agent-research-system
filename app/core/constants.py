"""
Application-wide constants.

Values that are not environment-specific live here; pricing may be overridden
per model in the LLM client.
"""

from typing import Final

API_PREFIX: Final[str] = "/api/v1"

# USD per 1M tokens — update when provider pricing changes
MODEL_INPUT_COST_PER_MILLION_USD: Final[dict[str, float]] = {
    "gpt-4o": 2.5,
    "gpt-4o-mini": 0.15,
    "gpt-4-turbo": 10.0,
}

MODEL_OUTPUT_COST_PER_MILLION_USD: Final[dict[str, float]] = {
    "gpt-4o": 10.0,
    "gpt-4o-mini": 0.6,
    "gpt-4-turbo": 30.0,
}

CIRCUIT_BREAKER_FAILURE_THRESHOLD: Final[int] = 5
CIRCUIT_BREAKER_WINDOW_SECONDS: Final[int] = 60

LLM_MAX_RETRIES: Final[int] = 3
