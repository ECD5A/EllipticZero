from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.compute.runners import FormalRunner
from app.models.tool_payloads import FormalConstraintPayload
from app.tools.base import BaseTool


class FormalConstraintTool(BaseTool):
    """Run bounded local formal equality checks through the configured formal runner."""

    name = "formal_constraint_tool"
    category = "research_formal"
    description = "Run bounded local SMT-backed equality checks for symbolic constraints."
    input_schema_hint = "FormalConstraintPayload"
    output_schema_hint = "Normalized bounded formal result"
    payload_model = FormalConstraintPayload

    def __init__(self, *, runner: FormalRunner) -> None:
        self.runner = runner

    def run(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self.runner.run_bounded_equality_check(
            left_expression=str(payload["left_expression"]),
            right_expression=str(payload["right_expression"]),
            variables=list(payload.get("variables") or []),
            domain_min=int(payload.get("domain_min", -8)),
            domain_max=int(payload.get("domain_max", 8)),
        )
