from __future__ import annotations

from app.models.hypothesis import Hypothesis


def score_hypothesis(hypothesis: Hypothesis) -> float:
    """Compute a lightweight branch quality score for early prioritization."""

    score = 0.2
    if hypothesis.branch_type.value == "core":
        score += 0.1
    if hypothesis.branch_type.value == "null":
        score += 0.05
    if len(hypothesis.summary.split()) >= 8:
        score += 0.25
    if len(hypothesis.rationale.split()) >= 10:
        score += 0.2
    if hypothesis.planned_test:
        score += 0.25
    if hypothesis.priority == 1:
        score += 0.1
    if "local" in hypothesis.rationale.lower() or "evidence" in hypothesis.rationale.lower():
        score += 0.1
    if len(hypothesis.summary.split()) < 5:
        score -= 0.15

    return max(0.0, min(score, 1.0))
