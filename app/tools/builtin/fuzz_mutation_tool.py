from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.compute.runners import FuzzRunner
from app.models.tool_payloads import FuzzMutationPayload
from app.tools.base import BaseTool


class FuzzMutationTool(BaseTool):
    """Run deterministic local mutation probes through the bounded fuzz runner."""

    name = "fuzz_mutation_tool"
    category = "research_fuzz"
    description = "Run bounded deterministic local mutation probes for curve or point-like targets."
    input_schema_hint = "FuzzMutationPayload"
    output_schema_hint = "Normalized fuzz mutation scan result"
    payload_model = FuzzMutationPayload

    def __init__(self, *, runner: FuzzRunner) -> None:
        self.runner = runner

    def run(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self.runner.run_mutation_probe(
            target_kind=str(payload["target_kind"]),
            seed_input=str(payload["seed_input"]),
            mutations=int(payload.get("mutations", 12)),
            curve_name=(
                str(payload["curve_name"]).strip()
                if payload.get("curve_name") is not None
                else None
            ),
        )
