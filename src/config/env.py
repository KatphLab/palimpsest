"""Runtime environment settings and defaults."""

from decimal import Decimal
from functools import lru_cache
from typing import Final, Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__: list[str] = ["Settings", "get_settings"]

_DEFAULT_OPENAI_MODEL: Final[str] = "gpt-4.1-mini"
_DEFAULT_TUI_REFRESH_MS: Final[int] = 250
_DEFAULT_STALE_VIEW_GUARDRAIL_MS: Final[int] = 500
_DEFAULT_GLOBAL_CONSISTENCY_CHECK_INTERVAL_MS: Final[int] = 60_000
_DEFAULT_MUTATION_BURST_TRIGGER_COUNT: Final[int] = 3
_DEFAULT_MUTATION_BURST_WINDOW_SECONDS: Final[int] = 10
_DEFAULT_GLOBAL_MUTATION_STORM_THRESHOLD: Final[int] = 5
_DEFAULT_SESSION_MUTATION_COOLDOWN_MS: Final[int] = 30_000
_DEFAULT_SESSION_MAX_SEED_LENGTH: Final[int] = 280
_DEFAULT_ENTROPY_BREACH_THRESHOLD: Final[float] = 0.80
_DEFAULT_SESSION_COHERENCE_TARGET: Final[float] = 0.80
_DEFAULT_TERMINATION_MAJORITY_THRESHOLD: Final[float] = 0.50
_DEFAULT_SESSION_BUDGET_USD: Final[Decimal] = Decimal("5.00")


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    log_level: str = "INFO"
    log_formatter: Literal["standard", "detailed"] = "standard"
    openai_model: str = Field(default=_DEFAULT_OPENAI_MODEL, min_length=1)
    openai_api_key: SecretStr = Field(
        ...,
        description="OpenAI API key must be present and non-empty",
        min_length=1,
    )
    session_budget_usd: Decimal = Field(default=_DEFAULT_SESSION_BUDGET_USD, gt=0)
    session_coherence_target: float = Field(
        default=_DEFAULT_SESSION_COHERENCE_TARGET,
        ge=0.0,
        le=1.0,
    )
    session_refresh_ms: int = Field(default=_DEFAULT_TUI_REFRESH_MS, ge=50)
    stale_view_guardrail_ms: int = Field(
        default=_DEFAULT_STALE_VIEW_GUARDRAIL_MS, ge=100
    )
    global_consistency_check_interval_ms: int = Field(
        default=_DEFAULT_GLOBAL_CONSISTENCY_CHECK_INTERVAL_MS,
        ge=1_000,
    )
    mutation_burst_trigger_count: int = Field(
        default=_DEFAULT_MUTATION_BURST_TRIGGER_COUNT, ge=1
    )
    mutation_burst_window_seconds: int = Field(
        default=_DEFAULT_MUTATION_BURST_WINDOW_SECONDS, ge=1
    )
    global_mutation_storm_threshold: int = Field(
        default=_DEFAULT_GLOBAL_MUTATION_STORM_THRESHOLD,
        ge=1,
    )
    session_mutation_cooldown_ms: int = Field(
        default=_DEFAULT_SESSION_MUTATION_COOLDOWN_MS,
        ge=0,
    )
    session_max_seed_length: int = Field(default=_DEFAULT_SESSION_MAX_SEED_LENGTH, ge=1)
    entropy_breach_threshold: float = Field(
        default=_DEFAULT_ENTROPY_BREACH_THRESHOLD,
        ge=0.0,
        le=1.0,
    )
    termination_majority_threshold: float = Field(
        default=_DEFAULT_TERMINATION_MAJORITY_THRESHOLD,
        gt=0.0,
        le=1.0,
    )

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    """Return a cached validated settings instance."""

    return Settings()
