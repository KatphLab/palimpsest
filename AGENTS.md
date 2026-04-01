## Project Overview

This project is a Self-Editing Narrative Hypergraph: a single, living hypergraph (built on NetworkX + LangGraph) where every node is a short-lived scene agent and every edge represents a narrative connection. Unlike traditional agent swarms with external memory, the agents are the graph—self-modification is native. At any step a node can invoke an edit_graph tool that emits JSON patches to add/remove nodes or edges, rewrite its own future behavior, or even prune boring branches, turning a simple seed story into a coherent-yet-unpredictable narrative that literally rewrites its own rules in real time.

- **Language:** Python 3.12+
- **Package Manager:** [uv](https://docs.astral.sh/uv/)
- **Layout:** `src/` layout

---

## Environment Setup

All environment and dependency management uses `uv`. Do not use `pip`, `pip-tools`, `poetry`, or `conda`.

# Add a runtime dependency

uv add <package>

# Add a dev-only dependency

uv add --dev <package>

# Remove a dependency

uv remove <package>

# Run a command in the project environment without activating

uv run python script.py
uv run pytest

> Never manually edit `uv.lock`. It is auto-managed by `uv`.

---

## Code Style & Best Practices

### Do

- Follow **PEP 8** and **PEP 257** (docstrings)
- Use **type hints** on all function signatures and return types
- Prefer **`pathlib.Path`** over `os.path` for file operations
- Always use **`pydantic`** models for structured data
- Write **small, focused functions** — one responsibility per function
- Use **f-strings** for string formatting (not `.format()` or `%`)
- Use **`logging`** module instead of `print()` for diagnostics
- Handle exceptions specifically — catch `ValueError`, not bare `except:`
- Write **docstrings** for all public modules, classes, and functions
- Keep imports sorted: stdlib → third-party → local (enforced by `ruff`)
- Use `__all__` to define public API in modules

### Don't

- Do not use **mutable default arguments** (e.g. `def f(x=[]):`)
- Do not use **wildcard imports** (`from module import *`)
- Do not commit **`.env` files**, secrets, or credentials
- Do not add **new heavy dependencies** without approval
- Do not use **global state** unless absolutely necessary
- Do not write **god functions** — split logic into helpers
- Do not leave **dead code**, commented-out blocks, or `TODO` without context

## Testing

- All tests live in `tests/` and mirror the `src/` structure
- Use **`pytest`** as the test runner
- Use **`pytest-cov`** for coverage reporting
- Aim for ≥80% coverage on new code
- Name test files `test_<module>.py` and test functions `test_<behavior>()`
