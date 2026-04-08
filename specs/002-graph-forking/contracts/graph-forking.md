# Graph Forking Contract

**Interface**: Graph Forking API
**Type**: Internal Service Contract
**Status**: Draft

## GraphForkRequest

Request payload for creating a graph fork.

```python
class GraphForkRequest(BaseModel):
    """Request to create a fork from an existing graph at a specific edge."""

    sourceGraphId: str = Field(
        ...,
        description="Unique identifier of the source graph to fork from",
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )

    forkEdgeId: str = Field(
        ...,
        description="ID of the edge where the fork should be created",
        min_length=1,
        max_length=255,
        examples=["edge_42", "decision_point_3"]
    )

    customSeed: Optional[str] = Field(
        default=None,
        description="Optional custom seed for deterministic generation. If not provided, auto-generated.",
        min_length=1,
        max_length=255,
        examples=["narrative_variant_a", "12345"]
    )

    label: Optional[str] = Field(
        default=None,
        description="Optional user-friendly label for this fork",
        min_length=1,
        max_length=100,
        examples=["Hero takes the left path"]
    )

# JSON Schema
def get_graph_fork_request_schema() -> dict:
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "GraphForkRequest",
        "type": "object",
        "required": ["sourceGraphId", "forkEdgeId"],
        "properties": {
            "sourceGraphId": {
                "type": "string",
                "format": "uuid",
                "description": "Source graph identifier"
            },
            "forkEdgeId": {
                "type": "string",
                "minLength": 1,
                "maxLength": 255,
                "description": "Edge identifier where fork occurs"
            },
            "customSeed": {
                "type": ["string", "null"],
                "minLength": 1,
                "maxLength": 255,
                "description": "Optional custom seed value"
            },
            "label": {
                "type": ["string", "null"],
                "minLength": 1,
                "maxLength": 100,
                "description": "Optional fork label"
            }
        },
        "additionalProperties": False
    }
```

## GraphForkResponse

Response payload after successful fork creation.

```python
class EdgeReference(BaseModel):
    """Reference to a specific edge in a graph."""

    edgeId: str = Field(..., description="Edge identifier")
    sourceNodeId: str = Field(..., description="Source node of edge")
    targetNodeId: str = Field(..., description="Target node of edge")


class GraphForkResponse(BaseModel):
    """Response after successfully creating a graph fork."""

    forkedGraphId: str = Field(
        ...,
        description="Unique identifier of the newly created forked graph",
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    )

    forkPoint: EdgeReference = Field(
        ...,
        description="The edge where the fork was created"
    )

    seed: str = Field(
        ...,
        description="The seed value used for this fork (custom or auto-generated)",
        min_length=1,
        max_length=255
    )

    creationTime: datetime = Field(
        ...,
        description="ISO 8601 timestamp when the fork was created"
    )

    parentGraphId: str = Field(
        ...,
        description="ID of the source graph",
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    )

    graphSummary: GraphSummary = Field(
        ...,
        description="Summary of the newly created graph"
    )

# JSON Schema
def get_graph_fork_response_schema() -> dict:
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "GraphForkResponse",
        "type": "object",
        "required": [
            "forkedGraphId", "forkPoint", "seed",
            "creationTime", "parentGraphId", "graphSummary"
        ],
        "properties": {
            "forkedGraphId": {
                "type": "string",
                "format": "uuid",
                "description": "New forked graph identifier"
            },
            "forkPoint": {
                "type": "object",
                "required": ["edgeId", "sourceNodeId", "targetNodeId"],
                "properties": {
                    "edgeId": {"type": "string"},
                    "sourceNodeId": {"type": "string"},
                    "targetNodeId": {"type": "string"}
                }
            },
            "seed": {
                "type": "string",
                "description": "Seed value used"
            },
            "creationTime": {
                "type": "string",
                "format": "date-time",
                "description": "Creation timestamp"
            },
            "parentGraphId": {
                "type": "string",
                "format": "uuid",
                "description": "Parent graph identifier"
            },
            "graphSummary": {
                "type": "object",
                "description": "Summary of new graph"
            }
        },
        "additionalProperties": False
    }
```

## Error Responses

```python
class ForkErrorCode(str, Enum):
    """Error codes for graph forking operations."""

    SOURCE_GRAPH_NOT_FOUND = "SOURCE_GRAPH_NOT_FOUND"
    EDGE_NOT_FOUND = "EDGE_NOT_FOUND"
    INVALID_SEED = "INVALID_SEED"
    GRAPH_LIMIT_EXCEEDED = "GRAPH_LIMIT_EXCEEDED"
    FORK_CYCLE_DETECTED = "FORK_CYCLE_DETECTED"
    COHERENCE_VIOLATION = "COHERENCE_VIOLATION"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class GraphForkError(BaseModel):
    """Error response for failed fork operations."""

    error: ForkErrorCode = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[dict] = Field(default=None, description="Additional error context")


# HTTP Status Mappings
ERROR_STATUS_CODES = {
    ForkErrorCode.SOURCE_GRAPH_NOT_FOUND: 404,
    ForkErrorCode.EDGE_NOT_FOUND: 404,
    ForkErrorCode.INVALID_SEED: 400,
    ForkErrorCode.GRAPH_LIMIT_EXCEEDED: 429,
    ForkErrorCode.FORK_CYCLE_DETECTED: 400,
    ForkErrorCode.COHERENCE_VIOLATION: 422,
    ForkErrorCode.INTERNAL_ERROR: 500
}
```

## Service Interface

```python
class GraphForker(ABC):
    """Service interface for graph forking operations."""

    @abstractmethod
    async def fork_graph(
        self,
        request: GraphForkRequest
    ) -> GraphForkResponse:
        """
        Create a fork of an existing graph at the specified edge.

        Args:
            request: The fork request with source graph, edge, and optional seed

        Returns:
            Response with new graph ID, fork point, and seed used

        Raises:
            GraphForkError: If fork cannot be completed

        Performance:
            Must complete within 500ms per CA-005
        """
        pass

    @abstractmethod
    async def validate_fork_request(
        self,
        request: GraphForkRequest
    ) -> tuple[bool, Optional[GraphForkError]]:
        """
        Validate a fork request without executing.

        Args:
            request: The fork request to validate

        Returns:
            Tuple of (is_valid, error_if_invalid)
        """
        pass
```

## Determinism Contract

**Seed Determinism Guarantee**:

```python
DETERMINISM_CONTRACT = """
Given:
  - Same source graph state
  - Same fork edge
  - Same seed value (custom or auto-generated)
When:
  - fork_graph() is called multiple times
Then:
  - All resulting graphs have identical node/edge structure
  - All resulting graphs have identical narrative content
  - Graph IDs are unique (UUID-based, not seed-based)
  - Only graph content is deterministic, not graph identity
"""
```

**Verification Test**:
```python
async def test_deterministic_fork():
    """Verify deterministic fork behavior."""
    # Create initial graph
    source = await create_sample_graph()
    edge_id = "test_edge_1"
    seed = "deterministic_test_seed_123"

    # Fork twice with same parameters
    fork1 = await forker.fork_graph(GraphForkRequest(
        sourceGraphId=source.id,
        forkEdgeId=edge_id,
        customSeed=seed
    ))

    fork2 = await forker.fork_graph(GraphForkRequest(
        sourceGraphId=source.id,
        forkEdgeId=edge_id,
        customSeed=seed
    ))

    # Verify: IDs are different but content is identical
    assert fork1.forkedGraphId != fork2.forkedGraphId
    assert fork1.seed == fork2.seed == seed
    # Content comparison would load and compare graph structures
```
