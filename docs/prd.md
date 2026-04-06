# Product Requirements Document: Self-Editing Narrative Hypergraph (SENH)

**Version**: 0.1 (Prototype)
**Timeline**: 5-Day Sprint
**Scope**: 100-200 node limit, session-based, real-time streaming

---

## 1. Executive Summary

**Problem Statement**: Traditional narrative generators produce linear or branching stories that require human curation to maintain coherence. There is no system that allows narrative structures to self-modify based on emergent "boredom" or drift, creating truly autonomous speculative fiction.

**Proposed Solution**: A real-time hypergraph where stateless LLM-based scene agents activate, evaluate local "narrative entropy," and mutate the graph topology (add/remove nodes/edges) to maintain coherence and interest. A Meta-Narrator LLM provides global consistency checks, while nodes democratically vote to terminate the story when natural conclusion is reached.

**Success Criteria**:

- Graph maintains **≥80% coherence score** (LLM-judged) throughout 30-minute session
- **Zero manual interventions** required for graph pruning during autonomous run
- Entropy detection triggers mutations within **<5 seconds** of threshold breach
- System completes **≥1 full narrative arc** (seed → termination vote) in <10 minutes
- API cost per session **<$5** (optimized prompt caching)

---

## 2. User Experience & Functionality

### User Personas

- **Speculative Modeler**: Wants to observe emergent narrative behavior, test "what if" scenarios by locking specific edges
- **Narrative Researcher**: Studies how local agent rules create global story structure; forks graphs to compare evolution paths

### User Stories & Acceptance Criteria

**Story 1: Seeding and Observation**

> As a user, I want to input a 1-2 sentence story seed and watch the hypergraph self-assemble in real-time so that I can observe emergent narrative structures.

- **AC**:
  - User can input seed text (max 280 chars) via web interface
  - System initializes graph with seed as Node 0 within 2 seconds
  - Graph visualization updates in real-time (WebSocket, <500ms latency) showing node activation as glowing pulses
  - User can pause/resume the simulation (freeze all agent activations)

**Story 2: Topological Intervention**

> As a user, I want to lock specific edges and fork the graph at any point so that I can test how constraints alter emergent behavior.

- **AC**:
  - Clicking an edge toggles "locked" status (visual: solid vs dashed line)
  - Locked edges cannot be removed by agent mutation or Meta-Narrator pruning
  - "Fork" button creates deep copy of current graph state; new tab/session with copied graph ID
  - Original graph continues running; forked graph starts independent evolution

**Story 3: Entropy Monitoring**

> As a user, I want to see the "entropy heatmap" of the graph so I can predict where mutations will occur.

- **AC**:
  - Nodes color-coded by entropy score (green: low, red: high)
  - Hovering shows last entropy evaluation timestamp and specific drift type (continuity error / trope repetition / logical contradiction)
  - Mutation events logged in sidebar stream (e.g., "Node 12 pruned Node 8 due to redundancy")

### Non-Goals (1-Week Constraints)

- **NO** persistent user accounts or cross-session memory
- **NO** collaborative editing (single user per graph instance)
- **NO** export to traditional formats (PDF/EPUB); only JSON graph dump
- **NO** fine-tuned local models; API-only to save setup time
- **NO** mobile-responsive visualization (desktop-only D3.js canvas)

---

## 3. AI System Requirements

### 3.1 Agent Architecture

**Scene Agent (Stateless)**

- **Trigger**: Activated when graph traversal reaches node OR entropy threshold detected locally
- **Inputs**:
  - Node content (current scene text)
  - 1-hop neighbor contexts (parent/child nodes, 500 token window)
  - Current graph metadata (total node count, session time)
- **Outputs**:
  - Continue narrative (generate 2-3 sentences)
  - **OR** Mutation command: `ADD_NODE`, `REMOVE_EDGE`, `MODIFY_SELF`, `VOTE_TERMINATE`
  - Entropy score (0-1) for self-evaluation

**Meta-Narrator (Global Consistency Engine)**

- **Trigger**: Every 60 seconds OR when 3+ mutations occur in 10-second window
- **Function**:
  - Samples 5 random nodes for contradiction detection
  - Evaluates global narrative arc coherence (beginning/middle/end progression)
  - Executes "pruning" if node count >150: removes lowest-entropy leaf nodes
- **Output**: Global coherence score (0-1), list of nodes to prune

**Entropy Judge (LLM-as-Judge)**

- **Prompt Strategy**: Few-shot examples of "boring" vs "interesting" narrative transitions
- **Evaluation Dimensions**:
  - **Continuity**: Logical flow from parent node (0-1)
  - **Novelty**: Avoidance of repetitive tropes (0-1)
  - **Tension**: Presence of narrative stakes (0-1)
- **Trigger**: Post-generation, every node evaluates self before committing to graph

### 3.2 Mutation Protocol

**Allowed Operations**:

1. `ADD_NODE(target_parent_id, edge_type)`: Creates new node, connects to parent
2. `SPLIT_NODE(ratio)`: Divides long node into two connected nodes (prevents bloat)
3. `REMOVE_EDGE(target_edge)`: Severs connection if redundancy detected
4. `MODIFY_SELF(instruction)`: Rewrites own content (e.g., "make this scene more ominous")
5. `VOTE_TERMINATE(confidence)`: If confidence >0.8 and >50% of active nodes vote terminate, story ends

**Constraints**:

- Max 1 mutation per activation (prevent cascade failures)
- Locked edges immune to `REMOVE_EDGE`
- Cannot remove seed node (Node 0)

### 3.3 Evaluation Strategy

**Automated Benchmarks**:

- **Coherence Test**: Run 10 sessions with identical seeds; Meta-Narrator should score >0.8 consistency across runs
- **Mutation Efficiency**: Track "useful" mutations (those that increase subsequent entropy scores) vs random; target 70% useful
- **Cost Monitoring**: Log tokens per session; alert if >100k tokens (>$2 with GPT-4o)

**Human Validation** (Day 5 testing):

- 3 external users observe 5-minute runs; rate "sense of story" 1-10; target >6 average

---

## 4. Technical Specifications

### 4.1 Architecture Overview

```
[User Browser]
    ↕ WebSocket (Socket.io)
[Node.js/FastAPI Server]
    ├─ Graph State Manager (In-Memory)
    ├─ Agent Orchestrator (Queue-based activation)
    └─ LLM Client (OpenAI/Anthropic API with retry logic)
```

**Data Flow**:

1. Seed → Graph Manager creates Node 0
2. **Event Loop**: Every 2 seconds, select 3 random "active" nodes (high connectivity)
3. Stateless activation: Fetch context → LLM API call → Parse mutation command → Update graph → Broadcast diff to client
4. Meta-Narrator cron job runs every 60s for global cleanup

### 4.2 Graph Schema (In-Memory)

```python
class Node:
    id: str
    content: str              # Scene text (max 300 tokens)
    entropy_score: float      # 0-1, updated per activation
    created_at: timestamp
    activation_count: int     # Prevent infinite loops
    vote_terminate: bool

class Edge:
    id: str
    source: node_id
    target: node_id
    type: Literal["causal", "thematic", "temporal", "contradiction"]
    locked: bool              # User-override protection
    weight: float             # Narrative strength (0-1)
```

**Storage**: Redis (if deploying) or Python `networkx` + `dataclasses` (local prototype). No persistence—session dies on browser close.

### 4.3 Integration Points

- **LLM API**: OpenAI GPT-4o-mini for Scene Agents (cost-efficient), GPT-4o for Meta-Narrator (quality-critical)
- **Frontend**: React + D3.js (force-directed graph layout) + Socket.io client
- **Rate Limiting**: Max 10 concurrent LLM calls (prevent API quota exhaustion)

### 4.4 Security & Privacy

- **Data Handling**: All graph content ephemeral; no logging of user seeds to persistent storage
- **API Key Management**: Server-side only; rotate key if exposed
- **Content Filter**: Basic keyword filter on seed input (prevent abuse of LLM API)

---

## 5. Risks & Roadmap

### 5.1 Phased Rollout (5-Day Sprint)

**Day 1-2: Core Graph Engine**

- Build in-memory hypergraph structure
- Implement basic node/edge CRUD
- WebSocket scaffolding

**Day 3: Agent System**

- Prompt engineering for Scene Agent (mutation commands)
- Entropy evaluation pipeline
- Meta-Narrator pruning logic

**Day 4: UX & Visualization**

- D3.js real-time graph rendering
- Entropy heatmap coloring
- Lock/fork interaction logic

**Day 5: Integration & Hardening**

- End-to-end testing with 100-node stress test
- Cost optimization (prompt compression)
- Demo video/documentation

### 5.2 Technical Risks

| Risk                            | Mitigation                                                                                                                        |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| **API Cost Explosion**          | Stateless design requires full context in prompts; implement aggressive context compression (summarize parent nodes >2 hops away) |
| **Recursive Mutation Storm**    | Rate limit: Max 1 mutation per node per 30 seconds; global cooldown if >5 mutations/10sec                                         |
| **Graph Fragmentation**         | Meta-Narrator ensures weakly connected components are merged or pruned; minimum 1 path from any node to Node 0                    |
| **LLM Latency Kills Real-Time** | Streaming responses: Show "thinking..." state while LLM generates; update graph on completion, not during                         |
| **Entropy Hallucination**       | LLM judge may disagree with human "boring"; implement override button for user to force mutation                                  |

### 5.3 Future Roadmap (Post-Prototype)

- **v0.2**: Persistent graph states (save interesting forks)
- **v0.3**: Multi-user "tournament mode" (graphs compete for coherence scores)
- **v0.4**: Local LLM support (Llama 3.1) to eliminate API costs

---

## Appendix: Prompt Templates (Draft)

**Scene Agent System Prompt**:

```
You are a Scene Agent in a narrative hypergraph. Your node contains a story scene.
CONTEXT: Parent scene: {parent_content}
TASK: Either continue the narrative (2-3 sentences) OR mutate the graph.
ENTROPY CHECK: Rate current continuity/novelty/tension (0-1).
If entropy <0.4, you MUST mutate: ADD_NODE, SPLIT_NODE, REMOVE_EDGE, or VOTE_TERMINATE.
Respond in JSON: {"content": "...", "entropy": 0.0, "mutation": null or {...}}
```

**Meta-Narrator Prompt**:

```
Evaluate this narrative hypergraph for global coherence:
{sampled_nodes}
Identify contradictions and low-entropy leaf nodes.
Return: {"global_coherence": 0.0, "prune_nodes": [ids], "contradictions": [...]}
```
