"""Shared validation utilities for request models."""

from __future__ import annotations

from pydantic import StringConstraints
from typing_extensions import Annotated

__all__ = [
    "CUSTOM_SEED_MAX_LENGTH",
    "CUSTOM_SEED_MIN_LENGTH",
    "SeedText",
    "validate_node_id",
    "validate_seed_text",
]

CUSTOM_SEED_MIN_LENGTH = 1
CUSTOM_SEED_MAX_LENGTH = 255

SeedText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=CUSTOM_SEED_MIN_LENGTH,
        max_length=CUSTOM_SEED_MAX_LENGTH,
    ),
]


def validate_node_id(value: str, field_name: str = "node_id") -> str:
    """Validate a node identifier is non-empty after stripping.

    Args:
        value: The node identifier to validate.
        field_name: The name of the field for error messages.

    Returns:
        The validated node identifier.

    Raises:
        ValueError: If the node ID is empty after stripping.
    """
    if len(value.strip()) < 1:
        raise ValueError(f"{field_name} must be non-empty")

    return value


def validate_seed_text(
    value: str | None,
    min_length: int = CUSTOM_SEED_MIN_LENGTH,
    max_length: int = CUSTOM_SEED_MAX_LENGTH,
    field_name: str = "seed",
) -> str | None:
    """Validate seed text constraints.

    Args:
        value: The seed value to validate, or None.
        min_length: Minimum allowed length (default: 1).
        max_length: Maximum allowed length (default: 255).
        field_name: The name of the field for error messages.

    Returns:
        The validated seed value, or None if input was None.

    Raises:
        ValueError: If the seed fails length constraints.
    """
    if value is None:
        return None

    stripped = value.strip()
    if len(stripped) < min_length:
        raise ValueError(
            f"{field_name} must be at least {min_length} character when provided"
        )

    if len(stripped) > max_length:
        raise ValueError(f"{field_name} must not exceed {max_length} characters")

    return stripped
