"""
Application configuration.

Loads all settings from the environment via Pydantic Settings for use across
routes, services, and agents.
"""

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_env: str = Field(default="development", description="Runtime environment name")
    app_version: str = Field(default="0.1.0", description="Application version")
    debug: bool = Field(default=False, description="Enable debug behaviours")
    log_level: str = Field(default="INFO", description="Logging level")

    api_host: str = Field(default="0.0.0.0", description="Bind host for Uvicorn")
    api_port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description=(
            "Bind port for Uvicorn. Environment: APP_PORT (preferred) or API_PORT. "
            "Compose maps host port to container 8000; the app service sets APP_PORT=8000 inside."
        ),
        validation_alias=AliasChoices("APP_PORT", "API_PORT"),
    )

    database_url: str = Field(
        ...,
        description="Async SQLAlchemy database URL (postgresql+asyncpg://...)",
    )

    openai_api_key: str = Field(
        ...,
        description="OpenAI API key for LLM calls",
    )
    ai_model: str = Field(default="gpt-4o", description="Default chat model name")
    ai_max_tokens: int = Field(default=4096, ge=1, description="Default max output tokens")
    ai_temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
        description="Sampling temperature for generations",
    )
    max_daily_cost_usd: float = Field(
        default=10.0,
        ge=0.0,
        description="Maximum aggregate LLM spend per UTC day (USD)",
    )
    max_request_cost_usd: float = Field(
        default=2.0,
        ge=0.0,
        description="Maximum estimated cost for a single LLM request (USD)",
    )

    agent_timeout_seconds: int = Field(
        default=120,
        ge=1,
        description="Per-agent execution timeout in seconds",
    )
    max_parallel_agents: int = Field(
        default=3,
        ge=1,
        description="Maximum concurrent agent executions",
    )
    research_subtask_timeout_seconds: int = Field(
        default=60,
        ge=1,
        description="Timeout for each parallel research sub-call (LLM per topic area)",
    )

    cors_allow_origins: list[str] = Field(
        default_factory=list,
        description="Allowed CORS origins; empty disables CORS wildcard in production",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def parse_cors_allow_origins(cls, value: object) -> object:
        """Parse comma-separated CORS origins from a single env string."""
        if isinstance(value, str) and value.strip():
            return [part.strip() for part in value.split(",") if part.strip()]
        return value
