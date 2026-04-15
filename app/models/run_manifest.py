from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.types import make_id


class RunArtifactReference(BaseModel):
    """Structured provenance reference for a run-related artifact."""

    model_config = ConfigDict(extra="forbid")

    workspace_id: str | None = None
    artifact_path: str
    description: str
    generating_tool: str | None = None
    experiment_type: str | None = None
    file_hash: str | None = None

    @field_validator("artifact_path", "description")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("RunArtifactReference text fields cannot be empty.")
        return stripped

    @field_validator("workspace_id", "generating_tool", "experiment_type", "file_hash")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class RunManifest(BaseModel):
    """Reproducibility manifest for one saved research session run."""

    model_config = ConfigDict(extra="forbid")

    manifest_id: str = Field(default_factory=lambda: make_id("manifest"))
    session_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    seed_hash: str
    session_hash: str | None = None
    session_file_path: str
    trace_file_path: str | None = None
    comparative_report_path: str | None = None
    approved_export_roots: list[str] = Field(default_factory=list)
    export_policy_summary: list[str] = Field(default_factory=list)
    filtered_artifact_count: int = 0
    session_export_ready: bool = False
    trace_export_ready: bool = False
    comparative_export_ready: bool = False
    artifact_paths: list[str] = Field(default_factory=list)
    artifacts: list[RunArtifactReference] = Field(default_factory=list)
    artifact_count: int = 0
    tool_names: list[str] = Field(default_factory=list)
    tool_metadata_snapshots: list[dict[str, Any]] = Field(default_factory=list)
    experiment_types: list[str] = Field(default_factory=list)
    local_experiment_summary: list[str] = Field(default_factory=list)
    report_focus_summary: list[str] = Field(default_factory=list)
    quality_gate_summary: list[str] = Field(default_factory=list)
    quality_gate_count: int = 0
    hardening_summary: list[str] = Field(default_factory=list)
    hardening_summary_count: int = 0
    evidence_coverage_summary: dict[str, Any] = Field(default_factory=dict)
    toolchain_fingerprint: dict[str, Any] = Field(default_factory=dict)
    secret_redaction_summary: list[str] = Field(default_factory=list)
    research_mode: str | None = None
    exploration_profile: str | None = None
    sandbox_id: str | None = None
    selected_pack_name: str | None = None
    recommended_pack_names: list[str] = Field(default_factory=list)
    executed_pack_steps: list[str] = Field(default_factory=list)
    exploratory_rounds_executed: int = 0
    research_target_kind: str | None = None
    research_target_reference: str | None = None
    research_target_origin: str | None = None
    synthetic_target_name: str | None = None
    research_target_profile: str | None = None
    confidence: str | None = None
    report_summary: str | None = None
    comparison_ready: bool = False
    environment_summary: dict[str, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    is_replay: bool = False
    replay_source_type: str | None = None
    replay_source_path: str | None = None
    original_session_id: str | None = None
    replay_mode: str | None = None
    comparison_baseline_session_id: str | None = None
    comparison_baseline_source_type: str | None = None
    comparison_baseline_source_path: str | None = None

    @field_validator("session_id", "seed_hash", "session_file_path")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("RunManifest required text fields cannot be empty.")
        return stripped

    @field_validator(
        "session_hash",
        "trace_file_path",
        "comparative_report_path",
        "research_mode",
        "exploration_profile",
        "sandbox_id",
        "selected_pack_name",
        "research_target_kind",
        "research_target_reference",
        "research_target_origin",
        "synthetic_target_name",
        "research_target_profile",
        "confidence",
        "report_summary",
        "replay_source_type",
        "replay_source_path",
        "original_session_id",
        "replay_mode",
        "comparison_baseline_session_id",
        "comparison_baseline_source_type",
        "comparison_baseline_source_path",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None
