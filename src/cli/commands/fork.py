"""CLI command helpers for graph fork operations."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from models.requests import GraphForkRequest
from models.responses import GraphForkResponse
from services.graph_forker import GraphForker

__all__ = ["configure_parser", "run_fork_command", "run_from_parsed_args"]

LOGGER = logging.getLogger(__name__)


def configure_parser(parser: argparse.ArgumentParser) -> None:
    """Configure argparse flags for the fork command."""

    parser.add_argument(
        "--source",
        dest="source_graph_id",
        required=True,
        help="source graph UUID",
    )
    parser.add_argument(
        "--edge",
        dest="fork_edge_id",
        required=True,
        help="edge identifier where the fork should be created",
    )
    parser.add_argument(
        "--seed",
        dest="custom_seed",
        default=None,
        help="optional deterministic seed value",
    )
    parser.add_argument(
        "--label",
        dest="label",
        default=None,
        help="optional user-facing label for the fork",
    )


def run_from_parsed_args(
    args: argparse.Namespace, *, root_dir: Path | None = None
) -> int:
    """Execute fork command from argparse namespace and emit summary logs."""

    response = run_fork_command(
        source_graph_id=args.source_graph_id,
        fork_edge_id=args.fork_edge_id,
        custom_seed=args.custom_seed,
        label=args.label,
        root_dir=root_dir,
    )
    LOGGER.info("fork created: %s", response.forked_graph_id)
    return 0


def run_fork_command(
    *,
    source_graph_id: str,
    fork_edge_id: str,
    custom_seed: str | None = None,
    label: str | None = None,
    root_dir: Path | None = None,
    forker: GraphForker | None = None,
) -> GraphForkResponse:
    """Run the graph fork flow and emit a three-step progress indicator."""

    operation_forker = (
        forker
        if forker is not None
        else GraphForker(root_dir=root_dir if root_dir is not None else Path.cwd())
    )
    request = GraphForkRequest(
        source_graph_id=source_graph_id,
        fork_edge_id=fork_edge_id,
        custom_seed=custom_seed,
        label=label,
    )

    LOGGER.info("%s validate request", _progress_indicator(1, 3))
    is_valid, error = asyncio.run(operation_forker.validate_fork_request(request))
    if not is_valid and error is not None:
        raise ValueError(f"{error.error.value}: {error.message}")

    LOGGER.info("%s create fork", _progress_indicator(2, 3))
    response = asyncio.run(operation_forker.fork_graph(request))

    LOGGER.info("%s complete", _progress_indicator(3, 3))
    return response


def _progress_indicator(step: int, total_steps: int) -> str:
    """Build a compact progress indicator string for status output."""

    bounded_step = max(0, min(step, total_steps))
    return f"[{bounded_step}/{total_steps}]"
