"""UUID validation helpers for contract-compliant identifiers."""

from __future__ import annotations

import re
from uuid import UUID

__all__ = ["UUID_PATTERN", "ensure_valid_uuid", "is_valid_uuid"]

UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
_UUID_REGEX = re.compile(UUID_PATTERN)


def is_valid_uuid(value: str) -> bool:
    """Return ``True`` when ``value`` is a lowercase canonical UUID string."""

    if not _UUID_REGEX.fullmatch(value):
        return False

    try:
        return str(UUID(value)) == value
    except ValueError:
        return False


def ensure_valid_uuid(value: str, *, field_name: str = "uuid") -> str:
    """Return a validated UUID string or raise ``ValueError`` with field context."""

    if not is_valid_uuid(value):
        raise ValueError(f"{field_name} must be a lowercase canonical UUID string")

    return value
