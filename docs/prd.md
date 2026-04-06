# Product Requirements Document: Self-Editing Narrative Hypergraph (SENH)

**Version**: 0.3 (Terminal-Only MVP)
**Timeline**: 5-day sprint
**Scope**: Session-based runtime, 100-200 nodes, terminal-first interaction (Textual TUI or plain CLI)

---

## 1) Executive Summary

### Problem
Most narrative generators are linear or manually curated branches. They generate text, but they do not autonomously restructure story topology when coherence declines, pacing stalls, or contradictions emerge.

### Solution
Build a self-editing narrative hypergraph where stateless Scene Agents generate scenes and propose graph mutations in real time. A Meta-Narrator performs periodic global consistency checks. The narrative terminates naturally through distributed node voting.

### MVP Delivery Constraint
This MVP is terminal-only to keep implementation surface small within one week.

- Primary UI target: Textual-based TUI.
- Fallback UI target: plain terminal CLI output.
- No browser frontend, no WebSocket transport, no client/server split for v0.3.

### Prototype Success Metrics
- Maintain `>= 0.80` global coherence (LLM-judged) during a 30-minute session.
- Require zero manual pruning during autonomous run.
- Trigger mutation handling within 5 seconds of entropy threshold breach.
- Complete at least one full arc (seed -> termination vote) in under 10 minutes.
- Keep API spend below `$5` per session through prompt and context controls.

### Scope Boundaries
- In scope: in-memory graph runtime, terminal live view, pause/resume, lock/fork controls, entropy and mutation logs.
- Out of scope: browser UI, persistent user accounts, collaborative editing, mobile optimization, EPUB/PDF export.

---

## 2) User Experience and Functional Requirements

### Personas
- **Speculative Modeler**: explores emergent behavior and constraint effects.
- **Narrative Researcher**: compares branch evolution and studies local-to-global narrative dynamics.

### Story 1: Seed and Observe (Terminal)
As a user, I want to enter a short seed in terminal and watch the graph self-assemble live.

**Acceptance Criteria**
- Seed input supports up to 280 characters.
- System creates Node 0 within 2 seconds of submit.
- Terminal updates state at least every 500 ms while simulation runs.
- Active nodes are visibly marked in the view (for example: `*`, color, or status column).
- User can pause and resume simulation from keyboard commands.

### Story 2: Intervene in Topology (Command-Driven)
As a user, I want to lock edges and fork the graph from terminal commands.

**Acceptance Criteria**
- User can toggle edge lock via command (example: `lock-edge <edge_id>`).
- Locked edges are immune to mutation-based removal.
- User can fork current graph state via command (example: `fork`).
- Fork creates an independent in-memory session with a new session ID.
- Original session continues unless user explicitly switches context.

### Story 3: Monitor Entropy and Mutations
As a user, I want to see entropy hotspots and mutation causes in terminal.

**Acceptance Criteria**
- Terminal view shows per-node entropy score and drift category.
- User can inspect node details via command (example: `show-node <node_id>`).
- Mutation events stream in chronological order with actor and target IDs.
- User can export current graph as JSON via command (example: `dump-json <path>`).

### Non-Goals (Sprint Constraint)
- No browser or web app.
- No persistent accounts or identity.
- No multi-user collaboration.
- No cross-session memory.
- No model fine-tuning or local model hosting.

---

## 3) AI and Narrative System Requirements

### 3.1 Scene Agent (Stateless)

**Trigger**
- Activated by traversal reach or local entropy threshold breach.

**Input Envelope**
- Current node text.
- One-hop neighbors (parent/child context, 500-token window).
- Graph metadata (node count, elapsed session time, activation limits).

**Input Contract (Detailed)**
- `session`: `{session_id, tick, elapsed_sec}`
- `node`: `{id, content, entropy_score, activation_count, vote_terminate}`
- `neighbors`:
  - `parents`: list of `{node_id, edge_id, edge_type, locked, summary}`
  - `children`: list of `{node_id, edge_id, edge_type, locked, summary}`
- `recent_events`: last 10 events, each as `{ts, actor_node_id, action, target_id, outcome}`
- `constraints`:
  - `max_mutations_per_activation = 1`
  - `remove_seed_forbidden = true`
  - `locked_edge_removal_forbidden = true`
  - `node_token_budget = 300`
- `termination_state`: `{active_votes, active_nodes, threshold = 0.5}`

**Input Validation Rules**
- `node.content` is required and non-empty.
- If neighbor summaries exceed 500 tokens total, truncate by oldest-first then lowest-edge-weight.
- Missing optional fields default safely (`recent_events = []`, `neighbors.children = []`).
- Activation is skipped if node has exceeded max activation_count guardrail.

**Output Contract**
- Either:
  - Narrative continuation (2-3 sentences), or
  - Exactly one mutation command:
    - `ADD_NODE(parent_id, edge_type)`
    - `SPLIT_NODE(ratio)`
    - `REMOVE_EDGE(edge_id)`
    - `MODIFY_SELF(instruction)`
    - `VOTE_TERMINATE(confidence)`
- Entropy evaluation payload with dimension scores and aggregate score.

**Output Contract (Detailed)**
- Top-level response fields:
  - `action`: `"CONTINUE" | "MUTATE"`
  - `content`: scene text (required for `CONTINUE`, optional for `MUTATE`)
  - `entropy`: `{continuity, novelty, tension, aggregate}` in `[0.0, 1.0]`
  - `diagnosis`: concise rationale (max 240 chars)
  - `mutation`: null or one mutation object
  - `projected_entropy_lift`: float in `[-1.0, 1.0]`

**Mutation Object Schemas**
- `ADD_NODE`: `{type:"ADD_NODE", parent_id:str, edge_type:"causal|thematic|temporal|contradiction", draft_content:str}`
- `SPLIT_NODE`: `{type:"SPLIT_NODE", node_id:str, ratio:float}` where `0.20 <= ratio <= 0.80`
- `REMOVE_EDGE`: `{type:"REMOVE_EDGE", edge_id:str, reason:str}`
- `MODIFY_SELF`: `{type:"MODIFY_SELF", node_id:str, instruction:str}`
- `VOTE_TERMINATE`: `{type:"VOTE_TERMINATE", node_id:str, confidence:float}` where `0.0 <= confidence <= 1.0`

**Output Validation Rules**
- Exactly one mutation object is allowed when `action = "MUTATE"`.
- `mutation` must be `null` when `action = "CONTINUE"`.
- `aggregate` must equal weighted score of dimensions (weights: continuity `0.4`, novelty `0.3`, tension `0.3`) within tolerance `0.01`.
- Invalid or policy-violating commands are rejected and treated as malformed output.

**Side Effects Emitted by Agent Step**
- `state_patch`: deterministic patch for graph manager (`add_node`, `update_node`, `remove_edge`, `set_vote`).
- `event_log_record`: `{session_id, tick, node_id, entropy, action, mutation_type, accepted}`.
- `telemetry`: token usage, latency, retry_count, validation_errors.

**Intelligence Model (How It Decides)**
- The agent runs a fixed four-step policy loop on every activation:
  1. **Interpret**: summarize local narrative state from current node + one-hop neighbors.
  2. **Diagnose**: score continuity, novelty, and tension with explicit rationale.
  3. **Decide**: choose `CONTINUE` or one mutation using deterministic policy gates.
  4. **Commit**: emit strict JSON payload that passes schema validation.
- Policy gate:
  - If aggregate entropy `< 0.40`, mutation is mandatory.
  - If continuity `< 0.35`, prefer `MODIFY_SELF` or `ADD_NODE` with causal edge.
  - If novelty `< 0.35`, prefer `ADD_NODE` with thematic/contradiction edge or `SPLIT_NODE`.
  - If tension `< 0.35`, prefer `ADD_NODE` with temporal edge that raises stakes.
  - If all dimensions `>= 0.40`, default to narrative continuation.
- Tie-break rule: when multiple actions satisfy the gate, choose the action with highest projected entropy lift (model-estimated).

**Prompting Strategy**
- Use a role prompt with:
  - explicit narrative objective (coherent but non-repetitive progression),
  - operation constraints (one mutation max, locked-edge immunity, Node 0 protection),
  - compact few-shot examples mapping failure patterns to valid actions.
- Use low temperature for action selection consistency and moderate temperature for scene text generation.

**Structured Output Schema**
- Agent output must include:
  - `content`: string
  - `entropy`: `{continuity, novelty, tension, aggregate}`
  - `diagnosis`: short explanation of the weakest dimension
  - `mutation`: null or one valid mutation object
- Output is rejected unless JSON parses and passes Pydantic validation.

**Reliability Controls**
- Retry once on malformed output using a repair prompt.
- On second failure, fall back to safe `CONTINUE` action with no topology mutation.
- Log decision trace (`scores`, `chosen_action`, `reason`) for later tuning.

**Learning During Session (Without Training)**
- No weight updates or fine-tuning in MVP.
- "Intelligence" improves in-session by dynamic context shaping:
  - down-weight stale branches,
  - prioritize contradictory or high-entropy neighborhoods,
  - inject recent mutation outcomes so the agent can avoid ineffective repeats.

### 3.2 Entropy Judge (LLM-as-Judge)

**Dimensions**
- Continuity (logical flow from parent)
- Novelty (trope and pattern repetition resistance)
- Tension (stakes, uncertainty, unresolved pressure)

**Timing**
- Run post-generation before graph commit.

**Action Rule**
- If aggregate entropy score < `0.40`, agent must emit one mutation command.

### 3.3 Meta-Narrator (Global Consistency)

**Trigger**
- Every 60 seconds, or
- Immediate run if 3 or more mutations occur within 10 seconds.

**Responsibilities**
- Sample 5 random nodes for contradiction detection.
- Score global arc progression (beginning/middle/end continuity).
- If node count > 150, prune lowest-value leaf nodes while preserving reachability to Node 0.

**Output**
- `global_coherence` in `[0,1]`
- `prune_nodes` list
- `contradictions` list with references

### 3.4 Mutation Constraints and Safety
- Max 1 mutation per activation.
- Locked edges cannot be removed.
- Node 0 cannot be removed.
- Global cooldown if mutation storm exceeds threshold (`>5 mutations / 10 sec`).
- Per-node cooldown: max 1 mutation per 30 seconds.

---

## 4) Technical Architecture (Terminal MVP)

### 4.1 Runtime Overview

```text
[Terminal UI Layer]
    |
[Simulation Controller]
    |- Graph State Manager (in-memory)
    |- Agent Orchestrator (queue + scheduler)
    |- LLM Gateway (retries, rate limits, cost tracking)
    `- Event Logger (mutation/coherence/session metrics)
```

### 4.2 Event Loop (Target Cadence: 2s)
1. Select up to 3 high-priority active nodes.
2. Build compact context for each activation.
3. Invoke scene-agent model and parse strict JSON output.
4. Apply narrative output or mutation command.
5. Push state diff to terminal renderer and append to event log.

### 4.3 In-Memory Graph Schema

```python
class Node:
    id: str
    content: str                # max 300 tokens
    entropy_score: float        # 0.0-1.0
    created_at: timestamp
    activation_count: int
    vote_terminate: bool

class Edge:
    id: str
    source: str
    target: str
    type: Literal["causal", "thematic", "temporal", "contradiction"]
    locked: bool
    weight: float               # 0.0-1.0
```

### 4.4 Integrations
- Scene agents: GPT-4o-mini (cost-oriented).
- Meta-Narrator: GPT-4o (quality-oriented).
- Runtime stack: Python + NetworkX + LangGraph.
- UI stack: Textual for rich TUI; fallback plain stdout renderer.
- Concurrency limit: 10 in-flight LLM calls max.

### 4.5 Security and Privacy
- Graph content is ephemeral for prototype sessions.
- User seed is not persisted to durable storage.
- API keys are read from environment and never printed.
- Seed input passes lightweight abuse keyword filtering.

---

## 5) Validation and Acceptance

### 5.1 Automated Evaluation
- **Coherence stability**: 10 runs with same seed; mean coherence >= 0.80.
- **Mutation usefulness**: >= 70% of mutations improve downstream entropy.
- **Cost guardrail**: alert if token budget exceeds 100k/session.
- **Latency SLO**: entropy breach to mutation application under 5 seconds.

### 5.2 Human Evaluation (Day 5)
- Three evaluators observe 5-minute terminal sessions.
- Prompt: rate "sense of story" on 1-10 scale.
- Target average score: > 6.0.

### 5.3 Termination Criteria
- Session ends when more than 50% of active nodes cast `VOTE_TERMINATE` with confidence > 0.80.
- System prints final narrative state summary and writes JSON graph dump.

---

## 6) Delivery Plan (5-Day Sprint)

### Day 1-2: Core Engine
- Build in-memory hypergraph model and CRUD operations.
- Add activation scheduler and event bus scaffolding.
- Implement simulation loop and deterministic tick controls.

### Day 3: Agent Pipeline
- Finalize Scene Agent prompt and strict JSON parsing.
- Implement entropy scoring pipeline.
- Add Meta-Narrator consistency and pruning pass.

### Day 4: Terminal UX
- Build minimal Textual dashboard (graph stats, active nodes, event stream).
- Add command set for pause/resume, lock-edge, fork, show-node, dump-json.
- Add plain CLI fallback mode for non-TUI environments.

### Day 5: Integration and Hardening
- End-to-end 100-node stress test.
- Optimize prompt footprint and context compression.
- Prepare terminal demo script and runbook.

---

## 7) Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| API cost growth from repeated context windows | Budget breach | Compress distant context and cap activation fan-out |
| Mutation storms | Graph instability | Global/per-node cooldown rules and strict one-mutation limit |
| Graph fragmentation | Narrative dead ends | Enforce weak connectivity checks back to Node 0 |
| Terminal readability at 200 nodes | Operator confusion | Add filters, paging, and focused node inspection commands |
| Entropy misclassification | Low-quality mutations | Allow manual override command and tune few-shot judge examples |

---

## 8) Post-Prototype Roadmap
- **v0.4**: Optional web dashboard and remote monitoring.
- **v0.5**: Persistent graph snapshots and branch replay.
- **v0.6**: Multi-user comparison mode for concurrent runs.

---

## Appendix A: Prompt Templates (Draft)

### Scene Agent Prompt

```text
You are a Scene Agent in a narrative hypergraph.
CONTEXT: Parent scene: {parent_content}
TASK: Continue the narrative in 2-3 sentences OR emit one mutation command.
ENTROPY: Score continuity, novelty, and tension in [0,1].
RULE: If aggregate entropy < 0.40, you must emit one mutation.
Return strict JSON:
{"content":"...","entropy":{"continuity":0.0,"novelty":0.0,"tension":0.0,"aggregate":0.0},"mutation":null|{...}}
```

### Meta-Narrator Prompt

```text
Evaluate this narrative hypergraph for global coherence.
INPUT: {sampled_nodes}
Find contradictions and low-value leaf nodes.
Return strict JSON:
{"global_coherence":0.0,"prune_nodes":[...],"contradictions":[...]}
```
