# Quickstart: Terminal Self-Editing Narrative MVP

**Spec Version**: 1.1.0

## 1) Set up the environment

```bash
uv sync --all-groups
```

If you are starting from a fresh shell, this installs runtime, dev, and test dependencies.

## 2) Configure environment variables

Create a local `.env` file (or update your shell environment) with the runtime settings the app will validate through Pydantic Settings:

```bash
OPENAI_API_KEY=your-key
OPENAI_MODEL=gpt-4.1-mini
LOG_LEVEL=INFO
SESSION_BUDGET_USD=5.00
SESSION_COHERENCE_TARGET=0.80
SESSION_MUTATION_COOLDOWN_MS=30000
SESSION_MAX_SEED_LENGTH=280
```

Recommended notes:

- Keep the seed limit aligned to FR-001.
- Keep the budget target aligned to FR-015 and CA-005.
- Keep the coherence target aligned to CA-001.
- Keep the mutation cooldown aligned to the 30s plan default unless you are explicitly overriding it for local development.

## 3) Run the app

```bash
uv run python src/main.py
```

The terminal UI should start, accept a seed, and render the session story-flow panel.
Mutation progression is cycle-based: press `c` (Continue) to advance one mutation cycle with one selected activation and at most one mutation resolution.

## 4) Core user flows

### Seed and start a session

1. Launch the TUI.
2. Enter a seed of 1-280 characters.
3. Confirm the initial scene appears and the session enters running state.

### Pause and resume

1. Run the pause command from the terminal controls.
2. Confirm graph growth stops while the current snapshot remains visible.
3. Issue resume and confirm growth continues from the same session state.

### Lock and unlock an edge

1. Select a visible relationship edge.
2. Lock it.
3. Trigger additional mutation cycles and confirm the edge remains intact.
4. Unlock it if you want the runtime to consider it mutable again.

### Step mutation cycles and inspect behavior

1. Start a running session and keep it active for several cycles.
2. Press `c` for each cycle you want to execute.
3. Confirm one node activation event per cycle and at most one mutation decision outcome per cycle.
4. Confirm accepted `add_node` mutations produce scene text immediately.
5. Confirm `prune_branch` removes the targeted branch subgraph while preserving seed/protected state.

### Fork a session

1. Choose an active session.
2. Fork it.
3. Confirm the new session has a different `session_id` and independent mutation history.

### Inspect a node

1. Open a node detail view.
2. Verify entropy, drift category, activation metadata, and termination vote state are visible.

### Export the graph

1. Choose export.
2. Write the export artifact to a JSON file.
3. Confirm the export contains the frozen session snapshot, graph contents, and event log.

## 5) Run tests

```bash
uv run pytest
```

Useful targeted checks:

```bash
uv run pytest tests/unit/test_models_base.py -q
uv run pytest tests/unit/test_tui_story_projection.py -q
uv run pytest tests/integration/test_live_story_flow_rendering.py -q
```

## 6) What to expect from failures

- Validation errors should fail fast when seed length, edge locks, or export paths are invalid.
- Runtime errors should be surfaced as terminal events, not as silent state corruption.
- Export and mutation commands should reject malformed payloads before they reach the graph.
