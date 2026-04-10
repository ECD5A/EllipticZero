from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.compute.runners import ContractTestbedRunner
from app.models.tool_payloads import SmartContractTestbedPayload
from app.tools.base import BaseTool


class ContractTestbedTool(BaseTool):
    """Run built-in bounded smart-contract review corpora through the local testbed runner."""

    name = "contract_testbed_tool"
    category = "smart_contract_audit"
    description = "Run built-in bounded smart-contract review corpora locally."
    input_schema_hint = "SmartContractTestbedPayload"
    output_schema_hint = "Normalized bounded smart-contract testbed result"
    payload_model = SmartContractTestbedPayload

    def __init__(self, *, runner: ContractTestbedRunner) -> None:
        self.runner = runner

    def run(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self.runner.run_testbed(
            testbed_name=str(payload["testbed_name"]),
            case_limit=int(payload.get("case_limit", 8)),
        )
