# Quickstart: TUI Multi-Graph Forking

**Feature**: TUI Multi-Graph Forking
**Branch**: 003-tui-graph-forking
**Date**: 2026-04-08

## Prerequisites

- Python 3.12+
- Environment prepared with `make install`
- Run commands from repository root: `/home/katph/projects/palimpsest`

## 1) Launch the Application Through the Supported Entrypoint

```bash
PYTHONPATH=src uv run python -m main
```

Expected:
- Textual UI opens.
- No alternate startup path is required for normal operation.

## 2) Start a Session and Prepare a Fork Point

- Press `s` and provide a seed value.
- Advance the session (`c`) until at least one current node is available.

Expected:
- Active session renders in main panel.
- Footer shows current runtime state.

## 3) Fork From Current Node (`f`)

- Press `f` to open fork flow.
- Enter a seed (or leave blank to use default behavior).
- Confirm.

Expected:
- A new graph session is created from the current node context.
- New graph becomes active immediately.
- Source graph history remains unchanged.

Cancel path:
- Press escape/cancel in fork flow.
- Confirm that active graph and graph count remain unchanged.

## 4) Switch Graphs (`Tab` / `Shift+Tab`)

- Press `Tab` to move to next graph.
- Press `Shift+Tab` to move to previous graph.

Expected:
- Graph cycling is deterministic and wraps around at boundaries.
- Status bar shows `active_graph_position / total_graphs`.

## 5) Validate Background Execution + Active-Only Status

- Keep at least two graphs running.
- Switch to another graph and wait.
- Switch back and observe progression.

Expected:
- Inactive graphs continue progressing while off-screen.
- Status line always reflects only the active graph's running state.

## 6) Verify Entrypoint and Behavioral Tests

```bash
uv run pytest tests/unit/test_tui_app.py tests/unit/test_tui_widgets.py -v
uv run pytest tests/integration/test_parallel_execution.py tests/integration/test_multi_graph_view.py -v
```

Contract verification:

```bash
uv run pytest tests/contract/test_multi_graph_view.py -v
```

## 7) Budget Verification

Targets:
- Graph switch feedback: `<300ms`
- Fork confirmation flow: `<1s`

Verification method:
- Use integration timing assertions and runtime logs to confirm thresholds in CI/local runs.
