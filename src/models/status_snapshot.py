"""Status snapshot model for TUI status/footer region display."""

from __future__ import annotations

from pydantic import Field, model_validator

from models.common import StrictBaseModel
from models.execution import ExecutionStatus

__all__ = ["StatusSnapshot"]


class StatusSnapshot(StrictBaseModel):
    """Payload rendered in status/footer region for active graph context.

    Displays the active graph position, total graph count, and the running
    state of the active graph only. Background graph states must not affect
    this display.
    """

    active_position: int = Field(
        ge=1,
        description="1-based active graph position",
    )
    total_graphs: int = Field(
        ge=0,
        description="Number of available graphs",
    )
    active_running_state: ExecutionStatus = Field(
        description="Running state of active graph only",
    )

    @model_validator(mode="after")
    def _validate_position_bounds(self) -> StatusSnapshot:
        """Ensure active position is within valid bounds when graphs exist."""
        if self.total_graphs > 0:
            if self.active_position < 1 or self.active_position > self.total_graphs:
                raise ValueError(
                    f"active_position ({self.active_position}) must be between "
                    f"1 and total_graphs ({self.total_graphs})"
                )
        else:
            # When no graphs exist, position should be 1
            if self.active_position != 1:
                raise ValueError(
                    f"active_position must be 1 when total_graphs is 0, "
                    f"got {self.active_position}"
                )

        return self
