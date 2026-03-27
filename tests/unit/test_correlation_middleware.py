"""
Tests for correlation id middleware.
"""

from __future__ import annotations

import uuid

from app.core.logging_config import get_correlation_id
from app.core.middleware.correlation import CorrelationIdMiddleware
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient


async def _read_cid(_request: Request) -> PlainTextResponse:
    return PlainTextResponse(get_correlation_id() or "none")


def _app() -> Starlette:
    application = Starlette(routes=[Route("/", _read_cid)])
    application.add_middleware(CorrelationIdMiddleware)
    return application


def test_generates_correlation_id() -> None:
    client = TestClient(_app())
    response = client.get("/")
    assert response.status_code == 200
    header = response.headers["X-Correlation-ID"]
    uuid.UUID(header)


def test_preserves_existing_correlation_id() -> None:
    fixed = "550e8400-e29b-41d4-a716-446655440000"
    client = TestClient(_app())
    response = client.get("/", headers={"X-Correlation-ID": fixed})
    assert response.headers["X-Correlation-ID"] == fixed
