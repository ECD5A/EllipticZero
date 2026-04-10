from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ToolMetadata(BaseModel):
    """Structured metadata for approved local research tools."""

    model_config = ConfigDict(extra="forbid")

    name: str
    category: str
    description: str
    deterministic: bool
    experimental: bool
    input_schema_hint: str
    output_schema_hint: str
    source_type: str = "built_in"
    plugin_name: str | None = None
