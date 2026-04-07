"""Unit tests for the TUI app shell."""

from __future__ import annotations

from importlib import import_module
from types import ModuleType

from textual.containers import ScrollableContainer
from textual.widgets import Static


def _app_module() -> ModuleType:
    return import_module("tui.app")


class _RuntimeStub:
    def __init__(self) -> None:
        self.session_id = None


class _StaticPanelSpy:
    def __init__(self) -> None:
        self.contents: list[str] = []

    def update(self, content: str) -> None:
        self.contents.append(content)


class _ScrollContainerSpy:
    def __init__(self) -> None:
        self.scroll_calls = 0

    def scroll_end(self, *, animate: bool = True) -> None:
        _ = animate
        self.scroll_calls += 1


def test_refresh_active_session_panel_updates_text_and_scrolls_to_latest() -> None:
    """Refreshing should update content and auto-follow the newest text."""

    app_module = _app_module()
    app = app_module.SessionApp(runtime=_RuntimeStub())
    panel = _StaticPanelSpy()
    scroll_container = _ScrollContainerSpy()

    app._render_session_panel = lambda: "updated content"

    def _query_one(selector: str, widget_type: type[object]) -> object:
        if selector == "#active-session-panel" and widget_type is Static:
            return panel
        if selector == "#active-session-scroll" and widget_type is ScrollableContainer:
            return scroll_container
        raise AssertionError(f"Unexpected query selector={selector} type={widget_type}")

    app.query_one = _query_one

    app._refresh_active_session_panel()

    assert panel.contents == ["updated content"]
    assert scroll_container.scroll_calls == 1
