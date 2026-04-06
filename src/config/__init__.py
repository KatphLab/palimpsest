"""Configuration helpers for runtime settings and logging."""

from .env import Settings, get_settings

__all__: list[str] = ["Settings", "get_settings", "setup_logging"]


def setup_logging() -> None:
    """Apply the configured logging defaults."""

    from .logging_config import setup_logging as _setup_logging

    _setup_logging()
