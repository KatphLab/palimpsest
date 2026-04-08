"""CLI command helpers for listing and filtering graph summaries."""

from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from cli.ui.multi_graph_display import render_multi_graph_view
from models.views import FilterState, MultiGraphView, ViewPreferences
from services.graph_manager import GraphManager

__all__ = ["configure_parser", "run_from_parsed_args", "run_list_graphs_command"]

LOGGER = logging.getLogger(__name__)


def configure_parser(parser: argparse.ArgumentParser) -> None:
    """Configure argparse options for listing graphs."""

    parser.add_argument("--search", dest="search_query", default=None)
    parser.add_argument("--fork-source", dest="fork_source", default=None)
    parser.add_argument("--created-after", dest="created_after", default=None)
    parser.add_argument("--created-before", dest="created_before", default=None)
    parser.add_argument("--status", choices=["active", "archived"], default=None)
    parser.add_argument(
        "--sort-by",
        dest="sort_by",
        choices=["createdAt", "name", "nodeCount", "lastModified"],
        default="createdAt",
    )
    parser.add_argument(
        "--sort-order",
        dest="sort_order",
        choices=["asc", "desc"],
        default="desc",
    )
    parser.add_argument(
        "--display-mode",
        dest="display_mode",
        choices=["list", "grid", "tree"],
        default="list",
    )
    parser.add_argument("--active-graph-id", dest="active_graph_id", default=None)


def run_from_parsed_args(
    args: argparse.Namespace,
    *,
    root_dir: Path | None = None,
) -> int:
    """Execute graph list command from parsed CLI arguments."""

    view = run_list_graphs_command(
        filters=FilterState(
            search_query=args.search_query,
            fork_source=args.fork_source,
            created_after=_parse_cli_datetime(args.created_after),
            created_before=_parse_cli_datetime(args.created_before),
            status=args.status,
        ),
        view_prefs=ViewPreferences(
            sort_by=args.sort_by,
            sort_order=args.sort_order,
            display_mode=args.display_mode,
        ),
        active_graph_id=args.active_graph_id,
        root_dir=root_dir,
    )
    LOGGER.info("\n%s", render_multi_graph_view(view))
    return 0


def run_list_graphs_command(
    *,
    filters: FilterState | None = None,
    view_prefs: ViewPreferences | None = None,
    active_graph_id: str | None = None,
    root_dir: Path | None = None,
    manager: GraphManager | None = None,
) -> MultiGraphView:
    """Run graph-list operation and return the rendered view model."""

    if manager is not None:
        operation_manager = manager
    else:
        resolved_root = root_dir if root_dir is not None else Path.cwd()
        operation_manager = GraphManager(root_dir=resolved_root)
    return asyncio.run(
        operation_manager.get_multi_graph_view(
            filters=filters,
            view_prefs=view_prefs,
            active_graph_id=active_graph_id,
        )
    )


def _parse_cli_datetime(value: str | None) -> datetime | None:
    """Parse ISO datetime CLI input into a timezone-aware UTC timestamp."""

    if value is None:
        return None

    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)
