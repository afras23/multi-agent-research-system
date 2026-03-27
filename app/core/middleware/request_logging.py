"""
Structured request logging (no request bodies).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging_config import get_correlation_id

logger = logging.getLogger("http.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log method, path, status, latency, and correlation id per request."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        started = time.perf_counter()
        response = await call_next(request)
        latency_ms = (time.perf_counter() - started) * 1000.0
        cid = get_correlation_id() or "unknown"
        extra = {
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "latency_ms": round(latency_ms, 3),
            "correlation_id": cid,
        }
        status_code = response.status_code
        if status_code >= 500:
            logger.error("Request completed", extra=extra)
        elif status_code >= 400:
            logger.warning("Request completed", extra=extra)
        else:
            logger.info("Request completed", extra=extra)
        return response
