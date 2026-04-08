"""Service for multi-graph listing, filtering, sorting, and lifecycle actions."""

from __future__ import annotations

import logging
from pathlib import Path

from models.graph_instance import GraphLifecycleState
from models.multi_graph_view import GraphSummary
from models.views import FilterState, MultiGraphView, ViewPreferences
from persistence.graph_store import GraphStore
from persistence.lineage_store import LineageStore
from services.structured_logging import OperationLogEntry, log_operation
from utils.time import utc_now

__all__ = ["GraphManager"]


class GraphManager:
    """Manage graph summaries and graph lifecycle operations."""

    def __init__(
        self,
        *,
        graph_store: GraphStore | None = None,
        lineage_store: LineageStore | None = None,
        root_dir: Path | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        storage_root = root_dir if root_dir is not None else Path.cwd()
        self._graph_store = (
            graph_store
            if graph_store is not None
            else GraphStore(root_dir=storage_root)
        )
        self._lineage_store = (
            lineage_store
            if lineage_store is not None
            else LineageStore(root_dir=storage_root)
        )
        self._logger = logger if logger is not None else logging.getLogger(__name__)

    def get_multi_graph_view(
        self,
        filters: FilterState | None = None,
        view_prefs: ViewPreferences | None = None,
        active_graph_id: str | None = None,
    ) -> MultiGraphView:
        """Return graph summaries after applying optional filters and sorting."""

        started_at = utc_now()
        resolved_filters = filters if filters is not None else FilterState()
        resolved_view_prefs = (
            view_prefs if view_prefs is not None else ViewPreferences()
        )

        summaries = self._graph_store.list_graphs()
        filtered = _apply_filters(summaries, resolved_filters)
        sorted_graphs = _apply_sort(filtered, resolved_view_prefs)

        response = MultiGraphView(
            graphs=sorted_graphs,
            active_graph_id=active_graph_id,
            total_count=len(summaries),
            filters=resolved_filters,
            view_prefs=resolved_view_prefs,
        )
        log_operation(
            self._logger,
            OperationLogEntry(
                operation="list",
                status="success",
                graph_id=active_graph_id,
                started_at=started_at,
                completed_at=utc_now(),
                metadata={
                    "total_count": response.total_count,
                    "visible_count": len(response.graphs),
                    "sort_by": response.view_prefs.sort_by,
                    "sort_order": response.view_prefs.sort_order,
                },
            ),
        )
        return response

    def delete_graph(self, graph_id: str, force: bool = False) -> None:
        """Delete a graph if allowed by child-fork constraints."""

        started_at = utc_now()
        self._graph_store.load(graph_id)

        child_graph_ids = self._lineage_store.get_children(graph_id)
        existing_graph_ids = {summary.id for summary in self._graph_store.list_graphs()}
        existing_children = [
            child_graph_id
            for child_graph_id in child_graph_ids
            if child_graph_id in existing_graph_ids
        ]
        if existing_children and not force:
            log_operation(
                self._logger,
                OperationLogEntry(
                    operation="delete",
                    status="failed",
                    graph_id=graph_id,
                    started_at=started_at,
                    completed_at=utc_now(),
                    metadata={
                        "reason": "graph_has_children",
                        "child_count": len(existing_children),
                    },
                ),
                level=logging.WARNING,
            )
            raise ValueError("graph has child forks; rerun with force=True")

        deleted = self._graph_store.delete(graph_id)
        if not deleted:
            raise FileNotFoundError(f"graph not found: {graph_id}")

        log_operation(
            self._logger,
            OperationLogEntry(
                operation="delete",
                status="success",
                graph_id=graph_id,
                started_at=started_at,
                completed_at=utc_now(),
                metadata={"force": force, "child_count": len(existing_children)},
            ),
        )

    def archive_graph(self, graph_id: str) -> None:
        """Archive an existing graph by updating its lifecycle state."""

        started_at = utc_now()
        graph = self._graph_store.load(graph_id)
        archived_at = utc_now()
        graph.state = GraphLifecycleState.ARCHIVED
        graph.last_modified = archived_at
        self._graph_store.save(graph)

        log_operation(
            self._logger,
            OperationLogEntry(
                operation="archive",
                status="success",
                graph_id=graph_id,
                started_at=started_at,
                completed_at=utc_now(),
                metadata={"archived_at": archived_at.isoformat()},
            ),
        )


def _apply_filters(
    summaries: list[GraphSummary],
    filters: FilterState,
) -> list[GraphSummary]:
    """Filter graph summaries using search, lineage, date, and status criteria."""

    filtered = summaries
    if filters.search_query is not None:
        query = filters.search_query.casefold()
        filtered = [
            summary
            for summary in filtered
            if query in summary.name.casefold()
            or any(query in label.casefold() for label in summary.labels)
        ]

    if filters.fork_source is not None:
        filtered = [
            summary
            for summary in filtered
            if summary.fork_source == filters.fork_source
        ]

    if filters.created_after is not None:
        filtered = [
            summary
            for summary in filtered
            if summary.created_at > filters.created_after
        ]

    if filters.created_before is not None:
        filtered = [
            summary
            for summary in filtered
            if summary.created_at < filters.created_before
        ]

    if filters.status == "active":
        filtered = [
            summary
            for summary in filtered
            if summary.current_state
            not in {
                GraphLifecycleState.ARCHIVED.value,
                GraphLifecycleState.DELETED.value,
            }
        ]
    elif filters.status == "archived":
        filtered = [
            summary
            for summary in filtered
            if summary.current_state == GraphLifecycleState.ARCHIVED.value
        ]

    return filtered


def _apply_sort(
    summaries: list[GraphSummary],
    view_prefs: ViewPreferences,
) -> list[GraphSummary]:
    """Sort graph summaries based on configured view preferences."""

    reverse = view_prefs.sort_order == "desc"
    if view_prefs.sort_by == "name":
        return sorted(
            summaries, key=lambda summary: summary.name.casefold(), reverse=reverse
        )
    if view_prefs.sort_by == "node_count":
        return sorted(
            summaries, key=lambda summary: summary.node_count, reverse=reverse
        )
    if view_prefs.sort_by == "last_modified":
        return sorted(
            summaries, key=lambda summary: summary.last_modified, reverse=reverse
        )

    return sorted(summaries, key=lambda summary: summary.created_at, reverse=reverse)
