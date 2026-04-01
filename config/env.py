from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    App configuration from env vars and .env file.
    """

    log_level: str = "INFO"
    log_formatter: Literal["standard", "detailed"] = "standard"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
