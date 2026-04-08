"""Shared constants for the TUI package."""

from __future__ import annotations

__all__ = [
    "SECTION_DIVIDER",
    "NO_INSPECTABLE_NODE_MSG",
    "DEFAULT_COMPACT_TEXT_LENGTH",
    "DEFAULT_ENTROPY_HOTSPOT_LIMIT",
    "DEFAULT_MUTATION_LOG_LIMIT",
]

# UI formatting constants
SECTION_DIVIDER = "-" * 40
NO_INSPECTABLE_NODE_MSG = "No inspectable node available."

# Default limits for display functions
DEFAULT_COMPACT_TEXT_LENGTH = 96
DEFAULT_ENTROPY_HOTSPOT_LIMIT = 5
DEFAULT_MUTATION_LOG_LIMIT = 8
