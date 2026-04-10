from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.compute.runners import SympyRunner
from app.models.tool_payloads import SymbolicCheckPayload
from app.tools.base import BaseTool


class SymbolicCheckTool(BaseTool):
    """Perform bounded symbolic parsing and normalization using SymPy."""

    name = "symbolic_check_tool"
    category = "symbolic"
    description = "Safely parse and normalize simple symbolic expressions or equations."
    input_schema_hint = "expression string or equation string"
    output_schema_hint = "status, conclusion, deterministic, notes, result_data"
    payload_model = SymbolicCheckPayload

    def __init__(self, *, runner: SympyRunner) -> None:
        self.runner = runner

    def run(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        expression_text = str(payload.get("expression", "")).strip()
        if "=" in expression_text:
            left, right = expression_text.split("=", 1)
            return self.runner.run_symbolic(
                expression=left.strip(),
                comparison_expression=right.strip(),
            )
        return self.runner.run_symbolic(expression=expression_text)
