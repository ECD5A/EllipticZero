from __future__ import annotations

import json
from pathlib import Path

from app.config import AppConfig
from app.core.experiment_packs import ExperimentPackRegistry
from app.core.replay_loader import ReplayLoader
from app.core.replay_planner import ReplayPlanner
from app.core.seed_parsing import build_smart_contract_seed
from app.main import build_orchestrator, render_experiment_packs
from app.models.replay_request import ReplayRequest
from app.models.sandbox import ResearchTarget
from app.types import make_id


def _make_config(run_root: Path) -> AppConfig:
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


def test_experiment_pack_registry_lists_built_in_workflows() -> None:
    registry = ExperimentPackRegistry()
    names = registry.names()

    assert "curve_metadata_audit_pack" in names
    assert "point_format_inspection_pack" in names
    assert "ecc_family_depth_benchmark_pack" in names
    assert "ecc_subgroup_hygiene_benchmark_pack" in names
    assert "ecc_domain_completeness_benchmark_pack" in names
    assert "symbolic_consistency_pack" in names
    assert "finite_field_consistency_pack" in names
    assert "comparative_tool_sweep_pack" in names
    assert "contract_static_benchmark_pack" in names
    assert "repo_casebook_benchmark_pack" in names
    assert "protocol_casebook_benchmark_pack" in names
    assert "upgrade_control_benchmark_pack" in names
    assert "vault_permission_benchmark_pack" in names
    assert "lending_protocol_benchmark_pack" in names
    assert "governance_timelock_benchmark_pack" in names
    assert "reward_distribution_benchmark_pack" in names
    assert "stablecoin_collateral_benchmark_pack" in names
    assert "amm_liquidity_benchmark_pack" in names
    assert "bridge_custody_benchmark_pack" in names
    assert "staking_rebase_benchmark_pack" in names
    assert "keeper_auction_benchmark_pack" in names
    assert "treasury_vesting_benchmark_pack" in names
    assert "insurance_recovery_benchmark_pack" in names


def test_experiment_pack_recommendation_matches_curve_oriented_target() -> None:
    run_root = Path(".test_runs") / make_id("packrec")
    orchestrator = build_orchestrator(_make_config(run_root))
    registry = ExperimentPackRegistry()
    research_target = orchestrator.target_registry.build_synthetic_target("toy_curve_secp256k1")

    recommendations = registry.recommend(
        seed_text="Audit secp256k1 aliases, usage category, and domain metadata consistency.",
        research_target=research_target,
    )

    assert recommendations
    assert recommendations[0].pack_name == "curve_metadata_audit_pack"
    assert recommendations[0].confidence_hint == "high"


def test_experiment_pack_recommendation_matches_ecc_family_depth_seed() -> None:
    run_root = Path(".test_runs") / make_id("packeccfamily")
    orchestrator = build_orchestrator(_make_config(run_root))
    registry = ExperimentPackRegistry()
    research_target = orchestrator.target_registry.build_synthetic_target("toy_curve_secp256k1")

    recommendations = registry.recommend(
        seed_text="Review Montgomery, Edwards, and short-Weierstrass family transitions before comparing bounded ECC validation assumptions.",
        research_target=research_target,
    )

    names = [item.pack_name for item in recommendations]
    assert "ecc_family_depth_benchmark_pack" in names


def test_experiment_pack_recommendation_matches_ecc_subgroup_hygiene_seed() -> None:
    run_root = Path(".test_runs") / make_id("packeccsubgroup")
    orchestrator = build_orchestrator(_make_config(run_root))
    registry = ExperimentPackRegistry()
    research_target = orchestrator.target_registry.build_synthetic_target("toy_coordinate_length_mismatch")

    recommendations = registry.recommend(
        seed_text="Review subgroup, cofactor clearing, torsion, and twist hygiene assumptions for 25519-family inputs.",
        research_target=research_target,
    )

    names = [item.pack_name for item in recommendations]
    assert "ecc_subgroup_hygiene_benchmark_pack" in names


def test_experiment_pack_recommendation_matches_ecc_domain_completeness_seed() -> None:
    run_root = Path(".test_runs") / make_id("packeccdomain")
    orchestrator = build_orchestrator(_make_config(run_root))
    registry = ExperimentPackRegistry()
    research_target = orchestrator.target_registry.build_synthetic_target("toy_curve_secp256k1")

    recommendations = registry.recommend(
        seed_text="Audit registry completeness, generator and order exposure, and domain completeness for bounded ECC review.",
        research_target=research_target,
    )

    names = [item.pack_name for item in recommendations]
    assert "ecc_domain_completeness_benchmark_pack" in names


def test_explicit_experiment_pack_executes_multi_step_bounded_workflow() -> None:
    run_root = Path(".test_runs") / make_id("packrun")
    orchestrator = build_orchestrator(_make_config(run_root))

    session = orchestrator.run_session(
        seed_text=(
            "Inspect whether this compressed secp256k1 public key format is well formed "
            "and whether bounded consistency checks agree with the descriptor path: "
            "0279BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798"
        ),
        author="pack-test",
        experiment_pack_name="point_format_inspection_pack",
    )

    assert session.selected_pack_name == "point_format_inspection_pack"
    assert "point_format_inspection_pack" in session.recommended_pack_names
    assert session.executed_pack_steps == [
        "point_format_inspection_pack:format_descriptor",
        "point_format_inspection_pack:bounded_consistency",
    ]
    assert [job.tool_name for job in session.jobs[:2]] == [
        "ecc_point_format_tool",
        "ecc_consistency_check_tool",
    ]
    assert session.report is not None
    assert session.report.selected_pack_name == "point_format_inspection_pack"
    assert session.report.executed_pack_steps == session.executed_pack_steps

    assert session.manifest_file_path is not None
    manifest = json.loads(Path(session.manifest_file_path).read_text(encoding="utf-8"))
    assert manifest["selected_pack_name"] == "point_format_inspection_pack"
    assert manifest["executed_pack_steps"] == session.executed_pack_steps
    assert "ecc_point_format_check" in manifest["experiment_types"]
    assert "ecc_consistency_check" in manifest["experiment_types"]


def test_free_form_flow_still_works_without_pack_selection() -> None:
    run_root = Path(".test_runs") / make_id("packfree")
    orchestrator = build_orchestrator(_make_config(run_root))

    session = orchestrator.run_session(
        seed_text="Inspect whether secp256k1 metadata labels remain consistent across local reasoning and tool output.",
        author="free-form-pack-test",
    )

    assert session.selected_pack_name is None
    assert "curve_metadata_audit_pack" in session.recommended_pack_names
    assert session.jobs
    assert session.evidence


def test_replay_preserves_selected_experiment_pack() -> None:
    run_root = Path(".test_runs") / make_id("packreplay")
    config = _make_config(run_root)
    orchestrator = build_orchestrator(config)
    session = orchestrator.run_session(
        seed_text="Check whether 10 and 3 are equivalent mod 7 under a finite field consistency test.",
        author="pack-replay-source",
        experiment_pack_name="finite_field_consistency_pack",
    )

    loader = ReplayLoader()
    planner = ReplayPlanner()
    request = ReplayRequest(
        source_type="session",
        source_path=session.session_file_path,
        dry_run=False,
        reexecute=True,
    )
    loaded = loader.load(request)
    plan = planner.build_plan(
        loaded_source=loaded,
        available_tools=orchestrator.executor.registry.names(),
        preserve_original_seed=True,
    )
    result = planner.execute(
        request=request,
        plan=plan,
        orchestrator=build_orchestrator(config),
        author="pack-replay-runner",
    )

    assert result.success is True
    assert result.generated_session_path is not None
    replay_payload = json.loads(Path(result.generated_session_path).read_text(encoding="utf-8"))
    assert replay_payload["selected_pack_name"] == "finite_field_consistency_pack"


def test_point_pack_uses_coordinate_probe_for_coordinate_style_synthetic_target() -> None:
    run_root = Path(".test_runs") / make_id("packcoord")
    orchestrator = build_orchestrator(_make_config(run_root))

    session = orchestrator.run_session(
        seed_text="Inspect bounded coordinate-shape anomalies for a toy ECC target.",
        author="pack-coordinate-test",
        experiment_pack_name="point_format_inspection_pack",
        synthetic_target_name="toy_coordinate_length_mismatch",
    )

    assert session.selected_pack_name == "point_format_inspection_pack"
    assert session.executed_pack_steps == [
        "point_format_inspection_pack:coordinate_shape_probe",
        "point_format_inspection_pack:format_descriptor",
        "point_format_inspection_pack:bounded_consistency",
    ]
    assert [job.tool_name for job in session.jobs[:3]] == [
        "point_descriptor_tool",
        "ecc_point_format_tool",
        "ecc_consistency_check_tool",
    ]
    assert any(evidence.tool_name == "point_descriptor_tool" for evidence in session.evidence)
    assert all(
        evidence.synthetic_target_name == "toy_coordinate_length_mismatch"
        for evidence in session.evidence
    )
    assert session.report is not None
    assert "point_format_inspection_pack:coordinate_shape_probe" in session.report.executed_pack_steps


def test_render_experiment_packs_lists_available_workflows() -> None:
    run_root = Path(".test_runs") / make_id("packrender")
    orchestrator = build_orchestrator(_make_config(run_root))

    rendered = render_experiment_packs(orchestrator, language="en")

    assert "Built-in Experiment Packs" in rendered
    assert "curve_metadata_audit_pack" in rendered
    assert "point_format_inspection_pack" in rendered
    assert "ecc_family_depth_benchmark_pack" in rendered
    assert "ecc_subgroup_hygiene_benchmark_pack" in rendered
    assert "ecc_domain_completeness_benchmark_pack" in rendered
    assert "contract_static_benchmark_pack" in rendered
    assert "repo_casebook_benchmark_pack" in rendered
    assert "vault_permission_benchmark_pack" in rendered
    assert "stablecoin_collateral_benchmark_pack" in rendered
    assert "amm_liquidity_benchmark_pack" in rendered
    assert "bridge_custody_benchmark_pack" in rendered
    assert "staking_rebase_benchmark_pack" in rendered
    assert "keeper_auction_benchmark_pack" in rendered
    assert "treasury_vesting_benchmark_pack" in rendered
    assert "insurance_recovery_benchmark_pack" in rendered


def test_explicit_ecc_family_depth_benchmark_pack_runs_anchored_corpora() -> None:
    run_root = Path(".test_runs") / make_id("packeccfamilyrun")
    orchestrator = build_orchestrator(_make_config(run_root))

    session = orchestrator.run_session(
        seed_text="Review Montgomery, Edwards, and short-Weierstrass family transitions for bounded ECC handling.",
        author="ecc-family-pack-test",
        experiment_pack_name="ecc_family_depth_benchmark_pack",
        synthetic_target_name="toy_curve_secp256k1",
    )

    assert session.selected_pack_name == "ecc_family_depth_benchmark_pack"
    assert "ecc_family_depth_benchmark_pack:family_domain_parameters" in session.executed_pack_steps
    assert "ecc_family_depth_benchmark_pack:family_transition_benchmark" in session.executed_pack_steps
    assert "ecc_family_depth_benchmark_pack:encoding_edge_benchmark" in session.executed_pack_steps
    assert any(evidence.tool_name == "ecc_testbed_tool" for evidence in session.evidence)
    assert session.report is not None
    assert any("Selected ECC benchmark pack" in line for line in session.report.ecc_benchmark_summary)
    assert any("family-transition" in line.lower() for line in session.report.ecc_benchmark_summary)


def test_explicit_ecc_subgroup_hygiene_benchmark_pack_runs_anchored_corpora() -> None:
    run_root = Path(".test_runs") / make_id("packeccsubgrouprun")
    orchestrator = build_orchestrator(_make_config(run_root))

    session = orchestrator.run_session(
        seed_text=(
            "Review subgroup, cofactor clearing, and twist hygiene assumptions for x25519 and ed25519 public-key handling."
        ),
        author="ecc-subgroup-pack-test",
        experiment_pack_name="ecc_subgroup_hygiene_benchmark_pack",
        synthetic_target_name="toy_coordinate_length_mismatch",
    )

    assert session.selected_pack_name == "ecc_subgroup_hygiene_benchmark_pack"
    assert "ecc_subgroup_hygiene_benchmark_pack:subgroup_hygiene_benchmark" in session.executed_pack_steps
    assert "ecc_subgroup_hygiene_benchmark_pack:twist_hygiene_benchmark" in session.executed_pack_steps
    assert session.report is not None
    assert any("twist-hygiene" in line.lower() or "subgroup" in line.lower() for line in session.report.ecc_benchmark_summary)
    assert any("twist" in line.lower() or "cofactor" in line.lower() for line in session.report.ecc_review_focus)


def test_explicit_ecc_domain_completeness_benchmark_pack_runs_anchored_corpora() -> None:
    run_root = Path(".test_runs") / make_id("packeccdomainrun")
    orchestrator = build_orchestrator(_make_config(run_root))

    session = orchestrator.run_session(
        seed_text="Audit registry completeness, generator and order exposure, and ECC domain completeness before stronger conclusions.",
        author="ecc-domain-pack-test",
        experiment_pack_name="ecc_domain_completeness_benchmark_pack",
        synthetic_target_name="toy_curve_secp256k1",
    )

    assert session.selected_pack_name == "ecc_domain_completeness_benchmark_pack"
    assert "ecc_domain_completeness_benchmark_pack:curve_parameters" in session.executed_pack_steps
    assert "ecc_domain_completeness_benchmark_pack:domain_completeness_benchmark" in session.executed_pack_steps
    assert "ecc_domain_completeness_benchmark_pack:family_transition_crosscheck" in session.executed_pack_steps
    assert session.report is not None
    assert any("domain-completeness" in line.lower() or "domain metadata" in line.lower() for line in session.report.ecc_benchmark_summary)


def test_experiment_pack_recommendation_matches_repo_scale_contract_seed() -> None:
    registry = ExperimentPackRegistry()
    seed = build_smart_contract_seed(
        idea_text="Audit the scoped repository for proxy upgrade, delegatecall, and storage-lane review.",
        contract_code="pragma solidity ^0.8.24; contract Proxy { address public implementation; }",
        language="solidity",
        source_label="contracts/Proxy.sol",
        contract_root="contracts",
    )
    research_target = ResearchTarget(
        target_kind="smart_contract",
        target_reference="pragma solidity ^0.8.24; contract Proxy { address public implementation; }",
    )

    recommendations = registry.recommend(seed_text=seed, research_target=research_target)
    names = [item.pack_name for item in recommendations]

    assert "contract_static_benchmark_pack" in names
    assert "repo_casebook_benchmark_pack" in names


def test_experiment_pack_recommendation_matches_vault_permission_repo_seed() -> None:
    registry = ExperimentPackRegistry()
    seed = build_smart_contract_seed(
        idea_text="Audit the scoped repository for permit, allowance, ERC4626 vault share accounting, and redeem review lanes.",
        contract_code="pragma solidity ^0.8.24; contract VaultRouter { function depositWithPermit() external {} }",
        language="solidity",
        source_label="contracts/VaultRouter.sol",
        contract_root="contracts",
    )
    research_target = ResearchTarget(
        target_kind="smart_contract",
        target_reference="pragma solidity ^0.8.24; contract VaultRouter { function depositWithPermit() external {} }",
    )

    recommendations = registry.recommend(seed_text=seed, research_target=research_target)
    names = [item.pack_name for item in recommendations]

    assert "vault_permission_benchmark_pack" in names
    assert "protocol_casebook_benchmark_pack" in names


def test_experiment_pack_recommendation_matches_lending_protocol_repo_seed() -> None:
    registry = ExperimentPackRegistry()
    seed = build_smart_contract_seed(
        idea_text="Audit the scoped repository for lending collateral, liquidation, reserve synchronization, and debt-accounting review lanes.",
        contract_code="pragma solidity ^0.8.24; contract LendingPool { function liquidate() external {} }",
        language="solidity",
        source_label="contracts/LendingPool.sol",
        contract_root="contracts",
    )
    research_target = ResearchTarget(
        target_kind="smart_contract",
        target_reference="pragma solidity ^0.8.24; contract LendingPool { function liquidate() external {} }",
    )

    recommendations = registry.recommend(seed_text=seed, research_target=research_target)
    names = [item.pack_name for item in recommendations]

    assert "lending_protocol_benchmark_pack" in names
    assert "protocol_casebook_benchmark_pack" in names


def test_experiment_pack_recommendation_matches_governance_timelock_repo_seed() -> None:
    registry = ExperimentPackRegistry()
    seed = build_smart_contract_seed(
        idea_text="Audit the scoped repository for governance queue, timelock execution, guardian pause, and queued upgrade review lanes.",
        contract_code="pragma solidity ^0.8.24; contract Governor { function executeUpgrade() external {} }",
        language="solidity",
        source_label="contracts/Governor.sol",
        contract_root="contracts",
    )
    research_target = ResearchTarget(
        target_kind="smart_contract",
        target_reference="pragma solidity ^0.8.24; contract Governor { function executeUpgrade() external {} }",
    )

    recommendations = registry.recommend(seed_text=seed, research_target=research_target)
    names = [item.pack_name for item in recommendations]

    assert "governance_timelock_benchmark_pack" in names


def test_experiment_pack_recommendation_matches_reward_distribution_repo_seed() -> None:
    registry = ExperimentPackRegistry()
    seed = build_smart_contract_seed(
        idea_text="Audit the scoped repository for reward index drift, reward debt updates, emission-rate changes, and reward-claim review lanes.",
        contract_code="pragma solidity ^0.8.24; contract RewardsController { function claimRewards() external {} }",
        language="solidity",
        source_label="contracts/RewardsController.sol",
        contract_root="contracts",
    )
    research_target = ResearchTarget(
        target_kind="smart_contract",
        target_reference="pragma solidity ^0.8.24; contract RewardsController { function claimRewards() external {} }",
    )

    recommendations = registry.recommend(seed_text=seed, research_target=research_target)
    names = [item.pack_name for item in recommendations]

    assert "reward_distribution_benchmark_pack" in names


def test_experiment_pack_recommendation_matches_stablecoin_collateral_repo_seed() -> None:
    registry = ExperimentPackRegistry()
    seed = build_smart_contract_seed(
        idea_text="Audit the scoped repository for stablecoin mint-against-collateral, redemption buffer, peg, liquidation, and reserve review lanes.",
        contract_code="pragma solidity ^0.8.24; contract MintController { function mintAgainstCollateral() external {} }",
        language="solidity",
        source_label="contracts/MintController.sol",
        contract_root="contracts",
    )
    research_target = ResearchTarget(
        target_kind="smart_contract",
        target_reference="pragma solidity ^0.8.24; contract MintController { function mintAgainstCollateral() external {} }",
    )

    recommendations = registry.recommend(seed_text=seed, research_target=research_target)
    names = [item.pack_name for item in recommendations]

    assert "stablecoin_collateral_benchmark_pack" in names


def test_experiment_pack_recommendation_matches_amm_liquidity_repo_seed() -> None:
    registry = ExperimentPackRegistry()
    seed = build_smart_contract_seed(
        idea_text="Audit the scoped repository for AMM swap, liquidity, reserve, fee growth, router, and TWAP review lanes.",
        contract_code="pragma solidity ^0.8.24; contract Router { function swapExactInput() external {} }",
        language="solidity",
        source_label="contracts/Router.sol",
        contract_root="contracts",
    )
    research_target = ResearchTarget(
        target_kind="smart_contract",
        target_reference="pragma solidity ^0.8.24; contract Router { function swapExactInput() external {} }",
    )

    recommendations = registry.recommend(seed_text=seed, research_target=research_target)
    names = [item.pack_name for item in recommendations]

    assert "amm_liquidity_benchmark_pack" in names
    assert "protocol_casebook_benchmark_pack" in names


def test_experiment_pack_recommendation_matches_bridge_custody_repo_seed() -> None:
    registry = ExperimentPackRegistry()
    seed = build_smart_contract_seed(
        idea_text="Audit the scoped repository for bridge custody, relay validation, replay protection, and finalize-withdrawal review lanes.",
        contract_code="pragma solidity ^0.8.24; contract BridgePortal { function finalizeWithdrawal() external {} }",
        language="solidity",
        source_label="contracts/BridgePortal.sol",
        contract_root="contracts",
    )
    research_target = ResearchTarget(
        target_kind="smart_contract",
        target_reference="pragma solidity ^0.8.24; contract BridgePortal { function finalizeWithdrawal() external {} }",
    )

    recommendations = registry.recommend(seed_text=seed, research_target=research_target)
    names = [item.pack_name for item in recommendations]

    assert "bridge_custody_benchmark_pack" in names
    assert "protocol_casebook_benchmark_pack" in names


def test_experiment_pack_recommendation_matches_staking_rebase_repo_seed() -> None:
    registry = ExperimentPackRegistry()
    seed = build_smart_contract_seed(
        idea_text="Audit the scoped repository for staking, rebase, validator rewards, slash handling, and withdrawal queue review lanes.",
        contract_code="pragma solidity ^0.8.24; contract StakingPool { function rebase(uint256 delta) external {} }",
        language="solidity",
        source_label="contracts/StakingPool.sol",
        contract_root="contracts",
    )
    research_target = ResearchTarget(
        target_kind="smart_contract",
        target_reference="pragma solidity ^0.8.24; contract StakingPool { function rebase(uint256 delta) external {} }",
    )

    recommendations = registry.recommend(seed_text=seed, research_target=research_target)
    names = [item.pack_name for item in recommendations]

    assert "staking_rebase_benchmark_pack" in names
    assert "protocol_casebook_benchmark_pack" in names


def test_experiment_pack_recommendation_matches_keeper_auction_repo_seed() -> None:
    registry = ExperimentPackRegistry()
    seed = build_smart_contract_seed(
        idea_text="Audit the scoped repository for keeper reward, auction settlement, liquidation bids, and oracle freshness review lanes.",
        contract_code="pragma solidity ^0.8.24; contract AuctionHouse { function settle() external {} }",
        language="solidity",
        source_label="contracts/AuctionHouse.sol",
        contract_root="contracts",
    )
    research_target = ResearchTarget(
        target_kind="smart_contract",
        target_reference="pragma solidity ^0.8.24; contract AuctionHouse { function settle() external {} }",
    )

    recommendations = registry.recommend(seed_text=seed, research_target=research_target)
    names = [item.pack_name for item in recommendations]

    assert "keeper_auction_benchmark_pack" in names
    assert "protocol_casebook_benchmark_pack" in names


def test_experiment_pack_recommendation_matches_treasury_vesting_repo_seed() -> None:
    registry = ExperimentPackRegistry()
    seed = build_smart_contract_seed(
        idea_text="Audit the scoped repository for treasury release, vesting schedule, beneficiary payout, and timelock-controlled sweep review lanes.",
        contract_code="pragma solidity ^0.8.24; contract Treasury { function releaseVested(address beneficiary) external {} }",
        language="solidity",
        source_label="contracts/Treasury.sol",
        contract_root="contracts",
    )
    research_target = ResearchTarget(
        target_kind="smart_contract",
        target_reference="pragma solidity ^0.8.24; contract Treasury { function releaseVested(address beneficiary) external {} }",
    )

    recommendations = registry.recommend(seed_text=seed, research_target=research_target)
    names = [item.pack_name for item in recommendations]

    assert "treasury_vesting_benchmark_pack" in names
    assert "protocol_casebook_benchmark_pack" in names


def test_experiment_pack_recommendation_matches_insurance_recovery_repo_seed() -> None:
    registry = ExperimentPackRegistry()
    seed = build_smart_contract_seed(
        idea_text="Audit the scoped repository for insurance fund depletion, deficit absorption, reserve recovery, and emergency-settlement review lanes.",
        contract_code="pragma solidity ^0.8.24; contract InsuranceFund { function absorbDeficit(uint256 amount) external {} }",
        language="solidity",
        source_label="contracts/InsuranceFund.sol",
        contract_root="contracts",
    )
    research_target = ResearchTarget(
        target_kind="smart_contract",
        target_reference="pragma solidity ^0.8.24; contract InsuranceFund { function absorbDeficit(uint256 amount) external {} }",
    )

    recommendations = registry.recommend(seed_text=seed, research_target=research_target)
    names = [item.pack_name for item in recommendations]

    assert "insurance_recovery_benchmark_pack" in names
    assert "protocol_casebook_benchmark_pack" in names


def test_explicit_contract_static_benchmark_pack_executes_bounded_contract_stack() -> None:
    run_root = Path(".test_runs") / make_id("packcontractstatic")
    orchestrator = build_orchestrator(_make_config(run_root))
    seed = build_smart_contract_seed(
        idea_text="Benchmark the contract with bounded static analysis and parser-to-surface cross-checks.",
        contract_code="""
pragma solidity ^0.8.20;
contract Vault {
    address public owner;
    constructor() { owner = msg.sender; }
    function deposit() external payable {}
    function withdraw(uint256 amount) external {
        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok, "send failed");
    }
}
""".strip(),
        language="solidity",
        source_label="contracts/Vault.sol",
    )

    session = orchestrator.run_session(
        seed_text=seed,
        author="contract-pack-test",
        experiment_pack_name="contract_static_benchmark_pack",
    )

    assert session.selected_pack_name == "contract_static_benchmark_pack"
    assert "contract_static_benchmark_pack:parse_outline" in session.executed_pack_steps
    assert "contract_static_benchmark_pack:surface_mapping" in session.executed_pack_steps
    assert any(job.tool_name == "contract_parser_tool" for job in session.jobs)
    assert any(job.tool_name == "contract_surface_tool" for job in session.jobs)
    assert session.report is not None
    assert session.report.contract_benchmark_pack_summary
    assert session.report.confidence_rationale


def test_explicit_repo_casebook_benchmark_pack_runs_inventory_and_repo_casebook(tmp_path: Path) -> None:
    run_root = Path(".test_runs") / make_id("packcontractrepo")
    orchestrator = build_orchestrator(_make_config(run_root))
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir(parents=True)
    source_path = contracts_dir / "Proxy.sol"
    source_path.write_text(
        """
pragma solidity ^0.8.24;
import "./ProxyLogic.sol";
contract Proxy {
    ProxyLogic public logic;
    function upgradeTo(address newImplementation) external {
        logic = ProxyLogic(newImplementation);
    }
}
""".strip(),
        encoding="utf-8",
    )
    (contracts_dir / "ProxyLogic.sol").write_text(
        """
pragma solidity ^0.8.24;
contract ProxyLogic {
    function delegate(bytes calldata payload) external returns (bytes memory) {
        (bool ok, bytes memory out) = address(this).delegatecall(payload);
        require(ok, "delegate");
        return out;
    }
}
""".strip(),
        encoding="utf-8",
    )
    seed = build_smart_contract_seed(
        idea_text="Benchmark the scoped repository for proxy upgrade, delegatecall, and storage review lanes.",
        contract_code=source_path.read_text(encoding="utf-8"),
        language="solidity",
        source_label=str(source_path),
        contract_root=str(contracts_dir),
    )

    session = orchestrator.run_session(
        seed_text=seed,
        author="repo-pack-test",
        experiment_pack_name="repo_casebook_benchmark_pack",
    )

    assert session.selected_pack_name == "repo_casebook_benchmark_pack"
    assert "repo_casebook_benchmark_pack:inventory_scope" in session.executed_pack_steps
    assert "repo_casebook_benchmark_pack:repo_casebook_match" in session.executed_pack_steps
    assert any(job.tool_name == "contract_inventory_tool" for job in session.jobs)
    assert any(job.tool_name == "contract_testbed_tool" for job in session.jobs)
    assert session.report is not None
    assert session.report.contract_benchmark_pack_summary
    assert session.report.contract_benchmark_case_summaries
    assert any(
        "repo_upgrade_casebook" in item or "proxy" in item.lower()
        for item in session.report.contract_benchmark_case_summaries
    )


def test_explicit_vault_permission_benchmark_pack_runs_anchored_casebook(tmp_path: Path) -> None:
    run_root = Path(".test_runs") / make_id("packcontractvaultpermission")
    orchestrator = build_orchestrator(_make_config(run_root))
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir(parents=True)
    source_path = contracts_dir / "VaultRouter.sol"
    source_path.write_text(
        """
pragma solidity ^0.8.24;
import "./PermitModule.sol";
import "./VaultAccounting.sol";
contract VaultRouter {
    PermitModule public permits;
    VaultAccounting public vault;
    function depositWithPermit(address owner, uint256 assets, bytes32 r, bytes32 s) external {
        permits.usePermit(owner, assets, r, s);
        vault.deposit(owner, assets);
    }
}
""".strip(),
        encoding="utf-8",
    )
    (contracts_dir / "PermitModule.sol").write_text(
        """
pragma solidity ^0.8.24;
contract PermitModule {
    function usePermit(address owner, uint256 assets, bytes32 r, bytes32 s) external pure {
        owner; assets; r; s;
    }
}
""".strip(),
        encoding="utf-8",
    )
    (contracts_dir / "VaultAccounting.sol").write_text(
        """
pragma solidity ^0.8.24;
contract VaultAccounting {
    mapping(address => uint256) public shares;
    function deposit(address owner, uint256 assets) external {
        shares[owner] += assets;
    }
}
""".strip(),
        encoding="utf-8",
    )
    seed = build_smart_contract_seed(
        idea_text="Benchmark the scoped repository for permit, allowance, vault share accounting, and redeem review lanes.",
        contract_code=source_path.read_text(encoding="utf-8"),
        language="solidity",
        source_label=str(source_path),
        contract_root=str(contracts_dir),
    )

    session = orchestrator.run_session(
        seed_text=seed,
        author="vault-permission-pack-test",
        experiment_pack_name="vault_permission_benchmark_pack",
    )

    assert session.selected_pack_name == "vault_permission_benchmark_pack"
    assert "vault_permission_benchmark_pack:vault_casebook_match" in session.executed_pack_steps
    assert any(job.tool_name == "contract_inventory_tool" for job in session.jobs)
    assert any(job.tool_name == "contract_testbed_tool" for job in session.jobs)
    assert session.report is not None
    assert any(
        "repo_vault_permission_casebook" in item for item in session.report.contract_benchmark_pack_summary
    )


def test_explicit_stablecoin_collateral_benchmark_pack_runs_anchored_casebook(tmp_path: Path) -> None:
    run_root = Path(".test_runs") / make_id("packcontractstablecoin")
    orchestrator = build_orchestrator(_make_config(run_root))
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir(parents=True)
    source_path = contracts_dir / "MintController.sol"
    source_path.write_text(
        """
pragma solidity ^0.8.24;
import "./OracleAdapter.sol";
import "./DebtBook.sol";
contract MintController {
    OracleAdapter public oracle;
    DebtBook public debtBook;
    function mintAgainstCollateral(uint256 amount) external {
        require(oracle.latestPrice() > 0, "price");
        debtBook.mint(msg.sender, amount);
    }
    function liquidate(address account) external {
        debtBook.liquidate(account);
    }
}
""".strip(),
        encoding="utf-8",
    )
    (contracts_dir / "OracleAdapter.sol").write_text(
        """
pragma solidity ^0.8.24;
contract OracleAdapter {
    uint256 public price;
    function latestPrice() external view returns (uint256) {
        return price;
    }
}
""".strip(),
        encoding="utf-8",
    )
    (contracts_dir / "DebtBook.sol").write_text(
        """
pragma solidity ^0.8.24;
contract DebtBook {
    mapping(address => uint256) public debt;
    function mint(address account, uint256 amount) external {
        debt[account] += amount;
    }
    function liquidate(address account) external {
        debt[account] = 0;
    }
}
""".strip(),
        encoding="utf-8",
    )
    seed = build_smart_contract_seed(
        idea_text="Benchmark the scoped repository for stablecoin mint, reserve buffer, redemption, collateral, and liquidation review lanes.",
        contract_code=source_path.read_text(encoding="utf-8"),
        language="solidity",
        source_label=str(source_path),
        contract_root=str(contracts_dir),
    )

    session = orchestrator.run_session(
        seed_text=seed,
        author="stablecoin-pack-test",
        experiment_pack_name="stablecoin_collateral_benchmark_pack",
    )

    assert session.selected_pack_name == "stablecoin_collateral_benchmark_pack"
    assert "stablecoin_collateral_benchmark_pack:stablecoin_casebook_match" in session.executed_pack_steps
    assert any(job.tool_name == "contract_inventory_tool" for job in session.jobs)
    assert any(job.tool_name == "contract_testbed_tool" for job in session.jobs)
    assert session.report is not None
    assert any(
        "repo_stablecoin_collateral_casebook" in item for item in session.report.contract_benchmark_pack_summary
    )
    assert any(
        "stablecoin and collateral archetype" in item.lower()
        for item in session.report.contract_casebook_case_studies
    )


def test_explicit_amm_liquidity_benchmark_pack_runs_anchored_casebook(tmp_path: Path) -> None:
    run_root = Path(".test_runs") / make_id("packcontractamm")
    orchestrator = build_orchestrator(_make_config(run_root))
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir(parents=True)
    source_path = contracts_dir / "Router.sol"
    source_path.write_text(
        """
pragma solidity ^0.8.24;
import "./Pool.sol";
contract Router {
    Pool public pool;
    function swapExactInput(uint256 amountIn) external {
        pool.swap(amountIn, 0);
    }
}
""".strip(),
        encoding="utf-8",
    )
    (contracts_dir / "Pool.sol").write_text(
        """
pragma solidity ^0.8.24;
contract Pool {
    uint256 public reserve0;
    uint256 public reserve1;
    function swap(uint256 amountIn, uint256 minOut) external {
        uint256 amountOut = reserve0 == 0 ? amountIn : (amountIn * reserve1) / reserve0;
        require(amountOut >= minOut, "slippage");
        reserve0 += amountIn;
        (bool ok,) = msg.sender.call{value: amountOut}("");
        require(ok, "swap");
        reserve1 -= amountOut;
    }
}
""".strip(),
        encoding="utf-8",
    )
    seed = build_smart_contract_seed(
        idea_text="Benchmark the scoped repository for AMM swap, liquidity, reserve, fee growth, router, and TWAP review lanes.",
        contract_code=source_path.read_text(encoding="utf-8"),
        language="solidity",
        source_label=str(source_path),
        contract_root=str(contracts_dir),
    )

    session = orchestrator.run_session(
        seed_text=seed,
        author="amm-pack-test",
        experiment_pack_name="amm_liquidity_benchmark_pack",
    )

    assert session.selected_pack_name == "amm_liquidity_benchmark_pack"
    assert "amm_liquidity_benchmark_pack:amm_casebook_match" in session.executed_pack_steps
    assert any(job.tool_name == "contract_inventory_tool" for job in session.jobs)
    assert any(job.tool_name == "contract_testbed_tool" for job in session.jobs)
    assert session.report is not None
    assert any("repo_amm_liquidity_casebook" in item for item in session.report.contract_benchmark_pack_summary)
    assert any("amm and liquidity archetype" in item.lower() for item in session.report.contract_casebook_case_studies)


def test_explicit_bridge_custody_benchmark_pack_runs_anchored_casebook(tmp_path: Path) -> None:
    run_root = Path(".test_runs") / make_id("packcontractbridge")
    orchestrator = build_orchestrator(_make_config(run_root))
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir(parents=True)
    source_path = contracts_dir / "BridgePortal.sol"
    source_path.write_text(
        """
pragma solidity ^0.8.24;
import "./CustodyVault.sol";
contract BridgePortal {
    CustodyVault public custody;
    function finalizeWithdrawal(address payable recipient, uint256 amount) external {
        custody.release(recipient, amount);
    }
}
""".strip(),
        encoding="utf-8",
    )
    (contracts_dir / "CustodyVault.sol").write_text(
        """
pragma solidity ^0.8.24;
contract CustodyVault {
    function release(address payable recipient, uint256 amount) external {
        (bool ok,) = recipient.call{value: amount}("");
        require(ok, "release");
        amount;
    }
}
""".strip(),
        encoding="utf-8",
    )
    seed = build_smart_contract_seed(
        idea_text="Benchmark the scoped repository for bridge custody, relay validation, replay protection, and finalize-withdrawal review lanes.",
        contract_code=source_path.read_text(encoding="utf-8"),
        language="solidity",
        source_label=str(source_path),
        contract_root=str(contracts_dir),
    )

    session = orchestrator.run_session(
        seed_text=seed,
        author="bridge-pack-test",
        experiment_pack_name="bridge_custody_benchmark_pack",
    )

    assert session.selected_pack_name == "bridge_custody_benchmark_pack"
    assert "bridge_custody_benchmark_pack:bridge_casebook_match" in session.executed_pack_steps
    assert any(job.tool_name == "contract_inventory_tool" for job in session.jobs)
    assert any(job.tool_name == "contract_testbed_tool" for job in session.jobs)
    assert session.report is not None
    assert any("repo_bridge_custody_casebook" in item for item in session.report.contract_benchmark_pack_summary)
    assert any("bridge and custody archetype" in item.lower() for item in session.report.contract_casebook_case_studies)


def test_explicit_staking_rebase_benchmark_pack_runs_anchored_casebook(tmp_path: Path) -> None:
    run_root = Path(".test_runs") / make_id("packcontractstaking")
    orchestrator = build_orchestrator(_make_config(run_root))
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir(parents=True)
    source_path = contracts_dir / "StakingPool.sol"
    source_path.write_text(
        """
pragma solidity ^0.8.24;
contract StakingPool {
    uint256 public rebaseIndex;
    function rebase(uint256 delta) external {
        rebaseIndex += delta;
    }
}
""".strip(),
        encoding="utf-8",
    )
    seed = build_smart_contract_seed(
        idea_text="Benchmark the scoped repository for staking, rebase, validator rewards, slash handling, and withdrawal queue review lanes.",
        contract_code=source_path.read_text(encoding="utf-8"),
        language="solidity",
        source_label=str(source_path),
        contract_root=str(contracts_dir),
    )

    session = orchestrator.run_session(
        seed_text=seed,
        author="staking-pack-test",
        experiment_pack_name="staking_rebase_benchmark_pack",
    )

    assert session.selected_pack_name == "staking_rebase_benchmark_pack"
    assert "staking_rebase_benchmark_pack:staking_casebook_match" in session.executed_pack_steps
    assert any(job.tool_name == "contract_inventory_tool" for job in session.jobs)
    assert any(job.tool_name == "contract_testbed_tool" for job in session.jobs)
    assert session.report is not None
    assert any("repo_staking_rebase_casebook" in item for item in session.report.contract_benchmark_pack_summary)
    assert any("staking and rebase archetype" in item.lower() for item in session.report.contract_casebook_case_studies)


def test_explicit_keeper_auction_benchmark_pack_runs_anchored_casebook(tmp_path: Path) -> None:
    run_root = Path(".test_runs") / make_id("packcontractkeeper")
    orchestrator = build_orchestrator(_make_config(run_root))
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir(parents=True)
    source_path = contracts_dir / "LiquidationManager.sol"
    source_path.write_text(
        """
pragma solidity ^0.8.24;
import "./AuctionHouse.sol";
contract LiquidationManager {
    AuctionHouse public auctionHouse;
    function startAuction(address account, uint256 debt) external {
        auctionHouse.start(account, debt);
    }
}
""".strip(),
        encoding="utf-8",
    )
    (contracts_dir / "AuctionHouse.sol").write_text(
        """
pragma solidity ^0.8.24;
contract AuctionHouse {
    mapping(address => uint256) public activeDebt;
    function start(address account, uint256 debt) external {
        activeDebt[account] = debt;
    }
    function settle(address payable keeper, address account, uint256 reward) external {
        (bool ok,) = keeper.call{value: reward}("");
        require(ok, "settle");
        activeDebt[account] = 0;
    }
}
""".strip(),
        encoding="utf-8",
    )
    seed = build_smart_contract_seed(
        idea_text="Benchmark the scoped repository for keeper reward, auction settlement, liquidation bids, and oracle freshness review lanes.",
        contract_code=source_path.read_text(encoding="utf-8"),
        language="solidity",
        source_label=str(source_path),
        contract_root=str(contracts_dir),
    )

    session = orchestrator.run_session(
        seed_text=seed,
        author="keeper-pack-test",
        experiment_pack_name="keeper_auction_benchmark_pack",
    )

    assert session.selected_pack_name == "keeper_auction_benchmark_pack"
    assert "keeper_auction_benchmark_pack:keeper_casebook_match" in session.executed_pack_steps
    assert session.report is not None
    assert any("repo_keeper_auction_casebook" in item for item in session.report.contract_benchmark_pack_summary)
    assert any("keeper and auction archetype" in item.lower() for item in session.report.contract_casebook_case_studies)


def test_explicit_treasury_vesting_benchmark_pack_runs_anchored_casebook(tmp_path: Path) -> None:
    run_root = Path(".test_runs") / make_id("packcontracttreasury")
    orchestrator = build_orchestrator(_make_config(run_root))
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir(parents=True)
    source_path = contracts_dir / "Treasury.sol"
    source_path.write_text(
        """
pragma solidity ^0.8.24;
import "./VestingVault.sol";
contract Treasury {
    VestingVault public vesting;
    function releaseVested(address beneficiary) external {
        vesting.release(beneficiary);
    }
}
""".strip(),
        encoding="utf-8",
    )
    (contracts_dir / "VestingVault.sol").write_text(
        """
pragma solidity ^0.8.24;
contract VestingVault {
    mapping(address => uint256) public releasable;
    function release(address beneficiary) external {
        uint256 amount = releasable[beneficiary];
        (bool ok,) = payable(beneficiary).call{value: amount}("");
        require(ok, "release");
        releasable[beneficiary] = 0;
    }
}
""".strip(),
        encoding="utf-8",
    )
    seed = build_smart_contract_seed(
        idea_text="Benchmark the scoped repository for treasury release, vesting schedule, beneficiary payout, and timelock-controlled sweep review lanes.",
        contract_code=source_path.read_text(encoding="utf-8"),
        language="solidity",
        source_label=str(source_path),
        contract_root=str(contracts_dir),
    )

    session = orchestrator.run_session(
        seed_text=seed,
        author="treasury-pack-test",
        experiment_pack_name="treasury_vesting_benchmark_pack",
    )

    assert session.selected_pack_name == "treasury_vesting_benchmark_pack"
    assert "treasury_vesting_benchmark_pack:treasury_casebook_match" in session.executed_pack_steps
    assert session.report is not None
    assert any("repo_treasury_vesting_casebook" in item for item in session.report.contract_benchmark_pack_summary)
    assert any("treasury and vesting archetype" in item.lower() for item in session.report.contract_casebook_case_studies)


def test_explicit_insurance_recovery_benchmark_pack_runs_anchored_casebook(tmp_path: Path) -> None:
    run_root = Path(".test_runs") / make_id("packcontractinsurance")
    orchestrator = build_orchestrator(_make_config(run_root))
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir(parents=True)
    source_path = contracts_dir / "InsuranceFund.sol"
    source_path.write_text(
        """
pragma solidity ^0.8.24;
contract InsuranceFund {
    uint256 public reserves;
    function absorbDeficit(uint256 amount) external {
        reserves -= amount;
    }
}
""".strip(),
        encoding="utf-8",
    )
    seed = build_smart_contract_seed(
        idea_text="Benchmark the scoped repository for insurance fund depletion, deficit absorption, reserve recovery, and emergency-settlement review lanes.",
        contract_code=source_path.read_text(encoding="utf-8"),
        language="solidity",
        source_label=str(source_path),
        contract_root=str(contracts_dir),
    )

    session = orchestrator.run_session(
        seed_text=seed,
        author="insurance-pack-test",
        experiment_pack_name="insurance_recovery_benchmark_pack",
    )

    assert session.selected_pack_name == "insurance_recovery_benchmark_pack"
    assert "insurance_recovery_benchmark_pack:insurance_casebook_match" in session.executed_pack_steps
    assert session.report is not None
    assert any("repo_insurance_recovery_casebook" in item for item in session.report.contract_benchmark_pack_summary)
    assert any("insurance and recovery archetype" in item.lower() for item in session.report.contract_casebook_case_studies)
