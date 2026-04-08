"""Tests for coherence scoring utilities."""

from __future__ import annotations

import pytest

from services.coherence_scorer import CoherenceScorer


def test_coherence_scorer_marks_high_score_as_coherent() -> None:
    """Scores above the policy threshold should pass coherence checks."""

    scorer = CoherenceScorer()
    score = scorer.score_transition(thematic_continuity=0.9, logical_continuity=0.8)

    assert score > 0.7
    assert scorer.is_coherent(score) is True


def test_coherence_scorer_marks_low_score_as_incoherent() -> None:
    """Scores below the policy threshold should fail coherence checks."""

    scorer = CoherenceScorer()
    score = scorer.score_transition(thematic_continuity=0.4, logical_continuity=0.5)

    assert score < 0.7
    assert scorer.is_coherent(score) is False


def test_coherence_scorer_rejects_out_of_range_components() -> None:
    """Component scores should remain inside the 0..1 contract."""

    scorer = CoherenceScorer()

    with pytest.raises(ValueError):
        scorer.score_transition(thematic_continuity=1.1, logical_continuity=0.5)
