from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.types import BranchType, ConfidenceLevel


class MathAgentResult(BaseModel):
    """Structured output of the Math Agent."""

    model_config = ConfigDict(extra="forbid")

    formalization_summary: str
    key_objects: list[str] = Field(default_factory=list)
    testable_elements: list[str] = Field(default_factory=list)

    @field_validator("formalization_summary")
    @classmethod
    def validate_summary(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("formalization_summary cannot be empty.")
        return stripped


class CryptographyAgentResult(BaseModel):
    """Structured output of the Cryptography Agent."""

    model_config = ConfigDict(extra="forbid")

    surface_summary: str
    focus_areas: list[str] = Field(default_factory=list)
    preferred_tool_families: list[str] = Field(default_factory=list)
    preferred_local_tools: list[str] = Field(default_factory=list)
    preferred_testbeds: list[str] = Field(default_factory=list)
    defensive_questions: list[str] = Field(default_factory=list)

    @field_validator("surface_summary")
    @classmethod
    def validate_summary(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("surface_summary cannot be empty.")
        return stripped


class StrategyAgentResult(BaseModel):
    """Structured output of the Strategy Agent."""

    model_config = ConfigDict(extra="forbid")

    strategy_summary: str
    primary_checks: list[str] = Field(default_factory=list)
    escalation_local_tools: list[str] = Field(default_factory=list)
    null_controls: list[str] = Field(default_factory=list)
    stop_conditions: list[str] = Field(default_factory=list)

    @field_validator("strategy_summary")
    @classmethod
    def validate_summary(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("strategy_summary cannot be empty.")
        return stripped


class HypothesisBranch(BaseModel):
    """One structured candidate branch produced by the Hypothesis Agent."""

    model_config = ConfigDict(extra="forbid")

    summary: str
    rationale: str
    planned_test: str
    branch_type: BranchType = BranchType.CORE
    priority: int = 1

    @field_validator("summary", "rationale", "planned_test")
    @classmethod
    def validate_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("HypothesisBranch text fields cannot be empty.")
        return stripped

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: int) -> int:
        if value < 1:
            raise ValueError("priority must be >= 1.")
        return value


class HypothesisAgentResult(BaseModel):
    """Structured output of the Hypothesis Agent."""

    model_config = ConfigDict(extra="forbid")

    branches: list[HypothesisBranch] = Field(default_factory=list)


class CriticAgentResult(BaseModel):
    """Structured output of the Critic Agent."""

    model_config = ConfigDict(extra="forbid")

    accepted_branches: list[int] = Field(default_factory=list)
    rejected_branches: list[int] = Field(default_factory=list)
    rejection_reasons: list[str] = Field(default_factory=list)
    critique_summary: str

    @field_validator("critique_summary")
    @classmethod
    def validate_summary(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("critique_summary cannot be empty.")
        return stripped


class ReportAgentResult(BaseModel):
    """Structured output of the Report Agent before final report shaping."""

    model_config = ConfigDict(extra="forbid")

    summary: str
    anomalies: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    confidence_hint: ConfidenceLevel

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("summary cannot be empty.")
        return stripped
