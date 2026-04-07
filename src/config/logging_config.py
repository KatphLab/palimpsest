import logging.config
from typing import Any, Dict

__all__: list[str] = ["setup_logging"]

LOGGING_CONFIG: Dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"},
        "detailed": {
            "format": "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s"
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "standard",
            "stream": "ext://sys.stdout",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG",
            "formatter": "detailed",
            "filename": "app.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
        },
    },
    "root": {"level": "INFO", "handlers": ["console", "file"]},
    "loggers": {
        "app": {
            "level": "DEBUG",
            "handlers": ["console"],
            "propagate": False,
        }
    },
}


def setup_logging() -> None:
    """Apply config. Call once at app start."""

    from config.env import get_settings

    settings = get_settings()
    # Optional: respect LOG_LEVEL env var
    level = settings.log_level.upper()
    formatter = settings.log_formatter.lower()

    LOGGING_CONFIG["root"]["level"] = level
    LOGGING_CONFIG["handlers"]["console"]["level"] = level
    LOGGING_CONFIG["handlers"]["console"]["formatter"] = formatter

    logging.config.dictConfig(LOGGING_CONFIG)
