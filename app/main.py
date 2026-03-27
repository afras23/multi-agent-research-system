"""
FastAPI application factory and ASGI entrypoint.
"""

from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.middleware.correlation import CorrelationIdMiddleware
from app.api.routes import health, research, tasks
from app.api.schemas import ErrorDetail, ErrorEnvelope, ResponseMetadata, utc_timestamp
from app.core.constants import API_PREFIX
from app.core.exceptions import BaseAppError
from app.core.logging_config import configure_logging
from app.db.session import configure_engine, dispose_engine
from app.dependencies import get_settings
from app.services.ai.client import LlmClient


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Configure shared resources and release them on shutdown."""
    settings = get_settings()
    configure_logging(settings.log_level)
    configure_engine(settings)
    app.state.llm_client = LlmClient(settings)
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    """Build the FastAPI application with middleware and routes."""
    settings = get_settings()
    app = FastAPI(
        title="Multi-Agent Research System",
        version=settings.app_version,
        lifespan=lifespan,
    )

    app.add_middleware(CorrelationIdMiddleware)

    cors_origins = list(settings.cors_allow_origins)
    if not cors_origins and settings.debug:
        cors_origins = ["*"]
    allow_credentials = cors_origins not in ([], ["*"])
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(BaseAppError)
    async def handle_base_app_error(request: Request, exc: BaseAppError) -> JSONResponse:
        started = time.perf_counter()
        request_id = request.headers.get("X-Correlation-ID", "unknown")
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        body = ErrorEnvelope(
            error=ErrorDetail(
                code=exc.error_code,
                message=exc.message,
                details=dict(exc.context),
            ),
            metadata=ResponseMetadata(
                request_id=request_id,
                timestamp=utc_timestamp(),
                processing_time_ms=elapsed_ms,
            ),
        )
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())

    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(research.router, prefix=API_PREFIX)
    app.include_router(tasks.router, prefix=API_PREFIX)

    return app


app = create_app()
