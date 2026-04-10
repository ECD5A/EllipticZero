from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BranchComparison(BaseModel):
    """Cautious comparison summary across multiple research branches."""

    model_config = ConfigDict(extra="forbid")

    hypothesis_ids: list[str] = Field(default_factory=list)
    compared_aspects: list[str] = Field(default_factory=list)
    summary: str
    stronger_branch_ids: list[str] = Field(default_factory=list)
    weaker_branch_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("BranchComparison summary cannot be empty.")
        return stripped


class ToolComparison(BaseModel):
    """Comparison summary across local tool outcomes."""

    model_config = ConfigDict(extra="forbid")

    tool_names: list[str] = Field(default_factory=list)
    experiment_types: list[str] = Field(default_factory=list)
    consistency_summary: str
    conflicting_signals: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @field_validator("consistency_summary")
    @classmethod
    def validate_consistency_summary(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("ToolComparison consistency_summary cannot be empty.")
        return stripped


class ComparativeReportSection(BaseModel):
    """Human- and machine-readable comparative report section."""

    model_config = ConfigDict(extra="forbid")

    title: str
    summary: str
    findings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)

    @field_validator("title", "summary")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("ComparativeReportSection text fields cannot be empty.")
        return stripped


class CrossSessionComparison(BaseModel):
    """Cautious before/after comparison against a saved baseline session."""

    model_config = ConfigDict(extra="forbid")

    baseline_session_id: str
    current_session_id: str
    baseline_source_path: str | None = None
    summary: str
    improvements: list[str] = Field(default_factory=list)
    regressions: list[str] = Field(default_factory=list)
    stable_findings: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @field_validator("baseline_session_id", "current_session_id", "summary")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("CrossSessionComparison required text fields cannot be empty.")
        return stripped

    @field_validator("baseline_source_path")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ComparativeReport(BaseModel):
    """Machine-readable comparative view over branches and tool outcomes."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    analysis_generated: bool = False
    summary: str
    baseline_session_id: str | None = None
    baseline_source_path: str | None = None
    branch_comparisons: list[BranchComparison] = Field(default_factory=list)
    tool_comparisons: list[ToolComparison] = Field(default_factory=list)
    cross_session_comparison: CrossSessionComparison | None = None
    sections: list[ComparativeReportSection] = Field(default_factory=list)
    manual_review_items: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @field_validator("session_id", "summary")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("ComparativeReport required text fields cannot be empty.")
        return stripped

    @field_validator("baseline_session_id", "baseline_source_path")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None
