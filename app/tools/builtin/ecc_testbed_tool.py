from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.compute.runners import ECCTestbedRunner
from app.models.tool_payloads import ECCTestbedPayload
from app.tools.base import BaseTool


class ECCTestbedTool(BaseTool):
    """Run built-in bounded ECC testbed sweeps through the local testbed runner."""

    name = "ecc_testbed_tool"
    category = "research_testbed"
    description = "Run built-in bounded ECC anomaly, encoding, subgroup/cofactor, alias, family, and domain corpora locally."
    input_schema_hint = "ECCTestbedPayload"
    output_schema_hint = "Normalized bounded ECC testbed result"
    payload_model = ECCTestbedPayload

    def __init__(self, *, runner: ECCTestbedRunner) -> None:
        self.runner = runner

    def run(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self.runner.run_testbed(
            testbed_name=str(payload["testbed_name"]),
            case_limit=int(payload.get("case_limit", 8)),
        )
