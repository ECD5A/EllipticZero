from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.compute.runners import PropertyRunner
from app.models.tool_payloads import PropertyInvariantPayload
from app.tools.base import BaseTool


class PropertyInvariantTool(BaseTool):
    """Run bounded property-based invariant checks through the local property runner."""

    name = "property_invariant_tool"
    category = "research_property"
    description = "Run bounded local property-based searches for symbolic equality counterexamples."
    input_schema_hint = "PropertyInvariantPayload"
    output_schema_hint = "Normalized property-based invariant result"
    payload_model = PropertyInvariantPayload

    def __init__(self, *, runner: PropertyRunner) -> None:
        self.runner = runner

    def run(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self.runner.run_equality_property(
            left_expression=str(payload["left_expression"]),
            right_expression=str(payload["right_expression"]),
            variables=list(payload.get("variables") or []),
            domain_min=int(payload.get("domain_min", -8)),
            domain_max=int(payload.get("domain_max", 8)),
            max_examples=int(payload.get("max_examples", 24)),
        )
