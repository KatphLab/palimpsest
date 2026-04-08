"""CLI command helpers for switching active graph context."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from models.requests import GraphSwitchRequest
from models.responses import GraphSwitchResponse
from services.graph_switcher import GraphSwitcher

__all__ = ["configure_parser", "run_from_parsed_args", "run_switch_graph_command"]

LOGGER = logging.getLogger(__name__)


def configure_parser(parser: argparse.ArgumentParser) -> None:
    """Configure argparse options for the graph-switch command."""

    parser.add_argument(
        "--target",
        dest="target_graph_id",
        required=True,
        help="target graph UUID",
    )
    parser.add_argument(
        "--no-preserve-current",
        dest="preserve_current",
        action="store_false",
        help="skip preserving current graph state before switching",
    )
    parser.set_defaults(preserve_current=True)


def run_from_parsed_args(
    args: argparse.Namespace,
    *,
    root_dir: Path | None = None,
) -> int:
    """Execute graph switch command from argparse namespace."""

    response = run_switch_graph_command(
        target_graph_id=args.target_graph_id,
        preserve_current=args.preserve_current,
        root_dir=root_dir,
    )
    LOGGER.info(
        "switched to %s in %.3fms",
        response.current_graph_id,
        response.load_time_ms,
    )
    return 0


def run_switch_graph_command(
    *,
    target_graph_id: str,
    preserve_current: bool = True,
    root_dir: Path | None = None,
    switcher: GraphSwitcher | None = None,
) -> GraphSwitchResponse:
    """Run graph switching and return a typed response payload."""

    if switcher is not None:
        operation_switcher = switcher
    else:
        resolved_root = root_dir if root_dir is not None else Path.cwd()
        operation_switcher = GraphSwitcher(root_dir=resolved_root)
    request = GraphSwitchRequest(
        target_graph_id=target_graph_id,
        preserve_current=preserve_current,
    )

    LOGGER.info("%s load target graph", _progress_indicator(1, 2))
    response = asyncio.run(operation_switcher.switch_graph(request))
    LOGGER.info("%s active graph switched", _progress_indicator(2, 2))
    return response


def _progress_indicator(step: int, total_steps: int) -> str:
    """Build a compact progress indicator string for status output."""

    bounded_step = max(0, min(step, total_steps))
    return f"[{bounded_step}/{total_steps}]"
