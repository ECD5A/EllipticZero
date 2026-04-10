from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.planning import ExperimentType


class ExperimentPackStep(BaseModel):
    """One bounded step inside a reusable research workflow pack."""

    model_config = ConfigDict(extra="forbid")

    step_id: str
    title: str
    description: str
    preferred_tool: str
    experiment_type: ExperimentType
    deterministic_expected: bool = True
    requires_coordinate_payload: bool = False
    requires_contract_root: bool = False
    target_kinds: list[str] = Field(default_factory=list)
    supported_contract_languages: list[str] = Field(default_factory=list)
    target_reference_override: str | None = None
    notes: list[str] = Field(default_factory=list)

    @field_validator("step_id", "title", "description", "preferred_tool")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("ExperimentPackStep text fields cannot be empty.")
        return stripped

    @field_validator("target_reference_override")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("target_kinds", "notes")
    @classmethod
    def normalize_text_list(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for item in value:
            stripped = item.strip()
            if stripped:
                normalized.append(stripped)
        return normalized

    @field_validator("supported_contract_languages")
    @classmethod
    def normalize_language_list(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for item in value:
            stripped = item.strip().lower()
            if stripped:
                normalized.append(stripped)
        return normalized


class ExperimentPack(BaseModel):
    """Built-in reusable bounded workflow for local defensive research."""

    model_config = ConfigDict(extra="forbid")

    pack_name: str
    version: str
    description: str
    target_kinds: list[str] = Field(default_factory=list)
    supported_tools: list[str] = Field(default_factory=list)
    default_experiment_types: list[ExperimentType] = Field(default_factory=list)
    steps: list[ExperimentPackStep] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @field_validator("pack_name", "version", "description")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("ExperimentPack text fields cannot be empty.")
        return stripped

    @field_validator("target_kinds", "supported_tools", "notes")
    @classmethod
    def normalize_text_list(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for item in value:
            stripped = item.strip()
            if stripped:
                normalized.append(stripped)
        return normalized


class ExperimentPackRecommendation(BaseModel):
    """Conservative recommendation describing why a pack may fit the current idea."""

    model_config = ConfigDict(extra="forbid")

    pack_name: str
    reason: str
    confidence_hint: str = "medium"
    notes: list[str] = Field(default_factory=list)

    @field_validator("pack_name", "reason", "confidence_hint")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("ExperimentPackRecommendation text fields cannot be empty.")
        return stripped

    @field_validator("confidence_hint")
    @classmethod
    def validate_confidence_hint(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"low", "medium", "high"}:
            raise ValueError("confidence_hint must be one of: low, medium, high.")
        return normalized

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for item in value:
            stripped = item.strip()
            if stripped:
                normalized.append(stripped)
        return normalized
