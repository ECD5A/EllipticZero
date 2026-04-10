from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.types import BranchType, HypothesisStatus, make_id


class Hypothesis(BaseModel):
    """Candidate research direction derived from the seed."""

    model_config = ConfigDict(extra="forbid")

    hypothesis_id: str = Field(default_factory=lambda: make_id("hyp"))
    parent_id: str | None = None
    source_agent: str
    summary: str
    rationale: str
    planned_test: str | None = None
    branch_type: BranchType = BranchType.CORE
    priority: int = 1
    score: float = 0.0
    status: HypothesisStatus = HypothesisStatus.SEEDED

    @field_validator("source_agent", "summary", "rationale")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Required hypothesis text field cannot be empty.")
        return stripped

    @field_validator("planned_test")
    @classmethod
    def normalize_planned_test(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: int) -> int:
        if value < 1:
            raise ValueError("priority must be >= 1.")
        return value
