from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.compute.runners.sage_runner import SageRunner
from app.models.tool_payloads import SymbolicCheckPayload
from app.tools.base import BaseTool


class SageSymbolicTool(BaseTool):
    """Bounded advanced symbolic tool routed through the Sage adapter foundation."""

    name = "sage_symbolic_tool"
    description = (
        "Use the bounded Sage adapter foundation for advanced symbolic normalization when available."
    )
    version = "0.6.0"
    category = "advanced_math"
    experimental = True
    input_schema_hint = "SymbolicCheckPayload"
    output_schema_hint = "Normalized Sage adapter symbolic result"
    payload_model = SymbolicCheckPayload

    def __init__(self, *, runner: SageRunner) -> None:
        self.runner = runner

    def run(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self.runner.run_symbolic(str(payload["expression"]))
