# Palimpsest — Self-Editing Narrative Hypergraph

An autonomous narrative engine where LLM-driven scene agents self-organize into a living hypergraph, dynamically mutating story topology while preserving coherence. From a single seed prompt, the system generates branching scenes, detects when narrative entropy declines, and autonomously restructures the graph through mutations like node splitting, edge addition, and branch pruning.

## What It Does

**Autonomous Story Generation**: Provide a seed prompt and watch the system generate a narrative hypergraph in real-time. Each node represents a story scene; edges represent causal, thematic, temporal, or contradiction relationships between scenes.

**Self-Modifying Graph Topology**: When the narrative detects low coherence, novelty, or tension, scene agents autonomously propose and execute mutations—adding nodes, splitting existing ones, removing stale connections, or voting for story termination.

**Scrollable Story View**: The TUI features a scrollable panel displaying the evolving narrative flow. Branches are shown with numbered indentation (1.1, 1.2, etc.), and detached scenes are listed separately.

**Generating Indicator**: A footer bar shows real-time session status and a "Generating..." indicator when LLM calls are in progress.

**Live Terminal Interface**: A rich Textual-based TUI provides real-time visibility into the evolving story graph, entropy scores, mutation events, and active scene nodes.

**Session Control**: Pause, resume, fork sessions, lock critical edges to protect them from mutation, and export the complete graph state at any time.

## Quick Start

### Prerequisites

- Python 3.12 or higher
- [UV](https://docs.astral.sh/uv/) package manager
- OpenAI API key (for scene generation and entropy evaluation)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd palimpsest

# Install dependencies and set up pre-commit hooks
make install
```

### Running a Session

```bash
# Start the terminal UI (sole supported entrypoint)
PYTHONPATH=src uv run python -m main
```

Run this command from the repository root. No alternate CLI entrypoint is
supported.

## Using the Application

### Starting a Story

1. Press `s` to start a new session
2. Enter a seed prompt (up to 280 characters)
3. The system generates Node 0 and begins autonomous expansion

### Session Controls

| Key | Action |
|-----|--------|
| `s` | Start a new session (seed entry) |
| `p` | Pause the current session |
| `r` | Resume a paused session |
| `c` | Manually advance one generation cycle |
| `↑/↓` or `PgUp/PgDn` | Scroll story view |

### Managing the Graph

**Lock/Unlock Edges**: Protect narrative branches from mutation by locking edges. Locked edges persist across mutations and ensure key story pathways remain intact.

**Fork Sessions**: Create an independent copy of the current session at any point. Forks share the parent session's graph state but evolve independently.

**Session Switching**: Switch between active sessions to compare different narrative branches.

### Understanding the Display

The live view shows:
- **Session Status**: CREATED, RUNNING, or PAUSED
- **State Version**: Incremented on each mutation
- **Node Count**: Total scenes in the graph
- **Active Nodes**: Currently processing or recently modified nodes
- **Story Projection**: Chronological narrative flow with branch numbering (1.1, 1.2, etc.)
- **Detached Scenes**: Orphan nodes not connected to the mainline

## LLM Mutation Strategy Layer

The system employs an LLM-driven strategy layer for intelligent mutation selection:

### Narrative Context Builder

The `NarrativeContextBuilder` extracts relevant context from the live session graph to inform mutation decisions:
- **Last Two Scenes**: The previous and current scene text provides narrative continuity
- **Graph Metrics**: Node count, edge count, active nodes, and graph version
- **Seed Node**: Reference to the original story seed for thematic consistency

### LLM Mutation Proposer

The `LLMMutationProposer` uses GPT-4o-mini to generate structured mutation proposals based on narrative context. It returns validated `MutationProposal` objects containing:
- Selected mutation action type
- Target node/edge IDs
- Confidence scoring and reasoning

### Failure Telemetry & Backoff

When the LLM proposer fails (network issues, parsing errors, schema violations), the system:
1. Logs the failure via structured `MutationEventKind.FAILED` events
2. Falls back to a simplified selection strategy
3. Implements backoff to avoid hammering the LLM provider
4. Records telemetry for debugging and optimization

### Mutation Decision Logging

All mutation decisions are logged with full context for transparency:
- Timestamp and session ID
- Narrative context at decision time
- Proposed vs executed actions
- Failure reasons (if applicable)

## Narrative Dynamics

Every scene node is continuously evaluated on three dimensions:
- **Continuity**: Logical flow and coherence with parent scenes
- **Novelty**: Resistance to tropes and pattern repetition
- **Tension**: Stakes, uncertainty, and unresolved pressure

When aggregate entropy drops below 0.40, the scene agent must propose a mutation to restore narrative vitality.

### Mutation Types

| Mutation | Description |
|----------|-------------|
| `ADD_NODE` | Add a new scene connected to an existing one |
| `SPLIT_NODE` | Divide a scene into two parts (20-80% ratio) |
| `REMOVE_EDGE` | Remove a connection between scenes |
| `MODIFY_SELF` | Rewrite scene content in place |
| `VOTE_TERMINATE` | Cast a vote to end the story arc |

### Safety Controls

- **Node 0 Protection**: The seed node cannot be removed
- **Locked Edge Immunity**: Locked edges survive mutations
- **Mutation Cooldown**: Per-node rate limiting (30s between mutations)
- **Burst Detection**: Global cooldown if mutation storm exceeds threshold

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and customize:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | OpenAI API key for LLM calls |
| `LOG_LEVEL` | `INFO` | Logging verbosity (DEBUG, INFO, WARNING, ERROR) |
| `LOG_FORMATTER` | `standard` | Log format (`standard` or `detailed`) |

### Performance Tuning

Control cost and quality tradeoffs through environment variables:

- Scene generation uses GPT-4o-mini for cost efficiency
- Context windows are compressed to manage token usage
- Max 10 concurrent LLM calls to respect rate limits

## Project Structure

```
.
├── src/
│   ├── agents/           # Scene agents, mutation engine, entropy scoring
│   ├── graph/            # Hypergraph model and session graph management
│   ├── models/           # Pydantic schemas (nodes, edges, sessions, mutations, narrative_context)
│   ├── runtime/          # Session runtime and command routing
│   ├── tui/              # Terminal UI components, screens, story projection
│   └── config/           # Environment and logging configuration
├── tests/                # Unit, integration, and contract tests
│   └── fixtures/         # Shared test utilities and fixtures
├── docs/prd.md           # Product requirements document
└── AGENTS.md             # Development conventions and patterns
```

## Development

### Running Tests

```bash
# All tests
uv run pytest

# With coverage
uv run pytest --cov=src --cov-report=html

# Unit tests only
uv run pytest -m unit

# Integration tests only
uv run pytest -m integration
```

### Code Quality

```bash
# Format code
ruff format .

# Check and auto-fix issues
ruff check . --fix

# Run pre-commit hooks
pre-commit run --all-files
```

## Architecture Highlights

**Stateless Scene Agents**: Each activation processes only the current node, its immediate neighbors (1-hop), and recent event history—no persistent agent state across steps.

**LangGraph Workflows**: Agent orchestration uses LangGraph for structured execution loops with explicit state management.

**NetworkX Hypergraph**: The narrative topology is modeled as a NetworkX multi-graph with typed edges and node attributes for entropy, content, and metadata.

**LLM Mutation Strategy**: The `LLMMutationProposer` uses narrative context (last two scenes + graph metrics) to make intelligent mutation decisions via GPT-4o-mini.

**Narrative Context Builder**: Extracts semantic context from the live graph—including previous/current scene text, node counts, and graph version—to inform LLM decisions.

**Mutation Engine**: Dedicated LangGraph subgraph for activation candidate selection, with scene-preference logic over seed nodes to avoid seed-anchored churn.

**Story Projection**: Deterministic rendering of narrative flow via FOLLOWS edges (mainline) and BRANCHES_FROM edges (branch numbering), with detached scene detection.

**In-Memory Sessions**: Graphs and session state live entirely in memory during runtime—ephemeral by design for the terminal MVP.

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]
