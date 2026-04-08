# Multi-Graph View Contract

**Interface**: Multi-Graph View API
**Type**: Internal Service Contract
**Status**: Draft

## GraphSummary

Lightweight representation of a graph for list views.

```python
class GraphSummary(BaseModel):
    """Summary information for a graph instance."""

    id: str = Field(
        ...,
        description="Unique graph identifier",
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    )

    name: str = Field(
        ...,
        description="Human-readable graph name",
        min_length=1,
        max_length=100
    )

    nodeCount: int = Field(
        ...,
        description="Number of nodes in the graph",
        ge=0
    )

    edgeCount: int = Field(
        ...,
        description="Number of edges in the graph",
        ge=0
    )

    createdAt: datetime = Field(
        ...,
        description="Graph creation timestamp"
    )

    forkSource: Optional[str] = Field(
        default=None,
        description="Parent graph ID if this is a fork, null if root graph",
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    )

    currentState: str = Field(
        ...,
        description="Description of current narrative state",
        max_length=200
    )

    lastModified: datetime = Field(
        ...,
        description="Last modification timestamp for conflict detection"
    )

    labels: list[str] = Field(
        default_factory=list,
        description="User-assigned labels for organization"
    )


# JSON Schema
def get_graph_summary_schema() -> dict:
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "GraphSummary",
        "type": "object",
        "required": [
            "id", "name", "nodeCount", "edgeCount",
            "createdAt", "currentState", "lastModified"
        ],
        "properties": {
            "id": {
                "type": "string",
                "format": "uuid",
                "description": "Graph identifier"
            },
            "name": {
                "type": "string",
                "minLength": 1,
                "maxLength": 100,
                "description": "Graph name"
            },
            "nodeCount": {
                "type": "integer",
                "minimum": 0,
                "description": "Number of nodes"
            },
            "edgeCount": {
                "type": "integer",
                "minimum": 0,
                "description": "Number of edges"
            },
            "createdAt": {
                "type": "string",
                "format": "date-time",
                "description": "Creation timestamp"
            },
            "forkSource": {
                "type": ["string", "null"],
                "format": "uuid",
                "description": "Parent graph ID if forked"
            },
            "currentState": {
                "type": "string",
                "maxLength": 200,
                "description": "Current narrative state description"
            },
            "lastModified": {
                "type": "string",
                "format": "date-time",
                "description": "Last modification timestamp"
            },
            "labels": {
                "type": "array",
                "items": {"type": "string"},
                "description": "User labels"
            }
        },
        "additionalProperties": False
    }
```

## MultiGraphView

Complete multi-graph view state.

```python
class ViewPreferences(BaseModel):
    """User preferences for the multi-graph view."""

    sortBy: str = Field(
        default="createdAt",
        description="Sort field: createdAt, name, nodeCount, lastModified",
        pattern=r"^(createdAt|name|nodeCount|lastModified)$"
    )

    sortOrder: str = Field(
        default="desc",
        description="Sort direction: asc or desc",
        pattern=r"^(asc|desc)$"
    )

    displayMode: str = Field(
        default="list",
        description="View mode: list, grid, or tree",
        pattern=r"^(list|grid|tree)$"
    )


class FilterState(BaseModel):
    """Active filters for graph list."""

    searchQuery: Optional[str] = Field(
        default=None,
        description="Text search across names and labels",
        max_length=100
    )

    forkSource: Optional[str] = Field(
        default=None,
        description="Filter by parent graph ID",
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    )

    createdAfter: Optional[datetime] = Field(
        default=None,
        description="Include graphs created after this date"
    )

    createdBefore: Optional[datetime] = Field(
        default=None,
        description="Include graphs created before this date"
    )

    status: Optional[str] = Field(
        default=None,
        description="Filter by status: active or archived",
        pattern=r"^(active|archived)$"
    )


class MultiGraphView(BaseModel):
    """Complete multi-graph view with all graphs and view state."""

    graphs: list[GraphSummary] = Field(
        ...,
        description="List of graph summaries (may be filtered/sorted)",
        max_length=1000  # Hard limit for performance
    )

    activeGraphId: Optional[str] = Field(
        default=None,
        description="ID of currently selected/active graph",
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    )

    totalCount: int = Field(
        ...,
        description="Total number of graphs (before filtering)",
        ge=0
    )

    filters: FilterState = Field(
        default_factory=FilterState,
        description="Currently applied filters"
    )

    viewPrefs: ViewPreferences = Field(
        default_factory=ViewPreferences,
        description="User view preferences"
    )


# JSON Schema
def get_multi_graph_view_schema() -> dict:
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "MultiGraphView",
        "type": "object",
        "required": ["graphs", "totalCount", "filters", "viewPrefs"],
        "properties": {
            "graphs": {
                "type": "array",
                "items": {"$ref": "#/definitions/GraphSummary"},
                "maxItems": 1000,
                "description": "Graph summaries"
            },
            "activeGraphId": {
                "type": ["string", "null"],
                "format": "uuid",
                "description": "Currently active graph"
            },
            "totalCount": {
                "type": "integer",
                "minimum": 0,
                "description": "Total graphs before filtering"
            },
            "filters": {
                "type": "object",
                "description": "Active filters"
            },
            "viewPrefs": {
                "type": "object",
                "description": "View preferences"
            }
        },
        "additionalProperties": False
    }
```

## GraphSwitchRequest

Request to switch to a different graph.

```python
class GraphSwitchRequest(BaseModel):
    """Request to switch active context to a different graph."""

    targetGraphId: str = Field(
        ...,
        description="ID of the graph to switch to",
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    )

    preserveCurrent: bool = Field(
        default=True,
        description="Whether to save current graph state before switching"
    )


class GraphSwitchResponse(BaseModel):
    """Response after successfully switching graphs."""

    previousGraphId: Optional[str] = Field(
        default=None,
        description="ID of the graph that was active before switch"
    )

    currentGraphId: str = Field(
        ...,
        description="ID of the now-active graph"
    )

    loadTimeMs: float = Field(
        ...,
        description="Time taken to load the graph in milliseconds",
        ge=0
    )

    graphSummary: GraphSummary = Field(
        ...,
        description="Summary of the now-active graph"
    )


# JSON Schema
def get_graph_switch_request_schema() -> dict:
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "GraphSwitchRequest",
        "type": "object",
        "required": ["targetGraphId"],
        "properties": {
            "targetGraphId": {
                "type": "string",
                "format": "uuid",
                "description": "Target graph to activate"
            },
            "preserveCurrent": {
                "type": "boolean",
                "default": True,
                "description": "Save current state before switch"
            }
        },
        "additionalProperties": False
    }
```

## Service Interface

```python
class GraphManager(ABC):
    """Service interface for multi-graph operations."""

    @abstractmethod
    async def get_multi_graph_view(
        self,
        filters: Optional[FilterState] = None,
        view_prefs: Optional[ViewPreferences] = None,
        active_graph_id: Optional[str] = None
    ) -> MultiGraphView:
        """
        Retrieve multi-graph view with all visible graphs.

        Args:
            filters: Optional filters to apply
            view_prefs: Optional view preferences
            active_graph_id: Currently active graph ID

        Returns:
            MultiGraphView with filtered/sorted graphs

        Performance:
            Must complete within 200ms for up to 50 graphs per CA-005
        """
        pass

    @abstractmethod
    async def switch_graph(
        self,
        request: GraphSwitchRequest
    ) -> GraphSwitchResponse:
        """
        Switch active context to a different graph.

        Args:
            request: Switch request with target graph ID

        Returns:
            Response with previous/current graph info and load time

        Raises:
            GraphNotFoundError: If target graph doesn't exist

        Performance:
            Must complete within 300ms per CA-005
        """
        pass

    @abstractmethod
    async def delete_graph(
        self,
        graph_id: str,
        force: bool = False
    ) -> None:
        """
        Delete a graph instance.

        Args:
            graph_id: ID of graph to delete
            force: If True, delete even if graph has children

        Raises:
            GraphNotFoundError: If graph doesn't exist
            GraphHasChildrenError: If graph has forks and force=False
        """
        pass

    @abstractmethod
    async def archive_graph(
        self,
        graph_id: str
    ) -> None:
        """
        Archive a graph (soft delete, can be restored).

        Args:
            graph_id: ID of graph to archive
        """
        pass
```

## Performance Contracts

```python
PERFORMANCE_CONTRACTS = {
    "multi_graph_view": {
        "max_latency_ms": 200,
        "max_graphs": 50,
        "description": "Render multi-graph view with metadata"
    },
    "graph_switch": {
        "max_latency_ms": 300,
        "max_nodes": 1000,
        "description": "Switch to graph and load complete state"
    },
    "graph_list_query": {
        "max_latency_ms": 100,
        "description": "Query graph summaries from index"
    }
}
```

## Error Responses

```python
class ViewErrorCode(str, Enum):
    """Error codes for multi-graph view operations."""

    GRAPH_NOT_FOUND = "GRAPH_NOT_FOUND"
    GRAPH_HAS_CHILDREN = "GRAPH_HAS_CHILDREN"
    INVALID_FILTER = "INVALID_FILTER"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class GraphViewError(BaseModel):
    """Error response for multi-graph operations."""

    error: ViewErrorCode = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[dict] = Field(default=None, description="Additional context")
```
