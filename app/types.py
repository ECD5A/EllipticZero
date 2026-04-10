from __future__ import annotations

from enum import Enum
from uuid import uuid4


def make_id(prefix: str) -> str:
    """Return a short stable-looking identifier for a domain entity."""

    return f"{prefix}_{uuid4().hex[:12]}"


class HypothesisStatus(str, Enum):
    SEEDED = "seeded"
    FORMALIZED = "formalized"
    EXPANDED = "expanded"
    PLANNED = "planned"
    RUNNING = "running"
    OBSERVED_SIGNAL = "observed_signal"
    VALIDATED = "validated"
    CLOSED = "closed"
    NEEDS_MANUAL_REVIEW = "needs_manual_review"
    DEFERRED = "deferred"
    REJECTED = "rejected"


class ConfidenceLevel(str, Enum):
    LOW = "low"
    INCONCLUSIVE = "inconclusive"
    MEDIUM = "medium"
    HIGH = "high"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"


class BranchType(str, Enum):
    CORE = "core"
    SUPPORTING = "supporting"
    NULL = "null"
    EXPLORATORY = "exploratory"
