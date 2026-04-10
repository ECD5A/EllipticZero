from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.models.tool_payloads import SmartContractAuditPayload
from app.tools.base import BaseTool
from app.tools.smart_contract_utils import build_contract_outline, infer_contract_language


class ContractParserTool(BaseTool):
    """Parse a bounded smart-contract source into a deterministic structural outline."""

    name = "contract_parser_tool"
    category = "smart_contract_audit"
    description = "Parse Solidity/Vyper-like contract text into a bounded structural outline."
    version = "0.1.0"
    input_schema_hint = "SmartContractAuditPayload"
    output_schema_hint = "Structural contract outline"
    payload_model = SmartContractAuditPayload

    def run(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        language = infer_contract_language(
            source_label=str(payload.get("source_label", "")).strip() or None,
            hinted_language=str(payload.get("language", "")).strip() or None,
            contract_code=str(payload.get("contract_code", "")),
        )
        outline = build_contract_outline(
            contract_code=str(payload.get("contract_code", "")),
            language=language,
        )
        parsed = bool(
            outline.contract_names
            or outline.library_names
            or outline.interface_names
            or outline.functions
        )
        return self.make_result(
            status="ok" if parsed else "observed_issue",
            conclusion="Smart-contract source was parsed locally into a bounded structural outline.",
            notes=["Static parsing is descriptive only and does not imply a verified vulnerability."],
            result_data={
                "parsed": parsed,
                "language": outline.language,
                "pragma": outline.pragma,
                "imports": outline.imports,
                "contract_names": outline.contract_names,
                "library_names": outline.library_names,
                "interface_names": outline.interface_names,
                "event_names": outline.events,
                "modifier_names": outline.modifiers,
                "function_names": [item.name for item in outline.functions],
                "function_count": len(outline.functions),
                "constructor_present": outline.constructor_present,
                "fallback_present": outline.fallback_present,
                "receive_present": outline.receive_present,
            },
        )
