"""Command-line entry point for graph forking workflows."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, cast

from cli.commands import fork, list_graphs, switch_graph

__all__ = ["build_parser", "main"]


class _CommandRunner(Protocol):
    """Callable contract for parsed CLI command handlers."""

    def __call__(
        self,
        args: argparse.Namespace,
        *,
        root_dir: Path | None = None,
    ) -> int: ...


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for fork/list/switch graph operations."""

    parser = argparse.ArgumentParser(prog="palimpsest-graphs")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fork_parser = subparsers.add_parser("fork", help="create a graph fork")
    fork.configure_parser(fork_parser)
    fork_parser.set_defaults(_runner=fork.run_from_parsed_args)

    list_parser = subparsers.add_parser(
        "list-graphs", help="list graph summaries with filters"
    )
    list_graphs.configure_parser(list_parser)
    list_parser.set_defaults(_runner=list_graphs.run_from_parsed_args)

    switch_parser = subparsers.add_parser("switch-graph", help="switch active graph")
    switch_graph.configure_parser(switch_parser)
    switch_parser.set_defaults(_runner=switch_graph.run_from_parsed_args)

    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    root_dir: Path | None = None,
) -> int:
    """Run the graph workflow CLI and return process exit code."""

    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    runner = getattr(args, "_runner")
    if not callable(runner):
        raise TypeError("invalid CLI command runner")

    command_runner = cast(_CommandRunner, runner)
    if root_dir is None:
        return command_runner(args)

    return command_runner(args, root_dir=root_dir)


if __name__ == "__main__":
    raise SystemExit(main())
