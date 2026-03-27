"""
Correlation identifier middleware.

Propagates ``X-Correlation-ID`` across logs and responses.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging_config import reset_correlation_id, set_correlation_id


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Bind a correlation identifier for each inbound HTTP request."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        incoming = request.headers.get("X-Correlation-ID")
        correlation_id = incoming.strip() if incoming and incoming.strip() else str(uuid.uuid4())
        token = set_correlation_id(correlation_id)
        try:
            response = await call_next(request)
        finally:
            reset_correlation_id(token)
        response.headers["X-Correlation-ID"] = correlation_id
        return response
