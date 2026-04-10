from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PluginMetadata(BaseModel):
    """Inspectable plugin load metadata for local EllipticZero extensions."""

    model_config = ConfigDict(extra="forbid")

    plugin_name: str
    plugin_version: str
    plugin_description: str
    registered_tools: list[str] = Field(default_factory=list)
    source_path: str
    load_status: str
    notes: list[str] = Field(default_factory=list)

    @field_validator(
        "plugin_name",
        "plugin_version",
        "plugin_description",
        "source_path",
        "load_status",
    )
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Plugin metadata text fields cannot be empty.")
        return stripped
