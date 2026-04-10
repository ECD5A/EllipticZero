from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.types import make_id


class Evidence(BaseModel):
    """Recorded evidence linked to a hypothesis and compute source."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(default_factory=lambda: make_id("ev"))
    hypothesis_id: str
    source: str
    summary: str
    tool_name: str | None = None
    tool_metadata_snapshot: dict[str, Any] | None = None
    experiment_type: str | None = None
    selected_by_roles: list[str] = Field(default_factory=list)
    selected_pack_name: str | None = None
    pack_step_id: str | None = None
    target_kind: str | None = None
    sandbox_id: str | None = None
    research_target_reference: str | None = None
    target_origin: str | None = None
    synthetic_target_name: str | None = None
    target_profile: str | None = None
    deterministic: bool = True
    conclusion: str | None = None
    workspace_id: str | None = None
    artifact_paths: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    raw_result: dict[str, Any]

    @field_validator("hypothesis_id", "source", "summary")
    @classmethod
    def validate_text_fields(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Evidence text fields cannot be empty.")
        return stripped

    @field_validator(
        "tool_name",
        "conclusion",
        "experiment_type",
        "selected_pack_name",
        "pack_step_id",
        "target_kind",
        "sandbox_id",
        "research_target_reference",
        "target_origin",
        "synthetic_target_name",
        "target_profile",
        "workspace_id",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None
