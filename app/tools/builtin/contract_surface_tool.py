from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.models.tool_payloads import SmartContractAuditPayload
from app.tools.base import BaseTool
from app.tools.smart_contract_utils import (
    build_contract_outline,
    infer_contract_language,
    summarize_contract_surface,
)


class ContractSurfaceTool(BaseTool):
    """Describe the externally reachable and privilege-sensitive contract surface."""

    name = "contract_surface_tool"
    category = "smart_contract_audit"
    description = "Describe public, external, payable, privileged, and low-level smart-contract surfaces."
    version = "0.1.0"
    input_schema_hint = "SmartContractAuditPayload"
    output_schema_hint = "Contract surface summary"
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
        summary = summarize_contract_surface(outline)
        issues: list[str] = []
        issues.extend(str(item) for item in summary["risk_flags"])

        return self.make_result(
            status="ok" if not issues else "observed_issue",
            conclusion="Smart-contract externally reachable and privilege-sensitive surfaces were described locally.",
            notes=["Surface mapping highlights review areas only; it does not claim exploitability."],
            result_data={
                "recognized": bool(summary["contract_count"] or summary["function_count"]),
                "language": outline.language,
                "contract_count": summary["contract_count"],
                "function_count": summary["function_count"],
                "public_functions": summary["public_functions"],
                "external_functions": summary["external_functions"],
                "payable_functions": summary["payable_functions"],
                "privileged_functions": summary["privileged_functions"],
                "role_management_functions": summary["role_management_functions"],
                "pause_control_functions": summary["pause_control_functions"],
                "role_guarded_functions": summary["role_guarded_functions"],
                "initializer_functions": summary["initializer_functions"],
                "state_changing_functions": summary["state_changing_functions"],
                "unguarded_state_changing_functions": summary["unguarded_state_changing_functions"],
                "low_level_call_functions": summary["low_level_call_functions"],
                "call_with_value_functions": summary["call_with_value_functions"],
                "delegatecall_functions": summary["delegatecall_functions"],
                "selfdestruct_functions": summary["selfdestruct_functions"],
                "tx_origin_functions": summary["tx_origin_functions"],
                "timestamp_functions": summary["timestamp_functions"],
                "entropy_source_functions": summary["entropy_source_functions"],
                "loop_functions": summary["loop_functions"],
                "assembly_functions": summary["assembly_functions"],
                "token_transfer_functions": summary["token_transfer_functions"],
                "token_transfer_from_functions": summary["token_transfer_from_functions"],
                "approve_functions": summary["approve_functions"],
                "signature_validation_functions": summary["signature_validation_functions"],
                "oracle_dependency_functions": summary["oracle_dependency_functions"],
                "collateral_management_functions": summary["collateral_management_functions"],
                "liquidation_functions": summary["liquidation_functions"],
                "liquidation_fee_functions": summary["liquidation_fee_functions"],
                "reserve_dependency_functions": summary["reserve_dependency_functions"],
                "fee_collection_functions": summary["fee_collection_functions"],
                "reserve_buffer_functions": summary["reserve_buffer_functions"],
                "reserve_accounting_functions": summary["reserve_accounting_functions"],
                "debt_accounting_functions": summary["debt_accounting_functions"],
                "bad_debt_socialization_functions": summary["bad_debt_socialization_functions"],
                "state_transition_functions": summary["state_transition_functions"],
                "accounting_mutation_functions": summary["accounting_mutation_functions"],
                "share_accounting_functions": summary["share_accounting_functions"],
                "vault_conversion_functions": summary["vault_conversion_functions"],
                "deposit_like_functions": summary["deposit_like_functions"],
                "asset_exit_functions": summary["asset_exit_functions"],
                "rescue_or_sweep_functions": summary["rescue_or_sweep_functions"],
                "proxy_delegatecall_functions": summary["proxy_delegatecall_functions"],
                "storage_slot_write_functions": summary["storage_slot_write_functions"],
                "implementation_reference_functions": summary["implementation_reference_functions"],
                "implementation_slot_constant_present": summary["implementation_slot_constant_present"],
                "storage_gap_present": summary["storage_gap_present"],
                "balance_validation_functions": summary["balance_validation_functions"],
                "constructor_present": summary["constructor_present"],
                "fallback_present": summary["fallback_present"],
                "receive_present": summary["receive_present"],
                "imports": summary["imports"],
                "issues": issues,
            },
        )
