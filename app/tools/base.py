from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel

from app.models.tool_metadata import ToolMetadata


class BaseTool(ABC):
    """Abstract interface for local compute tools."""

    name: str
    description: str
    version: str = "0.1.0"
    category: str = "research"
    deterministic: bool = True
    experimental: bool = False
    input_schema_hint: str = "Structured mapping payload"
    output_schema_hint: str = "Structured mapping result"
    payload_model: type[BaseModel] | None = None
    source_type: str = "built_in"
    plugin_name: str | None = None

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name=self.name,
            category=self.category,
            description=self.description,
            deterministic=self.deterministic,
            experimental=self.experimental,
            input_schema_hint=self.input_schema_hint,
            output_schema_hint=self.output_schema_hint,
            source_type=self.source_type,
            plugin_name=self.plugin_name,
        )

    def validate_payload(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        if self.payload_model is None:
            return dict(payload)
        validated = self.payload_model.model_validate(dict(payload))
        return validated.model_dump(mode="json", exclude_none=True)

    def make_result(
        self,
        *,
        status: str,
        conclusion: str,
        result_data: dict[str, Any],
        notes: list[str] | None = None,
        deterministic: bool | None = None,
    ) -> dict[str, Any]:
        return {
            "status": status,
            "conclusion": conclusion,
            "notes": notes or [],
            "deterministic": self.deterministic if deterministic is None else deterministic,
            "result_data": result_data,
        }

    @abstractmethod
    def run(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Run the tool with a structured payload."""
