"""Shared utilities for service initialization and dependency injection."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from persistence.graph_store import GraphStore
    from persistence.lineage_store import LineageStore


def initialize_service_deps(
    *,
    graph_store: "GraphStore | None" = None,
    lineage_store: "LineageStore | None" = None,
    root_dir: Path | None = None,
    logger: logging.Logger | None = None,
) -> tuple["GraphStore", "LineageStore", logging.Logger]:
    """Initialize common service dependencies.

    Args:
        graph_store: Optional pre-configured graph store.
        lineage_store: Optional pre-configured lineage store.
        root_dir: Optional storage root directory.
        logger: Optional pre-configured logger.

    Returns:
        Tuple of (graph_store, lineage_store, logger) with defaults applied.

    Example:
        >>> self._graph_store, self._lineage_store, self._logger = (
        ...     initialize_service_deps(
        ...         graph_store=graph_store,
        ...         lineage_store=lineage_store,
        ...         root_dir=root_dir,
        ...         logger=logger,
        ...     )
        ... )
    """
    from persistence.graph_store import GraphStore
    from persistence.lineage_store import LineageStore

    storage_root = root_dir if root_dir is not None else Path.cwd()

    resolved_graph_store = (
        graph_store if graph_store is not None else GraphStore(root_dir=storage_root)
    )
    resolved_lineage_store = (
        lineage_store
        if lineage_store is not None
        else LineageStore(root_dir=storage_root)
    )
    resolved_logger = logger if logger is not None else logging.getLogger(__name__)

    return resolved_graph_store, resolved_lineage_store, resolved_logger


__all__ = ["initialize_service_deps"]
