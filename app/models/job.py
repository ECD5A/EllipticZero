from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.planning import ExperimentSpec, ToolPlan
from app.types import make_id


class ComputeJob(BaseModel):
    """Registry-controlled local compute request."""

    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(default_factory=lambda: make_id("job"))
    hypothesis_id: str
    tool_name: str
    tool_plan: ToolPlan | None = None
    experiment_spec: ExperimentSpec | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = 30

    @field_validator("hypothesis_id", "tool_name")
    @classmethod
    def validate_text_fields(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Compute job text fields cannot be empty.")
        return stripped

    @field_validator("timeout_seconds")
    @classmethod
    def validate_timeout(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("timeout_seconds must be positive.")
        return value
