from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.types import make_id


class MathWorkspace(BaseModel):
    """Bounded local artifact workspace for advanced math experiments."""

    model_config = ConfigDict(extra="forbid")

    workspace_id: str = Field(default_factory=lambda: make_id("mathws"))
    session_id: str
    experiment_type: str
    tool_name: str
    artifact_paths: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @field_validator("session_id", "experiment_type", "tool_name")
    @classmethod
    def validate_text_fields(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("MathWorkspace text fields cannot be empty.")
        return stripped
