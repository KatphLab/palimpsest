"""CLI entry point for the terminal narrative runtime."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

from runtime.session_runtime import SessionRuntime

__all__ = ["main", "run_cli_fallback", "run_textual_mode"]

LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for runtime startup."""

    parser = argparse.ArgumentParser(prog="palimpsest")
    parser.add_argument(
        "--cli",
        action="store_true",
        help="start the plain CLI fallback instead of Textual mode",
    )
    return parser


def run_textual_mode(runtime: SessionRuntime) -> int:
    """Start the runtime in Textual mode."""

    LOGGER.info("starting runtime in Textual mode")
    _ = runtime
    return 0


def run_cli_fallback(runtime: SessionRuntime) -> int:
    """Start the runtime in plain CLI fallback mode."""

    LOGGER.info("starting runtime in CLI fallback mode")
    _ = runtime
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the runtime entry point."""

    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    runtime = SessionRuntime()

    if args.cli:
        return run_cli_fallback(runtime)

    try:
        return run_textual_mode(runtime)
    except (ImportError, RuntimeError) as exc:
        LOGGER.warning("Textual mode unavailable; falling back to CLI: %s", exc)
        return run_cli_fallback(runtime)


if __name__ == "__main__":
    raise SystemExit(main())
