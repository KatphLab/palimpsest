"""Terminal rendering helpers for the multi-graph browser."""

from __future__ import annotations

from models.views import MultiGraphView

__all__ = ["render_multi_graph_view"]


def render_multi_graph_view(view: MultiGraphView) -> str:
    """Render a compact text table for the current multi-graph state."""

    header = [
        "Graph ID  Name                  Nodes  Edges  Seed         State      Modified",
        "--------  --------------------  -----  -----  -----------  ---------  -------------------------",
    ]
    rows = [
        (
            f"{summary.id[:8]}  "
            f"{summary.name[:20]:<20}  "
            f"{summary.node_count:>5}  "
            f"{summary.edge_count:>5}  "
            f"{(summary.seed or '-'):11.11}  "
            f"{summary.current_state[:9]:<9}  "
            f"{summary.last_modified.isoformat().replace('+00:00', 'Z')}"
        )
        for summary in view.graphs
    ]
    filters = (
        "Filters: "
        f"search={view.filters.search_query!r}, "
        f"fork_source={view.filters.fork_source!r}, "
        f"status={view.filters.status!r}"
    )
    footer = (
        "Summary: "
        f"visible={len(view.graphs)} / total={view.total_count}, "
        f"sort={view.view_prefs.sort_by} {view.view_prefs.sort_order}, "
        f"display={view.view_prefs.display_mode}"
    )

    return "\n".join([*header, *rows, filters, footer])
