from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ContractFunction:
    name: str
    signature: str
    visibility: str
    modifiers: list[str]
    payable: bool
    body: str
    kind: str = "function"
    start_line: int = 0
    end_line: int = 0


@dataclass(frozen=True)
class ContractOutline:
    language: str
    pragma: str | None
    imports: list[str]
    contract_names: list[str]
    library_names: list[str]
    interface_names: list[str]
    events: list[str]
    modifiers: list[str]
    functions: list[ContractFunction]
    constructor_present: bool
    fallback_present: bool
    receive_present: bool
    source_text: str


def normalize_contract_code(code: str) -> str:
    return code.replace("\r\n", "\n").replace("\r", "\n").strip()


def infer_contract_language(
    *,
    source_label: str | None,
    hinted_language: str | None,
    contract_code: str | None = None,
) -> str:
    if hinted_language:
        value = hinted_language.strip().lower()
        if value in {"solidity", "vyper"}:
            return value
    if source_label:
        lowered = source_label.strip().lower()
        if lowered.endswith(".vy"):
            return "vyper"
        if lowered.endswith(".sol"):
            return "solidity"
    if contract_code:
        lowered_code = contract_code.lower()
        if any(
            token in lowered_code
            for token in (
                "@external",
                "@internal",
                "@view",
                "@payable",
                "# @version",
                "implements:",
                "def __init__",
            )
        ):
            return "vyper"
        if any(
            token in lowered_code
            for token in (
                "pragma solidity",
                "contract ",
                "interface ",
                "library ",
                "modifier ",
            )
        ):
            return "solidity"
    return "solidity"


def build_contract_outline(*, contract_code: str, language: str = "solidity") -> ContractOutline:
    code = normalize_contract_code(contract_code)
    if language == "vyper":
        pragma_match = re.search(r"^\s*#\s*@version\s+([^\n]+)", code, flags=re.MULTILINE)
        imports = re.findall(r"^\s*(?:from\s+\S+\s+import\s+[^\n]+|import\s+[^\n]+)", code, flags=re.MULTILINE)
        contract_names: list[str] = []
        library_names: list[str] = []
        interface_names = re.findall(r"^\s*interface\s+([A-Za-z_][A-Za-z0-9_]*)\s*:", code, flags=re.MULTILINE)
        events = re.findall(r"^\s*event\s+([A-Za-z_][A-Za-z0-9_]*)\s*:", code, flags=re.MULTILINE)
        modifiers: list[str] = []
        functions = _extract_vyper_functions(code)
    else:
        pragma_match = re.search(r"\bpragma\s+solidity\s+([^;]+);", code)
        imports = re.findall(r"\bimport\s+([^;]+);", code)
        contract_names = re.findall(r"\bcontract\s+([A-Za-z_][A-Za-z0-9_]*)", code)
        library_names = re.findall(r"\blibrary\s+([A-Za-z_][A-Za-z0-9_]*)", code)
        interface_names = re.findall(r"\binterface\s+([A-Za-z_][A-Za-z0-9_]*)", code)
        events = re.findall(r"\bevent\s+([A-Za-z_][A-Za-z0-9_]*)", code)
        modifiers = re.findall(r"\bmodifier\s+([A-Za-z_][A-Za-z0-9_]*)", code)
        functions = _extract_functions(code)
    return ContractOutline(
        language=language,
        pragma=pragma_match.group(1).strip() if pragma_match else None,
        imports=[item.strip() for item in imports],
        contract_names=contract_names,
        library_names=library_names,
        interface_names=interface_names,
        events=events,
        modifiers=modifiers,
        functions=functions,
        constructor_present=any(item.kind == "constructor" for item in functions),
        fallback_present=any(item.kind == "fallback" for item in functions),
        receive_present=any(item.kind == "receive" for item in functions),
        source_text=code,
    )


def summarize_contract_surface(outline: ContractOutline) -> dict[str, object]:
    functions = outline.functions
    callable_functions = [item for item in functions if item.kind == "function"]
    public_functions = [item.name for item in callable_functions if item.visibility == "public"]
    external_functions = [item.name for item in callable_functions if item.visibility == "external"]
    payable_functions = [item.name for item in functions if item.payable]
    privileged_functions = [
        item.name
        for item in callable_functions
        if _has_access_guard_modifier(item.modifiers) or _looks_admin_function(item.name)
    ]
    role_management_functions = [item.name for item in callable_functions if _looks_role_management_function(item.name)]
    pause_control_functions = [item.name for item in callable_functions if _looks_pause_control_function(item.name)]
    role_guarded_functions = [
        item.name for item in callable_functions if _has_explicit_role_guard(item.modifiers, item.body)
    ]
    initializer_functions = [item.name for item in callable_functions if _looks_initializer_function(item.name)]
    low_level_call_functions = [item.name for item in functions if _contains_low_level_call(item.body)]
    call_with_value_functions = [item.name for item in functions if _contains_call_with_value(item.body)]
    delegatecall_functions = [item.name for item in functions if _contains_delegatecall(item.body)]
    selfdestruct_functions = [item.name for item in functions if _contains_selfdestruct(item.body)]
    tx_origin_functions = [item.name for item in functions if _contains_tx_origin(item.body)]
    timestamp_functions = [item.name for item in functions if _contains_timestamp_dependency(item.body)]
    entropy_source_functions = [item.name for item in functions if _contains_entropy_source(item.body)]
    loop_functions = [item.name for item in functions if _contains_loop(item.body)]
    assembly_functions = [item.name for item in functions if re.search(r"\bassembly\s*\{", item.body)]
    token_transfer_functions = [item.name for item in functions if _contains_erc20_transfer_like(item.body)]
    token_transfer_from_functions = [item.name for item in functions if _contains_erc20_transfer_from_like(item.body)]
    approve_functions = [item.name for item in functions if _contains_erc20_approve_like(item.body)]
    signature_validation_functions = [item.name for item in functions if _contains_ecrecover(item.body)]
    oracle_dependency_functions = [item.name for item in functions if _contains_oracle_read(item.body)]
    collateral_management_functions = [
        item.name for item in callable_functions if _looks_collateral_management_function(item.name, item.signature, item.body)
    ]
    liquidation_functions = [
        item.name for item in callable_functions if _looks_liquidation_function(item.name, item.signature, item.body)
    ]
    liquidation_fee_functions = [
        item.name for item in callable_functions if _contains_liquidation_fee_logic(item.signature, item.body)
    ]
    reserve_dependency_functions = [item.name for item in functions if _contains_reserve_dependency(item.body)]
    fee_collection_functions = [
        item.name for item in callable_functions if _looks_fee_collection_function(item.name, item.signature, item.body)
    ]
    reserve_buffer_functions = [
        item.name for item in callable_functions if _contains_reserve_buffer_logic(item.signature, item.body)
    ]
    reserve_accounting_functions = [
        item.name for item in callable_functions if _contains_reserve_accounting_logic(item.signature, item.body)
    ]
    debt_accounting_functions = [
        item.name for item in callable_functions if _looks_debt_accounting_function(item.name, item.signature, item.body)
    ]
    bad_debt_socialization_functions = [
        item.name for item in callable_functions if _contains_bad_debt_socialization_logic(item.signature, item.body)
    ]
    state_transition_functions = [item.name for item in functions if _contains_state_transition(item.body)]
    accounting_mutation_functions = [item.name for item in functions if _contains_accounting_mutation(item.body)]
    share_accounting_functions = [item.name for item in callable_functions if _contains_share_accounting_mutation(item.body)]
    vault_conversion_functions = [
        item.name for item in callable_functions if _contains_vault_conversion_logic(item.signature, item.body)
    ]
    deposit_like_functions = [item.name for item in callable_functions if _looks_deposit_like_function(item.name, item.body)]
    asset_exit_functions = [item.name for item in callable_functions if _looks_asset_exit_function(item.name, item.body)]
    rescue_or_sweep_functions = [item.name for item in callable_functions if _looks_rescue_or_sweep_function(item.name)]
    proxy_delegatecall_functions = [item.name for item in functions if _looks_proxy_delegate_surface(item)]
    storage_slot_write_functions = [item.name for item in functions if _contains_storage_slot_write(item.body)]
    implementation_reference_functions = [
        item.name for item in functions if _contains_implementation_reference(f"{item.signature}\n{item.body}")
    ]
    implementation_slot_constant_present = _contains_implementation_slot_constant(outline.source_text)
    storage_gap_present = _contains_storage_gap(outline.source_text)
    balance_validation_functions = [
        item.name for item in callable_functions if _contains_balance_or_allowance_check(item.signature, item.body)
    ]
    state_changing_functions = [item.name for item in callable_functions if _looks_state_change(item.body)]
    unguarded_state_changing_functions = [
        item.name
        for item in callable_functions
        if item.visibility in {"public", "external"}
        and _looks_state_change(item.body)
        and not _has_access_guard_modifier(item.modifiers)
    ]
    risk_flags: list[str] = []
    if low_level_call_functions:
        risk_flags.append("low_level_call_surface_present")
    if call_with_value_functions:
        risk_flags.append("value_transfer_surface_present")
    if delegatecall_functions:
        risk_flags.append("delegatecall_surface_present")
    if selfdestruct_functions:
        risk_flags.append("selfdestruct_surface_present")
    if tx_origin_functions:
        risk_flags.append("tx_origin_surface_present")
    if timestamp_functions:
        risk_flags.append("time_dependency_surface_present")
    if entropy_source_functions:
        risk_flags.append("entropy_source_surface_present")
    if loop_functions:
        risk_flags.append("loop_surface_present")
    if payable_functions:
        risk_flags.append("payable_surface_present")
    if assembly_functions:
        risk_flags.append("assembly_surface_present")
    if token_transfer_functions:
        risk_flags.append("token_transfer_surface_present")
    if token_transfer_from_functions:
        risk_flags.append("token_transfer_from_surface_present")
    if approve_functions:
        risk_flags.append("approve_surface_present")
    if signature_validation_functions:
        risk_flags.append("signature_validation_surface_present")
    if oracle_dependency_functions:
        risk_flags.append("oracle_dependency_surface_present")
    if collateral_management_functions:
        risk_flags.append("collateral_management_surface_present")
    if liquidation_functions:
        risk_flags.append("liquidation_surface_present")
    if liquidation_fee_functions:
        risk_flags.append("liquidation_fee_surface_present")
    if reserve_dependency_functions:
        risk_flags.append("reserve_dependency_surface_present")
    if fee_collection_functions:
        risk_flags.append("fee_collection_surface_present")
    if reserve_buffer_functions:
        risk_flags.append("reserve_buffer_surface_present")
    if reserve_accounting_functions:
        risk_flags.append("reserve_accounting_surface_present")
    if debt_accounting_functions:
        risk_flags.append("debt_accounting_surface_present")
    if bad_debt_socialization_functions:
        risk_flags.append("bad_debt_socialization_surface_present")
    if state_transition_functions:
        risk_flags.append("state_transition_surface_present")
    if accounting_mutation_functions:
        risk_flags.append("accounting_surface_present")
    if share_accounting_functions:
        risk_flags.append("share_accounting_surface_present")
    if vault_conversion_functions:
        risk_flags.append("vault_conversion_surface_present")
    if deposit_like_functions:
        risk_flags.append("deposit_surface_present")
    if asset_exit_functions:
        risk_flags.append("asset_exit_surface_present")
    if rescue_or_sweep_functions:
        risk_flags.append("rescue_or_sweep_surface_present")
    if role_management_functions:
        risk_flags.append("role_management_surface_present")
    if pause_control_functions:
        risk_flags.append("pause_control_surface_present")
    if role_guarded_functions:
        risk_flags.append("role_guard_surface_present")
    if proxy_delegatecall_functions:
        risk_flags.append("proxy_delegate_surface_present")
    if storage_slot_write_functions:
        risk_flags.append("storage_slot_write_surface_present")
    if implementation_reference_functions:
        risk_flags.append("implementation_reference_surface_present")
    if proxy_delegatecall_functions and not implementation_slot_constant_present:
        risk_flags.append("unstructured_proxy_storage_surface_present")
    if outline.receive_present:
        risk_flags.append("receive_surface_present")
    if outline.fallback_present:
        risk_flags.append("fallback_surface_present")
    if privileged_functions:
        risk_flags.append("privileged_surface_present")
    if unguarded_state_changing_functions:
        risk_flags.append("unguarded_state_change_surface_present")

    return {
        "contract_count": len(outline.contract_names),
        "function_count": len(callable_functions),
        "public_functions": public_functions,
        "external_functions": external_functions,
        "payable_functions": payable_functions,
        "privileged_functions": privileged_functions,
        "role_management_functions": role_management_functions,
        "pause_control_functions": pause_control_functions,
        "role_guarded_functions": role_guarded_functions,
        "initializer_functions": initializer_functions,
        "state_changing_functions": state_changing_functions,
        "unguarded_state_changing_functions": unguarded_state_changing_functions,
        "low_level_call_functions": low_level_call_functions,
        "call_with_value_functions": call_with_value_functions,
        "delegatecall_functions": delegatecall_functions,
        "selfdestruct_functions": selfdestruct_functions,
        "tx_origin_functions": tx_origin_functions,
        "timestamp_functions": timestamp_functions,
        "entropy_source_functions": entropy_source_functions,
        "loop_functions": loop_functions,
        "assembly_functions": assembly_functions,
        "token_transfer_functions": token_transfer_functions,
        "token_transfer_from_functions": token_transfer_from_functions,
        "approve_functions": approve_functions,
        "signature_validation_functions": signature_validation_functions,
        "oracle_dependency_functions": oracle_dependency_functions,
        "collateral_management_functions": collateral_management_functions,
        "liquidation_functions": liquidation_functions,
        "liquidation_fee_functions": liquidation_fee_functions,
        "reserve_dependency_functions": reserve_dependency_functions,
        "fee_collection_functions": fee_collection_functions,
        "reserve_buffer_functions": reserve_buffer_functions,
        "reserve_accounting_functions": reserve_accounting_functions,
        "debt_accounting_functions": debt_accounting_functions,
        "bad_debt_socialization_functions": bad_debt_socialization_functions,
        "state_transition_functions": state_transition_functions,
        "accounting_mutation_functions": accounting_mutation_functions,
        "share_accounting_functions": share_accounting_functions,
        "vault_conversion_functions": vault_conversion_functions,
        "deposit_like_functions": deposit_like_functions,
        "asset_exit_functions": asset_exit_functions,
        "rescue_or_sweep_functions": rescue_or_sweep_functions,
        "proxy_delegatecall_functions": proxy_delegatecall_functions,
        "storage_slot_write_functions": storage_slot_write_functions,
        "implementation_reference_functions": implementation_reference_functions,
        "implementation_slot_constant_present": implementation_slot_constant_present,
        "storage_gap_present": storage_gap_present,
        "balance_validation_functions": balance_validation_functions,
        "imports": outline.imports,
        "constructor_present": outline.constructor_present,
        "fallback_present": outline.fallback_present,
        "receive_present": outline.receive_present,
        "risk_flags": risk_flags,
    }


def detect_echidna_property_functions(outline: ContractOutline) -> list[str]:
    return [
        item.name
        for item in outline.functions
        if item.kind == "function" and item.name.startswith("echidna_")
    ]


def has_assertion_surface(outline: ContractOutline) -> bool:
    return any(re.search(r"\bassert\s*\(", item.body) for item in outline.functions)


def detect_contract_patterns(outline: ContractOutline) -> tuple[list[str], list[str]]:
    issues: list[str] = []
    notes: list[str] = []
    has_implementation_slot_constant = _contains_implementation_slot_constant(outline.source_text)
    has_storage_gap = _contains_storage_gap(outline.source_text)
    callable_functions = [item for item in outline.functions if item.kind == "function"]
    share_accounting_functions = [item for item in callable_functions if _contains_share_accounting_mutation(item.body)]
    vault_conversion_functions = [
        item for item in callable_functions if _contains_vault_conversion_logic(item.signature, item.body)
    ]
    deposit_like_functions = [item for item in callable_functions if _looks_deposit_like_function(item.name, item.body)]
    asset_exit_functions = [item for item in callable_functions if _looks_asset_exit_function(item.name, item.body)]
    rescue_or_sweep_functions = [item for item in callable_functions if _looks_rescue_or_sweep_function(item.name)]
    collateral_management_functions = [
        item for item in callable_functions if _looks_collateral_management_function(item.name, item.signature, item.body)
    ]
    liquidation_functions = [
        item for item in callable_functions if _looks_liquidation_function(item.name, item.signature, item.body)
    ]
    liquidation_fee_functions = [
        item for item in callable_functions if _contains_liquidation_fee_logic(item.signature, item.body)
    ]
    reserve_dependency_functions = [item for item in callable_functions if _contains_reserve_dependency(item.body)]
    fee_collection_functions = [
        item for item in callable_functions if _looks_fee_collection_function(item.name, item.signature, item.body)
    ]
    reserve_buffer_functions = [
        item for item in callable_functions if _contains_reserve_buffer_logic(item.signature, item.body)
    ]
    reserve_accounting_functions = [
        item for item in callable_functions if _contains_reserve_accounting_logic(item.signature, item.body)
    ]
    debt_accounting_functions = [
        item for item in callable_functions if _looks_debt_accounting_function(item.name, item.signature, item.body)
    ]
    bad_debt_socialization_functions = [
        item for item in callable_functions if _contains_bad_debt_socialization_logic(item.signature, item.body)
    ]

    if outline.pragma is None:
        issues.append("missing_pragma")
    elif "^" in outline.pragma or ">" in outline.pragma:
        issues.append("floating_pragma")

    full_text = "\n".join(function.body for function in outline.functions)
    if re.search(r"\btx\.origin\b", full_text):
        issues.append("tx_origin_usage")
    if re.search(r"\.delegatecall\b", full_text):
        issues.append("delegatecall_usage")
    if re.search(r"\bselfdestruct\s*\(", full_text) or re.search(r"\bsuicide\s*\(", full_text):
        issues.append("selfdestruct_usage")
    if re.search(r"\bunchecked\s*\{", full_text):
        notes.append("unchecked_blocks_present")
    if has_storage_gap:
        notes.append("storage_gap_present")
    if deposit_like_functions:
        notes.append("deposit_flow_present")
    if asset_exit_functions:
        notes.append("asset_exit_flow_present")
    if rescue_or_sweep_functions:
        notes.append("rescue_or_sweep_flow_present")
    if collateral_management_functions:
        notes.append("collateral_management_flow_present")
    if liquidation_functions:
        notes.append("liquidation_flow_present")
    if liquidation_fee_functions:
        notes.append("liquidation_fee_flow_present")
    if reserve_dependency_functions:
        notes.append("reserve_dependency_flow_present")
    if fee_collection_functions:
        notes.append("fee_collection_flow_present")
    if reserve_buffer_functions:
        notes.append("reserve_buffer_flow_present")
    if reserve_accounting_functions:
        notes.append("reserve_accounting_flow_present")
    if debt_accounting_functions:
        notes.append("debt_accounting_flow_present")
    if bad_debt_socialization_functions:
        notes.append("bad_debt_socialization_flow_present")
    if share_accounting_functions:
        notes.append("share_accounting_flow_present")
    if vault_conversion_functions:
        notes.append("vault_conversion_logic_present")

    if deposit_like_functions and asset_exit_functions:
        notes.append("cross_function_fund_flow_present")
    if deposit_like_functions and any(_contains_accounting_mutation(item.body) for item in asset_exit_functions):
        notes.append("accounting_fund_flow_present")
    if share_accounting_functions and (deposit_like_functions or asset_exit_functions):
        notes.append("vault_share_flow_present")
    if asset_exit_functions and not any(
        _contains_balance_or_allowance_check(item.signature, item.body)
        for item in asset_exit_functions
    ):
        issues.append("asset_exit_without_balance_validation")
    if rescue_or_sweep_functions and not any(
        _has_access_guard_modifier(item.modifiers) or _has_explicit_role_guard(item.modifiers, item.body)
        for item in rescue_or_sweep_functions
    ):
        issues.append("unguarded_rescue_or_sweep_flow")

    for item in outline.functions:
        access_guarded = _has_access_guard_modifier(item.modifiers)
        reentrancy_guarded = _has_reentrancy_guard(item.modifiers)
        if _looks_admin_function(item.name) and not access_guarded:
            issues.append(f"unguarded_admin_surface:{item.name}")
        if _looks_role_management_function(item.name):
            notes.append(f"role_management_surface:{item.name}")
            if not access_guarded and not _has_explicit_role_guard(item.modifiers, item.body):
                issues.append(f"unguarded_role_management_surface:{item.name}")
        if _looks_pause_control_function(item.name):
            notes.append(f"pause_control_surface:{item.name}")
            if not access_guarded and not _has_explicit_role_guard(item.modifiers, item.body):
                issues.append(f"unguarded_pause_control_surface:{item.name}")
        if _looks_upgrade_function(item.name) and not access_guarded:
            issues.append(f"unguarded_upgrade_surface:{item.name}")
        if _looks_immediate_upgrade_execution_path(item) and not _has_upgrade_delay_or_governance_control(
            item.signature,
            item.body,
            item.modifiers,
        ):
            issues.append(f"upgrade_timelock_review_required:{item.name}")
        if _looks_initializer_function(item.name) and item.visibility in {"public", "external"} and not access_guarded:
            issues.append(f"public_initializer_surface:{item.name}")
        if item.payable and item.visibility in {"public", "external"} and not access_guarded:
            notes.append(f"payable_review:{item.name}")
        if item.payable and _looks_state_change(item.body) and not access_guarded:
            notes.append(f"payable_state_change_surface:{item.name}")
        if _contains_loop(item.body):
            notes.append(f"loop_review:{item.name}")
        if _contains_assembly(item.body):
            issues.append(f"assembly_review_required:{item.name}")

        if _contains_low_level_call(item.body):
            if _checks_external_call_result(item.body):
                notes.append(f"checked_external_call_surface:{item.name}")
            else:
                issues.append(f"unchecked_external_call_surface:{item.name}")
        if _contains_call_with_value(item.body):
            notes.append(f"value_transfer_review:{item.name}")
        if _contains_erc20_transfer_like(item.body):
            if _checks_token_call_result(item.body):
                notes.append(f"checked_token_transfer_surface:{item.name}")
            else:
                issues.append(f"unchecked_token_transfer_surface:{item.name}")
        if _contains_erc20_transfer_from_like(item.body):
            if _checks_token_call_result(item.body):
                notes.append(f"checked_token_transfer_from_surface:{item.name}")
            else:
                issues.append(f"unchecked_token_transfer_from_surface:{item.name}")
            if (
                _looks_deposit_like_function(item.name, item.body)
                and _contains_accounting_mutation(item.body)
                and not _has_token_balance_delta_check(item.body)
            ):
                issues.append(f"token_balance_delta_review_required:{item.name}")
            if _contains_parameter_transfer_from(signature=item.signature, body=item.body):
                issues.append(f"arbitrary_from_transfer_surface:{item.name}")
        if _contains_erc20_approve_like(item.body):
            if _checks_token_call_result(item.body):
                notes.append(f"checked_approve_surface:{item.name}")
            else:
                issues.append(f"unchecked_approve_surface:{item.name}")
            issues.append(f"approve_race_review_required:{item.name}")
        if _contains_ecrecover(item.body):
            notes.append(f"signature_validation_surface:{item.name}")
            if not _contains_signature_domain_separator(item.signature, item.body):
                issues.append(f"signature_domain_separation_review_required:{item.name}")
            if not _contains_signature_nonce_guard(item.signature, item.body):
                issues.append(f"signature_replay_review_required:{item.name}")
            if not _contains_signature_expiry_guard(item.signature, item.body):
                notes.append(f"signature_expiry_review:{item.name}")
                if _looks_permit_or_authorized_signature(item.name, item.signature, item.body):
                    issues.append(f"signature_deadline_review_required:{item.name}")
        if _contains_oracle_read(item.body):
            notes.append(f"oracle_dependency_review:{item.name}")
            if not _has_oracle_freshness_check(item.body):
                issues.append(f"oracle_staleness_review_required:{item.name}")
            if _contains_chainlink_oracle_read(item.body) and not _has_oracle_answer_bounds_check(item.body):
                issues.append(f"oracle_answer_bounds_review_required:{item.name}")
            if _contains_chainlink_oracle_read(item.body) and not _has_chainlink_round_completeness_check(item.body):
                issues.append(f"oracle_round_completeness_review_required:{item.name}")
            if _contains_oracle_price_math(item.body) and not _has_oracle_scaling_context(item.body):
                issues.append(f"oracle_decimal_scaling_review_required:{item.name}")
        if _looks_collateral_management_function(item.name, item.signature, item.body):
            notes.append(f"collateral_management_review:{item.name}")
            if _requires_collateral_ratio_check(item.name, item.signature, item.body) and not _has_collateral_ratio_validation(
                item.signature,
                item.body,
            ):
                issues.append(f"collateral_ratio_review_required:{item.name}")
        if _looks_liquidation_function(item.name, item.signature, item.body):
            notes.append(f"liquidation_surface_review:{item.name}")
            if not _has_collateral_ratio_validation(item.signature, item.body):
                issues.append(f"collateral_ratio_review_required:{item.name}")
            if (
                _contains_oracle_read(item.body) or _contains_reserve_dependency(item.body)
            ) and not (_has_oracle_freshness_check(item.body) or _has_reserve_window_check(item.body)):
                issues.append(f"liquidation_without_fresh_price_review:{item.name}")
        if _contains_liquidation_fee_logic(item.signature, item.body):
            notes.append(f"liquidation_fee_review:{item.name}")
            if not _has_liquidation_fee_validation(item.signature, item.body):
                issues.append(f"liquidation_fee_allocation_review_required:{item.name}")
        if _contains_reserve_dependency(item.body):
            notes.append(f"reserve_dependency_review:{item.name}")
            if not _has_reserve_window_check(item.body):
                issues.append(f"reserve_spot_dependency_review_required:{item.name}")
        if _looks_fee_collection_function(item.name, item.signature, item.body):
            notes.append(f"protocol_fee_review:{item.name}")
            if _contains_asset_movement(item.body) and not _has_reserve_sync_validation(item.signature, item.body):
                issues.append(f"protocol_fee_without_reserve_sync_review:{item.name}")
        if _contains_reserve_buffer_logic(item.signature, item.body):
            notes.append(f"reserve_buffer_review:{item.name}")
        if _contains_reserve_accounting_logic(item.signature, item.body):
            notes.append(f"reserve_accounting_review:{item.name}")
            if (
                _looks_state_change(item.body)
                and (
                    _contains_asset_movement(item.body)
                    or _looks_fee_collection_function(item.name, item.signature, item.body)
                    or _looks_debt_accounting_function(item.name, item.signature, item.body)
                )
                and not _has_reserve_sync_validation(item.signature, item.body)
            ):
                issues.append(f"reserve_accounting_drift_review_required:{item.name}")
        if _looks_debt_accounting_function(item.name, item.signature, item.body):
            notes.append(f"debt_accounting_review:{item.name}")
            if _looks_state_change(item.body) and not _has_debt_state_validation(item.signature, item.body):
                issues.append(f"debt_state_transition_review_required:{item.name}")
        if _contains_bad_debt_socialization_logic(item.signature, item.body):
            notes.append(f"bad_debt_socialization_review:{item.name}")
            if not _has_bad_debt_socialization_validation(item.signature, item.body):
                issues.append(f"bad_debt_socialization_review_required:{item.name}")
        if _contains_accounting_mutation(item.body):
            notes.append(f"accounting_surface_review:{item.name}")
        if _contains_share_accounting_mutation(item.body):
            notes.append(f"share_accounting_review:{item.name}")
        if _contains_vault_conversion_logic(item.signature, item.body):
            notes.append(f"vault_conversion_surface:{item.name}")
        if _looks_deposit_like_function(item.name, item.body):
            notes.append(f"deposit_flow_review:{item.name}")
        if _looks_asset_exit_function(item.name, item.body):
            notes.append(f"asset_exit_flow_review:{item.name}")
        if _looks_rescue_or_sweep_function(item.name):
            notes.append(f"rescue_or_sweep_review:{item.name}")
        if _has_explicit_role_guard(item.modifiers, item.body):
            notes.append(f"role_guard_present:{item.name}")
        if _looks_proxy_delegate_surface(item):
            notes.append(f"proxy_delegate_surface:{item.name}")
            if item.kind in {"fallback", "receive"}:
                issues.append(f"proxy_fallback_delegatecall_review_required:{item.name}")
                if not has_implementation_slot_constant:
                    issues.append(f"proxy_storage_collision_review_required:{item.name}")
        if _contains_storage_slot_write(item.body):
            notes.append(f"storage_slot_write_surface:{item.name}")
            issues.append(f"storage_slot_write_review_required:{item.name}")
        if _contains_implementation_reference(f"{item.signature}\n{item.body}"):
            notes.append(f"implementation_reference_surface:{item.name}")
        if _contains_parameter_target_low_level_call(item.signature, item.body):
            issues.append(f"user_supplied_call_target:{item.name}")
        if _contains_parameter_target_delegatecall(item.signature, item.body):
            issues.append(f"user_supplied_delegatecall_target:{item.name}")

        address_params = _address_parameter_names(item.signature)
        if address_params and (
            _looks_admin_function(item.name)
            or _looks_upgrade_function(item.name)
            or _looks_initializer_function(item.name)
        ):
            unchecked_address_params = [
                name
                for name in address_params
                if not _has_zero_address_validation(name, item.body)
            ]
            if unchecked_address_params:
                issues.append(f"missing_zero_address_validation:{item.name}")
        if _looks_upgrade_function(item.name) and address_params:
            implementation_checks = [
                name
                for name in address_params
                if _has_contract_code_validation(name, item.body)
            ]
            if not implementation_checks:
                issues.append(f"unvalidated_implementation_target:{item.name}")

        if _contains_delegatecall(item.body) and not access_guarded:
            issues.append(f"unguarded_delegatecall_surface:{item.name}")
        if _contains_selfdestruct(item.body) and not access_guarded:
            issues.append(f"unguarded_selfdestruct_surface:{item.name}")
        if _contains_tx_origin(item.body) and re.search(r"\brequire\s*\([^)]*tx\.origin", item.body, re.IGNORECASE):
            issues.append(f"tx_origin_auth_surface:{item.name}")
        if _contains_timestamp_dependency(item.body):
            notes.append(f"time_dependency_review:{item.name}")
        if _contains_randomness_like_usage(item.body):
            issues.append(f"entropy_source_review_required:{item.name}")
        if _contains_loop(item.body) and _contains_low_level_call(item.body):
            issues.append(f"external_call_in_loop:{item.name}")
        if _contains_state_transition_after_external_call(item.body):
            issues.append(f"state_transition_after_external_call:{item.name}")
        if _contains_accounting_update_after_external_call(item.body):
            issues.append(f"accounting_update_after_external_call:{item.name}")
        if (
            _looks_withdraw_like_function(item.name)
            and _contains_accounting_mutation(item.body)
            and any(
                check(item.body)
                for check in (
                    _contains_low_level_call,
                    _contains_call_with_value,
                    _contains_erc20_transfer_like,
                    _contains_erc20_transfer_from_like,
                )
            )
            and not _contains_balance_or_allowance_check(item.signature, item.body)
        ):
            issues.append(f"withdrawal_without_balance_validation:{item.name}")
        if (
            _looks_vault_entry_or_mint_function(item.name, item.signature, item.body)
            and _contains_share_accounting_mutation(item.body)
            and not any(
                (
                    _contains_call_with_value(item.body),
                    _contains_erc20_transfer_from_like(item.body),
                    _contains_balance_or_allowance_check(item.signature, item.body),
                )
            )
        ):
            issues.append(f"share_mint_without_asset_backing_review:{item.name}")
        if (
            _looks_vault_exit_or_redeem_function(item.name, item.signature, item.body)
            and _contains_share_accounting_mutation(item.body)
            and any(
                check(item.body)
                for check in (
                    _contains_low_level_call,
                    _contains_call_with_value,
                    _contains_erc20_transfer_like,
                )
            )
            and not _contains_balance_or_allowance_check(item.signature, item.body)
        ):
            issues.append(f"share_redeem_without_share_validation:{item.name}")
        if (
            _looks_vault_conversion_sensitive_function(item.name, item.signature, item.body)
            and _references_assets_and_shares(item.signature, item.body)
            and not _contains_vault_conversion_logic(item.signature, item.body)
        ):
            issues.append(f"vault_conversion_review_required:{item.name}")
        if (
            _looks_rescue_or_sweep_function(item.name)
            and any(
                check(item.body)
                for check in (
                    _contains_low_level_call,
                    _contains_call_with_value,
                    _contains_erc20_transfer_like,
                    _contains_erc20_transfer_from_like,
                )
            )
            and not access_guarded
            and not _has_explicit_role_guard(item.modifiers, item.body)
        ):
            issues.append(f"unguarded_rescue_or_sweep_surface:{item.name}")
        if (
            item.visibility in {"public", "external"}
            and _looks_state_change(item.body)
            and not access_guarded
            and not _has_explicit_role_guard(item.modifiers, item.body)
            and _looks_sensitive_authority_function(item.name, item.body)
        ):
            issues.append(f"unguarded_privileged_state_change:{item.name}")

        if _looks_reentrancy_review(item.body):
            if reentrancy_guarded:
                notes.append(f"reentrancy_guard_present:{item.name}")
            else:
                issues.append(f"reentrancy_review_required:{item.name}")

        if item.kind == "fallback":
            notes.append("fallback_function_present")
            if item.payable:
                notes.append("payable_fallback_present")
        if item.kind == "receive":
            notes.append("receive_function_present")

    return _ordered_unique(issues), _ordered_unique(notes)


def prioritize_contract_issues(issues: list[str]) -> list[dict[str, str]]:
    prioritized = [
        {
            "issue": issue,
            "family": issue.split(":", 1)[0],
            "priority": contract_issue_priority(issue),
            "summary": contract_issue_summary(issue),
        }
        for issue in _ordered_unique(issues)
    ]
    prioritized.sort(
        key=lambda item: (
            _contract_priority_rank(item["priority"]),
            item["family"],
            item["issue"],
        )
    )
    return prioritized


def build_normalized_contract_findings(
    prioritized_issues: list[dict[str, object]],
    *,
    known_case_matches: list[dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    known_cases_by_family = _known_case_matches_by_family(known_case_matches or [])

    for item in prioritized_issues:
        issue = str(item.get("issue", "")).strip()
        if not issue:
            continue
        family, _, raw_target = issue.partition(":")
        target = raw_target.strip()
        priority = str(item.get("priority", contract_issue_priority(issue))).strip().lower() or "medium"
        summary = str(item.get("summary", contract_issue_summary(issue))).strip() or contract_issue_summary(issue)
        line = _contract_item_line(item)
        line_evidence = str(item.get("line_evidence", "")).strip()
        family_matches = known_cases_by_family.get(family, [])
        finding: dict[str, object] = {
            "finding_id": f"ez-contract-{_contract_issue_slug(issue)}",
            "issue": issue,
            "family": family,
            "target": target or None,
            "summary": summary,
            "severity": _contract_finding_severity(priority),
            "priority": priority,
            "confidence": _contract_finding_confidence(line=line, known_case_matches=family_matches),
            "source": "contract_pattern_check_tool",
            "review_required": True,
            "evidence": _normalized_contract_finding_evidence(
                issue=issue,
                line=line,
                line_evidence=line_evidence,
                known_case_matches=family_matches,
            ),
            "fix_direction": _contract_fix_direction(family),
            "recheck": _contract_recheck_path(family),
        }
        if line is not None:
            finding["line"] = line
            finding["line_hint"] = f"Line hint: {line}"
        if line_evidence:
            finding["line_evidence"] = line_evidence
        if family_matches:
            finding["known_case_matches"] = family_matches[:3]
        findings.append(finding)

    return findings


def build_contract_issue_line_hints(
    outline: ContractOutline,
    issues: list[str],
) -> list[dict[str, object]]:
    hints: list[dict[str, object]] = []
    functions_by_name: dict[str, ContractFunction] = {}
    for function in outline.functions:
        functions_by_name.setdefault(function.name, function)

    for issue in _ordered_unique(issues):
        family, _, detail = issue.partition(":")
        target = detail.strip()
        function = functions_by_name.get(target) if target else None
        tokens = _issue_line_hint_tokens(family)
        line = 0
        evidence = ""
        hint_source = ""

        if function is not None:
            line, evidence = _line_hint_in_function(outline, function, tokens)
            hint_source = "function"
            if line == 0 and function.start_line > 0:
                line = function.start_line
                evidence = function.name
                hint_source = "function_entry"

        if line == 0 and tokens:
            line, evidence = _line_hint_in_text(outline.source_text, tokens, base_line=1)
            hint_source = "source"

        if line <= 0:
            continue

        hint: dict[str, object] = {
            "issue": issue,
            "family": family,
            "line": line,
            "source": hint_source or "source",
        }
        if target:
            hint["function"] = target
        if evidence:
            hint["evidence"] = evidence
        hints.append(hint)

    return hints


def contract_issue_priority(issue: str) -> str:
    family = issue.split(":", 1)[0]
    high_priority_families = {
        "unguarded_upgrade_surface",
        "unguarded_role_management_surface",
        "unguarded_pause_control_surface",
        "unguarded_privileged_state_change",
        "asset_exit_without_balance_validation",
        "unguarded_rescue_or_sweep_flow",
        "unguarded_rescue_or_sweep_surface",
        "public_initializer_surface",
        "unchecked_external_call_surface",
        "user_supplied_call_target",
        "user_supplied_delegatecall_target",
        "unguarded_delegatecall_surface",
        "unguarded_selfdestruct_surface",
        "tx_origin_auth_surface",
        "reentrancy_review_required",
        "external_call_in_loop",
        "state_transition_after_external_call",
        "accounting_update_after_external_call",
        "withdrawal_without_balance_validation",
        "share_mint_without_asset_backing_review",
        "share_redeem_without_share_validation",
        "protocol_fee_without_reserve_sync_review",
        "reserve_accounting_drift_review_required",
        "debt_state_transition_review_required",
        "collateral_ratio_review_required",
        "liquidation_without_fresh_price_review",
        "liquidation_fee_allocation_review_required",
        "bad_debt_socialization_review_required",
        "signature_replay_review_required",
        "signature_domain_separation_review_required",
        "signature_deadline_review_required",
        "oracle_staleness_review_required",
        "oracle_answer_bounds_review_required",
        "oracle_round_completeness_review_required",
        "unvalidated_implementation_target",
        "proxy_storage_collision_review_required",
        "selfdestruct_usage",
    }
    medium_priority_families = {
        "floating_pragma",
        "missing_pragma",
        "tx_origin_usage",
        "unguarded_admin_surface",
        "unchecked_token_transfer_surface",
        "unchecked_token_transfer_from_surface",
        "unchecked_approve_surface",
        "approve_race_review_required",
        "token_balance_delta_review_required",
        "vault_conversion_review_required",
        "reserve_spot_dependency_review_required",
        "oracle_decimal_scaling_review_required",
        "arbitrary_from_transfer_surface",
        "assembly_review_required",
        "entropy_source_review_required",
        "missing_zero_address_validation",
        "upgrade_timelock_review_required",
        "delegatecall_usage",
        "proxy_fallback_delegatecall_review_required",
        "storage_slot_write_review_required",
    }
    if family in high_priority_families:
        return "high"
    if family in medium_priority_families:
        return "medium"
    return "low"


def contract_issue_summary(issue: str) -> str:
    family, _, detail = issue.partition(":")
    target = detail.strip()
    if family == "floating_pragma":
        return "floating pragma range should be confirmed against the intended compiler set"
    if family == "missing_pragma":
        return "compiler expectations should be confirmed because the contract has no pragma"
    if family == "selfdestruct_usage":
        return "destructive lifecycle behavior should be reviewed"
    if family == "tx_origin_usage":
        return "tx.origin usage should be reviewed before trusting authorization assumptions"
    if family == "unguarded_admin_surface" and target:
        return f"access control on `{target}` should be reviewed"
    if family == "unguarded_role_management_surface" and target:
        return f"role-management authorization in `{target}` should be reviewed"
    if family == "unguarded_pause_control_surface" and target:
        return f"pause or unpause authorization in `{target}` should be reviewed"
    if family == "unguarded_privileged_state_change" and target:
        return f"privileged state-changing authority in `{target}` should be reviewed"
    if family == "asset_exit_without_balance_validation":
        return "asset-exit paths should be reviewed for balance or allowance validation"
    if family == "unguarded_rescue_or_sweep_flow":
        return "rescue or sweep flows should be reviewed for missing authorization boundaries"
    if family == "unguarded_rescue_or_sweep_surface" and target:
        return f"rescue or sweep authority in `{target}` should be reviewed"
    if family == "unguarded_upgrade_surface" and target:
        return f"upgrade authorization on `{target}` should be reviewed"
    if family == "public_initializer_surface" and target:
        return f"public initializer exposure on `{target}` should be reviewed"
    if family == "unchecked_external_call_surface" and target:
        return f"unchecked low-level call handling in `{target}` should be reviewed"
    if family == "user_supplied_call_target" and target:
        return f"user-supplied external call targets in `{target}` should be reviewed"
    if family == "user_supplied_delegatecall_target" and target:
        return f"user-supplied delegatecall targets in `{target}` should be reviewed"
    if family == "unguarded_delegatecall_surface" and target:
        return f"unguarded delegatecall behavior in `{target}` should be reviewed"
    if family == "unguarded_selfdestruct_surface" and target:
        return f"unguarded selfdestruct behavior in `{target}` should be reviewed"
    if family == "tx_origin_auth_surface" and target:
        return f"tx.origin-based authorization in `{target}` should be reviewed"
    if family == "reentrancy_review_required" and target:
        return f"reentrancy-adjacent sequencing in `{target}` should be reviewed"
    if family == "external_call_in_loop" and target:
        return f"external call behavior inside loops in `{target}` should be reviewed"
    if family == "state_transition_after_external_call" and target:
        return f"state transitions after external calls in `{target}` should be reviewed"
    if family == "accounting_update_after_external_call" and target:
        return f"balance, allowance, or claim-accounting updates after external calls in `{target}` should be reviewed"
    if family == "withdrawal_without_balance_validation" and target:
        return f"withdrawal or claim-like balance validation in `{target}` should be reviewed"
    if family == "share_mint_without_asset_backing_review" and target:
        return f"share minting and asset-backing assumptions in `{target}` should be reviewed"
    if family == "share_redeem_without_share_validation" and target:
        return f"share redemption validation in `{target}` should be reviewed"
    if family == "protocol_fee_without_reserve_sync_review" and target:
        return f"protocol-fee or skim behavior in `{target}` should be reviewed for missing reserve synchronization"
    if family == "reserve_accounting_drift_review_required" and target:
        return f"reserve-accounting drift assumptions in `{target}` should be reviewed"
    if family == "debt_state_transition_review_required" and target:
        return f"debt-state transition assumptions in `{target}` should be reviewed"
    if family == "collateral_ratio_review_required" and target:
        return f"collateral-ratio or health-factor validation in `{target}` should be reviewed"
    if family == "liquidation_without_fresh_price_review" and target:
        return f"liquidation pricing freshness in `{target}` should be reviewed"
    if family == "liquidation_fee_allocation_review_required" and target:
        return f"liquidation bonus, penalty, or fee allocation in `{target}` should be reviewed"
    if family == "bad_debt_socialization_review_required" and target:
        return f"bad-debt socialization, writeoff, or reserve-buffer coverage in `{target}` should be reviewed"
    if family == "unchecked_token_transfer_surface" and target:
        return f"ERC20 transfer return handling in `{target}` should be reviewed"
    if family == "unchecked_token_transfer_from_surface" and target:
        return f"ERC20 transferFrom return handling in `{target}` should be reviewed"
    if family == "unchecked_approve_surface" and target:
        return f"ERC20 approve return handling in `{target}` should be reviewed"
    if family == "approve_race_review_required" and target:
        return f"allowance reset and approve race behavior in `{target}` should be reviewed"
    if family == "token_balance_delta_review_required" and target:
        return f"token balance-delta accounting in `{target}` should be reviewed"
    if family == "vault_conversion_review_required" and target:
        return f"asset and share conversion assumptions in `{target}` should be reviewed"
    if family == "signature_replay_review_required" and target:
        return f"replay protection and nonce use in `{target}` should be reviewed"
    if family == "signature_domain_separation_review_required" and target:
        return f"signature domain separation in `{target}` should be reviewed"
    if family == "signature_deadline_review_required" and target:
        return f"signature deadline or expiry handling in `{target}` should be reviewed"
    if family == "arbitrary_from_transfer_surface" and target:
        return f"arbitrary `from` transfer behavior in `{target}` should be reviewed"
    if family == "assembly_review_required" and target:
        return f"inline assembly in `{target}` should be reviewed"
    if family == "entropy_source_review_required" and target:
        return f"randomness and entropy assumptions in `{target}` should be reviewed"
    if family == "oracle_staleness_review_required" and target:
        return f"oracle freshness and staleness handling in `{target}` should be reviewed"
    if family == "oracle_answer_bounds_review_required" and target:
        return f"oracle answer bounds and non-positive price handling in `{target}` should be reviewed"
    if family == "oracle_round_completeness_review_required" and target:
        return f"Chainlink round completeness in `{target}` should be reviewed"
    if family == "oracle_decimal_scaling_review_required" and target:
        return f"oracle decimal scaling and price precision in `{target}` should be reviewed"
    if family == "reserve_spot_dependency_review_required" and target:
        return f"reserve-derived spot price assumptions in `{target}` should be reviewed"
    if family == "missing_zero_address_validation" and target:
        return f"zero-address validation in `{target}` should be reviewed"
    if family == "unvalidated_implementation_target" and target:
        return f"implementation target validation in `{target}` should be reviewed"
    if family == "upgrade_timelock_review_required" and target:
        return f"upgrade delay, queue, or governance controls in `{target}` should be reviewed"
    if family == "proxy_fallback_delegatecall_review_required" and target:
        return f"proxy-style fallback delegatecall behavior in `{target}` should be reviewed"
    if family == "proxy_storage_collision_review_required" and target:
        return f"proxy storage collision and slot-isolation assumptions in `{target}` should be reviewed"
    if family == "storage_slot_write_review_required" and target:
        return f"storage-slot write behavior in `{target}` should be reviewed"
    return issue.replace("_", " ")


def _contract_item_line(item: dict[str, object]) -> int | None:
    raw_line = item.get("line")
    if isinstance(raw_line, int) and raw_line > 0:
        return raw_line
    if isinstance(raw_line, str) and raw_line.isdigit():
        line = int(raw_line)
        return line if line > 0 else None
    return None


def _known_case_matches_by_family(matches: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    indexed: dict[str, list[dict[str, object]]] = {}
    for match in matches:
        matched_checks = match.get("matched_checks")
        if not isinstance(matched_checks, list):
            continue
        compact = {
            "profile_id": str(match.get("profile_id", "")).strip(),
            "title": str(match.get("title", "")).strip(),
            "family": str(match.get("family", "")).strip(),
            "source_id": str(match.get("source_id", "")).strip(),
            "risk_hint": str(match.get("risk_hint", "")).strip(),
            "evidence_strength": str(match.get("evidence_strength", "")).strip(),
        }
        for raw_check in matched_checks:
            check_family = str(raw_check).split(":", 1)[0].strip()
            if check_family:
                indexed.setdefault(check_family, []).append(compact)
    return indexed


def _normalized_contract_finding_evidence(
    *,
    issue: str,
    line: int | None,
    line_evidence: str,
    known_case_matches: list[dict[str, object]],
) -> list[str]:
    evidence = [f"Local pattern signal: {issue}."]
    if line is not None:
        evidence.append(f"Line hint: {line}.")
    if line_evidence:
        evidence.append(f"Matched local token: {line_evidence}.")
    for match in known_case_matches[:2]:
        title = str(match.get("title", "")).strip() or str(match.get("profile_id", "")).strip()
        source = str(match.get("source_id", "")).strip()
        risk = str(match.get("risk_hint", "")).strip()
        fragments = [title]
        if source:
            fragments.append(f"source={source}")
        if risk:
            fragments.append(f"risk_hint={risk}")
        evidence.append("Known-case context: " + "; ".join(fragments) + ".")
    return evidence


def _contract_finding_severity(priority: str) -> str:
    normalized = priority.strip().lower()
    if normalized in {"high", "medium", "low"}:
        return normalized
    return "review"


def _contract_finding_confidence(
    *,
    line: int | None,
    known_case_matches: list[dict[str, object]],
) -> str:
    if line is not None and known_case_matches:
        return "candidate_with_local_evidence_and_known_case_context"
    if line is not None:
        return "candidate_with_local_evidence"
    if known_case_matches:
        return "candidate_with_known_case_context"
    return "candidate_review_required"


def _contract_fix_direction(family: str) -> str:
    if family in {
        "unguarded_admin_surface",
        "unguarded_role_management_surface",
        "unguarded_pause_control_surface",
        "unguarded_upgrade_surface",
        "unguarded_privileged_state_change",
        "public_initializer_surface",
        "missing_zero_address_validation",
        "unvalidated_implementation_target",
        "upgrade_timelock_review_required",
    }:
        return "Add explicit authorization, target validation, and upgrade delay or governance controls where applicable."
    if family in {
        "unchecked_external_call_surface",
        "user_supplied_call_target",
        "reentrancy_review_required",
        "external_call_in_loop",
        "state_transition_after_external_call",
        "accounting_update_after_external_call",
        "withdrawal_without_balance_validation",
        "asset_exit_without_balance_validation",
        "unguarded_rescue_or_sweep_flow",
        "unguarded_rescue_or_sweep_surface",
    }:
        return "Narrow the value-flow path, check call results, validate balances before transfer, and prefer checks-effects-interactions."
    if family in {
        "unchecked_token_transfer_surface",
        "unchecked_token_transfer_from_surface",
        "unchecked_approve_surface",
        "approve_race_review_required",
        "token_balance_delta_review_required",
        "arbitrary_from_transfer_surface",
    }:
        return "Use safe token wrappers, validate return values, and confirm allowance or balance-delta assumptions."
    if family in {
        "signature_replay_review_required",
        "signature_domain_separation_review_required",
        "signature_deadline_review_required",
    }:
        return "Bind signatures to domain, chain, contract, nonce, signer, and expiry before accepting the action."
    if family in {
        "oracle_staleness_review_required",
        "oracle_answer_bounds_review_required",
        "oracle_round_completeness_review_required",
        "oracle_decimal_scaling_review_required",
        "reserve_spot_dependency_review_required",
    }:
        return "Validate oracle freshness, round completeness, non-zero bounds, and decimal scaling before price-dependent state changes."
    if family in {
        "user_supplied_delegatecall_target",
        "unguarded_delegatecall_surface",
        "proxy_fallback_delegatecall_review_required",
        "proxy_storage_collision_review_required",
        "storage_slot_write_review_required",
        "delegatecall_usage",
    }:
        return "Constrain delegatecall targets, validate implementation code, and preserve proxy storage-layout assumptions."
    if family in {
        "collateral_ratio_review_required",
        "liquidation_without_fresh_price_review",
        "liquidation_fee_allocation_review_required",
    }:
        return "Re-check health-factor, liquidation price, and fee-allocation invariants against fresh market inputs."
    if family in {
        "protocol_fee_without_reserve_sync_review",
        "reserve_accounting_drift_review_required",
        "debt_state_transition_review_required",
        "bad_debt_socialization_review_required",
    }:
        return "Tie fee, reserve, debt, and bad-debt transitions to explicit accounting invariants and sync checks."
    if family in {
        "share_mint_without_asset_backing_review",
        "share_redeem_without_share_validation",
        "vault_conversion_review_required",
    }:
        return "Validate asset-share conversion, backing, and redemption assumptions before mint or burn effects."
    return "Add a minimal local reproduction or invariant, harden the implicated path, and keep the claim in manual review until rechecked."


def _contract_recheck_path(family: str) -> str:
    if family.startswith("oracle") or family == "reserve_spot_dependency_review_required":
        return "Re-run pattern checks, compile/test paths, and an oracle-focused golden or casebook run after the fix."
    if family.startswith("signature"):
        return "Re-run pattern checks and signature or permit replay cases after adding nonce, domain, and deadline controls."
    if "delegatecall" in family or "proxy" in family or "storage" in family:
        return "Re-run pattern checks, proxy/storage casebook lanes, and compile tests after target or storage hardening."
    return "Re-run the same scoped smart-contract audit path and compare the normalized findings after remediation."


def _contract_issue_slug(issue: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", issue.strip().lower()).strip("-")
    return slug or "review-signal"


def _extract_functions(code: str) -> list[ContractFunction]:
    entries: list[tuple[int, ContractFunction]] = []
    patterns = (
        ("function", re.compile(r"\bfunction\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")),
        ("constructor", re.compile(r"\bconstructor\s*\(")),
        ("receive", re.compile(r"\breceive\s*\(\s*\)")),
        ("fallback", re.compile(r"\bfallback\s*\(")),
    )
    for kind, pattern in patterns:
        for match in pattern.finditer(code):
            start = match.start()
            header_end = code.find("{", start)
            semicolon_end = code.find(";", start)
            if semicolon_end != -1 and (header_end == -1 or semicolon_end < header_end):
                continue
            if header_end == -1:
                continue
            signature = code[start:header_end].strip()
            body, block_end = _extract_braced_block(code, header_end)
            header = signature.lower()
            if kind in {"receive", "fallback"}:
                visibility = "external"
            else:
                visibility = "internal"
            for candidate in ("external", "public", "internal", "private"):
                if re.search(rf"\b{candidate}\b", header):
                    visibility = candidate
                    break
            name = match.group(1) if kind == "function" else kind
            entries.append(
                (
                    start,
                    ContractFunction(
                        name=name,
                        signature=signature,
                        visibility=visibility,
                        modifiers=_extract_modifier_tokens(signature),
                        payable=bool(re.search(r"\bpayable\b", header)),
                        body=body,
                        kind=kind,
                        start_line=_line_number_for_offset(code, start),
                        end_line=_line_number_for_offset(code, block_end),
                    ),
                )
            )
            _ = block_end
    entries.sort(key=lambda item: item[0])
    return [item[1] for item in entries]


def _extract_vyper_functions(code: str) -> list[ContractFunction]:
    lines = code.splitlines()
    entries: list[ContractFunction] = []
    index = 0
    while index < len(lines):
        decorators: list[str] = []
        while index < len(lines) and lines[index].strip().startswith("@"):
            decorators.append(lines[index].strip())
            index += 1

        if index >= len(lines):
            break

        line = lines[index]
        match = re.match(r"^(\s*)def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", line)
        if match is None:
            index += 1
            continue

        indent = len(match.group(1))
        name = match.group(2)
        signature_lines = [*decorators, line.strip()]
        body_lines: list[str] = []
        body_index = index + 1
        while body_index < len(lines):
            candidate = lines[body_index]
            stripped = candidate.strip()
            candidate_indent = len(candidate) - len(candidate.lstrip(" \t"))
            if stripped and candidate_indent <= indent and not stripped.startswith("#"):
                break
            body_lines.append(candidate)
            body_index += 1

        decorator_text = " ".join(decorators).lower()
        visibility = "external" if "@external" in decorator_text else "internal"
        payable = "@payable" in decorator_text
        kind = "function"
        if name == "__init__":
            kind = "constructor"
        elif name == "__default__":
            kind = "fallback"

        entries.append(
            ContractFunction(
                name=name,
                signature="\n".join(signature_lines),
                visibility=visibility,
                modifiers=_extract_modifier_tokens(" ".join(signature_lines)),
                payable=payable,
                body="\n".join(body_lines),
                kind=kind,
                start_line=index + 1,
                end_line=body_index,
            )
        )
        index = body_index

    return entries


def _line_number_for_offset(text: str, offset: int) -> int:
    safe_offset = max(0, min(offset, len(text)))
    return text.count("\n", 0, safe_offset) + 1


def _line_hint_in_function(
    outline: ContractOutline,
    function: ContractFunction,
    tokens: tuple[str, ...],
) -> tuple[int, str]:
    if function.start_line <= 0:
        return 0, ""
    lines = outline.source_text.splitlines()
    start_index = max(function.start_line - 1, 0)
    end_index = function.end_line if function.end_line > function.start_line else len(lines)
    segment = "\n".join(lines[start_index:end_index])
    return _line_hint_in_text(segment, tokens, base_line=function.start_line)


def _line_hint_in_text(text: str, tokens: tuple[str, ...], *, base_line: int) -> tuple[int, str]:
    if not text or not tokens:
        return 0, ""
    lowered = text.lower()
    best_index: int | None = None
    best_token = ""
    for token in tokens:
        normalized_token = token.lower()
        index = lowered.find(normalized_token)
        if index == -1:
            continue
        if best_index is None or index < best_index:
            best_index = index
            best_token = token
    if best_index is None:
        return 0, ""
    return base_line + text.count("\n", 0, best_index), best_token


def _issue_line_hint_tokens(family: str) -> tuple[str, ...]:
    token_map: dict[str, tuple[str, ...]] = {
        "floating_pragma": ("pragma solidity",),
        "selfdestruct_usage": ("selfdestruct(", "suicide("),
        "tx_origin_usage": ("tx.origin",),
        "tx_origin_auth_surface": ("tx.origin",),
        "delegatecall_usage": (".delegatecall(", ".delegatecall{"),
        "proxy_fallback_delegatecall_review_required": (".delegatecall(", ".delegatecall{"),
        "proxy_storage_collision_review_required": (".delegatecall(", ".delegatecall{"),
        "user_supplied_delegatecall_target": (".delegatecall(", ".delegatecall{"),
        "unguarded_delegatecall_surface": (".delegatecall(", ".delegatecall{"),
        "unchecked_external_call_surface": (".call{", ".call(", ".staticcall{", ".staticcall("),
        "user_supplied_call_target": (".call{", ".call(", ".staticcall{", ".staticcall("),
        "external_call_in_loop": (".call{", ".call(", ".delegatecall(", ".staticcall(", "send(", "transfer("),
        "state_transition_after_external_call": (
            ".call{",
            ".call(",
            ".delegatecall(",
            ".staticcall(",
            "send(",
            "transfer(",
        ),
        "accounting_update_after_external_call": (
            ".call{",
            ".call(",
            ".delegatecall(",
            ".staticcall(",
            "send(",
            "transfer(",
            "transferfrom(",
        ),
        "withdrawal_without_balance_validation": (".call{", ".call(", "transfer(", "transferfrom("),
        "reentrancy_review_required": (".call{", ".call(", ".delegatecall(", "send(", "transfer("),
        "unchecked_token_transfer_surface": (".transfer(",),
        "unchecked_token_transfer_from_surface": (".transferfrom(",),
        "arbitrary_from_transfer_surface": (".transferfrom(",),
        "token_balance_delta_review_required": (".transferfrom(", ".transfer("),
        "unchecked_approve_surface": (".approve(",),
        "approve_race_review_required": (".approve(",),
        "signature_replay_review_required": ("ecrecover(",),
        "signature_domain_separation_review_required": ("ecrecover(",),
        "signature_deadline_review_required": ("deadline", "expiry", "ecrecover("),
        "oracle_staleness_review_required": (
            ".latestrounddata(",
            ".getrounddata(",
            ".latestanswer(",
            ".consult(",
            ".getreserves(",
            "oracle.",
        ),
        "oracle_answer_bounds_review_required": (
            ".latestrounddata(",
            ".getrounddata(",
            ".latestanswer(",
            "pricefeed",
        ),
        "oracle_round_completeness_review_required": (
            ".latestrounddata(",
            ".getrounddata(",
            "answeredinround",
            "roundid",
        ),
        "oracle_decimal_scaling_review_required": ("price", "answer", ".latestrounddata("),
        "reserve_spot_dependency_review_required": (".getreserves(", "reserve"),
        "collateral_ratio_review_required": ("collateral", "health", "ratio"),
        "liquidation_without_fresh_price_review": ("liquidat", "price", "oracle", ".getreserves("),
        "liquidation_fee_allocation_review_required": ("liquidat", "fee", "bonus", "penalty"),
        "bad_debt_socialization_review_required": ("baddebt", "bad_debt", "writeoff", "socialize"),
        "protocol_fee_without_reserve_sync_review": ("fee", "skim", "reserve"),
        "reserve_accounting_drift_review_required": ("reserve", "sync"),
        "debt_state_transition_review_required": ("debt", "borrow", "repay", "accrue"),
        "share_mint_without_asset_backing_review": ("mint", "shares", "totalsupply"),
        "share_redeem_without_share_validation": ("redeem", "shares", "burn"),
        "vault_conversion_review_required": ("convert", "preview", "assets", "shares"),
        "assembly_review_required": ("assembly",),
        "entropy_source_review_required": ("keccak256(", "block.timestamp", "blockhash(", "prevrandao"),
        "storage_slot_write_review_required": ("sstore", ".slot", "storage"),
        "public_initializer_surface": ("initialize", "initializer"),
        "missing_zero_address_validation": ("address",),
        "unvalidated_implementation_target": ("implementation",),
        "upgrade_timelock_review_required": ("upgrade", "implementation"),
        "unguarded_admin_surface": ("admin", "owner"),
        "unguarded_role_management_surface": ("role", "grant", "revoke"),
        "unguarded_pause_control_surface": ("pause", "unpause"),
        "unguarded_privileged_state_change": ("owner", "admin", "role"),
        "unguarded_upgrade_surface": ("upgrade", "implementation"),
        "asset_exit_without_balance_validation": ("withdraw", "claim", "redeem", "transfer"),
        "unguarded_rescue_or_sweep_flow": ("rescue", "sweep"),
        "unguarded_rescue_or_sweep_surface": ("rescue", "sweep"),
        "unguarded_selfdestruct_surface": ("selfdestruct(", "suicide("),
    }
    return token_map.get(family, ())


def _extract_braced_block(code: str, brace_index: int) -> tuple[str, int]:
    depth = 0
    start = brace_index + 1
    for index in range(brace_index, len(code)):
        char = code[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return code[start:index], index + 1
    return code[start:], len(code)


def _extract_modifier_tokens(signature: str) -> list[str]:
    header = signature.replace("\n", " ")
    header_tail = header.split(")", 1)[1] if ")" in header else header
    matches = re.findall(
        r"\b(only[A-Za-z0-9_]*|admin[A-Za-z0-9_]*|owner[A-Za-z0-9_]*|role[A-Za-z0-9_]*|nonReentrant|initializer|whenNotPaused|whenPaused)\b",
        header_tail,
        flags=re.IGNORECASE,
    )
    return matches


def _has_access_guard_modifier(modifiers: list[str]) -> bool:
    return any(
        token.lower().startswith(("only", "admin", "owner", "role"))
        for token in modifiers
    )


def _has_reentrancy_guard(modifiers: list[str]) -> bool:
    return any(token.lower() == "nonreentrant" for token in modifiers)


def _looks_admin_function(name: str) -> bool:
    lowered = name.lower()
    if lowered.startswith("echidna_"):
        return False
    return any(
        token in lowered
        for token in ("admin", "owner", "pause", "upgrade", "mint", "burn", "set", "withdraw")
    )


def _looks_initializer_function(name: str) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in ("init", "initialize"))


def _looks_upgrade_function(name: str) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in ("upgrade", "implementation", "beacon", "proxy", "logic"))


def _looks_role_management_function(name: str) -> bool:
    lowered = name.lower()
    return any(
        token in lowered
        for token in (
            "grantrole",
            "grant_role",
            "revokerole",
            "revoke_role",
            "renouncerole",
            "renounce_role",
            "setrole",
            "set_role",
            "setoperator",
            "set_operator",
            "addoperator",
            "add_operator",
            "removeoperator",
            "remove_operator",
            "setguardian",
            "set_guardian",
            "addguardian",
            "add_guardian",
            "removeguardian",
            "remove_guardian",
            "setmanager",
            "set_manager",
            "addmanager",
            "add_manager",
            "removemanager",
            "remove_manager",
        )
    )


def _looks_pause_control_function(name: str) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in ("pause", "unpause", "freeze", "unfreeze"))


def _looks_proxy_delegate_surface(item: ContractFunction) -> bool:
    if not _contains_delegatecall(item.body):
        return False
    if item.kind in {"fallback", "receive"}:
        return True
    combined = f"{item.signature}\n{item.body}".lower()
    return any(
        token in combined
        for token in (
            "implementation",
            "_implementation",
            "beacon",
            "_beacon",
            "proxy",
        )
    )


def _contains_low_level_call(body: str) -> bool:
    lowered = body.lower()
    return any(
        token in lowered
        for token in (
            ".call(",
            ".call{",
            ".delegatecall(",
            ".delegatecall{",
            ".staticcall(",
            ".staticcall{",
        )
    )


def _contains_call_with_value(body: str) -> bool:
    lowered = body.lower()
    return any(
        token in lowered
        for token in (
            ".call{value:",
            ".call{ value:",
        )
    )


def _contains_delegatecall(body: str) -> bool:
    lowered = body.lower()
    return ".delegatecall(" in lowered or ".delegatecall{" in lowered


def _contains_selfdestruct(body: str) -> bool:
    lowered = body.lower()
    return "selfdestruct(" in lowered or "suicide(" in lowered


def _contains_tx_origin(body: str) -> bool:
    return "tx.origin" in body.lower()


def _contains_timestamp_dependency(body: str) -> bool:
    lowered = body.lower()
    return "block.timestamp" in lowered or re.search(r"\bnow\b", lowered) is not None


def _contains_entropy_source(body: str) -> bool:
    lowered = body.lower()
    return any(
        token in lowered
        for token in (
            "block.timestamp",
            "blockhash(",
            "block.prevrandao",
            "prevrandao",
            "block.difficulty",
            "now",
        )
    )


def _contains_randomness_like_usage(body: str) -> bool:
    lowered = body.lower()
    if not _contains_entropy_source(body):
        return False
    return bool(
        re.search(r"\b(keccak256|sha256|ripemd160)\s*\(", lowered)
        or "%" in lowered
        or "random" in lowered
        or "lottery" in lowered
    )


def _contains_loop(body: str) -> bool:
    return bool(re.search(r"\bfor\s*\(|\bwhile\s*\(", body, flags=re.IGNORECASE))


def _contains_assembly(body: str) -> bool:
    return re.search(r"\bassembly\s*\{", body, flags=re.IGNORECASE) is not None


def _contains_erc20_transfer_like(body: str) -> bool:
    lowered = body.lower()
    return ".transfer(" in lowered and "transferfrom(" not in lowered


def _contains_erc20_transfer_from_like(body: str) -> bool:
    return ".transferfrom(" in body.lower()


def _contains_erc20_approve_like(body: str) -> bool:
    return ".approve(" in body.lower()


def _contains_ecrecover(body: str) -> bool:
    return "ecrecover(" in body.lower()


def _contains_signature_nonce_guard(signature: str, body: str) -> bool:
    combined = f"{signature} {body}".lower()
    return any(
        token in combined
        for token in (
            " nonce",
            "nonces",
            "useddigest",
            "usedhash",
            "usedsig",
            "consumed",
            "replay",
            "executed[",
            "executed(",
        )
    )


def _contains_signature_expiry_guard(signature: str, body: str) -> bool:
    combined = f"{signature} {body}".lower()
    return any(
        token in combined
        for token in (
            "deadline",
            "expiry",
            "expiration",
            "validuntil",
            "expiresat",
        )
    )


def _contains_signature_domain_separator(signature: str, body: str) -> bool:
    combined = f"{signature} {body}".lower()
    return any(
        token in combined
        for token in (
            "domain_separator",
            "domainseparator",
            "eip712",
            "_hashTypedDataV4".lower(),
            "hashTypedDataV4".lower(),
            "verifyingcontract",
            "block.chainid",
            "chainid",
            "address(this)",
        )
    )


def _looks_permit_or_authorized_signature(name: str, signature: str, body: str) -> bool:
    combined = f"{name} {signature} {body}".lower()
    return any(
        token in combined
        for token in (
            "permit",
            "authorization",
            "authorize",
            "signature",
            "signed",
            "execute",
            "meta",
            "eip712",
        )
    )


def _contains_oracle_read(body: str) -> bool:
    lowered = body.lower()
    return any(
        token in lowered
        for token in (
            ".latestrounddata(",
            ".getrounddata(",
            ".latestanswer(",
            ".consult(",
            ".getreserves(",
            "aggregatorv3interface",
            "pricefeed",
            "oracle.",
        )
    )


def _contains_chainlink_oracle_read(body: str) -> bool:
    lowered = body.lower()
    return any(
        token in lowered
        for token in (
            ".latestrounddata(",
            ".getrounddata(",
            ".latestanswer(",
            "aggregatorv3interface",
            "pricefeed",
        )
    )


def _has_oracle_answer_bounds_check(body: str) -> bool:
    lowered = body.lower()
    if any(token in lowered for token in ("minprice", "maxprice", "minanswer", "maxanswer")):
        return True
    value_names = set(
        re.findall(r"\b(?:int|uint)(?:8|16|32|64|96|128|160|192|224|256)?\s+([A-Za-z_][A-Za-z0-9_]*)", body)
    )
    value_names.update({"answer", "price", "value"})
    review_names = [name for name in value_names if any(token in name.lower() for token in ("answer", "price", "value"))]
    for raw_name in review_names:
        name = raw_name.lower()
        patterns = (
            rf"\b(require|assert)\s*\([^)]*\b{name}\b\s*>\s*0\b",
            rf"\b(require|assert)\s*\([^)]*0\s*<\s*\b{name}\b",
            rf"\bif\s*\([^)]*\b{name}\b\s*<=\s*0\b[^)]*\)\s*\{{?\s*revert\b",
            rf"\bif\s*\([^)]*0\s*>=\s*\b{name}\b[^)]*\)\s*\{{?\s*revert\b",
        )
        if any(re.search(pattern, lowered) for pattern in patterns):
            return True
    return False


def _contains_oracle_price_math(body: str) -> bool:
    lowered = body.lower()
    price_names = ("price", "answer", "rate", "quote")
    return any(
        re.search(rf"\b{name}\b[^;\n]*[*\/]", lowered) or re.search(rf"[*\/][^;\n]*\b{name}\b", lowered)
        for name in price_names
    )


def _has_oracle_scaling_context(body: str) -> bool:
    lowered = body.lower()
    return any(
        token in lowered
        for token in (
            ".decimals(",
            "decimals()",
            "priceprecision",
            "price_precision",
            "price scale",
            "pricescale",
            "oracle_scale",
            "oraclescale",
            "scale",
            "1e8",
            "1e18",
            "10 **",
            "10**",
            "wad",
            "ray",
        )
    )


def _has_token_balance_delta_check(body: str) -> bool:
    lowered = body.lower()
    if ".balanceof(address(this))" in lowered or ".balanceof(this)" in lowered:
        return True
    return any(
        token in lowered
        for token in (
            "balancebefore",
            "balance_before",
            "beforebalance",
            "before_balance",
            "balanceafter",
            "balance_after",
            "afterbalance",
            "after_balance",
            "actualreceived",
            "actual_received",
            "receivedamount",
            "received_amount",
            "amountreceived",
            "amount_received",
        )
    )


def _contains_reserve_dependency(body: str) -> bool:
    lowered = body.lower()
    return any(
        token in lowered
        for token in (
            ".getreserves(",
            "getreserves(",
            "reserve0",
            "reserve1",
            "reservein",
            "reserveout",
        )
    )


def _contains_reserve_accounting_mutation(body: str) -> bool:
    return bool(
        re.search(
            r"\b(totalreserves?|protocolreserves?|accruedfees?|protocolfees?|reservefactor|surplus)\b[^;\n]*[\+\-\*\/%]?=",
            body,
            flags=re.IGNORECASE,
        )
    )


def _looks_fee_collection_function(name: str, signature: str, body: str) -> bool:
    lowered_name = name.lower()
    combined = f"{signature}\n{body}".lower()
    return any(
        token in lowered_name
        for token in (
            "collectfee",
            "collectprotocolfee",
            "skim",
            "takefee",
            "withdrawfee",
            "claimfee",
            "sweepfee",
            "accruefee",
            "harvestfee",
        )
    ) or any(
        token in combined
        for token in (
            "protocolfee",
            "protocol fee",
            "accruedfee",
            "accrued fee",
            "managementfee",
            "management fee",
            "performancefee",
            "performance fee",
            "reservefactor",
            "reserve factor",
            "treasuryfee",
            "treasury fee",
        )
    )


def _contains_reserve_buffer_logic(signature: str, body: str) -> bool:
    combined = f"{signature}\n{body}".lower()
    return any(
        token in combined
        for token in (
            "reservebuffer",
            "reserve buffer",
            "insurancefund",
            "insurance fund",
            "backstop",
            "surplusbuffer",
            "surplus buffer",
            "safetymodule",
            "safety module",
        )
    )


def _contains_reserve_accounting_logic(signature: str, body: str) -> bool:
    combined = f"{signature}\n{body}".lower()
    if _contains_reserve_accounting_mutation(body):
        return True
    return any(
        token in combined
        for token in (
            "totalreserves",
            "protocolreserves",
            "reservefactor",
            "syncreserve",
            "syncreserves",
            "updatereserve",
            "updatereserves",
            "settlereserve",
            "accruedfee",
            "protocolfee",
            "reservebuffer",
            "reserve buffer",
            "insurancefund",
            "insurance fund",
            "backstop",
        )
    )


def _looks_debt_accounting_function(name: str, signature: str, body: str) -> bool:
    lowered_name = name.lower()
    combined = f"{signature}\n{body}".lower()
    return any(
        token in lowered_name
        for token in (
            "debt",
            "borrow",
            "repay",
            "accrue",
            "writeoff",
            "baddebt",
            "liquidat",
        )
    ) or any(
        token in combined
        for token in (
            "totaldebt",
            "debtindex",
            "borrowindex",
            "baddebt",
            "accrual",
            "interestindex",
            "reservefactor",
        )
    )


def _has_oracle_freshness_check(body: str) -> bool:
    lowered = body.lower()
    return any(
        token in lowered
        for token in (
            "updatedat",
            "answeredinround",
            "heartbeat",
            "stale",
            "maxdelay",
            "maxage",
            "roundid",
        )
    )


def _has_chainlink_round_completeness_check(body: str) -> bool:
    lowered = body.lower()
    if not (".latestrounddata(" in lowered or ".getrounddata(" in lowered):
        return True
    has_updated_at = "updatedat" in lowered or "updated_at" in lowered
    has_round_identity = "answeredinround" in lowered and "roundid" in lowered
    has_round_comparison = bool(
        re.search(r"\bansweredinround\b[^;\n]*(?:>=|==|>|<)\s*\broundid\b", lowered)
        or re.search(r"\broundid\b[^;\n]*(?:<=|==|<|>)\s*\bansweredinround\b", lowered)
    )
    return has_updated_at and has_round_identity and has_round_comparison


def _has_reserve_window_check(body: str) -> bool:
    lowered = body.lower()
    return any(
        token in lowered
        for token in (
            "twap",
            "consult(",
            "observation",
            "cumulative",
            "average",
            "window",
            "period",
            "secondsago",
            "updatedat",
            "lasttimestamp",
        )
    )


def _has_reserve_sync_validation(signature: str, body: str) -> bool:
    combined = f"{signature}\n{body}".lower()
    return _contains_reserve_accounting_mutation(body) or any(
        token in combined
        for token in (
            "_syncreserve(",
            "_syncreserves(",
            "syncreserve(",
            "syncreserves(",
            "_updatereserve(",
            "_updatereserves(",
            "updatereserve(",
            "updatereserves(",
            "settlereserve(",
            "settlebaddebt(",
        )
    )


def _contains_collateral_logic(signature: str, body: str) -> bool:
    combined = f"{signature}\n{body}".lower()
    return any(
        token in combined
        for token in (
            "collateral",
            "borrow",
            "repay",
            "debt",
            "liquidat",
            "healthfactor",
            "health factor",
            "ltv",
            "loan to value",
            "liquidationthreshold",
            "closefactor",
            "position",
        )
    )


def _looks_collateral_management_function(name: str, signature: str, body: str) -> bool:
    lowered_name = name.lower()
    if any(
        token in lowered_name
        for token in (
            "collateral",
            "borrow",
            "repay",
            "margin",
            "position",
            "healthfactor",
            "healthcheck",
        )
    ):
        return True
    return _contains_collateral_logic(signature, body) and _looks_state_change(body)


def _looks_liquidation_function(name: str, signature: str, body: str) -> bool:
    lowered_name = name.lower()
    combined = f"{signature}\n{body}".lower()
    return any(token in lowered_name for token in ("liquidat", "auction", "seize")) or (
        "liquidat" in combined and _looks_state_change(body)
    )


def _contains_liquidation_fee_logic(signature: str, body: str) -> bool:
    combined = f"{signature}\n{body}".lower()
    if not any(token in combined for token in ("liquidat", "auction", "seize")):
        return False
    return any(
        token in combined
        for token in (
            "liquidationbonus",
            "liquidation bonus",
            "liquidationfee",
            "liquidation fee",
            "bonusbps",
            "bonus bps",
            "keeperfee",
            "keeper fee",
            "penalty",
            "seizebonus",
            "closefactor",
            "liquidatorreward",
            "liquidator reward",
        )
    )


def _requires_collateral_ratio_check(name: str, signature: str, body: str) -> bool:
    lowered_name = name.lower()
    lowered_signature = signature.lower()
    if _looks_liquidation_function(name, signature, body):
        return True
    if " view" in lowered_signature or " pure" in lowered_signature:
        return False
    return any(
        token in lowered_name
        for token in (
            "borrow",
            "repay",
            "withdrawcollateral",
            "draw",
            "mintdebt",
            "burndebt",
            "openposition",
            "closeposition",
        )
    ) or (_contains_collateral_logic(signature, body) and _looks_state_change(body))


def _has_collateral_ratio_validation(signature: str, body: str) -> bool:
    combined = f"{signature}\n{body}".lower()
    validation_tokens = (
        "healthfactor",
        "health factor",
        "collateralratio",
        "collateral ratio",
        "ltv",
        "loan to value",
        "liquidationthreshold",
        "liquidation threshold",
        "maxltv",
        "borrowlimit",
        "borrow limit",
        "closefactor",
        "close factor",
        "ishealthy",
        "canliquidate",
    )
    return any(token in combined for token in validation_tokens) and bool(
        re.search(r"\b(require|assert)\s*\(", combined)
        or re.search(r"\bif\s*\(", combined)
    )


def _has_liquidation_fee_validation(signature: str, body: str) -> bool:
    combined = f"{signature}\n{body}".lower()
    validation_tokens = (
        "bonusbps",
        "bonus bps",
        "maxbonus",
        "max bonus",
        "maxliquidationbonus",
        "liquidationfeecap",
        "fee cap",
        "closefactor",
        "close factor",
        "keeperfee",
        "keeper fee",
        "liquidatorreward",
        "liquidator reward",
        "reservebuffer",
        "insurancefund",
    )
    return any(
        re.search(
            rf"\b(require|assert|if)\s*\([^)]*\b{re.escape(token)}\b",
            combined,
        )
        for token in validation_tokens
    )


def _has_debt_state_validation(signature: str, body: str) -> bool:
    combined = f"{signature}\n{body}".lower()
    validation_tokens = (
        "healthfactor",
        "health factor",
        "collateralratio",
        "collateral ratio",
        "baddebt",
        "bad debt",
        "insolvent",
        "liquidationthreshold",
        "reservefactor",
        "reserve factor",
        "debtceiling",
        "debt ceiling",
        "borrowlimit",
        "borrow limit",
        "maxborrow",
        "closefactor",
        "close factor",
    )
    return any(token in combined for token in validation_tokens) and bool(
        re.search(r"\b(require|assert)\s*\(", combined)
        or re.search(r"\bif\s*\(", combined)
    )


def _contains_bad_debt_socialization_logic(signature: str, body: str) -> bool:
    combined = f"{signature}\n{body}".lower()
    debt_tokens = (
        "baddebt",
        "bad debt",
        "writeoff",
        "write off",
        "deficit",
        "insolvent",
        "absorbdebt",
        "absorb debt",
    )
    socialization_tokens = (
        "socialize",
        "socialized",
        "reservebuffer",
        "reserve buffer",
        "insurancefund",
        "insurance fund",
        "backstop",
        "surplusbuffer",
        "surplus buffer",
        "coverdeficit",
        "cover deficit",
    )
    return any(token in combined for token in debt_tokens) and any(token in combined for token in socialization_tokens)


def _has_bad_debt_socialization_validation(signature: str, body: str) -> bool:
    combined = f"{signature}\n{body}".lower()
    validation_tokens = (
        "baddebt",
        "bad debt",
        "deficit",
        "reservebuffer",
        "reserve buffer",
        "insurancefund",
        "insurance fund",
        "backstop",
        "surplusbuffer",
        "surplus buffer",
        "coverage",
        "maxwriteoff",
        "writeoffcap",
        "socializationcap",
    )
    return any(
        re.search(
            rf"\b(require|assert|if)\s*\([^)]*\b{re.escape(token)}\b",
            combined,
        )
        for token in validation_tokens
    )


def _address_parameter_names(signature: str) -> list[str]:
    return re.findall(
        r"\baddress(?:\s+payable)?\s+([A-Za-z_][A-Za-z0-9_]*)\b",
        signature,
        flags=re.IGNORECASE,
    )


def _contains_parameter_target_low_level_call(signature: str, body: str) -> bool:
    for name in _address_parameter_names(signature):
        if re.search(rf"\b{name}\s*\.\s*(call|staticcall|delegatecall)\b", body):
            return True
    return False


def _contains_parameter_target_delegatecall(signature: str, body: str) -> bool:
    for name in _address_parameter_names(signature):
        if re.search(rf"\b{name}\s*\.\s*delegatecall\b", body):
            return True
    return False


def _contains_parameter_transfer_from(signature: str, body: str) -> bool:
    for name in _address_parameter_names(signature):
        if re.search(rf"\.transferFrom\s*\(\s*{name}\b", body, flags=re.IGNORECASE):
            return True
    return False


def _has_zero_address_validation(param_name: str, body: str) -> bool:
    patterns = (
        rf"\b{param_name}\b\s*!=\s*address\s*\(\s*0\s*\)",
        rf"\b{param_name}\b\s*==\s*address\s*\(\s*0\s*\)",
        rf"address\s*\(\s*0\s*\)\s*!=\s*\b{param_name}\b",
        rf"address\s*\(\s*0\s*\)\s*==\s*\b{param_name}\b",
    )
    return any(re.search(pattern, body, flags=re.IGNORECASE) for pattern in patterns)


def _has_contract_code_validation(param_name: str, body: str) -> bool:
    patterns = (
        rf"\b{param_name}\b\s*\.\s*code\s*\.\s*length",
        rf"\bextcodesize\s*\(\s*{param_name}\s*\)",
        rf"\bisContract\s*\(\s*{param_name}\s*\)",
    )
    return any(re.search(pattern, body, flags=re.IGNORECASE) for pattern in patterns)


def _checks_external_call_result(body: str) -> bool:
    lowered = body.lower()
    if not _contains_low_level_call(body):
        return False
    if ".transfer(" in lowered:
        return True
    if re.search(r"\brequire\s*\([^)]*(?:\.call|\.delegatecall|\.staticcall|send\s*\()", lowered):
        return True

    bool_names = set(
        re.findall(r"\(\s*bool\s+([A-Za-z_][A-Za-z0-9_]*)\s*,?", body)
        + re.findall(r"\bbool\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*[^;]*(?:\.call|\.delegatecall|\.staticcall|send\s*\()", body)
    )
    for name in bool_names:
        if re.search(rf"\b(require|assert)\s*\([^)]*\b{name}\b", body):
            return True
        if re.search(rf"\bif\s*\(\s*!?\s*{name}\s*\)", body):
            return True
    return False


def _checks_token_call_result(body: str) -> bool:
    lowered = body.lower()
    if not (
        _contains_erc20_transfer_like(body)
        or _contains_erc20_transfer_from_like(body)
        or _contains_erc20_approve_like(body)
    ):
        return False
    if re.search(r"\brequire\s*\([^)]*\.transfer(?:from)?\s*\(", lowered):
        return True
    if re.search(r"\brequire\s*\([^)]*\.approve\s*\(", lowered):
        return True
    bool_names = set(
        re.findall(r"\(\s*bool\s+([A-Za-z_][A-Za-z0-9_]*)\s*,?", body)
        + re.findall(r"\bbool\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*[^;]*\.transfer(?:from)?\s*\(", body)
        + re.findall(r"\bbool\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*[^;]*\.approve\s*\(", body)
    )
    for name in bool_names:
        if re.search(rf"\b(require|assert)\s*\([^)]*\b{name}\b", body):
            return True
        if re.search(rf"\bif\s*\(\s*!?\s*{name}\s*\)", body):
            return True
    return False


def _looks_state_change(body: str) -> bool:
    return bool(
        re.search(r"(?<![=!<>])=(?!=)", body)
        or re.search(r"\+\+|--|\+=|-=|\*=|/=|%=|\bdelete\b", body)
    )


def _contains_asset_movement(body: str) -> bool:
    return any(
        check(body)
        for check in (
            _contains_low_level_call,
            _contains_call_with_value,
            _contains_erc20_transfer_like,
            _contains_erc20_transfer_from_like,
        )
    )


def _contains_state_transition(body: str) -> bool:
    return bool(re.search(r"\b(state|status|phase|stage)\b\s*[\+\-\*\/%]?=", body, flags=re.IGNORECASE))


def _contains_accounting_mutation(body: str) -> bool:
    return bool(
        re.search(
            r"\b(balances?|allowances?|shares?|assets?|claims?|claimable|claimed|reserves?|debt|debts|credits?|payouts?|withdrawals?)\b[^;\n]*[\+\-\*\/%]?=",
            body,
            flags=re.IGNORECASE,
        )
        or re.search(
            r"\b(totalSupply|totalsupply|totalAssets|totalassets|totalDebt|totaldebt|totalClaims|totalclaims)\b\s*[\+\-\*\/%]?=",
            body,
            flags=re.IGNORECASE,
        )
    )


def _contains_share_accounting_mutation(body: str) -> bool:
    lowered = body.lower()
    return bool(
        re.search(r"\bshares?\b[^;\n]*[\+\-\*\/%]?=", body, flags=re.IGNORECASE)
        or re.search(r"\btotalSupply\b\s*[\+\-\*\/%]?=", body, flags=re.IGNORECASE)
        or "_mint(" in lowered
        or "_burn(" in lowered
    )


def _contains_vault_conversion_logic(signature: str, body: str) -> bool:
    combined = f"{signature}\n{body}".lower()
    return any(
        token in combined
        for token in (
            "previewdeposit",
            "previewmint",
            "previewwithdraw",
            "previewredeem",
            "converttoshares",
            "converttoassets",
            "totalassets",
            "pricepershare",
            "assetspershare",
            "exchangerate",
            "shareprice",
        )
    )


def _contains_storage_slot_write(body: str) -> bool:
    return bool(
        re.search(r"\bsstore\s*\(", body, flags=re.IGNORECASE)
        or re.search(
            r"\bStorageSlot(?:Upgradeable)?\s*\.\s*get[A-Za-z0-9_]+Slot\s*\([^)]*\)\s*\.\s*value\s*=",
            body,
            flags=re.IGNORECASE,
        )
        or re.search(r"\bERC1967Utils\s*\.\s*upgradeTo(?:AndCall)?\s*\(", body, flags=re.IGNORECASE)
    )


def _contains_implementation_reference(text: str) -> bool:
    lowered = text.lower()
    return any(
        token in lowered
        for token in (
            "implementation",
            "_implementation",
            "beacon",
            "_beacon",
            "_implementation_slot",
            "_admin_slot",
            "_beacon_slot",
        )
    )


def _contains_implementation_slot_constant(text: str) -> bool:
    lowered = text.lower()
    return any(
        token in lowered
        for token in (
            "_implementation_slot",
            "_admin_slot",
            "_beacon_slot",
            "eip1967",
            "erc1967",
            "storageslot",
            "storageslotupgradeable",
        )
    )


def _contains_storage_gap(text: str) -> bool:
    return re.search(r"\b__gap\b", text, flags=re.IGNORECASE) is not None


def _looks_immediate_upgrade_execution_path(item: ContractFunction) -> bool:
    lowered_name = item.name.lower()
    if any(token in lowered_name for token in ("queue", "schedule", "propose", "request", "commit")):
        return False
    combined = f"{item.signature}\n{item.body}"
    if not _looks_upgrade_function(item.name):
        return False
    return _looks_state_change(item.body) and (
        _contains_implementation_reference(combined)
        or _contains_storage_slot_write(item.body)
        or _contains_delegatecall(item.body)
        or re.search(r"\b(?:implementation|beacon|logic)\b\s*=", item.body, flags=re.IGNORECASE) is not None
    )


def _has_upgrade_delay_or_governance_control(signature: str, body: str, modifiers: list[str]) -> bool:
    combined = f"{signature}\n{body}\n{' '.join(modifiers)}".lower()
    return any(
        token in combined
        for token in (
            "timelock",
            "time_lock",
            "delay",
            "eta",
            "queued",
            "queue",
            "schedule",
            "proposal",
            "governance",
            "governor",
            "multisig",
            "safe",
            "onlytimelock",
            "onlygovernance",
            "onlygovernor",
        )
    )


def _has_explicit_role_guard(modifiers: list[str], body: str) -> bool:
    if any(
        token.lower().startswith(("onlyrole", "role", "guardian", "operator", "manager"))
        for token in modifiers
    ):
        return True
    lowered = body.lower()
    return bool(
        re.search(r"\b(_checkrole|hasrole|onlyrole)\s*\(", lowered)
        or re.search(r"\b(require|assert|if)\s*\([^)]*\b(isoperator|isguardian|ismanager|operators\s*\[|guardians\s*\[|managers\s*\[)", lowered)
    )


def _amount_parameter_names(signature: str) -> list[str]:
    return re.findall(
        r"\b(?:uint|int)(?:8|16|32|64|96|128|160|192|224|256)?\s+([A-Za-z_][A-Za-z0-9_]*)\b",
        signature,
        flags=re.IGNORECASE,
    )


def _contains_balance_or_allowance_check(signature: str, body: str) -> bool:
    amount_params = [
        name
        for name in _amount_parameter_names(signature)
        if any(token in name.lower() for token in ("amount", "value", "share", "asset", "claim", "quantity"))
    ]
    accounting_tokens = (
        "balance",
        "balances",
        "allowance",
        "allowances",
        "share",
        "shares",
        "asset",
        "assets",
        "claimable",
        "available",
        "reserve",
        "debt",
    )
    for param_name in amount_params:
        for token in accounting_tokens:
            patterns = (
                rf"\b(require|assert)\s*\([^)]*\b{param_name}\b\s*(?:<=|<)\s*[^)]*\b{token}\b",
                rf"\b(require|assert)\s*\([^)]*\b{token}\b[^)]*(?:>=|>)\s*[^)]*\b{param_name}\b",
                rf"\bif\s*\([^)]*\b{param_name}\b\s*(?:<=|<)\s*[^)]*\b{token}\b[^)]*\)\s*\{{?\s*revert\b",
                rf"\bif\s*\([^)]*\b{token}\b[^)]*(?:>=|>)\s*[^)]*\b{param_name}\b[^)]*\)\s*\{{?\s*revert\b",
            )
            if any(re.search(pattern, body, flags=re.IGNORECASE) for pattern in patterns):
                return True
    return False


def _contains_state_transition_after_external_call(body: str) -> bool:
    lowered = body.lower()
    call_indexes = [
        lowered.find(token)
        for token in (
            ".call(",
            ".call{",
            ".delegatecall(",
            ".delegatecall{",
            ".staticcall(",
            ".staticcall{",
            "send(",
            "transfer(",
        )
        if lowered.find(token) != -1
    ]
    if not call_indexes:
        return False
    trailing = body[min(call_indexes) :]
    return _contains_state_transition(trailing)


def _contains_accounting_update_after_external_call(body: str) -> bool:
    lowered = body.lower()
    call_indexes = [
        lowered.find(token)
        for token in (
            ".call(",
            ".call{",
            ".delegatecall(",
            ".delegatecall{",
            ".staticcall(",
            ".staticcall{",
            "send(",
            "transfer(",
            "transferfrom(",
        )
        if lowered.find(token) != -1
    ]
    if not call_indexes:
        return False
    trailing = body[min(call_indexes) :]
    return _contains_accounting_mutation(trailing)


def _looks_reentrancy_review(body: str) -> bool:
    lowered = body.lower()
    if not _contains_low_level_call(body):
        return False
    external_call_index = min(
        (
            lowered.find(token)
            for token in (
                ".call(",
                ".call{",
                ".delegatecall(",
                ".delegatecall{",
                ".staticcall(",
                ".staticcall{",
                "send(",
                "transfer(",
            )
            if lowered.find(token) != -1
        ),
        default=-1,
    )
    if external_call_index == -1:
        return False
    trailing = lowered[external_call_index:]
    return bool(
        re.search(r"\b(balance|balances|owner|amount|total|supply|status|locked|mapping)\b", trailing)
        or re.search(r"\b[a-zA-Z_][a-zA-Z0-9_]*\s*[\+\-\*\/%]?=", trailing)
    )


def _looks_withdraw_like_function(name: str) -> bool:
    lowered = name.lower()
    return any(
        token in lowered
        for token in ("withdraw", "redeem", "claim", "collect", "payout", "distribute", "sweep")
    )


def _looks_deposit_like_function(name: str, body: str) -> bool:
    lowered_name = name.lower()
    lowered_body = body.lower()
    return any(token in lowered_name for token in ("deposit", "stake", "supply", "fund")) or (
        "msg.value" in lowered_body and _contains_accounting_mutation(body)
    )


def _looks_asset_exit_function(name: str, body: str) -> bool:
    lowered_name = name.lower()
    return any(
        token in lowered_name
        for token in ("withdraw", "claim", "redeem", "collect", "payout", "rescue", "sweep", "unstake")
    ) and any(
        check(body)
        for check in (
            _contains_low_level_call,
            _contains_call_with_value,
            _contains_erc20_transfer_like,
            _contains_erc20_transfer_from_like,
        )
    )


def _looks_rescue_or_sweep_function(name: str) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in ("rescue", "sweep", "recover", "skim"))


def _references_assets_and_shares(signature: str, body: str) -> bool:
    combined = f"{signature}\n{body}".lower()
    has_assets = any(token in combined for token in ("asset", "assets", "totalassets"))
    has_shares = any(token in combined for token in ("share", "shares", "totalsupply", "_mint(", "_burn("))
    return has_assets and has_shares


def _looks_vault_entry_or_mint_function(name: str, signature: str, body: str) -> bool:
    lowered_name = name.lower()
    combined = f"{signature}\n{body}".lower()
    if not any(token in lowered_name for token in ("deposit", "mint")):
        return False
    return any(token in combined for token in ("share", "shares", "asset", "assets", "_mint(", "totalassets"))


def _looks_vault_exit_or_redeem_function(name: str, signature: str, body: str) -> bool:
    lowered_name = name.lower()
    combined = f"{signature}\n{body}".lower()
    if not any(token in lowered_name for token in ("withdraw", "redeem", "burn")):
        return False
    return any(token in combined for token in ("share", "shares", "asset", "assets", "_burn(", "totalassets"))


def _looks_vault_conversion_sensitive_function(name: str, signature: str, body: str) -> bool:
    lowered_name = name.lower()
    combined = f"{signature}\n{body}".lower()
    if any(
        token in lowered_name
        for token in ("previewdeposit", "previewmint", "previewwithdraw", "previewredeem", "converttoshares", "converttoassets")
    ):
        return True
    return any(token in lowered_name for token in ("deposit", "mint", "withdraw", "redeem")) and any(
        token in combined for token in ("asset", "assets", "share", "shares", "totalassets")
    )


def _looks_sensitive_authority_function(name: str, body: str) -> bool:
    lowered_name = name.lower()
    lowered_body = body.lower()
    if any(
        token in lowered_name
        for token in (
            "setowner",
            "setadmin",
            "setoperator",
            "setguardian",
            "grantrole",
            "revokerole",
            "pause",
            "unpause",
            "mint",
            "burn",
            "upgrade",
            "skim",
            "collectfee",
            "setreservefactor",
            "writeoff",
        )
    ):
        return True
    return any(
        token in lowered_body
        for token in (
            "owner =",
            "admin =",
            "operator =",
            "guardian =",
            "_grantrole(",
            "_revokerole(",
            "_setroleadmin(",
            "_pause(",
            "_unpause(",
            "_mint(",
            "_burn(",
            "protocolfee",
            "reservefactor",
            "baddebt",
        )
    )


def _ordered_unique(items: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output


def _contract_priority_rank(priority: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(priority, 3)
