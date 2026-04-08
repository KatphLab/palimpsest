"""Time utilities for consistent UTC timestamp handling."""

from __future__ import annotations

from datetime import datetime, timezone

__all__ = ["utc_now"]


def utc_now() -> datetime:
    """Return the current UTC datetime.

    This centralized helper ensures consistent UTC timestamp handling
    across the codebase and enables easier testability through mocking.

    Returns:
        Current UTC datetime with timezone info.
    """
    return datetime.now(timezone.utc)
