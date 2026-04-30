from __future__ import annotations

from app.models import ResearchTarget, ResearchTargetProfile, SyntheticResearchTarget


class ResearchTargetRegistry:
    """Controlled registry of bounded research target profiles."""

    def __init__(self) -> None:
        self._profiles: dict[str, ResearchTargetProfile] = {
            "curve": ResearchTargetProfile(
                profile_name="named_curve_target",
                target_kind="curve",
                description="Named or aliased elliptic-curve metadata target.",
                allowed_tool_names=[
                    "curve_metadata_tool",
                    "ecc_curve_parameter_tool",
                    "ecc_consistency_check_tool",
                    "ecc_testbed_tool",
                    "fuzz_mutation_tool",
                ],
                max_reference_length=64,
                notes=[
                    "Curve targets stay metadata-oriented unless a later bounded check explicitly upgrades the path.",
                ],
            ),
            "point": ResearchTargetProfile(
                profile_name="ecc_point_input_target",
                target_kind="point",
                description="Point-like or public-key-like ECC input.",
                allowed_tool_names=[
                    "point_descriptor_tool",
                    "ecc_point_format_tool",
                    "ecc_consistency_check_tool",
                    "fuzz_mutation_tool",
                    "ecc_testbed_tool",
                ],
                max_reference_length=192,
            ),
            "ecc_consistency": ResearchTargetProfile(
                profile_name="ecc_consistency_target",
                target_kind="ecc_consistency",
                description="Bounded ECC format or on-curve consistency target.",
                allowed_tool_names=[
                    "point_descriptor_tool",
                    "ecc_point_format_tool",
                    "ecc_consistency_check_tool",
                    "fuzz_mutation_tool",
                    "ecc_testbed_tool",
                ],
                max_reference_length=192,
            ),
            "symbolic": ResearchTargetProfile(
                profile_name="symbolic_expression_target",
                target_kind="symbolic",
                description="Bounded symbolic expression or equation target.",
                allowed_tool_names=[
                    "symbolic_check_tool",
                    "sage_symbolic_tool",
                    "property_invariant_tool",
                    "formal_constraint_tool",
                ],
                max_reference_length=256,
            ),
            "testbed": ResearchTargetProfile(
                profile_name="ecc_testbed_target",
                target_kind="testbed",
                description="Built-in bounded ECC testbed or anomaly corpus target.",
                allowed_tool_names=[
                    "ecc_testbed_tool",
                ],
                max_reference_length=64,
            ),
            "finite_field": ResearchTargetProfile(
                profile_name="finite_field_relation_target",
                target_kind="finite_field",
                description="Bounded modular arithmetic or finite-field relation.",
                allowed_tool_names=[
                    "finite_field_check_tool",
                ],
                max_reference_length=128,
            ),
            "experiment": ResearchTargetProfile(
                profile_name="deterministic_probe_target",
                target_kind="experiment",
                description="Repeatability or normalization probe for bounded local experiments.",
                allowed_tool_names=[
                    "deterministic_experiment_tool",
                ],
                max_reference_length=128,
            ),
            "smart_contract": ResearchTargetProfile(
                profile_name="smart_contract_audit_target",
                target_kind="smart_contract",
                description="Bounded local smart-contract audit target based on pasted code or a local source file.",
                allowed_tool_names=[
                    "contract_inventory_tool",
                    "contract_compile_tool",
                    "slither_audit_tool",
                    "echidna_audit_tool",
                    "foundry_audit_tool",
                    "contract_parser_tool",
                    "contract_surface_tool",
                    "contract_pattern_check_tool",
                    "contract_testbed_tool",
                ],
                max_reference_length=128,
                notes=[
                    "Smart-contract targets remain static-analysis-oriented in the first MVP path.",
                ],
            ),
            "smart_contract_testbed": ResearchTargetProfile(
                profile_name="smart_contract_testbed_target",
                target_kind="smart_contract_testbed",
                description="Built-in scoped smart-contract review corpus target.",
                allowed_tool_names=[
                    "contract_testbed_tool",
                ],
                max_reference_length=64,
                notes=[
                    "Smart-contract testbeds stay local and corpus-based in the current path.",
                ],
            ),
            "generic": ResearchTargetProfile(
                profile_name="generic_seed_target",
                target_kind="generic",
                description="Fallback descriptive seed-level target when a more specific target cannot be inferred.",
                allowed_tool_names=[
                    "placeholder_math_tool",
                ],
                max_reference_length=256,
            ),
        }
        self._synthetic_targets: dict[str, SyntheticResearchTarget] = {
            "toy_curve_secp256k1": SyntheticResearchTarget(
                target_name="toy_curve_secp256k1",
                description="Named-curve metadata target for secp256k1.",
                research_target=ResearchTarget(
                    target_kind="curve",
                    target_reference="secp256k1",
                    target_origin="synthetic",
                    synthetic_target_name="toy_curve_secp256k1",
                    curve_name="secp256k1",
                    notes=[
                        "Built-in toy curve target for bounded metadata and registry checks.",
                    ],
                ),
            ),
            "toy_secp256k1_generator_compressed": SyntheticResearchTarget(
                target_name="toy_secp256k1_generator_compressed",
                description="Compressed generator-style secp256k1 public-key target.",
                research_target=ResearchTarget(
                    target_kind="ecc_consistency",
                    target_reference="0279BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798",
                    target_origin="synthetic",
                    synthetic_target_name="toy_secp256k1_generator_compressed",
                    curve_name="secp256k1",
                    notes=[
                        "Built-in toy ECC consistency target based on a common compressed generator representation.",
                    ],
                ),
            ),
            "toy_secp256r1_generator_uncompressed": SyntheticResearchTarget(
                target_name="toy_secp256r1_generator_uncompressed",
                description="Uncompressed generator-style P-256 public-key target.",
                research_target=ResearchTarget(
                    target_kind="point",
                    target_reference=(
                        "046B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296"
                        "4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5"
                    ),
                    target_origin="synthetic",
                    synthetic_target_name="toy_secp256r1_generator_uncompressed",
                    curve_name="secp256r1",
                    notes=[
                        "Built-in toy ECC point-format target for P-256 style uncompressed parsing checks.",
                    ],
                ),
            ),
            "toy_secp256k1_bad_prefix_compressed": SyntheticResearchTarget(
                target_name="toy_secp256k1_bad_prefix_compressed",
                description="Malformed compressed-style secp256k1 public-key target with an invalid prefix byte.",
                research_target=ResearchTarget(
                    target_kind="ecc_consistency",
                    target_reference="0579BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798",
                    target_origin="synthetic",
                    synthetic_target_name="toy_secp256k1_bad_prefix_compressed",
                    curve_name="secp256k1",
                    notes=[
                        "Built-in malformed ECC consistency target for bounded prefix and format anomaly research.",
                    ],
                ),
            ),
            "toy_coordinate_length_mismatch": SyntheticResearchTarget(
                target_name="toy_coordinate_length_mismatch",
                description="Coordinate-style secp256k1 target with intentionally mismatched x/y lengths.",
                research_target=ResearchTarget(
                    target_kind="ecc_consistency",
                    target_reference=(
                        "x=79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798, "
                        "y=483ADA7726A3C4655DA4FBFC0E1108A8"
                    ),
                    target_origin="synthetic",
                    synthetic_target_name="toy_coordinate_length_mismatch",
                    curve_name="secp256k1",
                    notes=[
                        "Built-in coordinate-shape anomaly target for bounded x/y length mismatch research.",
                    ],
                ),
            ),
            "toy_curve_alias_p256": SyntheticResearchTarget(
                target_name="toy_curve_alias_p256",
                description="Named-curve metadata target using the P-256 alias form.",
                research_target=ResearchTarget(
                    target_kind="curve",
                    target_reference="P-256",
                    target_origin="synthetic",
                    synthetic_target_name="toy_curve_alias_p256",
                    curve_name="P-256",
                    notes=[
                        "Built-in alias-focused curve metadata target for bounded registry and domain normalization checks.",
                    ],
                ),
            ),
            "toy_symbolic_balance": SyntheticResearchTarget(
                target_name="toy_symbolic_balance",
                description="Symbolic equivalence target for bounded normalization checks.",
                research_target=ResearchTarget(
                    target_kind="symbolic",
                    target_reference="x + y - y = x",
                    target_origin="synthetic",
                    synthetic_target_name="toy_symbolic_balance",
                    notes=[
                        "Built-in toy symbolic target for deterministic normalization experiments.",
                    ],
                ),
            ),
            "toy_modular_equivalence": SyntheticResearchTarget(
                target_name="toy_modular_equivalence",
                description="Finite-field style modular equivalence target.",
                research_target=ResearchTarget(
                    target_kind="finite_field",
                    target_reference="left=10, right=3, modulus=7",
                    target_origin="synthetic",
                    synthetic_target_name="toy_modular_equivalence",
                    notes=[
                        "Built-in toy modular target for bounded finite-field consistency checks.",
                    ],
                ),
            ),
            "toy_point_anomaly_testbed": SyntheticResearchTarget(
                target_name="toy_point_anomaly_testbed",
                description="Built-in bounded ECC point anomaly corpus.",
                research_target=ResearchTarget(
                    target_kind="testbed",
                    target_reference="point_anomaly_corpus",
                    target_origin="synthetic",
                    synthetic_target_name="toy_point_anomaly_testbed",
                    notes=[
                        "Built-in ECC point anomaly corpus for bounded local testbed sweeps.",
                    ],
                ),
            ),
            "toy_curve_alias_testbed": SyntheticResearchTarget(
                target_name="toy_curve_alias_testbed",
                description="Built-in bounded curve alias corpus.",
                research_target=ResearchTarget(
                    target_kind="testbed",
                    target_reference="curve_alias_corpus",
                    target_origin="synthetic",
                    synthetic_target_name="toy_curve_alias_testbed",
                    notes=[
                        "Built-in curve alias corpus for bounded local testbed sweeps.",
                    ],
                ),
            ),
            "toy_curve_encoding_edge_testbed": SyntheticResearchTarget(
                target_name="toy_curve_encoding_edge_testbed",
                description="Built-in bounded ECC encoding-edge corpus.",
                research_target=ResearchTarget(
                    target_kind="testbed",
                    target_reference="encoding_edge_corpus",
                    target_origin="synthetic",
                    synthetic_target_name="toy_curve_encoding_edge_testbed",
                    notes=[
                        "Built-in encoding-edge corpus for bounded compressed, uncompressed, and family-limited ECC parsing sweeps.",
                    ],
                ),
            ),
            "toy_coordinate_shape_testbed": SyntheticResearchTarget(
                target_name="toy_coordinate_shape_testbed",
                description="Built-in bounded coordinate-shape anomaly corpus.",
                research_target=ResearchTarget(
                    target_kind="testbed",
                    target_reference="coordinate_shape_corpus",
                    target_origin="synthetic",
                    synthetic_target_name="toy_coordinate_shape_testbed",
                    notes=[
                        "Built-in coordinate-shape corpus for bounded local ECC testbed sweeps.",
                    ],
                ),
            ),
            "toy_curve_subgroup_cofactor_testbed": SyntheticResearchTarget(
                target_name="toy_curve_subgroup_cofactor_testbed",
                description="Built-in bounded subgroup/cofactor ECC review corpus.",
                research_target=ResearchTarget(
                    target_kind="testbed",
                    target_reference="subgroup_cofactor_corpus",
                    target_origin="synthetic",
                    synthetic_target_name="toy_curve_subgroup_cofactor_testbed",
                    notes=[
                        "Built-in subgroup/cofactor corpus for bounded curve-family, cofactor, and twist-hygiene review.",
                    ],
                ),
            ),
            "toy_curve_domain_testbed": SyntheticResearchTarget(
                target_name="toy_curve_domain_testbed",
                description="Built-in bounded curve-domain completeness corpus.",
                research_target=ResearchTarget(
                    target_kind="testbed",
                    target_reference="curve_domain_corpus",
                    target_origin="synthetic",
                    synthetic_target_name="toy_curve_domain_testbed",
                    notes=[
                        "Built-in curve-domain corpus for bounded registry completeness and defensive metadata sweeps.",
                    ],
                ),
            ),
            "toy_curve_family_testbed": SyntheticResearchTarget(
                target_name="toy_curve_family_testbed",
                description="Built-in bounded ECC curve-family review corpus.",
                research_target=ResearchTarget(
                    target_kind="testbed",
                    target_reference="curve_family_corpus",
                    target_origin="synthetic",
                    synthetic_target_name="toy_curve_family_testbed",
                    notes=[
                        "Built-in curve-family corpus for bounded secp, Montgomery, and Edwards handling review.",
                    ],
                ),
            ),
            "toy_contract_reentrancy_testbed": SyntheticResearchTarget(
                target_name="toy_contract_reentrancy_testbed",
                description="Built-in scoped smart-contract corpus for reentrancy-style review signals.",
                research_target=ResearchTarget(
                    target_kind="smart_contract_testbed",
                    target_reference="reentrancy_review_corpus",
                    target_origin="synthetic",
                    synthetic_target_name="toy_contract_reentrancy_testbed",
                    notes=[
                        "Built-in smart-contract corpus for bounded reentrancy-style review sweeps.",
                    ],
                ),
            ),
            "toy_contract_access_control_testbed": SyntheticResearchTarget(
                target_name="toy_contract_access_control_testbed",
                description="Built-in scoped smart-contract corpus for access-control review signals.",
                research_target=ResearchTarget(
                    target_kind="smart_contract_testbed",
                    target_reference="access_control_corpus",
                    target_origin="synthetic",
                    synthetic_target_name="toy_contract_access_control_testbed",
                    notes=[
                        "Built-in smart-contract corpus for bounded access-control sweeps.",
                    ],
                ),
            ),
            "toy_contract_asset_flow_testbed": SyntheticResearchTarget(
                target_name="toy_contract_asset_flow_testbed",
                description="Built-in scoped smart-contract corpus for deposit, withdraw, claim, rescue, and sweep flow review signals.",
                research_target=ResearchTarget(
                    target_kind="smart_contract_testbed",
                    target_reference="asset_flow_corpus",
                    target_origin="synthetic",
                    synthetic_target_name="toy_contract_asset_flow_testbed",
                    notes=[
                        "Built-in smart-contract corpus for bounded asset-flow and fund-movement review sweeps.",
                    ],
                ),
            ),
            "toy_contract_authorization_flow_testbed": SyntheticResearchTarget(
                target_name="toy_contract_authorization_flow_testbed",
                description="Built-in scoped smart-contract corpus for role-management, operator, guardian, and pause-control review signals.",
                research_target=ResearchTarget(
                    target_kind="smart_contract_testbed",
                    target_reference="authorization_flow_corpus",
                    target_origin="synthetic",
                    synthetic_target_name="toy_contract_authorization_flow_testbed",
                    notes=[
                        "Built-in smart-contract corpus for bounded authorization-flow and privileged-control sweeps.",
                    ],
                ),
            ),
            "toy_contract_dangerous_call_testbed": SyntheticResearchTarget(
                target_name="toy_contract_dangerous_call_testbed",
                description="Built-in scoped smart-contract corpus for delegatecall, tx.origin, and selfdestruct review signals.",
                research_target=ResearchTarget(
                    target_kind="smart_contract_testbed",
                    target_reference="dangerous_call_corpus",
                    target_origin="synthetic",
                    synthetic_target_name="toy_contract_dangerous_call_testbed",
                    notes=[
                        "Built-in smart-contract corpus for bounded dangerous-call review sweeps.",
                    ],
                ),
            ),
            "toy_contract_upgrade_surface_testbed": SyntheticResearchTarget(
                target_name="toy_contract_upgrade_surface_testbed",
                description="Built-in scoped smart-contract corpus for upgrade and implementation review signals.",
                research_target=ResearchTarget(
                    target_kind="smart_contract_testbed",
                    target_reference="upgrade_surface_corpus",
                    target_origin="synthetic",
                    synthetic_target_name="toy_contract_upgrade_surface_testbed",
                    notes=[
                        "Built-in smart-contract corpus for bounded upgrade-surface review sweeps.",
                    ],
                ),
            ),
            "toy_contract_proxy_storage_testbed": SyntheticResearchTarget(
                target_name="toy_contract_proxy_storage_testbed",
                description="Built-in scoped smart-contract corpus for proxy delegation, storage-slot, and storage-collision review signals.",
                research_target=ResearchTarget(
                    target_kind="smart_contract_testbed",
                    target_reference="proxy_storage_corpus",
                    target_origin="synthetic",
                    synthetic_target_name="toy_contract_proxy_storage_testbed",
                    notes=[
                        "Built-in smart-contract corpus for bounded proxy and storage-layout review sweeps.",
                    ],
                ),
            ),
            "toy_contract_time_entropy_testbed": SyntheticResearchTarget(
                target_name="toy_contract_time_entropy_testbed",
                description="Built-in scoped smart-contract corpus for timestamp and entropy review signals.",
                research_target=ResearchTarget(
                    target_kind="smart_contract_testbed",
                    target_reference="time_entropy_corpus",
                    target_origin="synthetic",
                    synthetic_target_name="toy_contract_time_entropy_testbed",
                    notes=[
                        "Built-in smart-contract corpus for bounded timestamp and entropy review sweeps.",
                    ],
                ),
            ),
            "toy_contract_upgrade_validation_testbed": SyntheticResearchTarget(
                target_name="toy_contract_upgrade_validation_testbed",
                description="Built-in scoped smart-contract corpus for zero-address and implementation validation review signals.",
                research_target=ResearchTarget(
                    target_kind="smart_contract_testbed",
                    target_reference="upgrade_validation_corpus",
                    target_origin="synthetic",
                    synthetic_target_name="toy_contract_upgrade_validation_testbed",
                    notes=[
                        "Built-in smart-contract corpus for bounded upgrade target validation sweeps.",
                    ],
                ),
            ),
            "toy_contract_token_interaction_testbed": SyntheticResearchTarget(
                target_name="toy_contract_token_interaction_testbed",
                description="Built-in scoped smart-contract corpus for ERC20 transfer and transferFrom review signals.",
                research_target=ResearchTarget(
                    target_kind="smart_contract_testbed",
                    target_reference="token_interaction_corpus",
                    target_origin="synthetic",
                    synthetic_target_name="toy_contract_token_interaction_testbed",
                    notes=[
                        "Built-in smart-contract corpus for bounded token interaction review sweeps.",
                    ],
                ),
            ),
            "toy_contract_approval_review_testbed": SyntheticResearchTarget(
                target_name="toy_contract_approval_review_testbed",
                description="Built-in scoped smart-contract corpus for ERC20 approve and allowance review signals.",
                research_target=ResearchTarget(
                    target_kind="smart_contract_testbed",
                    target_reference="approval_review_corpus",
                    target_origin="synthetic",
                    synthetic_target_name="toy_contract_approval_review_testbed",
                    notes=[
                        "Built-in smart-contract corpus for bounded approve and allowance review sweeps.",
                    ],
                ),
            ),
            "toy_contract_accounting_review_testbed": SyntheticResearchTarget(
                target_name="toy_contract_accounting_review_testbed",
                description="Built-in scoped smart-contract corpus for balance, claim-state, and withdrawal-order review signals.",
                research_target=ResearchTarget(
                    target_kind="smart_contract_testbed",
                    target_reference="accounting_review_corpus",
                    target_origin="synthetic",
                    synthetic_target_name="toy_contract_accounting_review_testbed",
                    notes=[
                        "Built-in smart-contract corpus for bounded accounting and withdrawal-order review sweeps.",
                    ],
                ),
            ),
            "toy_contract_vault_share_testbed": SyntheticResearchTarget(
                target_name="toy_contract_vault_share_testbed",
                description="Built-in scoped smart-contract corpus for vault share mint, redeem, and asset-conversion review signals.",
                research_target=ResearchTarget(
                    target_kind="smart_contract_testbed",
                    target_reference="vault_share_corpus",
                    target_origin="synthetic",
                    synthetic_target_name="toy_contract_vault_share_testbed",
                    notes=[
                        "Built-in smart-contract corpus for bounded vault-share and asset-conversion review sweeps.",
                    ],
                ),
            ),
            "toy_contract_assembly_review_testbed": SyntheticResearchTarget(
                target_name="toy_contract_assembly_review_testbed",
                description="Built-in scoped smart-contract corpus for inline assembly review signals.",
                research_target=ResearchTarget(
                    target_kind="smart_contract_testbed",
                    target_reference="assembly_review_corpus",
                    target_origin="synthetic",
                    synthetic_target_name="toy_contract_assembly_review_testbed",
                    notes=[
                        "Built-in smart-contract corpus for bounded inline assembly review sweeps.",
                    ],
                ),
            ),
            "toy_contract_state_machine_testbed": SyntheticResearchTarget(
                target_name="toy_contract_state_machine_testbed",
                description="Built-in scoped smart-contract corpus for state-transition and status-update review signals.",
                research_target=ResearchTarget(
                    target_kind="smart_contract_testbed",
                    target_reference="state_machine_corpus",
                    target_origin="synthetic",
                    synthetic_target_name="toy_contract_state_machine_testbed",
                    notes=[
                        "Built-in smart-contract corpus for bounded state-machine review sweeps.",
                    ],
                ),
            ),
            "toy_contract_signature_review_testbed": SyntheticResearchTarget(
                target_name="toy_contract_signature_review_testbed",
                description="Built-in scoped smart-contract corpus for signature validation and replay review signals.",
                research_target=ResearchTarget(
                    target_kind="smart_contract_testbed",
                    target_reference="signature_review_corpus",
                    target_origin="synthetic",
                    synthetic_target_name="toy_contract_signature_review_testbed",
                    notes=[
                        "Built-in smart-contract corpus for bounded signature-validation and replay review sweeps.",
                    ],
                ),
            ),
            "toy_contract_oracle_review_testbed": SyntheticResearchTarget(
                target_name="toy_contract_oracle_review_testbed",
                description="Built-in scoped smart-contract corpus for price-oracle freshness and dependency review signals.",
                research_target=ResearchTarget(
                    target_kind="smart_contract_testbed",
                    target_reference="oracle_review_corpus",
                    target_origin="synthetic",
                    synthetic_target_name="toy_contract_oracle_review_testbed",
                    notes=[
                        "Built-in smart-contract corpus for bounded oracle freshness and dependency review sweeps.",
                    ],
                ),
            ),
            "toy_contract_collateral_liquidation_testbed": SyntheticResearchTarget(
                target_name="toy_contract_collateral_liquidation_testbed",
                description="Built-in scoped smart-contract corpus for collateral ratio, liquidation, and reserve-derived pricing review signals.",
                research_target=ResearchTarget(
                    target_kind="smart_contract_testbed",
                    target_reference="collateral_liquidation_corpus",
                    target_origin="synthetic",
                    synthetic_target_name="toy_contract_collateral_liquidation_testbed",
                    notes=[
                        "Built-in smart-contract corpus for bounded collateral, liquidation, and reserve-dependency review sweeps.",
                    ],
                ),
            ),
            "toy_contract_reserve_fee_accounting_testbed": SyntheticResearchTarget(
                target_name="toy_contract_reserve_fee_accounting_testbed",
                description="Built-in scoped smart-contract corpus for protocol-fee, reserve-accounting, and debt-state review signals.",
                research_target=ResearchTarget(
                    target_kind="smart_contract_testbed",
                    target_reference="reserve_fee_accounting_corpus",
                    target_origin="synthetic",
                    synthetic_target_name="toy_contract_reserve_fee_accounting_testbed",
                    notes=[
                        "Built-in smart-contract corpus for bounded protocol-fee, reserve-sync, and debt-accounting review sweeps.",
                    ],
                ),
            ),
            "toy_contract_loop_payout_testbed": SyntheticResearchTarget(
                target_name="toy_contract_loop_payout_testbed",
                description="Built-in scoped smart-contract corpus for payout-loop and batch distribution review signals.",
                research_target=ResearchTarget(
                    target_kind="smart_contract_testbed",
                    target_reference="loop_payout_corpus",
                    target_origin="synthetic",
                    synthetic_target_name="toy_contract_loop_payout_testbed",
                    notes=[
                        "Built-in smart-contract corpus for bounded payout-loop and batch distribution review sweeps.",
                    ],
                ),
            ),
            "toy_contract_repo_upgrade_casebook": SyntheticResearchTarget(
                target_name="toy_contract_repo_upgrade_casebook",
                description="Built-in bounded repo-scale smart-contract casebook for proxy, upgrade, and storage review lanes.",
                research_target=ResearchTarget(
                    target_kind="smart_contract_testbed",
                    target_reference="repo_upgrade_casebook",
                    target_origin="synthetic",
                    synthetic_target_name="toy_contract_repo_upgrade_casebook",
                    notes=[
                        "Built-in repo-scale smart-contract casebook for bounded proxy and upgrade review sweeps.",
                    ],
                ),
            ),
            "toy_contract_repo_asset_flow_casebook": SyntheticResearchTarget(
                target_name="toy_contract_repo_asset_flow_casebook",
                description="Built-in bounded repo-scale smart-contract casebook for asset-flow, rescue, and vault-style review lanes.",
                research_target=ResearchTarget(
                    target_kind="smart_contract_testbed",
                    target_reference="repo_asset_flow_casebook",
                    target_origin="synthetic",
                    synthetic_target_name="toy_contract_repo_asset_flow_casebook",
                    notes=[
                        "Built-in repo-scale smart-contract casebook for bounded asset-flow and vault-style review sweeps.",
                    ],
                ),
            ),
            "toy_contract_repo_oracle_casebook": SyntheticResearchTarget(
                target_name="toy_contract_repo_oracle_casebook",
                description="Built-in bounded repo-scale smart-contract casebook for oracle, price, collateral, and liquidation review lanes.",
                research_target=ResearchTarget(
                    target_kind="smart_contract_testbed",
                    target_reference="repo_oracle_casebook",
                    target_origin="synthetic",
                    synthetic_target_name="toy_contract_repo_oracle_casebook",
                    notes=[
                        "Built-in repo-scale smart-contract casebook for bounded oracle and liquidation review sweeps.",
                    ],
                ),
            ),
            "toy_contract_repo_protocol_accounting_casebook": SyntheticResearchTarget(
                target_name="toy_contract_repo_protocol_accounting_casebook",
                description="Built-in bounded repo-scale smart-contract casebook for protocol-fee, reserve-sync, and debt-accounting review lanes.",
                research_target=ResearchTarget(
                    target_kind="smart_contract_testbed",
                    target_reference="repo_protocol_accounting_casebook",
                    target_origin="synthetic",
                    synthetic_target_name="toy_contract_repo_protocol_accounting_casebook",
                    notes=[
                        "Built-in repo-scale smart-contract casebook for bounded protocol-fee, reserve, and debt-accounting review sweeps.",
                    ],
                ),
            ),
            "toy_contract_repo_vault_permission_casebook": SyntheticResearchTarget(
                target_name="toy_contract_repo_vault_permission_casebook",
                description="Built-in bounded repo-scale smart-contract casebook for vault, permit, allowance, and share-accounting review lanes.",
                research_target=ResearchTarget(
                    target_kind="smart_contract_testbed",
                    target_reference="repo_vault_permission_casebook",
                    target_origin="synthetic",
                    synthetic_target_name="toy_contract_repo_vault_permission_casebook",
                    notes=[
                        "Built-in repo-scale smart-contract casebook for bounded vault, permit, allowance, and share-accounting review sweeps.",
                    ],
                ),
            ),
            "toy_contract_repo_governance_timelock_casebook": SyntheticResearchTarget(
                target_name="toy_contract_repo_governance_timelock_casebook",
                description="Built-in bounded repo-scale smart-contract casebook for governance, timelock, guardian, and queued-upgrade review lanes.",
                research_target=ResearchTarget(
                    target_kind="smart_contract_testbed",
                    target_reference="repo_governance_timelock_casebook",
                    target_origin="synthetic",
                    synthetic_target_name="toy_contract_repo_governance_timelock_casebook",
                    notes=[
                        "Built-in repo-scale smart-contract casebook for bounded governance, timelock, guardian, and queued-upgrade review sweeps.",
                    ],
                ),
            ),
            "toy_contract_repo_rewards_distribution_casebook": SyntheticResearchTarget(
                target_name="toy_contract_repo_rewards_distribution_casebook",
                description="Built-in bounded repo-scale smart-contract casebook for reward-index, emission, claim, and reserve-backed distribution review lanes.",
                research_target=ResearchTarget(
                    target_kind="smart_contract_testbed",
                    target_reference="repo_rewards_distribution_casebook",
                    target_origin="synthetic",
                    synthetic_target_name="toy_contract_repo_rewards_distribution_casebook",
                    notes=[
                        "Built-in repo-scale smart-contract casebook for bounded reward-index, claim, emission, and reserve-backed distribution review sweeps.",
                    ],
                ),
            ),
            "toy_contract_repo_stablecoin_collateral_casebook": SyntheticResearchTarget(
                target_name="toy_contract_repo_stablecoin_collateral_casebook",
                description="Built-in bounded repo-scale smart-contract casebook for stablecoin mint, redemption, collateral, reserve, and liquidation review lanes.",
                research_target=ResearchTarget(
                    target_kind="smart_contract_testbed",
                    target_reference="repo_stablecoin_collateral_casebook",
                    target_origin="synthetic",
                    synthetic_target_name="toy_contract_repo_stablecoin_collateral_casebook",
                    notes=[
                        "Built-in repo-scale smart-contract casebook for bounded stablecoin mint, redemption, collateral, reserve, and liquidation review sweeps.",
                    ],
                ),
            ),
            "toy_contract_repo_amm_liquidity_casebook": SyntheticResearchTarget(
                target_name="toy_contract_repo_amm_liquidity_casebook",
                description="Built-in bounded repo-scale smart-contract casebook for AMM swap, liquidity, reserve, fee-growth, and oracle-sync review lanes.",
                research_target=ResearchTarget(
                    target_kind="smart_contract_testbed",
                    target_reference="repo_amm_liquidity_casebook",
                    target_origin="synthetic",
                    synthetic_target_name="toy_contract_repo_amm_liquidity_casebook",
                    notes=[
                        "Built-in repo-scale smart-contract casebook for bounded AMM, liquidity, reserve, fee-growth, and oracle-sync review sweeps.",
                    ],
                ),
            ),
            "toy_contract_repo_bridge_custody_casebook": SyntheticResearchTarget(
                target_name="toy_contract_repo_bridge_custody_casebook",
                description="Built-in bounded repo-scale smart-contract casebook for bridge relay, custody, proof, withdrawal-finalization, and replay-protection review lanes.",
                research_target=ResearchTarget(
                    target_kind="smart_contract_testbed",
                    target_reference="repo_bridge_custody_casebook",
                    target_origin="synthetic",
                    synthetic_target_name="toy_contract_repo_bridge_custody_casebook",
                    notes=[
                        "Built-in repo-scale smart-contract casebook for bounded bridge relay, custody, proof, withdrawal-finalization, and replay-protection review sweeps.",
                    ],
                ),
            ),
            "toy_contract_repo_staking_rebase_casebook": SyntheticResearchTarget(
                target_name="toy_contract_repo_staking_rebase_casebook",
                description="Built-in bounded repo-scale smart-contract casebook for staking, rebase, queued withdrawal, slash, and validator-reward review lanes.",
                research_target=ResearchTarget(
                    target_kind="smart_contract_testbed",
                    target_reference="repo_staking_rebase_casebook",
                    target_origin="synthetic",
                    synthetic_target_name="toy_contract_repo_staking_rebase_casebook",
                    notes=[
                        "Built-in repo-scale smart-contract casebook for bounded staking, rebase, queued withdrawal, slash, and validator-reward review sweeps.",
                    ],
                ),
            ),
            "toy_contract_repo_keeper_auction_casebook": SyntheticResearchTarget(
                target_name="toy_contract_repo_keeper_auction_casebook",
                description="Built-in bounded repo-scale smart-contract casebook for keeper reward, auction settlement, liquidation, oracle, and reserve-buffer review lanes.",
                research_target=ResearchTarget(
                    target_kind="smart_contract_testbed",
                    target_reference="repo_keeper_auction_casebook",
                    target_origin="synthetic",
                    synthetic_target_name="toy_contract_repo_keeper_auction_casebook",
                    notes=[
                        "Built-in repo-scale smart-contract casebook for bounded keeper reward, auction settlement, liquidation, oracle, and reserve-buffer review sweeps.",
                    ],
                ),
            ),
            "toy_contract_repo_treasury_vesting_casebook": SyntheticResearchTarget(
                target_name="toy_contract_repo_treasury_vesting_casebook",
                description="Built-in bounded repo-scale smart-contract casebook for treasury release, vesting schedule, beneficiary payout, sweep, and timelock review lanes.",
                research_target=ResearchTarget(
                    target_kind="smart_contract_testbed",
                    target_reference="repo_treasury_vesting_casebook",
                    target_origin="synthetic",
                    synthetic_target_name="toy_contract_repo_treasury_vesting_casebook",
                    notes=[
                        "Built-in repo-scale smart-contract casebook for bounded treasury release, vesting schedule, beneficiary payout, sweep, and timelock review sweeps.",
                    ],
                ),
            ),
            "toy_contract_repo_insurance_recovery_casebook": SyntheticResearchTarget(
                target_name="toy_contract_repo_insurance_recovery_casebook",
                description="Built-in bounded repo-scale smart-contract casebook for insurance-fund depletion, deficit absorption, reserve recovery, and emergency-settlement review lanes.",
                research_target=ResearchTarget(
                    target_kind="smart_contract_testbed",
                    target_reference="repo_insurance_recovery_casebook",
                    target_origin="synthetic",
                    synthetic_target_name="toy_contract_repo_insurance_recovery_casebook",
                    notes=[
                        "Built-in repo-scale smart-contract casebook for bounded insurance-fund depletion, deficit absorption, reserve recovery, and emergency-settlement review sweeps.",
                    ],
                ),
            ),
        }

    def list_profiles(self) -> list[ResearchTargetProfile]:
        return [self._profiles[name] for name in sorted(self._profiles)]

    def list_synthetic_targets(self) -> list[SyntheticResearchTarget]:
        return [self._synthetic_targets[name] for name in sorted(self._synthetic_targets)]

    def get_synthetic_target(self, target_name: str) -> SyntheticResearchTarget:
        try:
            return self._synthetic_targets[target_name]
        except KeyError as exc:
            raise ValueError(f"Unknown synthetic research target: {target_name}") from exc

    def build_synthetic_target(self, target_name: str) -> ResearchTarget:
        synthetic_target = self.get_synthetic_target(target_name)
        target = synthetic_target.research_target.model_copy(deep=True)
        return self.apply_profile(target)

    def resolve_profile(self, target: ResearchTarget) -> ResearchTargetProfile:
        return self._profiles.get(target.target_kind, self._profiles["generic"])

    def apply_profile(self, target: ResearchTarget) -> ResearchTarget:
        profile = self.resolve_profile(target)
        notes = list(target.notes)
        profile_note = f"target_profile={profile.profile_name}"
        if profile_note not in notes:
            notes.append(profile_note)
        return target.model_copy(
            update={
                "target_profile": profile.profile_name,
                "notes": notes,
            }
        )

    def validate_target(self, target: ResearchTarget) -> tuple[ResearchTargetProfile, list[str]]:
        profile = self.resolve_profile(target)
        normalized = self.apply_profile(target)
        notes = list(normalized.notes)
        if len(normalized.target_reference) > profile.max_reference_length:
            raise ValueError(
                f"Research target exceeds bounded length for profile {profile.profile_name}: "
                f"{len(normalized.target_reference)} > {profile.max_reference_length}"
            )
        if normalized.safety_scope != "authorized_local_research":
            raise ValueError(
                "Research target safety scope is not approved for sandboxed defensive execution."
            )
        notes.append(f"target_origin={normalized.target_origin}")
        if normalized.synthetic_target_name:
            notes.append(f"synthetic_target_name={normalized.synthetic_target_name}")
        notes.append(
            f"target_reference_length={len(normalized.target_reference)}"
        )
        return profile, notes
