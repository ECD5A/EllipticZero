from __future__ import annotations

from app.models.hypothesis import Hypothesis
from app.types import HypothesisStatus

ALLOWED_TRANSITIONS: dict[HypothesisStatus, set[HypothesisStatus]] = {
    HypothesisStatus.SEEDED: {HypothesisStatus.FORMALIZED},
    HypothesisStatus.FORMALIZED: {HypothesisStatus.EXPANDED},
    HypothesisStatus.EXPANDED: {
        HypothesisStatus.REJECTED,
        HypothesisStatus.PLANNED,
    },
    HypothesisStatus.PLANNED: {HypothesisStatus.RUNNING},
    HypothesisStatus.RUNNING: {
        HypothesisStatus.OBSERVED_SIGNAL,
        HypothesisStatus.CLOSED,
    },
    HypothesisStatus.OBSERVED_SIGNAL: {
        HypothesisStatus.VALIDATED,
        HypothesisStatus.NEEDS_MANUAL_REVIEW,
    },
    HypothesisStatus.VALIDATED: {HypothesisStatus.CLOSED},
    HypothesisStatus.NEEDS_MANUAL_REVIEW: set(),
    HypothesisStatus.REJECTED: set(),
    HypothesisStatus.CLOSED: set(),
    HypothesisStatus.DEFERRED: set(),
}


def transition_hypothesis(
    hypothesis: Hypothesis,
    target_status: HypothesisStatus,
) -> Hypothesis:
    """Apply a controlled lifecycle transition to a hypothesis."""

    current = hypothesis.status
    if current == target_status:
        return hypothesis

    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if target_status not in allowed:
        raise ValueError(
            f"Invalid hypothesis status transition: {current.value} -> {target_status.value}"
        )
    hypothesis.status = target_status
    return hypothesis
