from __future__ import annotations

import json
from pathlib import Path

from app.config import AppConfig
from app.core.research_targets import ResearchTargetRegistry
from app.main import build_orchestrator, render_synthetic_targets
from app.models.sandbox import ResearchMode
from app.types import make_id


def _synthetic_config(run_root: Path) -> AppConfig:
    return AppConfig.model_validate(
        {
            "llm": {
                "default_provider": "mock",
                "default_model": "mock-default",
                "timeout_seconds": 30,
                "max_request_tokens": 2048,
                "max_total_requests_per_session": 16,
            },
            "storage": {
                "artifacts_dir": str(run_root),
                "sessions_dir": str(run_root / "sessions"),
                "traces_dir": str(run_root / "traces"),
                "math_artifacts_dir": str(run_root / "math"),
                "bundles_dir": str(run_root / "bundles"),
            },
            "plugins": {
                "enabled": True,
                "directory": "plugins",
                "allow_local_plugins": True,
            },
            "sage": {
                "enabled": False,
                "binary": "sage",
                "timeout_seconds": 5,
            },
            "research": {
                "default_mode": "standard",
                "max_exploratory_branches": 2,
                "max_jobs_per_session": 2,
                "require_manual_review_for_exploratory": True,
            },
            "advanced_math_enabled": True,
            "log_level": "INFO",
            "max_hypotheses": 3,
            "tool_timeout_seconds": 15,
        }
    )


def test_research_target_registry_lists_controlled_synthetic_targets() -> None:
    registry = ResearchTargetRegistry()
    names = [item.target_name for item in registry.list_synthetic_targets()]

    assert "toy_curve_secp256k1" in names
    assert "toy_secp256k1_generator_compressed" in names
    assert "toy_secp256k1_bad_prefix_compressed" in names
    assert "toy_coordinate_length_mismatch" in names
    assert "toy_curve_alias_p256" in names
    assert "toy_symbolic_balance" in names
    assert "toy_modular_equivalence" in names
    assert "toy_point_anomaly_testbed" in names
    assert "toy_curve_alias_testbed" in names
    assert "toy_curve_encoding_edge_testbed" in names
    assert "toy_coordinate_shape_testbed" in names
    assert "toy_curve_subgroup_cofactor_testbed" in names
    assert "toy_curve_domain_testbed" in names
    assert "toy_curve_family_testbed" in names
    assert "toy_contract_upgrade_surface_testbed" in names
    assert "toy_contract_asset_flow_testbed" in names
    assert "toy_contract_authorization_flow_testbed" in names
    assert "toy_contract_proxy_storage_testbed" in names
    assert "toy_contract_time_entropy_testbed" in names
    assert "toy_contract_upgrade_validation_testbed" in names
    assert "toy_contract_token_interaction_testbed" in names
    assert "toy_contract_approval_review_testbed" in names
    assert "toy_contract_assembly_review_testbed" in names
    assert "toy_contract_state_machine_testbed" in names
    assert "toy_contract_vault_share_testbed" in names
    assert "toy_contract_signature_review_testbed" in names
    assert "toy_contract_oracle_review_testbed" in names
    assert "toy_contract_collateral_liquidation_testbed" in names
    assert "toy_contract_reserve_fee_accounting_testbed" in names
    assert "toy_contract_loop_payout_testbed" in names
    assert "toy_contract_repo_upgrade_casebook" in names
    assert "toy_contract_repo_asset_flow_casebook" in names
    assert "toy_contract_repo_oracle_casebook" in names
    assert "toy_contract_repo_protocol_accounting_casebook" in names
    assert "toy_contract_repo_governance_timelock_casebook" in names
    assert "toy_contract_repo_rewards_distribution_casebook" in names
    assert "toy_contract_repo_stablecoin_collateral_casebook" in names
    assert "toy_contract_repo_amm_liquidity_casebook" in names
    assert "toy_contract_repo_bridge_custody_casebook" in names
    assert "toy_contract_repo_staking_rebase_casebook" in names
    assert "toy_contract_repo_keeper_auction_casebook" in names
    assert "toy_contract_repo_treasury_vesting_casebook" in names
    assert "toy_contract_repo_insurance_recovery_casebook" in names


def test_exploratory_session_can_use_explicit_synthetic_target() -> None:
    run_root = Path(".test_runs") / make_id("synthetic")
    config = _synthetic_config(run_root)
    orchestrator = build_orchestrator(config)

    session = orchestrator.run_session(
        seed_text="Explore bounded defensive consistency leads with a safe toy target.",
        author="synthetic-test",
        research_mode=ResearchMode.SANDBOXED_EXPLORATORY,
        synthetic_target_name="toy_modular_equivalence",
    )

    assert session.research_target is not None
    assert session.research_target.target_origin == "synthetic"
    assert session.research_target.synthetic_target_name == "toy_modular_equivalence"
    assert session.research_target.target_kind == "finite_field"
    assert session.research_target.target_profile == "finite_field_relation_target"
    assert session.jobs
    assert all(job.tool_name == "finite_field_check_tool" for job in session.jobs)
    assert session.evidence
    assert all(evidence.synthetic_target_name == "toy_modular_equivalence" for evidence in session.evidence)
    assert all(evidence.target_origin == "synthetic" for evidence in session.evidence)

    assert session.manifest_file_path is not None
    manifest_payload = json.loads(Path(session.manifest_file_path).read_text(encoding="utf-8"))
    assert manifest_payload["synthetic_target_name"] == "toy_modular_equivalence"
    assert manifest_payload["research_target_origin"] == "synthetic"


def test_render_synthetic_targets_lists_available_toy_targets() -> None:
    run_root = Path(".test_runs") / make_id("syntheticrender")
    orchestrator = build_orchestrator(_synthetic_config(run_root))

    rendered = render_synthetic_targets(orchestrator, language="en")

    assert "Built-in Synthetic Research Targets" in rendered
    assert "toy_curve_secp256k1" in rendered
    assert "toy_modular_equivalence" in rendered
    assert "toy_secp256k1_bad_prefix_compressed" in rendered
    assert "toy_point_anomaly_testbed" in rendered
    assert "toy_curve_encoding_edge_testbed" in rendered
    assert "toy_curve_domain_testbed" in rendered
    assert "toy_curve_family_testbed" in rendered
    assert "toy_contract_upgrade_surface_testbed" in rendered
    assert "toy_contract_asset_flow_testbed" in rendered
    assert "toy_contract_authorization_flow_testbed" in rendered
    assert "toy_contract_proxy_storage_testbed" in rendered
    assert "toy_contract_time_entropy_testbed" in rendered
    assert "toy_contract_upgrade_validation_testbed" in rendered
    assert "toy_contract_token_interaction_testbed" in rendered
    assert "toy_contract_approval_review_testbed" in rendered
    assert "toy_contract_assembly_review_testbed" in rendered
    assert "toy_contract_state_machine_testbed" in rendered
    assert "toy_contract_vault_share_testbed" in rendered
    assert "toy_contract_signature_review_testbed" in rendered
    assert "toy_contract_oracle_review_testbed" in rendered
    assert "toy_contract_collateral_liquidation_testbed" in rendered
    assert "toy_contract_reserve_fee_accounting_testbed" in rendered
    assert "toy_contract_loop_payout_testbed" in rendered
    assert "toy_contract_repo_upgrade_casebook" in rendered
    assert "toy_contract_repo_asset_flow_casebook" in rendered
    assert "toy_contract_repo_oracle_casebook" in rendered
    assert "toy_contract_repo_protocol_accounting_casebook" in rendered
    assert "toy_contract_repo_governance_timelock_casebook" in rendered
    assert "toy_contract_repo_rewards_distribution_casebook" in rendered
    assert "toy_contract_repo_stablecoin_collateral_casebook" in rendered
    assert "toy_contract_repo_amm_liquidity_casebook" in rendered
    assert "toy_contract_repo_bridge_custody_casebook" in rendered
    assert "toy_contract_repo_staking_rebase_casebook" in rendered
    assert "toy_contract_repo_keeper_auction_casebook" in rendered
    assert "toy_contract_repo_treasury_vesting_casebook" in rendered
    assert "toy_contract_repo_insurance_recovery_casebook" in rendered


def test_exploratory_session_can_use_explicit_testbed_target() -> None:
    run_root = Path(".test_runs") / make_id("synthetictestbed")
    config = _synthetic_config(run_root)
    orchestrator = build_orchestrator(config)

    session = orchestrator.run_session(
        seed_text="Explore bounded ECC anomaly corpus leads with a safe toy testbed target.",
        author="synthetic-testbed",
        research_mode=ResearchMode.SANDBOXED_EXPLORATORY,
        synthetic_target_name="toy_point_anomaly_testbed",
    )

    assert session.research_target is not None
    assert session.research_target.target_kind == "testbed"
    assert session.jobs
    assert all(job.tool_name == "ecc_testbed_tool" for job in session.jobs)


def test_exploratory_session_can_use_curve_domain_testbed_target() -> None:
    run_root = Path(".test_runs") / make_id("syntheticdomaintestbed")
    config = _synthetic_config(run_root)
    orchestrator = build_orchestrator(config)

    session = orchestrator.run_session(
        seed_text="Explore bounded registry domain completeness signals with a safe toy testbed target.",
        author="synthetic-domain-testbed",
        research_mode=ResearchMode.SANDBOXED_EXPLORATORY,
        synthetic_target_name="toy_curve_domain_testbed",
    )

    assert session.research_target is not None
    assert session.research_target.target_kind == "testbed"
    assert session.research_target.target_reference == "curve_domain_corpus"
    assert session.jobs
    assert all(job.tool_name == "ecc_testbed_tool" for job in session.jobs)
    assert any(evidence.synthetic_target_name == "toy_curve_domain_testbed" for evidence in session.evidence)


def test_exploratory_session_can_use_curve_subgroup_testbed_target() -> None:
    run_root = Path(".test_runs") / make_id("syntheticsubgrouptestbed")
    config = _synthetic_config(run_root)
    orchestrator = build_orchestrator(config)

    session = orchestrator.run_session(
        seed_text="Explore bounded subgroup and cofactor hygiene signals with a safe toy ECC testbed target.",
        author="synthetic-subgroup-testbed",
        research_mode=ResearchMode.SANDBOXED_EXPLORATORY,
        synthetic_target_name="toy_curve_subgroup_cofactor_testbed",
    )

    assert session.research_target is not None
    assert session.research_target.target_kind == "testbed"
    assert session.research_target.target_reference == "subgroup_cofactor_corpus"
    assert session.jobs
    assert all(job.tool_name == "ecc_testbed_tool" for job in session.jobs)
    assert any(evidence.synthetic_target_name == "toy_curve_subgroup_cofactor_testbed" for evidence in session.evidence)


def test_exploratory_session_can_use_smart_contract_testbed_target() -> None:
    run_root = Path(".test_runs") / make_id("syntheticcontracttestbed")
    config = _synthetic_config(run_root)
    orchestrator = build_orchestrator(config)

    session = orchestrator.run_session(
        seed_text="Explore bounded upgrade and implementation review signals with a safe toy contract testbed target.",
        author="synthetic-contract-testbed",
        research_mode=ResearchMode.SANDBOXED_EXPLORATORY,
        synthetic_target_name="toy_contract_upgrade_surface_testbed",
    )

    assert session.research_target is not None
    assert session.research_target.target_kind == "smart_contract_testbed"
    assert session.research_target.target_reference == "upgrade_surface_corpus"
    assert session.jobs
    assert all(job.tool_name == "contract_testbed_tool" for job in session.jobs)
    assert any(evidence.synthetic_target_name == "toy_contract_upgrade_surface_testbed" for evidence in session.evidence)


def test_exploratory_session_can_use_asset_flow_contract_testbed() -> None:
    run_root = Path(".test_runs") / make_id("syntheticcontractassetflow")
    config = _synthetic_config(run_root)
    orchestrator = build_orchestrator(config)

    session = orchestrator.run_session(
        seed_text="Explore bounded deposit, withdraw, rescue, and sweep flow review signals with a safe toy contract testbed target.",
        author="synthetic-contract-asset-flow-testbed",
        research_mode=ResearchMode.SANDBOXED_EXPLORATORY,
        synthetic_target_name="toy_contract_asset_flow_testbed",
    )

    assert session.research_target is not None
    assert session.research_target.target_reference == "asset_flow_corpus"
    assert session.jobs
    assert all(job.tool_name == "contract_testbed_tool" for job in session.jobs)
    assert any(evidence.synthetic_target_name == "toy_contract_asset_flow_testbed" for evidence in session.evidence)


def test_exploratory_session_can_use_vault_share_contract_testbed() -> None:
    run_root = Path(".test_runs") / make_id("syntheticcontractvaultshare")
    config = _synthetic_config(run_root)
    orchestrator = build_orchestrator(config)

    session = orchestrator.run_session(
        seed_text="Explore bounded vault share mint, redeem, and asset-conversion review signals with a safe toy contract testbed target.",
        author="synthetic-contract-vault-share-testbed",
        research_mode=ResearchMode.SANDBOXED_EXPLORATORY,
        synthetic_target_name="toy_contract_vault_share_testbed",
    )

    assert session.research_target is not None
    assert session.research_target.target_reference == "vault_share_corpus"
    assert session.jobs
    assert all(job.tool_name == "contract_testbed_tool" for job in session.jobs)
    assert any(evidence.synthetic_target_name == "toy_contract_vault_share_testbed" for evidence in session.evidence)


def test_exploratory_session_can_use_authorization_flow_contract_testbed() -> None:
    run_root = Path(".test_runs") / make_id("syntheticcontractauth")
    config = _synthetic_config(run_root)
    orchestrator = build_orchestrator(config)

    session = orchestrator.run_session(
        seed_text="Explore bounded authorization-flow and pause-control review signals with a safe toy contract testbed target.",
        author="synthetic-contract-auth-testbed",
        research_mode=ResearchMode.SANDBOXED_EXPLORATORY,
        synthetic_target_name="toy_contract_authorization_flow_testbed",
    )

    assert session.research_target is not None
    assert session.research_target.target_reference == "authorization_flow_corpus"
    assert session.jobs
    assert all(job.tool_name == "contract_testbed_tool" for job in session.jobs)


def test_exploratory_session_can_use_token_and_assembly_contract_testbeds() -> None:
    run_root = Path(".test_runs") / make_id("syntheticcontractextra")
    config = _synthetic_config(run_root)
    orchestrator = build_orchestrator(config)

    token_session = orchestrator.run_session(
        seed_text="Explore bounded token transfer and allowance review signals with a safe toy contract testbed target.",
        author="synthetic-contract-token-testbed",
        research_mode=ResearchMode.SANDBOXED_EXPLORATORY,
        synthetic_target_name="toy_contract_token_interaction_testbed",
    )
    assembly_session = orchestrator.run_session(
        seed_text="Explore bounded inline assembly review signals with a safe toy contract testbed target.",
        author="synthetic-contract-assembly-testbed",
        research_mode=ResearchMode.SANDBOXED_EXPLORATORY,
        synthetic_target_name="toy_contract_assembly_review_testbed",
    )

    assert token_session.research_target is not None
    assert token_session.research_target.target_reference == "token_interaction_corpus"
    assert token_session.jobs
    assert all(job.tool_name == "contract_testbed_tool" for job in token_session.jobs)

    assert assembly_session.research_target is not None
    assert assembly_session.research_target.target_reference == "assembly_review_corpus"
    assert assembly_session.jobs
    assert all(job.tool_name == "contract_testbed_tool" for job in assembly_session.jobs)


def test_exploratory_session_can_use_proxy_storage_contract_testbed() -> None:
    run_root = Path(".test_runs") / make_id("syntheticcontractproxy")
    config = _synthetic_config(run_root)
    orchestrator = build_orchestrator(config)

    session = orchestrator.run_session(
        seed_text="Explore bounded proxy delegation and storage-layout review signals with a safe toy contract testbed target.",
        author="synthetic-contract-proxy-testbed",
        research_mode=ResearchMode.SANDBOXED_EXPLORATORY,
        synthetic_target_name="toy_contract_proxy_storage_testbed",
    )

    assert session.research_target is not None
    assert session.research_target.target_reference == "proxy_storage_corpus"
    assert session.jobs
    assert all(job.tool_name == "contract_testbed_tool" for job in session.jobs)


def test_exploratory_session_can_use_validation_approval_and_state_machine_contract_testbeds() -> None:
    run_root = Path(".test_runs") / make_id("syntheticcontractadvanced")
    config = _synthetic_config(run_root)
    orchestrator = build_orchestrator(config)

    validation_session = orchestrator.run_session(
        seed_text="Explore bounded zero-address and implementation validation review signals with a safe toy contract testbed target.",
        author="synthetic-contract-validation-testbed",
        research_mode=ResearchMode.SANDBOXED_EXPLORATORY,
        synthetic_target_name="toy_contract_upgrade_validation_testbed",
    )
    approval_session = orchestrator.run_session(
        seed_text="Explore bounded approval and allowance review signals with a safe toy contract testbed target.",
        author="synthetic-contract-approval-testbed",
        research_mode=ResearchMode.SANDBOXED_EXPLORATORY,
        synthetic_target_name="toy_contract_approval_review_testbed",
    )
    accounting_session = orchestrator.run_session(
        seed_text="Explore bounded balance accounting and withdrawal-order review signals with a safe toy contract testbed target.",
        author="synthetic-contract-accounting-testbed",
        research_mode=ResearchMode.SANDBOXED_EXPLORATORY,
        synthetic_target_name="toy_contract_accounting_review_testbed",
    )
    state_session = orchestrator.run_session(
        seed_text="Explore bounded state-machine transition review signals with a safe toy contract testbed target.",
        author="synthetic-contract-state-testbed",
        research_mode=ResearchMode.SANDBOXED_EXPLORATORY,
        synthetic_target_name="toy_contract_state_machine_testbed",
    )

    assert validation_session.research_target is not None
    assert validation_session.research_target.target_reference == "upgrade_validation_corpus"
    assert all(job.tool_name == "contract_testbed_tool" for job in validation_session.jobs)

    assert approval_session.research_target is not None
    assert approval_session.research_target.target_reference == "approval_review_corpus"
    assert all(job.tool_name == "contract_testbed_tool" for job in approval_session.jobs)

    assert accounting_session.research_target is not None
    assert accounting_session.research_target.target_reference == "accounting_review_corpus"
    assert all(job.tool_name == "contract_testbed_tool" for job in accounting_session.jobs)

    assert state_session.research_target is not None
    assert state_session.research_target.target_reference == "state_machine_corpus"
    assert all(job.tool_name == "contract_testbed_tool" for job in state_session.jobs)


def test_exploratory_session_can_use_signature_oracle_collateral_reserve_and_loop_contract_testbeds() -> None:
    run_root = Path(".test_runs") / make_id("syntheticcontractsignals")
    config = _synthetic_config(run_root)
    orchestrator = build_orchestrator(config)

    signature_session = orchestrator.run_session(
        seed_text="Explore bounded signature replay and permit review signals with a safe toy contract testbed target.",
        author="synthetic-contract-signature-testbed",
        research_mode=ResearchMode.SANDBOXED_EXPLORATORY,
        synthetic_target_name="toy_contract_signature_review_testbed",
    )
    oracle_session = orchestrator.run_session(
        seed_text="Explore bounded oracle freshness and price dependency review signals with a safe toy contract testbed target.",
        author="synthetic-contract-oracle-testbed",
        research_mode=ResearchMode.SANDBOXED_EXPLORATORY,
        synthetic_target_name="toy_contract_oracle_review_testbed",
    )
    collateral_session = orchestrator.run_session(
        seed_text="Explore bounded collateral ratio, liquidation, and reserve-derived pricing review signals with a safe toy contract testbed target.",
        author="synthetic-contract-collateral-testbed",
        research_mode=ResearchMode.SANDBOXED_EXPLORATORY,
        synthetic_target_name="toy_contract_collateral_liquidation_testbed",
    )
    reserve_fee_session = orchestrator.run_session(
        seed_text="Explore bounded protocol fee, reserve synchronization, and debt-accounting review signals with a safe toy contract testbed target.",
        author="synthetic-contract-reserve-fee-testbed",
        research_mode=ResearchMode.SANDBOXED_EXPLORATORY,
        synthetic_target_name="toy_contract_reserve_fee_accounting_testbed",
    )
    loop_session = orchestrator.run_session(
        seed_text="Explore bounded payout-loop and batch distribution review signals with a safe toy contract testbed target.",
        author="synthetic-contract-loop-testbed",
        research_mode=ResearchMode.SANDBOXED_EXPLORATORY,
        synthetic_target_name="toy_contract_loop_payout_testbed",
    )

    assert signature_session.research_target is not None
    assert signature_session.research_target.target_reference == "signature_review_corpus"
    assert all(job.tool_name == "contract_testbed_tool" for job in signature_session.jobs)

    assert oracle_session.research_target is not None
    assert oracle_session.research_target.target_reference == "oracle_review_corpus"
    assert all(job.tool_name == "contract_testbed_tool" for job in oracle_session.jobs)

    assert collateral_session.research_target is not None
    assert collateral_session.research_target.target_reference == "collateral_liquidation_corpus"
    assert all(job.tool_name == "contract_testbed_tool" for job in collateral_session.jobs)

    assert reserve_fee_session.research_target is not None
    assert reserve_fee_session.research_target.target_reference == "reserve_fee_accounting_corpus"
    assert all(job.tool_name == "contract_testbed_tool" for job in reserve_fee_session.jobs)

    assert loop_session.research_target is not None
    assert loop_session.research_target.target_reference == "loop_payout_corpus"
    assert all(job.tool_name == "contract_testbed_tool" for job in loop_session.jobs)


def test_exploratory_session_can_use_repo_casebook_contract_testbeds() -> None:
    run_root = Path(".test_runs") / make_id("syntheticcontractrepocasebook")
    config = _synthetic_config(run_root)
    orchestrator = build_orchestrator(config)

    upgrade_session = orchestrator.run_session(
        seed_text="Explore bounded repo-scale proxy and upgrade review lanes with a safe toy contract casebook target.",
        author="synthetic-contract-repo-upgrade-casebook",
        research_mode=ResearchMode.SANDBOXED_EXPLORATORY,
        synthetic_target_name="toy_contract_repo_upgrade_casebook",
    )
    asset_session = orchestrator.run_session(
        seed_text="Explore bounded repo-scale asset-flow and rescue review lanes with a safe toy contract casebook target.",
        author="synthetic-contract-repo-asset-casebook",
        research_mode=ResearchMode.SANDBOXED_EXPLORATORY,
        synthetic_target_name="toy_contract_repo_asset_flow_casebook",
    )
    oracle_session = orchestrator.run_session(
        seed_text="Explore bounded repo-scale oracle and liquidation review lanes with a safe toy contract casebook target.",
        author="synthetic-contract-repo-oracle-casebook",
        research_mode=ResearchMode.SANDBOXED_EXPLORATORY,
        synthetic_target_name="toy_contract_repo_oracle_casebook",
    )
    protocol_session = orchestrator.run_session(
        seed_text="Explore bounded repo-scale protocol fee, reserve synchronization, and debt-accounting review lanes with a safe toy contract casebook target.",
        author="synthetic-contract-repo-protocol-casebook",
        research_mode=ResearchMode.SANDBOXED_EXPLORATORY,
        synthetic_target_name="toy_contract_repo_protocol_accounting_casebook",
    )

    assert upgrade_session.research_target is not None
    assert upgrade_session.research_target.target_reference == "repo_upgrade_casebook"
    assert all(job.tool_name == "contract_testbed_tool" for job in upgrade_session.jobs)

    assert asset_session.research_target is not None
    assert asset_session.research_target.target_reference == "repo_asset_flow_casebook"
    assert all(job.tool_name == "contract_testbed_tool" for job in asset_session.jobs)

    assert oracle_session.research_target is not None
    assert oracle_session.research_target.target_reference == "repo_oracle_casebook"
    assert all(job.tool_name == "contract_testbed_tool" for job in oracle_session.jobs)

    assert protocol_session.research_target is not None
    assert protocol_session.research_target.target_reference == "repo_protocol_accounting_casebook"
    assert all(job.tool_name == "contract_testbed_tool" for job in protocol_session.jobs)
