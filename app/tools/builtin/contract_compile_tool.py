from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.compute.runners import ContractCompileRunner
from app.models.tool_payloads import SmartContractAuditPayload
from app.tools.base import BaseTool
from app.tools.smart_contract_utils import infer_contract_language


class ContractCompileTool(BaseTool):
    """Run a bounded local Solidity compile check through the approved compiler runner."""

    name = "contract_compile_tool"
    category = "smart_contract_audit"
    description = "Run a bounded local Solidity compile check through solc or solcjs."
    version = "0.1.0"
    input_schema_hint = "SmartContractAuditPayload"
    output_schema_hint = "Scoped smart-contract compile result"
    payload_model = SmartContractAuditPayload

    def __init__(self, *, runner: ContractCompileRunner) -> None:
        self.runner = runner

    def run(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        language = infer_contract_language(
            source_label=str(payload.get("source_label", "")).strip() or None,
            hinted_language=str(payload.get("language", "")).strip() or None,
            contract_code=str(payload.get("contract_code", "")),
        )
        return self.runner.run_compile(
            contract_code=str(payload.get("contract_code", "")),
            language=language,
            source_label=str(payload.get("source_label", "")).strip() or None,
        )
