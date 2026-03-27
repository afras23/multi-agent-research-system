"""
Async OpenAI LLM client with retries, circuit breaker, and cost accounting.

All model calls should go through this wrapper so limits and observability stay
consistent.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections import deque
from datetime import UTC, date, datetime

import httpx
from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, RateLimitError
from pydantic import BaseModel, Field

from app.config import Settings
from app.core.constants import (
    CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    CIRCUIT_BREAKER_WINDOW_SECONDS,
    LLM_MAX_RETRIES,
    MODEL_INPUT_COST_PER_MILLION_USD,
    MODEL_OUTPUT_COST_PER_MILLION_USD,
)
from app.core.exceptions import CostLimitExceeded, RateLimitExceeded, RetryableError
from app.core.logging_config import get_correlation_id

logger = logging.getLogger(__name__)


class LlmCallResult(BaseModel):
    """Structured result from a single LLM invocation."""

    content: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: float
    model: str
    prompt_version: str = Field(default="unspecified")


class _SlidingWindowFailures:
    """Track failures in a sliding time window for circuit breaking."""

    def __init__(self, window_seconds: int, threshold: int) -> None:
        self._window_seconds = window_seconds
        self._threshold = threshold
        self._failure_times: deque[float] = deque()

    def record_failure(self) -> None:
        """Record a failed attempt at monotonic time."""
        self._failure_times.append(time.monotonic())
        self._trim(time.monotonic())

    def record_success(self) -> None:
        """Clear failures after a successful call."""
        self._failure_times.clear()

    def is_open(self) -> bool:
        """Return True if the circuit should reject calls."""
        now = time.monotonic()
        self._trim(now)
        return len(self._failure_times) >= self._threshold

    def _trim(self, now: float) -> None:
        while self._failure_times and now - self._failure_times[0] > self._window_seconds:
            self._failure_times.popleft()


def _utc_day() -> date:
    return datetime.now(UTC).date()


def _estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    in_rate = MODEL_INPUT_COST_PER_MILLION_USD.get(model, 2.5)
    out_rate = MODEL_OUTPUT_COST_PER_MILLION_USD.get(model, 10.0)
    return (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000.0


class LlmClient:
    """Unified async LLM client with cost limits and resilience controls."""

    def __init__(
        self,
        settings: Settings,
        *,
        openai_client: AsyncOpenAI | None = None,
    ) -> None:
        self._settings = settings
        self._client = openai_client or AsyncOpenAI(api_key=settings.openai_api_key)
        self._circuit = _SlidingWindowFailures(
            CIRCUIT_BREAKER_WINDOW_SECONDS,
            CIRCUIT_BREAKER_FAILURE_THRESHOLD,
        )
        self._cost_day: date | None = None
        self._daily_cost_usd: float = 0.0

    @property
    def daily_cost_usd(self) -> float:
        """Return total LLM spend for the current UTC day."""
        self._roll_daily_if_needed()
        return self._daily_cost_usd

    @property
    def max_daily_cost_usd(self) -> float:
        """Return configured daily cost budget (USD)."""
        return self._settings.max_daily_cost_usd

    def _roll_daily_if_needed(self) -> None:
        today = _utc_day()
        if self._cost_day != today:
            self._cost_day = today
            self._daily_cost_usd = 0.0

    def _assert_daily_budget_allows(self, increment_usd: float) -> None:
        self._roll_daily_if_needed()
        if self._daily_cost_usd >= self._settings.max_daily_cost_usd:
            raise CostLimitExceeded(
                current_cost_usd=self._daily_cost_usd,
                limit_usd=self._settings.max_daily_cost_usd,
                scope="daily",
            )
        projected = self._daily_cost_usd + increment_usd
        if projected > self._settings.max_daily_cost_usd:
            raise CostLimitExceeded(
                current_cost_usd=self._daily_cost_usd,
                limit_usd=self._settings.max_daily_cost_usd,
                scope="daily",
            )

    def _assert_request_cost_allowed(self, call_cost_usd: float) -> None:
        if call_cost_usd > self._settings.max_request_cost_usd:
            raise CostLimitExceeded(
                current_cost_usd=call_cost_usd,
                limit_usd=self._settings.max_request_cost_usd,
                scope="request",
            )

    async def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        prompt_version: str,
    ) -> LlmCallResult:
        """
        Run a chat completion with retries and full cost accounting.

        Args:
            system_prompt: Model system instructions.
            user_prompt: User content for the request.
            prompt_version: Prompt template version identifier for auditing.

        Returns:
            Parsed result with usage and timing metadata.

        Raises:
            CostLimitExceeded: When configured USD caps would be exceeded.
            RateLimitExceeded: When the provider signals rate limiting.
            RetryableError: When retries are exhausted for transient failures.
        """
        if self._circuit.is_open():
            logger.error(
                "LLM circuit breaker open",
                extra={
                    "correlation_id": get_correlation_id(),
                    "window_seconds": CIRCUIT_BREAKER_WINDOW_SECONDS,
                    "failure_threshold": CIRCUIT_BREAKER_FAILURE_THRESHOLD,
                },
            )
            raise RetryableError("LLM circuit breaker is open")

        last_error: Exception | None = None
        for attempt in range(1, LLM_MAX_RETRIES + 1):
            try:
                return await self._invoke_once(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    prompt_version=prompt_version,
                )
            except CostLimitExceeded:
                raise
            except RateLimitError as exc:
                self._circuit.record_failure()
                logger.warning(
                    "OpenAI rate limit",
                    extra={
                        "correlation_id": get_correlation_id(),
                        "attempt": attempt,
                    },
                )
                raise RateLimitExceeded(retry_after_seconds=None) from exc
            except (
                APITimeoutError,
                APIConnectionError,
                httpx.TimeoutException,
                httpx.ConnectError,
            ) as exc:
                last_error = exc
                self._circuit.record_failure()
                logger.warning(
                    "LLM transient failure",
                    extra={
                        "correlation_id": get_correlation_id(),
                        "attempt": attempt,
                        "error_type": type(exc).__name__,
                    },
                )
                if attempt >= LLM_MAX_RETRIES:
                    raise RetryableError("LLM request failed after retries") from exc
                await self._backoff(attempt)

        raise RetryableError("LLM request failed after retries") from last_error

    async def _invoke_once(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        prompt_version: str,
    ) -> LlmCallResult:
        self._roll_daily_if_needed()
        self._assert_daily_budget_allows(0.0)
        model = self._settings.ai_model
        start = time.perf_counter()
        response = await self._client.chat.completions.create(
            model=model,
            max_tokens=self._settings.ai_max_tokens,
            temperature=self._settings.ai_temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        latency_ms = (time.perf_counter() - start) * 1000.0
        choice = response.choices[0].message
        content = choice.content or ""
        usage = response.usage
        input_tokens = usage.prompt_tokens if usage is not None else 0
        output_tokens = usage.completion_tokens if usage is not None else 0
        cost_usd = _estimate_cost_usd(model, input_tokens, output_tokens)

        self._assert_daily_budget_allows(cost_usd)
        self._assert_request_cost_allowed(cost_usd)
        self._roll_daily_if_needed()
        self._daily_cost_usd += cost_usd
        self._circuit.record_success()

        result = LlmCallResult(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            model=model,
            prompt_version=prompt_version,
        )

        logger.info(
            "LLM call completed",
            extra={
                "correlation_id": get_correlation_id(),
                "model": model,
                "tokens_in": input_tokens,
                "tokens_out": output_tokens,
                "cost_usd": cost_usd,
                "latency_ms": latency_ms,
                "prompt_version": prompt_version,
            },
        )
        return result

    async def _backoff(self, attempt: int) -> None:
        base = 0.5 * (2 ** (attempt - 1))
        jitter = random.uniform(0.0, base * 0.1)
        delay = min(base + jitter, 30.0)
        await asyncio.sleep(delay)

    def reset_daily_cost_for_tests(self) -> None:
        """Reset internal counters for isolated unit tests."""
        self._cost_day = _utc_day()
        self._daily_cost_usd = 0.0
        self._circuit.record_success()
