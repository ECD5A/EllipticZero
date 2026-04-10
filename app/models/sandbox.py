from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.types import make_id


class ResearchMode(str, Enum):
    STANDARD = "standard"
    SANDBOXED_EXPLORATORY = "sandboxed_exploratory"


class ExplorationProfile(str, Enum):
    CAUTIOUS = "cautious"
    AGGRESSIVE_BOUNDED = "aggressive_bounded"


class SandboxSpec(BaseModel):
    """Bounded local sandbox policy for one research session."""

    model_config = ConfigDict(extra="forbid")

    sandbox_id: str = Field(default_factory=lambda: make_id("sandbox"))
    mode: ResearchMode
    exploration_profile: ExplorationProfile = ExplorationProfile.CAUTIOUS
    local_only: bool = True
    reversible: bool = True
    bounded: bool = True
    max_exploratory_branches: int = 2
    max_exploratory_rounds: int = 2
    max_jobs_per_session: int = 2
    approved_tool_names: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @field_validator(
        "max_exploratory_branches",
        "max_exploratory_rounds",
        "max_jobs_per_session",
    )
    @classmethod
    def validate_positive_limits(cls, value: int) -> int:
        if value < 1:
            raise ValueError("Sandbox limits must be >= 1.")
        return value


class ResearchTarget(BaseModel):
    """Normalized description of the bounded local research target."""

    model_config = ConfigDict(extra="forbid")

    target_id: str = Field(default_factory=lambda: make_id("target"))
    target_kind: str
    target_reference: str
    target_origin: str = "inferred"
    target_profile: str | None = None
    synthetic_target_name: str | None = None
    curve_name: str | None = None
    safety_scope: str = "authorized_local_research"
    notes: list[str] = Field(default_factory=list)

    @field_validator("target_kind", "target_reference", "target_origin", "safety_scope")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("ResearchTarget text fields cannot be empty.")
        return stripped

    @field_validator("target_profile", "synthetic_target_name", "curve_name")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class SyntheticResearchTarget(BaseModel):
    """Named built-in toy target for safe sandboxed defensive experiments."""

    model_config = ConfigDict(extra="forbid")

    target_name: str
    description: str
    research_target: ResearchTarget
    notes: list[str] = Field(default_factory=list)

    @field_validator("target_name", "description")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("SyntheticResearchTarget text fields cannot be empty.")
        return stripped


class ResearchTargetProfile(BaseModel):
    """Controlled target profile for bounded sandbox execution."""

    model_config = ConfigDict(extra="forbid")

    profile_name: str
    target_kind: str
    description: str
    allowed_tool_names: list[str] = Field(default_factory=list)
    max_reference_length: int = 256
    notes: list[str] = Field(default_factory=list)

    @field_validator("profile_name", "target_kind", "description")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("ResearchTargetProfile text fields cannot be empty.")
        return stripped

    @field_validator("max_reference_length")
    @classmethod
    def validate_max_reference_length(cls, value: int) -> int:
        if value < 8:
            raise ValueError("max_reference_length must be >= 8.")
        return value


class SandboxExecutionRequest(BaseModel):
    """Typed sandbox execution request passed to the bounded sandbox executor."""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(default_factory=lambda: make_id("sxreq"))
    session_id: str
    hypothesis_id: str
    sandbox_id: str
    research_mode: ResearchMode
    local_only: bool = True
    reversible: bool = True
    bounded: bool = True
    tool_name: str
    research_target: ResearchTarget
    approved_tool_names: list[str] = Field(default_factory=list)

    @field_validator("session_id", "hypothesis_id", "sandbox_id", "tool_name")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("SandboxExecutionRequest text fields cannot be empty.")
        return stripped


class SandboxExecutionResult(BaseModel):
    """Structured result from the bounded sandbox execution layer."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    sandbox_id: str
    allowed: bool
    executed: bool
    target_profile: str
    notes: list[str] = Field(default_factory=list)
    raw_result: dict[str, Any] | None = None

    @field_validator("request_id", "sandbox_id", "target_profile")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("SandboxExecutionResult text fields cannot be empty.")
        return stripped
