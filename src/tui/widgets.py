"""TUI helpers for command routing and inspection panels."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID, uuid4

from textual.timer import Timer
from textual.widgets import Static

from graph.session_graph import SessionGraph
from graph.utils import get_graph_node, get_scene_node
from models.commands import (
    CommandResult,
    CommandType,
    ForkSessionCommand,
    ForkSessionPayload,
    LockEdgeCommand,
    LockEdgePayload,
    TerminalCommand,
    UnlockEdgeCommand,
    UnlockEdgePayload,
)
from models.common import DriftCategory
from models.events import EventType, MutationStreamEvent
from models.graph import GraphNode
from models.node import SceneNode
from models.session import Session
from runtime.event_log import EventLog
from tui.constants import (
    DEFAULT_COMPACT_TEXT_LENGTH,
    NO_INSPECTABLE_NODE_MSG,
    SECTION_DIVIDER,
)

__all__ = [
    "build_entropy_hotspot_lines",
    "build_mutation_log_lines",
    "build_node_detail_lines",
    "ShortcutFooterBar",
    "SessionSwitcher",
    "handle_fork_request",
    "handle_lock_request",
    "handle_unlock_request",
]


class ShortcutFooterBar(Static):
    """Dedicated footer bar that shows shortcuts and generation status."""

    DEFAULT_CSS = """
    ShortcutFooterBar {
        dock: bottom;
        height: 1;
        background: $surface;
        color: $text;
        padding: 0 1;
    }
    """

    _SPINNER_FRAMES = ("|", "/", "-", "\\")

    def __init__(self, id: str | None = None) -> None:
        super().__init__(id=id)
        self._is_generating = False
        self._spinner_index = 0
        self._spinner_timer: Timer | None = None

    def on_mount(self) -> None:
        """Render the footer text when mounted."""

        self._update_display()

    def on_unmount(self) -> None:
        """Stop spinner updates when unmounted."""

        if self._spinner_timer is not None:
            self._spinner_timer.stop()
            self._spinner_timer = None

    def shortcuts_text(self) -> str:
        """Return the static shortcuts legend shown in the footer."""

        return "s Start   p Pause   r Resume   c Continue"

    def status_text(self) -> str:
        """Return the current runtime status text."""

        if not self._is_generating:
            return "Idle"

        frame = self._SPINNER_FRAMES[self._spinner_index]
        return f"{frame} Generating scene..."

    def advance_spinner_frame(self) -> None:
        """Advance the spinner and redraw the footer."""

        self._spinner_index = (self._spinner_index + 1) % len(self._SPINNER_FRAMES)
        self._update_display()

    def set_generating(self, is_generating: bool) -> None:
        """Toggle generation status and spinner activity."""

        if self._is_generating == is_generating:
            return

        self._is_generating = is_generating
        if is_generating:
            self._spinner_index = 0
            if self.is_mounted and self._spinner_timer is None:
                self._spinner_timer = self.set_interval(
                    0.15,
                    self.advance_spinner_frame,
                )
        elif self._spinner_timer is not None:
            self._spinner_timer.stop()
            self._spinner_timer = None

        self._update_display()

    def _update_display(self) -> None:
        footer_text = f"{self.shortcuts_text()}    {self.status_text()}"
        self.update(footer_text)


class _CommandRuntime(Protocol):
    """Runtime contract for dispatching terminal commands."""

    def handle_command(self, command: TerminalCommand) -> CommandResult:
        """Dispatch a terminal command."""


class _SessionSwitchRuntime(Protocol):
    """Runtime contract for switching an active session."""

    def switch_session(self, session_id: UUID) -> None:
        """Switch the active session."""


def _active_session_id(runtime: _CommandRuntime) -> UUID | None:
    """Return the runtime session identifier when available."""

    session_id = getattr(runtime, "session_id", None)
    return session_id if isinstance(session_id, UUID) else None


def _command_id(prefix: str) -> str:
    """Return a unique command identifier for a UI request."""

    return f"{prefix}-{uuid4().hex}"


def _section_lines(title: str) -> list[str]:
    return [
        SECTION_DIVIDER,
        title,
    ]


def _compact_text(text: str, *, max_length: int = DEFAULT_COMPACT_TEXT_LENGTH) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_length:
        return cleaned

    return f"{cleaned[: max_length - 1].rstrip()}…"


def _scene_snapshots(session_graph: SessionGraph) -> list[tuple[GraphNode, SceneNode]]:
    snapshots: list[tuple[GraphNode, SceneNode]] = []
    for _, node_data in session_graph.graph.nodes(data=True):
        if not isinstance(node_data, dict):
            continue

        graph_node = node_data.get("node")
        scene_node = node_data.get("scene_node")
        if isinstance(graph_node, GraphNode) and isinstance(scene_node, SceneNode):
            snapshots.append((graph_node, scene_node))

    return sorted(
        snapshots,
        key=lambda snapshot: (
            -snapshot[1].entropy_score,
            snapshot[0].node_id,
        ),
    )


def _detail_node_id(
    *,
    session: Session,
    session_graph: SessionGraph,
    node_id: str | None = None,
) -> str | None:
    if node_id is not None and session_graph.graph.has_node(node_id):
        return node_id

    for active_node_id in reversed(session.active_node_ids):
        if session_graph.graph.has_node(active_node_id):
            return active_node_id

    snapshots = _scene_snapshots(session_graph)
    if snapshots:
        return snapshots[0][0].node_id

    return None


def handle_lock_request(runtime: _CommandRuntime, edge_id: str) -> CommandResult:
    """Lock an edge by dispatching a lock-edge command through the runtime."""

    command = LockEdgeCommand(
        command_id=_command_id("ui-lock-edge"),
        session_id=_active_session_id(runtime),
        command_type=CommandType.LOCK_EDGE,
        payload=LockEdgePayload(edge_id=edge_id),
    )
    return runtime.handle_command(command)


def handle_unlock_request(runtime: _CommandRuntime, edge_id: str) -> CommandResult:
    """Unlock an edge by dispatching an unlock-edge command through the runtime."""

    command = UnlockEdgeCommand(
        command_id=_command_id("ui-unlock-edge"),
        session_id=_active_session_id(runtime),
        command_type=CommandType.UNLOCK_EDGE,
        payload=UnlockEdgePayload(edge_id=edge_id),
    )
    return runtime.handle_command(command)


def handle_fork_request(
    runtime: _CommandRuntime,
    fork_label: str | None = None,
) -> CommandResult:
    """Fork the active session by dispatching a fork-session command."""

    command = ForkSessionCommand(
        command_id=_command_id("ui-fork-session"),
        session_id=_active_session_id(runtime),
        command_type=CommandType.FORK_SESSION,
        payload=ForkSessionPayload(fork_label=fork_label),
    )
    return runtime.handle_command(command)


def build_entropy_hotspot_lines(
    *,
    session_graph: SessionGraph,
    limit: int = 5,
) -> list[str]:
    """Build deterministic entropy hotspot lines for the active graph."""

    lines = _section_lines("🔥 ENTROPY HOTSPOTS")
    snapshots = _scene_snapshots(session_graph)
    if not snapshots:
        lines.extend(["No entropy hotspots found.", ""])
        return lines

    for index, (graph_node, scene_node) in enumerate(snapshots[:limit], start=1):
        lines.append(
            " | ".join(
                [
                    f"{index}. {graph_node.node_id}",
                    f"entropy={scene_node.entropy_score:.2f}",
                    f"drift={(scene_node.drift_category or DriftCategory.STABLE).value}",
                    f"activations={scene_node.activation_count}",
                ]
            )
        )
        lines.append(f"   {_compact_text(graph_node.text)}")

    lines.append("")
    return lines


def build_node_detail_lines(
    *,
    session_graph: SessionGraph,
    session: Session,
    node_id: str | None = None,
) -> list[str]:
    """Build deterministic node detail lines for the focused scene node."""

    lines = _section_lines("🧭 NODE DETAIL")
    detail_node_id = _detail_node_id(
        session=session,
        session_graph=session_graph,
        node_id=node_id,
    )
    if detail_node_id is None:
        lines.extend([NO_INSPECTABLE_NODE_MSG, ""])
        return lines

    graph_node = get_graph_node(session_graph, detail_node_id)
    scene_node = get_scene_node(session_graph, detail_node_id)
    if graph_node is None or scene_node is None:
        lines.extend([NO_INSPECTABLE_NODE_MSG, ""])
        return lines

    chronology = " -> ".join(session.active_node_ids) or "unknown"
    lines.extend(
        [
            f"node_id={graph_node.node_id}",
            f"kind={graph_node.node_kind.value}",
            f"entropy={scene_node.entropy_score:.2f}",
            f"drift={(scene_node.drift_category or DriftCategory.STABLE).value}",
            f"activations={scene_node.activation_count}",
        ]
    )
    if scene_node.last_activated_at is not None:
        lines.append(f"last_activated_at={scene_node.last_activated_at.isoformat()}")

    lines.append(f"chronology={chronology}")
    lines.append(f"text={_compact_text(graph_node.text, max_length=120)}")
    lines.append("")
    return lines


def build_mutation_log_lines(
    *,
    event_log: EventLog | None,
    limit: int = 8,
) -> list[str]:
    """Build deterministic mutation log lines from the active event stream."""

    lines = _section_lines("🧬 MUTATION LOG")
    if event_log is None:
        lines.extend(["No mutation events recorded yet.", ""])
        return lines

    mutation_events = [
        event
        for event in event_log.read().events
        if event.event_type
        in {
            EventType.MUTATION_PROPOSED,
            EventType.MUTATION_APPLIED,
            EventType.MUTATION_REJECTED,
        }
    ]
    if not mutation_events:
        lines.extend(["No mutation events recorded yet.", ""])
        return lines

    for event in mutation_events[-limit:]:
        details = [f"{event.sequence}. {event.event_type.value}"]
        if isinstance(event, MutationStreamEvent) and event.mutation_id is not None:
            details.append(f"mutation={event.mutation_id}")
        if event.target_ids:
            details.append(f"targets={', '.join(event.target_ids)}")
        if isinstance(event, MutationStreamEvent) and event.outcome is not None:
            details.append(f"outcome={event.outcome.value}")
        details.append(_compact_text(event.message, max_length=120))
        lines.append(" | ".join(details))

    lines.append("")
    return lines


class SessionSwitcher:
    """Thin wrapper around the runtime session switching API."""

    def __init__(self, runtime: _SessionSwitchRuntime) -> None:
        self._runtime = runtime

    def switch_session(self, session_id: UUID) -> None:
        """Switch the active session through the runtime."""

        self._runtime.switch_session(session_id)
