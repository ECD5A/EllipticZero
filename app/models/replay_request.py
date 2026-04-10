from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ReplayRequest(BaseModel):
    """Structured request for dry-run inspection or controlled replay."""

    model_config = ConfigDict(extra="forbid")

    source_type: str
    source_path: str
    dry_run: bool = False
    reexecute: bool = True
    preserve_original_seed: bool = True
    notes: list[str] = Field(default_factory=list)

    @field_validator("source_type", "source_path")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("ReplayRequest text fields cannot be empty.")
        return stripped

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"session", "manifest", "bundle"}:
            raise ValueError("source_type must be one of: session, manifest, bundle.")
        return normalized

    @model_validator(mode="after")
    def validate_mode(self) -> "ReplayRequest":
        if self.dry_run and self.reexecute:
            self.reexecute = False
        if not self.dry_run and not self.reexecute:
            raise ValueError("ReplayRequest must be either dry-run or reexecute.")
        return self
