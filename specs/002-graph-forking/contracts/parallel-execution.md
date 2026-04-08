# Parallel Execution Contract

**Interface**: Parallel Graph Execution API
**Type**: Internal Service Contract
**Status**: Draft

## ExecutionState

State tracking for parallel graph execution.

```python
class ExecutionStatus(str, Enum):
    """Status of a graph execution instance."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


class ExecutionState(BaseModel):
    """Current execution state for a graph instance."""

    graphId: str = Field(
        ...,
        description="Graph being executed",
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    )

    status: ExecutionStatus = Field(
        ...,
        description="Current execution status"
    )

    currentNodeId: Optional[str] = Field(
        default=None,
        description="ID of currently executing node"
    )

    completedNodes: int = Field(
        default=0,
        description="Count of completed nodes",
        ge=0
    )

    totalNodes: int = Field(
        ...,
        description="Total nodes in graph",
        ge=0
    )

    progress: float = Field(
        ...,
        description="Execution progress 0.0 to 1.0",
        ge=0.0,
        le=1.0
    )

    startedAt: Optional[datetime] = Field(
        default=None,
        description="When execution started"
    )

    lastActivity: datetime = Field(
        ...,
        description="Timestamp of last execution activity"
    )


class ParallelExecutionState(BaseModel):
    """State of all parallel graph executions."""

    executions: list[ExecutionState] = Field(
        ...,
        description="Execution states for all active graphs",
        max_length=50
    )

    activeCount: int = Field(
        ...,
        description="Number of currently running executions",
        ge=0
    )

    maxParallel: int = Field(
        default=10,
        description="Maximum allowed parallel executions",
        ge=1,
        le=50
    )
```

## Isolation Guarantees

```python
ISOLATION_CONTRACT = """
Graph Execution Isolation Requirements:

1. STATE ISOLATION
   - Each graph instance has independent node/edge state
   - Mutations to one graph never affect another
   - Shared history (up to fork point) is immutable

2. MEMORY ISOLATION
   - Each graph execution has separate memory space
   - No shared mutable objects between graphs
   - Deep copy enforced for all cross-graph operations

3. RANDOM STATE ISOLATION
   - Each graph has independent RNG with its own seed
   - Seed scoping prevents cross-graph randomness leakage
   - Deterministic per-graph, independent across graphs

4. PERSISTENCE ISOLATION
   - Each graph stored in separate file
   - No shared write operations
   - Atomic saves prevent cross-contamination

5. EXECUTION ISOLATION
   - Graph executions are logically parallel
   - No blocking between graph operations
   - Background operations don't block foreground UI
"""


class IsolationViolation(BaseModel):
    """Report of isolation violation detected."""

    violationType: str = Field(
        ...,
        description="Type: state, memory, random, persistence, execution"
    )

    sourceGraphId: str = Field(..., description="Graph that caused violation")
    affectedGraphId: str = Field(..., description="Graph that was affected")

    description: str = Field(..., description="Human-readable violation details")

    detectedAt: datetime = Field(..., description="When violation was detected")
```

## Service Interface

```python
class MultiGraphExecutor(ABC):
    """Service interface for parallel graph execution."""

    @abstractmethod
    async def execute_graph(
        self,
        graph_id: str,
        entry_node: Optional[str] = None
    ) -> ExecutionState:
        """
        Begin or resume execution of a graph instance.

        Args:
            graph_id: Graph to execute
            entry_node: Optional specific node to start from

        Returns:
            Current execution state

        Raises:
            GraphNotFoundError: If graph doesn't exist
            MaxParallelExceeded: If too many graphs already running

        Isolation:
            Execution is fully isolated from other running graphs
        """
        pass

    @abstractmethod
    async def pause_graph(
        self,
        graph_id: str
    ) -> ExecutionState:
        """
        Pause execution of a graph.

        Args:
            graph_id: Graph to pause

        Returns:
            Updated execution state
        """
        pass

    @abstractmethod
    async def resume_graph(
        self,
        graph_id: str
    ) -> ExecutionState:
        """
        Resume paused graph execution.

        Args:
            graph_id: Graph to resume

        Returns:
            Updated execution state
        """
        pass

    @abstractmethod
    async def stop_graph(
        self,
        graph_id: str
    ) -> ExecutionState:
        """
        Stop execution of a graph (preserves state).

        Args:
            graph_id: Graph to stop

        Returns:
            Final execution state
        """
        pass

    @abstractmethod
    async def get_execution_state(
        self,
        graph_id: str
    ) -> Optional[ExecutionState]:
        """
        Get current execution state for a graph.

        Args:
            graph_id: Graph to query

        Returns:
            Execution state or None if not executing
        """
        pass

    @abstractmethod
    async def get_all_execution_states(self) -> ParallelExecutionState:
        """
        Get execution states for all graphs.

        Returns:
            Combined execution state
        """
        pass

    @abstractmethod
    async def advance_step(
        self,
        graph_id: str
    ) -> tuple[ExecutionState, Any]:
        """
        Advance a graph by one execution step.

        Args:
            graph_id: Graph to advance

        Returns:
            Tuple of (new state, step result data)

        Isolation:
            Step execution must not affect other running graphs
        """
        pass
```

## Conflict Detection

```python
class ConflictInfo(BaseModel):
    """Information about a detected conflict."""

    graphId: str = Field(..., description="Graph with conflict")
    lastLocalModified: datetime = Field(..., description="Local last modified time")
    lastRemoteModified: datetime = Field(..., description="Remote (background) modified time")
    conflictingFields: list[str] = Field(..., description="Fields that conflict")


class ConflictResolution(str, Enum):
    """Resolution strategy for conflicts."""

    KEEP_LOCAL = "keep_local"      # Last-write-wins, keep user's changes
    ACCEPT_REMOTE = "accept_remote"  # Discard local, use background result
    MANUAL_MERGE = "manual_merge"    # Require user intervention


class ConflictHandler(ABC):
    """Interface for handling background/user conflicts."""

    @abstractmethod
    async def detect_conflicts(
        self,
        graph_id: str,
        local_state: dict,
        remote_state: dict
    ) -> Optional[ConflictInfo]:
        """
        Detect conflicts between local and remote state.

        Args:
            graph_id: Graph to check
            local_state: Current local state
            remote_state: State from background operation

        Returns:
            Conflict info if conflict detected, None otherwise
        """
        pass

    @abstractmethod
    async def resolve_conflict(
        self,
        conflict: ConflictInfo,
        strategy: ConflictResolution
    ) -> dict:
        """
        Resolve a conflict using specified strategy.

        Args:
            conflict: Conflict information
            strategy: Resolution strategy

        Returns:
            Resolved state
        """
        pass

    @abstractmethod
    def notify_conflict(
        self,
        conflict: ConflictInfo
    ) -> None:
        """
        Notify user of conflict (non-blocking).

        Per spec clarification: optimistic locking with last-write-wins,
        but notify user when conflicts occur.
        """
        pass
```

## Performance & Resource Limits

```python
RESOURCE_LIMITS = {
    "max_parallel_graphs": 10,  # Primary workflow optimization
    "max_supported_graphs": 50,  # Functional limit
    "max_nodes_per_graph": 10000,
    "max_memory_per_graph_mb": 100,
    "background_operation_timeout_sec": 30
}


class ResourceUsage(BaseModel):
    """Current resource usage statistics."""

    activeGraphs: int = Field(..., ge=0)
    totalMemoryMB: float = Field(..., ge=0.0)
    cpuPercent: float = Field(..., ge=0.0, le=100.0)

    warning: Optional[str] = Field(
        default=None,
        description="Resource warning if approaching limits"
    )
```
