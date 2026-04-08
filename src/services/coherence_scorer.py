"""Coherence scoring utility for narrative transition validation."""

from __future__ import annotations

from pydantic import Field, ValidationError

from models.common import StrictBaseModel

__all__ = ["COHERENCE_THRESHOLD", "CoherenceScorer"]

COHERENCE_THRESHOLD = 0.7


class _CoherenceComponents(StrictBaseModel):
    """Input components used to evaluate transition coherence."""

    thematic_continuity: float = Field(ge=0.0, le=1.0)
    logical_continuity: float = Field(ge=0.0, le=1.0)


class CoherenceScorer:
    """Score narrative transitions against the coherence policy threshold."""

    def __init__(self, *, threshold: float = COHERENCE_THRESHOLD) -> None:
        self.threshold = threshold

    def score_transition(
        self,
        *,
        thematic_continuity: float,
        logical_continuity: float,
    ) -> float:
        """Return weighted coherence score for one narrative transition."""

        try:
            components = _CoherenceComponents(
                thematic_continuity=thematic_continuity,
                logical_continuity=logical_continuity,
            )
        except ValidationError as exc:
            raise ValueError("coherence components must be in the range 0..1") from exc

        return round(
            (components.thematic_continuity + components.logical_continuity) / 2,
            4,
        )

    def is_coherent(self, score: float) -> bool:
        """Return ``True`` when score exceeds the required coherence threshold."""

        return score > self.threshold
