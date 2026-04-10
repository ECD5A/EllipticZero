from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.types import make_id


class ReplayResult(BaseModel):
    """Structured result of replay inspection or controlled re-execution."""

    model_config = ConfigDict(extra="forbid")

    replay_id: str = Field(default_factory=lambda: make_id("replay"))
    source_type: str
    source_path: str
    session_id: str | None = None
    dry_run: bool = False
    reexecuted: bool = False
    success: bool
    summary: str
    generated_session_path: str | None = None
    generated_trace_path: str | None = None
    generated_bundle_path: str | None = None
    notes: list[str] = Field(default_factory=list)

    @field_validator("source_type", "source_path", "summary")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("ReplayResult required text fields cannot be empty.")
        return stripped

    @field_validator(
        "session_id",
        "generated_session_path",
        "generated_trace_path",
        "generated_bundle_path",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None
