"""Graph forking service with lineage tracking and isolation guarantees."""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from uuid import uuid4

import networkx as nx
from pydantic import JsonValue

from models.common import GraphT
from models.errors import ForkErrorCode, GraphForkError
from models.execution import RESOURCE_LIMITS
from models.fork_point import ForkPoint
from models.graph_instance import GraphInstance, GraphLifecycleState
from models.graph_lineage import GraphLineage
from models.requests import (
    CUSTOM_SEED_MAX_LENGTH,
    CUSTOM_SEED_MIN_LENGTH,
    GraphForkRequest,
)
from models.responses import EdgeReference, GraphForkResponse
from models.seed_config import SeedConfiguration
from persistence.graph_store import GraphStore
from persistence.lineage_store import LineageStore
from services.coherence_scorer import COHERENCE_THRESHOLD, CoherenceScorer
from services.structured_logging import OperationLogEntry, log_operation
from services.utils import initialize_service_deps
from utils.time import utc_now

__all__ = ["GraphForker"]


class GraphForker:
    """Create isolated forks from existing graph instances."""

    def __init__(
        self,
        *,
        graph_store: GraphStore | None = None,
        lineage_store: LineageStore | None = None,
        root_dir: Path | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._graph_store, self._lineage_store, self._logger = initialize_service_deps(
            graph_store=graph_store,
            lineage_store=lineage_store,
            root_dir=root_dir,
            logger=logger,
        )

    def validate_fork_request(
        self,
        request: GraphForkRequest,
    ) -> tuple[bool, GraphForkError | None]:
        """Validate that source graph and fork edge exist before forking."""

        seed_error = _validate_custom_seed(request.custom_seed)
        if seed_error is not None:
            return False, seed_error

        try:
            source_graph = self._graph_store.load(request.source_graph_id)
        except FileNotFoundError:
            return (
                False,
                GraphForkError(
                    error=ForkErrorCode.SOURCE_GRAPH_NOT_FOUND,
                    message="source graph does not exist",
                    details={"source_graph_id": request.source_graph_id},
                ),
            )

        edge_reference = _find_edge_reference(
            source_graph.graph_data,
            request.fork_edge_id,
        )
        if edge_reference is None:
            return (
                False,
                GraphForkError(
                    error=ForkErrorCode.EDGE_NOT_FOUND,
                    message="fork edge does not exist in source graph",
                    details={
                        "source_graph_id": request.source_graph_id,
                        "fork_edge_id": request.fork_edge_id,
                    },
                ),
            )

        graph_limit = RESOURCE_LIMITS["max_supported_graphs"]
        if len(self._graph_store.list_graphs()) >= graph_limit:
            return (
                False,
                GraphForkError(
                    error=ForkErrorCode.GRAPH_LIMIT_EXCEEDED,
                    message=(
                        f"maximum graph limit reached ({graph_limit}); "
                        "archive or delete a graph before forking"
                    ),
                    details={"graph_limit": graph_limit},
                ),
            )

        if _edge_participates_in_cycle(source_graph.graph_data, edge_reference):
            return (
                False,
                GraphForkError(
                    error=ForkErrorCode.FORK_CYCLE_DETECTED,
                    message=(
                        "fork edge introduces a circular reference; "
                        "choose a non-cyclic transition"
                    ),
                    details={
                        "fork_edge_id": request.fork_edge_id,
                        "source_graph_id": request.source_graph_id,
                    },
                ),
            )

        coherence_error = _validate_transition_coherence(
            source_graph.graph_data,
            edge_reference,
        )
        if coherence_error is not None:
            return (
                False,
                GraphForkError(
                    error=ForkErrorCode.COHERENCE_VIOLATION,
                    message=coherence_error,
                    details={
                        "fork_edge_id": request.fork_edge_id,
                        "source_graph_id": request.source_graph_id,
                        "coherence_threshold": COHERENCE_THRESHOLD,
                    },
                ),
            )

        return True, None

    def fork_graph(self, request: GraphForkRequest) -> GraphForkResponse:
        """Fork a source graph at a given edge and persist child lineage."""

        started_at = utc_now()
        log_operation(
            self._logger,
            OperationLogEntry(
                operation="fork",
                status="started",
                graph_id=request.source_graph_id,
                started_at=started_at,
                metadata={"fork_edge_id": request.fork_edge_id},
            ),
        )

        is_valid, error = self.validate_fork_request(request)
        if not is_valid and error is not None:
            log_operation(
                self._logger,
                OperationLogEntry(
                    operation="fork",
                    status="failed",
                    graph_id=request.source_graph_id,
                    started_at=started_at,
                    completed_at=utc_now(),
                    metadata={
                        "error_code": error.error.value,
                        "error_message": error.message,
                        "fork_edge_id": request.fork_edge_id,
                    },
                ),
                level=logging.ERROR,
            )
            raise ValueError(f"{error.error.value}: {error.message}")

        source_graph = self._graph_store.load(request.source_graph_id)
        edge_reference = _find_edge_reference(
            source_graph.graph_data, request.fork_edge_id
        )
        if edge_reference is None:
            raise ValueError("edge disappeared during fork validation")

        copied_graph = _copy_graph_history_up_to_edge(
            source_graph.graph_data,
            edge_reference.source_node_id,
            edge_reference.target_node_id,
        )
        forked_graph_id = str(uuid4())
        created_at = utc_now()
        normalized_custom_seed = _normalize_custom_seed(request.custom_seed)
        seed_config = SeedConfiguration.generate(seed=normalized_custom_seed)
        seed_scope = _build_seed_scope(
            source_graph_id=request.source_graph_id,
            fork_edge_id=request.fork_edge_id,
        )
        fork_metadata = copy.deepcopy(source_graph.metadata)
        fork_metadata.update(
            {
                "seed_numeric_state": seed_config.numeric_state(),
                "seed_scope": seed_scope,
                "seed_scoped_numeric_state": seed_config.scoped_numeric_state(
                    scope=seed_scope
                ),
            }
        )
        fork_point = ForkPoint(
            source_graph_id=request.source_graph_id,
            fork_edge_id=request.fork_edge_id,
            timestamp=created_at,
            label=request.label,
        )
        forked_graph = GraphInstance(
            id=forked_graph_id,
            name=request.label
            if request.label is not None
            else f"{source_graph.name} fork",
            created_at=created_at,
            fork_point=fork_point,
            seed_config=seed_config,
            graph_data=copied_graph,
            metadata=fork_metadata,
            last_modified=created_at,
            state=GraphLifecycleState.ACTIVE,
        )
        create_started_at = utc_now()
        self._graph_store.save(forked_graph)
        log_operation(
            self._logger,
            OperationLogEntry(
                operation="create",
                status="success",
                graph_id=forked_graph.id,
                started_at=create_started_at,
                completed_at=utc_now(),
                metadata={
                    "parent_graph_id": source_graph.id,
                    "fork_edge_id": request.fork_edge_id,
                },
            ),
        )

        lineage = _build_lineage(
            lineage_store=self._lineage_store,
            parent_graph_id=source_graph.id,
            child_graph_id=forked_graph.id,
        )
        self._lineage_store.add_lineage(lineage)

        response = GraphForkResponse(
            forked_graph_id=forked_graph.id,
            fork_point=edge_reference,
            seed=seed_config.seed,
            creation_time=created_at,
            parent_graph_id=source_graph.id,
            graph_summary=forked_graph.to_summary(),
        )

        log_operation(
            self._logger,
            OperationLogEntry(
                operation="fork",
                status="success",
                graph_id=forked_graph.id,
                started_at=started_at,
                completed_at=utc_now(),
                metadata={
                    "parent_graph_id": source_graph.id,
                    "fork_edge_id": request.fork_edge_id,
                    "branch_id": lineage.branch_id,
                },
            ),
        )
        return response


def _find_edge_reference(graph: GraphT, fork_edge_id: str) -> EdgeReference | None:
    """Return edge node references for a fork edge identifier."""

    for source_node_id, target_node_id, edge_data in graph.edges(data=True):
        if edge_data.get("edge_id") == fork_edge_id:
            return EdgeReference(
                edge_id=fork_edge_id,
                source_node_id=str(source_node_id),
                target_node_id=str(target_node_id),
            )

    return None


def _copy_graph_history_up_to_edge(
    source_graph: GraphT,
    source_node_id: str,
    target_node_id: str,
) -> GraphT:
    """Deep-copy graph history up to the selected fork edge."""

    history_nodes = set(nx.ancestors(source_graph, target_node_id))
    history_nodes.add(source_node_id)
    history_nodes.add(target_node_id)

    subgraph = source_graph.subgraph(history_nodes).copy()
    copied_graph = nx.DiGraph(subgraph)
    copied_graph.graph = copy.deepcopy(source_graph.graph)
    return copy.deepcopy(copied_graph)


def _build_lineage(
    *,
    lineage_store: LineageStore,
    parent_graph_id: str,
    child_graph_id: str,
) -> GraphLineage:
    """Build the lineage record for a new forked graph."""

    depth = len(lineage_store.get_ancestry(parent_graph_id)) + 1
    return GraphLineage(
        parent_graph_id=parent_graph_id,
        child_graph_id=child_graph_id,
        depth=depth,
        branch_id=f"{parent_graph_id[:8]}-{child_graph_id[:8]}-d{depth}",
    )


def _normalize_custom_seed(custom_seed: str | None) -> str | None:
    """Normalize optional custom seed input for deterministic handling."""

    if custom_seed is None:
        return None

    return custom_seed.strip()


def _build_seed_scope(*, source_graph_id: str, fork_edge_id: str) -> str:
    """Build a deterministic scope key for per-fork seed state."""

    return f"{source_graph_id}:{fork_edge_id}"


def _validate_custom_seed(custom_seed: str | None) -> GraphForkError | None:
    """Validate optional custom seed using contract min/max boundaries."""

    if custom_seed is None:
        return None

    if not isinstance(custom_seed, str):
        return GraphForkError(
            error=ForkErrorCode.INVALID_SEED,
            message="custom seed must be a string",
            details={"custom_seed": str(custom_seed)},
        )

    normalized_seed = custom_seed.strip()
    seed_length = len(normalized_seed)
    if seed_length < CUSTOM_SEED_MIN_LENGTH or seed_length > CUSTOM_SEED_MAX_LENGTH:
        return GraphForkError(
            error=ForkErrorCode.INVALID_SEED,
            message=(
                "custom seed length must be between "
                f"{CUSTOM_SEED_MIN_LENGTH} and {CUSTOM_SEED_MAX_LENGTH}"
            ),
            details={
                "seed_length": seed_length,
                "min_length": CUSTOM_SEED_MIN_LENGTH,
                "max_length": CUSTOM_SEED_MAX_LENGTH,
            },
        )

    return None


def _edge_participates_in_cycle(
    graph: GraphT,
    edge_reference: EdgeReference,
) -> bool:
    """Return ``True`` when an edge is part of a directed cycle."""

    return nx.has_path(
        graph,
        edge_reference.target_node_id,
        edge_reference.source_node_id,
    )


def _validate_transition_coherence(
    graph: GraphT,
    edge_reference: EdgeReference,
) -> str | None:
    """Validate coherence threshold for the selected narrative transition."""

    edge_data = graph.get_edge_data(
        edge_reference.source_node_id,
        edge_reference.target_node_id,
        default={},
    )
    if not isinstance(edge_data, dict):
        return "fork edge metadata is unavailable for coherence validation"

    normalized_edge_data: dict[str, JsonValue] = {
        str(key): value for key, value in edge_data.items()
    }
    coherence_scorer = CoherenceScorer()
    coherence_score = _resolve_transition_coherence_score(
        coherence_scorer=coherence_scorer,
        edge_data=normalized_edge_data,
    )
    if coherence_score is None:
        return (
            "fork edge is missing coherence metadata; provide coherence_score "
            "or thematic_continuity/logical_continuity"
        )

    if not coherence_scorer.is_coherent(coherence_score):
        return (
            f"coherence score must be greater than {COHERENCE_THRESHOLD}; "
            f"received {coherence_score:.3f}"
        )

    return None


def _resolve_transition_coherence_score(
    *,
    coherence_scorer: CoherenceScorer,
    edge_data: dict[str, JsonValue],
) -> float | None:
    """Resolve transition coherence from explicit score or component metrics."""

    explicit_score = edge_data.get("coherence_score")
    if isinstance(explicit_score, float | int):
        return float(explicit_score)

    thematic = edge_data.get("thematic_continuity")
    logical = edge_data.get("logical_continuity")
    if not isinstance(thematic, float | int) or not isinstance(logical, float | int):
        return None

    return coherence_scorer.score_transition(
        thematic_continuity=float(thematic),
        logical_continuity=float(logical),
    )
