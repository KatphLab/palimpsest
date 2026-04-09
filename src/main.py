"""CLI entry point for the terminal narrative runtime."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

from config.logging_config import setup_logging
from runtime.session_runtime import SessionRuntime
from tui.app import SessionApp

__all__ = ["main", "run_textual_mode"]

LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for runtime startup."""

    parser = argparse.ArgumentParser(prog="palimpsest")
    return parser


def run_textual_mode(runtime: SessionRuntime) -> int:
    """Start the runtime in Textual mode."""

    LOGGER.info("starting runtime in Textual mode")
    app = SessionApp(runtime=runtime)
    app.run()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the runtime entry point."""

    setup_logging()

    parser = build_parser()
    _ = parser.parse_args(list(argv) if argv is not None else None)

    runtime = SessionRuntime()
    return run_textual_mode(runtime)


if __name__ == "__main__":
    raise SystemExit(main())
