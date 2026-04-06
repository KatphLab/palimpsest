from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    App configuration from env vars and .env file.
    """

    log_level: str = "INFO"
    log_formatter: Literal["standard", "detailed"] = "standard"
    openai_api_key: SecretStr = Field(
        ...,
        description="OpenAI API key must be present and non-empty",
        min_length=1,
    )

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
