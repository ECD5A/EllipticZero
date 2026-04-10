from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.compute.runners import SlitherRunner
from app.models.tool_payloads import SmartContractAuditPayload
from app.tools.base import BaseTool
from app.tools.smart_contract_utils import infer_contract_language


class SlitherAuditTool(BaseTool):
    """Run a bounded local Slither static analysis pass on Solidity source."""

    name = "slither_audit_tool"
    category = "smart_contract_audit"
    description = "Run a bounded local Slither detector pass on Solidity source."
    version = "0.1.0"
    input_schema_hint = "SmartContractAuditPayload"
    output_schema_hint = "Bounded Slither static-analysis result"
    payload_model = SmartContractAuditPayload

    def __init__(self, *, runner: SlitherRunner) -> None:
        self.runner = runner

    def run(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        language = infer_contract_language(
            source_label=str(payload.get("source_label", "")).strip() or None,
            hinted_language=str(payload.get("language", "")).strip() or None,
            contract_code=str(payload.get("contract_code", "")),
        )
        return self.runner.run_audit(
            contract_code=str(payload.get("contract_code", "")),
            language=language,
            source_label=str(payload.get("source_label", "")).strip() or None,
        )
