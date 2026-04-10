from __future__ import annotations

import json
import subprocess
from pathlib import Path

import app.compute.runners.contract_compile_runner as contract_compile_runner_module
import app.compute.runners.echidna_runner as echidna_runner_module
import app.compute.runners.foundry_runner as foundry_runner_module
import app.compute.runners.slither_runner as slither_runner_module
from app.config import AppConfig
from app.core.planning_helpers import determine_target_kind, select_smart_contract_testbed_reference
from app.core.seed_parsing import (
    build_smart_contract_seed,
    extract_contract_code,
    extract_contract_language,
    extract_contract_name,
    extract_contract_root,
    extract_contract_source_label,
    infer_contract_root_from_source_path,
)
from app.main import build_orchestrator, build_parser
from app.tools.builtin import (
    ContractInventoryTool,
    ContractParserTool,
    ContractPatternCheckTool,
    ContractSurfaceTool,
)
from app.tools.smart_contract_utils import infer_contract_language
from app.types import make_id

SAMPLE_CONTRACT = """
pragma solidity ^0.8.20;

contract Vault {
    address public owner;
    mapping(address => uint256) public balances;

    modifier onlyOwner() {
        require(msg.sender == owner, "owner");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }

    function withdraw(uint256 amount) external {
        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok, "send failed");
        balances[msg.sender] -= amount;
    }

    function adminSetOwner(address newOwner) external {
        owner = newOwner;
    }

    function destroy(address payable target) external {
        selfdestruct(target);
    }
}
""".strip()

VYPER_SAMPLE = """
# @version ^0.3.10

owner: public(address)

@external
def __init__():
    self.owner = msg.sender
""".strip()


def test_smart_contract_seed_helpers_extract_contract_context() -> None:
    seed = build_smart_contract_seed(
        idea_text="Audit the contract for externally reachable risk surfaces.",
        contract_code=SAMPLE_CONTRACT,
        language="solidity",
        source_label="contracts/Vault.sol",
        contract_root="contracts",
    )

    assert extract_contract_language(seed) == "solidity"
    assert extract_contract_source_label(seed) == "contracts/Vault.sol"
    assert extract_contract_root(seed) == "contracts"
    assert "contract Vault" in (extract_contract_code(seed) or "")
    assert extract_contract_name(seed) == "Vault"
    assert determine_target_kind(
        seed_text=seed,
        planned_test="parse and inspect contract surfaces",
        summary="Audit contract review surfaces",
    ) == "smart_contract"


def test_infer_contract_root_from_source_path_prefers_bounded_contract_scope(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    contracts_dir = repo_root / "contracts"
    modules_dir = contracts_dir / "modules"
    modules_dir.mkdir(parents=True)
    source_path = modules_dir / "Vault.sol"
    source_path.write_text(
        "pragma solidity ^0.8.20; contract Vault {}",
        encoding="utf-8",
    )
    (contracts_dir / "Proxy.sol").write_text(
        "pragma solidity ^0.8.20; contract Proxy {}",
        encoding="utf-8",
    )

    inferred_root = infer_contract_root_from_source_path(str(source_path))

    assert inferred_root is not None
    assert Path(inferred_root).resolve() == contracts_dir.resolve()


def test_contract_inventory_tool_builds_bounded_repo_inventory(tmp_path: Path) -> None:
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir(parents=True)
    (contracts_dir / "SharedBase.sol").write_text(
        """
pragma solidity ^0.8.20;
contract SharedBase { address internal owner; }
""".strip(),
        encoding="utf-8",
    )
    (contracts_dir / "Vault.sol").write_text(
        """
pragma solidity ^0.8.20;
import "./SharedBase.sol";
contract Vault is SharedBase { function deposit() external payable {} function withdraw(uint256 amount) external {} }
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
    (contracts_dir / "Proxy.sol").write_text(
        """
pragma solidity ^0.8.24;
import "./SharedBase.sol";
import "./ProxyLogic.sol";
contract Proxy is SharedBase { ProxyLogic public logic; }
""".strip(),
        encoding="utf-8",
    )
    tool = ContractInventoryTool()
    payload = tool.validate_payload({"root_path": str(contracts_dir)})
    result = tool.run(payload)

    assert result["status"] == "ok"
    assert result["result_data"]["recognized"] is True
    assert result["result_data"]["file_count"] == 4
    assert result["result_data"]["first_party_file_count"] == 4
    assert result["result_data"]["dependency_file_count"] == 0
    assert result["result_data"]["solidity_file_count"] == 4
    assert any(item.startswith("solidity ^0.8.20") for item in result["result_data"]["pragma_summary"])
    assert any(item.endswith("Vault.sol") for item in result["result_data"]["candidate_files"])
    assert any(item.endswith("Vault.sol") for item in result["result_data"]["entrypoint_candidates"])
    assert any(item.endswith("Proxy.sol") for item in result["result_data"]["entrypoint_candidates"])
    assert any("SharedBase.sol" in item for item in result["result_data"]["shared_dependency_files"])
    assert any("local import edges=" in item for item in result["result_data"]["import_graph_summary"])
    assert any("Proxy.sol -> ProxyLogic.sol" in item for item in result["result_data"]["entrypoint_flow_summaries"])
    assert any("Proxy.sol -> ProxyLogic.sol => delegatecall" in item for item in result["result_data"]["entrypoint_review_lanes"])
    assert any("Proxy.sol => delegatecall via ProxyLogic.sol" in item for item in result["result_data"]["risk_family_lane_summaries"])
    assert any("Vault.sol => withdraw/claim" in item for item in result["result_data"]["entrypoint_function_family_priorities"])
    assert any("Proxy.sol => proxy/storage via ProxyLogic.sol" in item for item in result["result_data"]["entrypoint_function_family_priorities"])
    assert any("ProxyLogic.sol [delegatecall]" in item for item in result["result_data"]["risk_linked_files"])
    assert "multi_file_repo_surface_present" not in result["result_data"]["issues"]
    assert "repo_local_import_graph_present" in result["result_data"]["issues"]
    assert "multiple_entrypoint_candidates_present" in result["result_data"]["issues"]
    assert "shared_dependency_hub_present" in result["result_data"]["issues"]
    assert "entrypoint_dependency_flow_present" in result["result_data"]["issues"]
    assert "entrypoint_risk_lane_present" in result["result_data"]["issues"]
    assert "entrypoint_risk_family_lane_present" in result["result_data"]["issues"]
    assert "entrypoint_function_family_priority_present" in result["result_data"]["issues"]
    assert "repo_risk_linked_files_present" in result["result_data"]["issues"]


def test_contract_inventory_tool_separates_first_party_and_dependency_scope(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    contracts_dir = repo_root / "contracts"
    lib_dir = repo_root / "lib" / "openzeppelin"
    contracts_dir.mkdir(parents=True)
    lib_dir.mkdir(parents=True)
    (contracts_dir / "Vault.sol").write_text(
        """
pragma solidity ^0.8.24;
import "../lib/openzeppelin/UpgradeLib.sol";
contract Vault {
    function upgrade(address implementation) external {
        UpgradeLib.upgrade(implementation);
    }
}
""".strip(),
        encoding="utf-8",
    )
    (contracts_dir / "Treasury.sol").write_text(
        """
pragma solidity ^0.8.24;
import "../lib/openzeppelin/UpgradeLib.sol";
contract Treasury {
    function setImplementation(address implementation) external {
        UpgradeLib.upgrade(implementation);
    }
}
""".strip(),
        encoding="utf-8",
    )
    (lib_dir / "UpgradeLib.sol").write_text(
        """
pragma solidity ^0.8.24;
library UpgradeLib {
    function upgrade(address implementation) internal {
        bytes memory payload = abi.encodeWithSignature("version()");
        implementation.delegatecall(payload);
    }
}
""".strip(),
        encoding="utf-8",
    )
    tool = ContractInventoryTool()
    payload = tool.validate_payload({"root_path": str(repo_root)})
    result = tool.run(payload)

    assert result["status"] == "ok"
    assert result["result_data"]["file_count"] == 3
    assert result["result_data"]["first_party_file_count"] == 2
    assert result["result_data"]["dependency_file_count"] == 1
    assert result["result_data"]["candidate_files"] == ["contracts/Treasury.sol", "contracts/Vault.sol"]
    assert result["result_data"]["dependency_candidate_files"] == ["lib/openzeppelin/UpgradeLib.sol"]
    assert result["result_data"]["first_party_dependency_edges"] == 2
    assert any("scope split=first-party:2 dependency:1" in item for item in result["result_data"]["import_graph_summary"])
    assert any("first-party -> dependency edges=2" in item for item in result["result_data"]["import_graph_summary"])
    assert any("UpgradeLib.sol" in item for item in result["result_data"]["shared_dependency_files"])
    assert any("UpgradeLib.sol [delegatecall" in item or "UpgradeLib.sol [upgrade" in item for item in result["result_data"]["dependency_review_files"])
    assert "dependency_contract_files_present" in result["result_data"]["issues"]
    assert "first_party_dependency_edges_present" in result["result_data"]["issues"]
    assert "dependency_review_surface_present" in result["result_data"]["issues"]


def test_contract_inventory_tool_builds_protocol_accounting_review_lanes(tmp_path: Path) -> None:
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir(parents=True)
    (contracts_dir / "LendingPool.sol").write_text(
        """
pragma solidity ^0.8.20;
import "./DebtLedger.sol";
import "./FeeController.sol";
contract LendingPool {
    DebtLedger public ledger;
    FeeController public fees;
    function borrow(uint256 amount) external { ledger.accrueDebt(msg.sender, amount); }
    function skimProtocolFees(address payable treasury, uint256 amount) external { fees.skimProtocolFee(treasury, amount); }
}
""".strip(),
        encoding="utf-8",
    )
    (contracts_dir / "DebtLedger.sol").write_text(
        """
pragma solidity ^0.8.20;
contract DebtLedger {
    mapping(address => uint256) public debt;
    uint256 public totalDebt;
    function accrueDebt(address account, uint256 amount) external {
        debt[account] += amount;
        totalDebt += amount;
    }
}
""".strip(),
        encoding="utf-8",
    )
    (contracts_dir / "FeeController.sol").write_text(
        """
pragma solidity ^0.8.20;
contract FeeController {
    uint256 public protocolReserves;
    function skimProtocolFee(address payable treasury, uint256 amount) external {
        (bool ok,) = treasury.call{value: amount}("");
        require(ok, "send failed");
    }
}
""".strip(),
        encoding="utf-8",
    )
    tool = ContractInventoryTool()
    payload = tool.validate_payload({"root_path": str(contracts_dir)})
    result = tool.run(payload)

    assert result["status"] == "ok"
    assert any(
        "LendingPool.sol" in item and "fee/reserve/debt" in item
        for item in result["result_data"]["entrypoint_function_family_priorities"]
    )
    assert any(
        "LendingPool.sol => protocol-fee, debt via DebtLedger.sol" in item
        for item in result["result_data"]["risk_family_lane_summaries"]
    )
    assert any(
        "FeeController.sol [protocol-fee]" in item or "DebtLedger.sol [debt]" in item
        for item in result["result_data"]["risk_linked_files"]
    )


def test_contract_testbed_selection_prefers_specific_accounting_cues_over_generic_hints() -> None:
    selected = select_smart_contract_testbed_reference(
        text="Review balance accounting, claim-state ordering, and withdrawal-order consistency around external value flow.",
        preferred_testbeds={"access_control_corpus"},
    )

    assert selected in {"accounting_review_corpus", "asset_flow_corpus", "state_machine_corpus"}
    assert selected != "access_control_corpus"


def test_contract_testbed_selection_prefers_repo_casebook_over_generic_hints_for_repo_scope() -> None:
    selected = select_smart_contract_testbed_reference(
        text="Audit proxy upgrade, delegatecall, and storage-slot review lanes across the scoped codebase.",
        preferred_testbeds={"access_control_corpus"},
        prefer_repo_casebooks=True,
    )

    assert selected == "repo_upgrade_casebook"


def test_contract_testbed_selection_prefers_protocol_accounting_casebook_for_repo_scope() -> None:
    selected = select_smart_contract_testbed_reference(
        text="Audit protocol fee skimming, reserve synchronization, and debt-accounting review lanes across the scoped codebase.",
        preferred_testbeds={"access_control_corpus"},
        prefer_repo_casebooks=True,
    )

    assert selected == "repo_protocol_accounting_casebook"


def test_contract_testbed_selection_prefers_vault_permission_casebook_for_repo_scope() -> None:
    selected = select_smart_contract_testbed_reference(
        text="Audit permit, allowance, vault share accounting, and redeem review lanes across the scoped codebase.",
        preferred_testbeds={"repo_asset_flow_casebook"},
        prefer_repo_casebooks=True,
    )

    assert selected == "repo_vault_permission_casebook"


def test_contract_testbed_selection_prefers_governance_timelock_casebook_for_repo_scope() -> None:
    selected = select_smart_contract_testbed_reference(
        text="Audit governance queue, timelock execution, guardian pause, and queued upgrade review lanes across the scoped codebase.",
        preferred_testbeds={"repo_upgrade_casebook"},
        prefer_repo_casebooks=True,
    )

    assert selected == "repo_governance_timelock_casebook"


def test_contract_testbed_selection_prefers_reward_distribution_casebook_for_repo_scope() -> None:
    selected = select_smart_contract_testbed_reference(
        text="Audit reward index drift, reward debt, emission-rate changes, and reward-claim review lanes across the scoped codebase.",
        preferred_testbeds={"repo_asset_flow_casebook"},
        prefer_repo_casebooks=True,
    )

    assert selected == "repo_rewards_distribution_casebook"


def test_contract_testbed_selection_prefers_stablecoin_collateral_casebook_for_repo_scope() -> None:
    selected = select_smart_contract_testbed_reference(
        text="Audit stablecoin mint-against-collateral, redemption buffer, peg, reserve, and liquidation review lanes across the scoped codebase.",
        preferred_testbeds={"repo_oracle_casebook"},
        prefer_repo_casebooks=True,
    )

    assert selected == "repo_stablecoin_collateral_casebook"


def test_contract_testbed_selection_prefers_amm_liquidity_casebook_for_repo_scope() -> None:
    selected = select_smart_contract_testbed_reference(
        text="Audit AMM swap routing, LP accounting, reserve sync, fee growth, and TWAP review lanes across the scoped codebase.",
        preferred_testbeds={"repo_protocol_accounting_casebook"},
        prefer_repo_casebooks=True,
    )

    assert selected == "repo_amm_liquidity_casebook"


def test_contract_testbed_selection_prefers_bridge_custody_casebook_for_repo_scope() -> None:
    selected = select_smart_contract_testbed_reference(
        text="Audit bridge relay validation, custody release, finalize-withdrawal, proof handling, and replay-protection review lanes across the scoped codebase.",
        preferred_testbeds={"repo_asset_flow_casebook"},
        prefer_repo_casebooks=True,
    )

    assert selected == "repo_bridge_custody_casebook"


def test_contract_testbed_selection_prefers_staking_rebase_casebook_for_repo_scope() -> None:
    selected = select_smart_contract_testbed_reference(
        text="Audit staking, rebase, slash handling, validator rewards, and withdrawal queue review lanes across the scoped codebase.",
        preferred_testbeds={"repo_rewards_distribution_casebook"},
        prefer_repo_casebooks=True,
    )

    assert selected == "repo_staking_rebase_casebook"


def test_contract_testbed_selection_prefers_keeper_auction_casebook_for_repo_scope() -> None:
    selected = select_smart_contract_testbed_reference(
        text="Audit keeper reward, auction settlement, liquidation bid, and oracle freshness review lanes across the scoped codebase.",
        preferred_testbeds={"repo_oracle_casebook"},
        prefer_repo_casebooks=True,
    )

    assert selected == "repo_keeper_auction_casebook"


def test_contract_testbed_selection_prefers_treasury_vesting_casebook_for_repo_scope() -> None:
    selected = select_smart_contract_testbed_reference(
        text="Audit treasury release, vesting schedule, beneficiary payout, and timelock-controlled sweep review lanes across the scoped codebase.",
        preferred_testbeds={"repo_governance_timelock_casebook"},
        prefer_repo_casebooks=True,
    )

    assert selected == "repo_treasury_vesting_casebook"


def test_contract_testbed_selection_prefers_insurance_recovery_casebook_for_repo_scope() -> None:
    selected = select_smart_contract_testbed_reference(
        text="Audit insurance-fund depletion, deficit absorption, reserve recovery, and emergency-settlement review lanes across the scoped codebase.",
        preferred_testbeds={"repo_protocol_accounting_casebook"},
        prefer_repo_casebooks=True,
    )

    assert selected == "repo_insurance_recovery_casebook"


def test_contract_testbed_selection_prefers_collateral_liquidation_cues() -> None:
    selected = select_smart_contract_testbed_reference(
        text="Review collateral ratios, liquidation thresholds, reserve-derived pricing, and health-factor assumptions.",
        preferred_testbeds={"oracle_review_corpus"},
    )

    assert selected == "collateral_liquidation_corpus"


def test_contract_testbed_selection_prefers_reserve_fee_accounting_cues() -> None:
    selected = select_smart_contract_testbed_reference(
        text="Review protocol fee skimming, reserve synchronization, debt accounting, and bad debt accrual assumptions.",
        preferred_testbeds={"oracle_review_corpus"},
    )

    assert selected == "reserve_fee_accounting_corpus"


def test_contract_testbed_selection_prefers_socialized_bad_debt_cues() -> None:
    selected = select_smart_contract_testbed_reference(
        text="Review reserve buffer, insurance fund, and bad debt socialization assumptions across the protocol.",
        preferred_testbeds={"oracle_review_corpus"},
    )

    assert selected == "reserve_fee_accounting_corpus"


def test_contract_testbed_selection_prefers_liquidation_fee_cues() -> None:
    selected = select_smart_contract_testbed_reference(
        text="Review liquidation bonus, keeper fee, and liquidation fee assumptions around collateralized liquidations.",
        preferred_testbeds={"oracle_review_corpus"},
    )

    assert selected == "collateral_liquidation_corpus"


def test_contract_parser_tool_builds_outline() -> None:
    tool = ContractParserTool()
    payload = tool.validate_payload({"contract_code": SAMPLE_CONTRACT, "language": "solidity"})
    result = tool.run(payload)

    assert result["status"] == "ok"
    assert result["result_data"]["parsed"] is True
    assert result["result_data"]["contract_names"] == ["Vault"]
    assert "withdraw" in result["result_data"]["function_names"]
    assert result["result_data"]["constructor_present"] is True


def test_contract_pattern_tool_does_not_treat_echidna_properties_as_admin_surfaces() -> None:
    tool = ContractPatternCheckTool()
    payload = tool.validate_payload(
        {
            "contract_code": """
pragma solidity ^0.8.20;
contract VaultHarness {
    address public owner;
    function setOwner(address newOwner) external { owner = newOwner; }
    function echidna_owner_is_not_zero() public returns (bool) { return owner != address(0); }
}
""".strip(),
            "language": "solidity",
        }
    )
    result = tool.run(payload)
    issues = result["result_data"]["issues"]

    assert "unguarded_admin_surface:setOwner" in issues
    assert "unguarded_admin_surface:echidna_owner_is_not_zero" not in issues


def test_contract_language_is_inferred_from_source_or_code() -> None:
    assert infer_contract_language(source_label="contracts/Vault.sol", hinted_language=None) == "solidity"
    assert infer_contract_language(source_label="contracts/Vault.vy", hinted_language=None) == "vyper"
    assert (
        infer_contract_language(
            source_label=None,
            hinted_language=None,
            contract_code=VYPER_SAMPLE,
        )
        == "vyper"
    )


def test_contract_parser_tool_can_infer_vyper_without_explicit_hint() -> None:
    tool = ContractParserTool()
    payload = tool.validate_payload({"contract_code": VYPER_SAMPLE, "source_label": "contracts/Wallet.vy"})
    result = tool.run(payload)

    assert result["status"] == "ok"
    assert result["result_data"]["language"] == "vyper"
    assert result["result_data"]["parsed"] is True


def test_contract_surface_tool_finds_public_payable_and_low_level_surfaces() -> None:
    tool = ContractSurfaceTool()
    payload = tool.validate_payload({"contract_code": SAMPLE_CONTRACT, "language": "solidity"})
    result = tool.run(payload)

    assert result["result_data"]["recognized"] is True
    assert "deposit" in result["result_data"]["payable_functions"]
    assert "withdraw" in result["result_data"]["low_level_call_functions"]
    assert "withdraw" in result["result_data"]["call_with_value_functions"]
    assert "low_level_call_surface_present" in result["result_data"]["issues"]
    assert "value_transfer_surface_present" in result["result_data"]["issues"]


def test_contract_surface_tool_reports_token_and_assembly_surfaces() -> None:
    tool = ContractSurfaceTool()
    payload = tool.validate_payload(
        {
            "contract_code": """
pragma solidity ^0.8.20;
interface IERC20 { function transfer(address to, uint256 amount) external returns (bool); }

contract TokenAssemblySurface {
    function sweep(address token, address to, uint256 amount) external {
        IERC20(token).transfer(to, amount);
    }

    function rawStore(address newOwner) external {
        assembly {
            sstore(0, newOwner)
        }
    }
}
""".strip(),
            "language": "solidity",
        }
    )
    result = tool.run(payload)

    assert "sweep" in result["result_data"]["token_transfer_functions"]
    assert "rawStore" in result["result_data"]["assembly_functions"]
    assert result["result_data"]["low_level_call_functions"] == []
    assert result["result_data"]["call_with_value_functions"] == []
    assert "transfer" not in result["result_data"]["assembly_functions"]
    assert "transferFrom" not in result["result_data"]["assembly_functions"]
    assert "token_transfer_surface_present" in result["result_data"]["issues"]
    assert "assembly_surface_present" in result["result_data"]["issues"]


def test_contract_surface_tool_reports_signature_and_oracle_surfaces() -> None:
    tool = ContractSurfaceTool()
    payload = tool.validate_payload(
        {
            "contract_code": """
pragma solidity ^0.8.20;
interface AggregatorV3Interface {
    function latestRoundData() external view returns (uint80, int256, uint256, uint256, uint80);
}
contract SignatureOracleSurface {
    AggregatorV3Interface public priceFeed;

    function permitAction(bytes32 digest, uint8 v, bytes32 r, bytes32 s) external pure returns (address) {
        return ecrecover(digest, v, r, s);
    }

    function quote() external view returns (int256) {
        (, int256 price,,,) = priceFeed.latestRoundData();
        return price;
    }
}
""".strip(),
            "language": "solidity",
        }
    )
    result = tool.run(payload)

    assert "permitAction" in result["result_data"]["signature_validation_functions"]
    assert "quote" in result["result_data"]["oracle_dependency_functions"]
    assert "signature_validation_surface_present" in result["result_data"]["issues"]
    assert "oracle_dependency_surface_present" in result["result_data"]["issues"]


def test_contract_surface_tool_reports_collateral_and_liquidation_surfaces() -> None:
    tool = ContractSurfaceTool()
    payload = tool.validate_payload(
        {
            "contract_code": """
pragma solidity ^0.8.20;
interface AggregatorV3Interface {
    function latestRoundData() external view returns (uint80, int256, uint256, uint256, uint80);
}
interface IPair { function getReserves() external view returns (uint112, uint112, uint32); }
contract CollateralLiquidationSurface {
    AggregatorV3Interface public priceFeed;

    function collateralRatio(address pair) external view returns (uint256) {
        (uint112 reserve0, uint112 reserve1,) = IPair(pair).getReserves();
        return uint256(reserve1) * 1e18 / uint256(reserve0);
    }

    function liquidate(address account) external {
        (, int256 price,,,) = priceFeed.latestRoundData();
        if (account != address(0) && price > 0) {}
    }
}
""".strip(),
            "language": "solidity",
        }
    )
    result = tool.run(payload)

    assert "collateralRatio" in result["result_data"]["collateral_management_functions"]
    assert "liquidate" in result["result_data"]["liquidation_functions"]
    assert "collateralRatio" in result["result_data"]["reserve_dependency_functions"]
    assert "collateral_management_surface_present" in result["result_data"]["issues"]
    assert "liquidation_surface_present" in result["result_data"]["issues"]
    assert "reserve_dependency_surface_present" in result["result_data"]["issues"]


def test_contract_surface_tool_reports_accounting_surfaces() -> None:
    tool = ContractSurfaceTool()
    payload = tool.validate_payload(
        {
            "contract_code": """
pragma solidity ^0.8.20;
contract AccountingSurface {
    mapping(address => uint256) public balances;
    mapping(address => bool) public claimed;

    function withdraw(uint256 amount) external {
        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok, "send failed");
        balances[msg.sender] -= amount;
    }

    function claim() external {
        claimed[msg.sender] = true;
    }
}
""".strip(),
            "language": "solidity",
        }
    )
    result = tool.run(payload)

    assert "withdraw" in result["result_data"]["accounting_mutation_functions"]
    assert "claim" in result["result_data"]["accounting_mutation_functions"]
    assert "accounting_surface_present" in result["result_data"]["issues"]


def test_contract_surface_tool_reports_proxy_and_storage_surfaces() -> None:
    tool = ContractSurfaceTool()
    payload = tool.validate_payload(
        {
            "contract_code": """
pragma solidity ^0.8.20;
contract ProxySurface {
    address public implementation;
    bytes32 internal constant _IMPLEMENTATION_SLOT = bytes32(uint256(keccak256("eip1967.proxy.implementation")) - 1);
    uint256[50] private __gap;

    fallback() external payable {
        address impl = implementation;
        (bool ok,) = impl.delegatecall(msg.data);
        require(ok, "delegate failed");
    }

    function upgradeTo(address newImplementation) external {
        assembly {
            sstore(_IMPLEMENTATION_SLOT, newImplementation)
        }
    }
}
""".strip(),
            "language": "solidity",
        }
    )
    result = tool.run(payload)

    assert "fallback" in result["result_data"]["proxy_delegatecall_functions"]
    assert "upgradeTo" in result["result_data"]["storage_slot_write_functions"]
    assert "upgradeTo" in result["result_data"]["implementation_reference_functions"]
    assert result["result_data"]["implementation_slot_constant_present"] is True
    assert result["result_data"]["storage_gap_present"] is True
    assert "proxy_delegate_surface_present" in result["result_data"]["issues"]
    assert "storage_slot_write_surface_present" in result["result_data"]["issues"]


def test_contract_surface_tool_reports_authorization_and_pause_surfaces() -> None:
    tool = ContractSurfaceTool()
    payload = tool.validate_payload(
        {
            "contract_code": """
pragma solidity ^0.8.20;
contract AuthorizationSurface {
    mapping(address => bool) public operators;
    bool public paused;

    function grantRole(address operator) external {
        operators[operator] = true;
    }

    function pause() external {
        paused = true;
    }

    function setOperator(address operator, bool enabled) external {
        require(hasRole(msg.sender), "role");
        operators[operator] = enabled;
    }

    function hasRole(address account) internal pure returns (bool) {
        return account != address(0);
    }
}
""".strip(),
            "language": "solidity",
        }
    )
    result = tool.run(payload)

    assert "grantRole" in result["result_data"]["role_management_functions"]
    assert "pause" in result["result_data"]["pause_control_functions"]
    assert "setOperator" in result["result_data"]["role_guarded_functions"]
    assert "role_management_surface_present" in result["result_data"]["issues"]
    assert "pause_control_surface_present" in result["result_data"]["issues"]


def test_contract_surface_tool_reports_asset_flow_surfaces() -> None:
    tool = ContractSurfaceTool()
    payload = tool.validate_payload(
        {
            "contract_code": """
pragma solidity ^0.8.20;
interface IERC20 { function transfer(address to, uint256 amount) external returns (bool); }
contract AssetFlowSurface {
    mapping(address => uint256) public balances;
    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }
    function withdraw(uint256 amount) external {
        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok, "send failed");
        balances[msg.sender] -= amount;
    }
    function sweep(address token, address to, uint256 amount) external {
        IERC20(token).transfer(to, amount);
    }
}
""".strip(),
            "language": "solidity",
        }
    )
    result = tool.run(payload)

    assert "deposit" in result["result_data"]["deposit_like_functions"]
    assert "withdraw" in result["result_data"]["asset_exit_functions"]
    assert "sweep" in result["result_data"]["rescue_or_sweep_functions"]
    assert "deposit_surface_present" in result["result_data"]["issues"]
    assert "asset_exit_surface_present" in result["result_data"]["issues"]
    assert "rescue_or_sweep_surface_present" in result["result_data"]["issues"]


def test_contract_surface_tool_reports_vault_share_surfaces() -> None:
    tool = ContractSurfaceTool()
    payload = tool.validate_payload(
        {
            "contract_code": """
pragma solidity ^0.8.20;
interface IERC20 { function transfer(address to, uint256 amount) external returns (bool); }
interface IERC20In { function transferFrom(address from, address to, uint256 amount) external returns (bool); }
contract VaultShareSurface {
    IERC20 public assetToken;
    mapping(address => uint256) public shares;
    uint256 public totalSupply;
    uint256 public totalAssets;

    function previewDeposit(uint256 assets) public pure returns (uint256) {
        return assets;
    }

    function deposit(uint256 assets) external {
        bool ok = IERC20In(address(assetToken)).transferFrom(msg.sender, address(this), assets);
        require(ok, "transfer failed");
        uint256 mintedShares = previewDeposit(assets);
        shares[msg.sender] += mintedShares;
        totalSupply += mintedShares;
        totalAssets += assets;
    }

    function redeem(uint256 sharesAmount) external {
        require(shares[msg.sender] >= sharesAmount, "insufficient");
        shares[msg.sender] -= sharesAmount;
        totalSupply -= sharesAmount;
        totalAssets -= sharesAmount;
        bool ok = assetToken.transfer(msg.sender, sharesAmount);
        require(ok, "transfer failed");
    }
}
""".strip(),
            "language": "solidity",
        }
    )
    result = tool.run(payload)

    assert "deposit" in result["result_data"]["share_accounting_functions"]
    assert "redeem" in result["result_data"]["share_accounting_functions"]
    assert "previewDeposit" in result["result_data"]["vault_conversion_functions"]
    assert "share_accounting_surface_present" in result["result_data"]["issues"]
    assert "vault_conversion_surface_present" in result["result_data"]["issues"]


def test_contract_pattern_check_tool_flags_bounded_review_signals() -> None:
    tool = ContractPatternCheckTool()
    payload = tool.validate_payload({"contract_code": SAMPLE_CONTRACT, "language": "solidity"})
    result = tool.run(payload)

    issues = result["result_data"]["issues"]
    assert result["status"] == "observed_issue"
    assert result["result_data"]["manual_review_recommended"] is True
    assert "floating_pragma" in issues
    assert "selfdestruct_usage" in issues
    assert any(item.startswith("reentrancy_review_required:withdraw") for item in issues)
    assert any(item.startswith("unguarded_admin_surface:adminSetOwner") for item in issues)
    assert result["result_data"]["issue_family_counts"]["selfdestruct_usage"] == 1
    assert result["result_data"]["highest_priority"] == "high"
    assert result["result_data"]["priority_counts"]["high"] >= 1
    assert any(
        item["issue"].startswith("reentrancy_review_required:withdraw") and item["priority"] == "high"
        for item in result["result_data"]["prioritized_issues"]
    )


def test_contract_pattern_check_tool_flags_upgrade_entropy_and_user_supplied_call_targets() -> None:
    tool = ContractPatternCheckTool()
    payload = tool.validate_payload(
        {
            "contract_code": """
pragma solidity ^0.8.20;

contract UpgradeableLottery {
    address public implementation;

    function upgradeTo(address newImplementation, bytes calldata data) external {
        implementation = newImplementation;
        (bool ok,) = newImplementation.delegatecall(data);
        require(ok, "delegate failed");
    }

    function draw(uint256 upper) external view returns (uint256) {
        return uint256(keccak256(abi.encodePacked(block.timestamp, blockhash(block.number - 1)))) % upper;
    }
}
""".strip(),
            "language": "solidity",
        }
    )
    result = tool.run(payload)

    issues = result["result_data"]["issues"]
    notes = result["result_data"]["notes"]
    assert any(item.startswith("unguarded_upgrade_surface:upgradeTo") for item in issues)
    assert any(item.startswith("user_supplied_delegatecall_target:upgradeTo") for item in issues)
    assert any(item.startswith("user_supplied_call_target:upgradeTo") for item in issues)
    assert any(item.startswith("entropy_source_review_required:draw") for item in issues)
    assert any(item.startswith("time_dependency_review:draw") for item in notes)


def test_contract_pattern_check_tool_flags_token_and_assembly_review_signals() -> None:
    tool = ContractPatternCheckTool()
    payload = tool.validate_payload(
        {
            "contract_code": """
pragma solidity ^0.8.20;
interface IERC20 { function transfer(address to, uint256 amount) external returns (bool); function transferFrom(address from, address to, uint256 amount) external returns (bool); }

contract TokenAndAssemblySurface {
    function sweep(address token, address to, uint256 amount) external {
        IERC20(token).transfer(to, amount);
    }

    function rescue(address token, address from, address to, uint256 amount) external {
        IERC20(token).transferFrom(from, to, amount);
    }

    function rawStore(address newOwner) external {
        assembly {
            sstore(0, newOwner)
        }
    }
}
""".strip(),
            "language": "solidity",
        }
    )
    result = tool.run(payload)

    issues = result["result_data"]["issues"]
    assert any(item.startswith("unchecked_token_transfer_surface:sweep") for item in issues)
    assert any(item.startswith("unchecked_token_transfer_from_surface:rescue") for item in issues)
    assert any(item.startswith("arbitrary_from_transfer_surface:rescue") for item in issues)
    assert any(item.startswith("assembly_review_required:rawStore") for item in issues)


def test_contract_pattern_check_tool_flags_approval_validation_and_state_machine_signals() -> None:
    tool = ContractPatternCheckTool()
    payload = tool.validate_payload(
        {
            "contract_code": """
pragma solidity ^0.8.20;
interface IERC20 { function approve(address spender, uint256 amount) external returns (bool); }

contract ApprovalAndUpgradeSurface {
    address public implementation;
    uint256 public status;

    function approveSpender(address token, address spender, uint256 amount) external {
        IERC20(token).approve(spender, amount);
    }

    function upgradeTo(address newImplementation) external {
        implementation = newImplementation;
    }

    function execute(address target) external {
        (bool ok,) = target.call("");
        require(ok, "call failed");
        status = 2;
    }
}
""".strip(),
            "language": "solidity",
        }
    )
    result = tool.run(payload)

    issues = result["result_data"]["issues"]
    assert any(item.startswith("unchecked_approve_surface:approveSpender") for item in issues)
    assert any(item.startswith("approve_race_review_required:approveSpender") for item in issues)
    assert any(item.startswith("missing_zero_address_validation:upgradeTo") for item in issues)
    assert any(item.startswith("unvalidated_implementation_target:upgradeTo") for item in issues)
    assert any(item.startswith("state_transition_after_external_call:execute") for item in issues)


def test_contract_pattern_check_tool_flags_signature_and_oracle_review_signals() -> None:
    tool = ContractPatternCheckTool()
    payload = tool.validate_payload(
        {
            "contract_code": """
pragma solidity ^0.8.20;
interface AggregatorV3Interface {
    function latestRoundData() external view returns (uint80, int256, uint256, uint256, uint80);
}
contract SignatureOracleSurface {
    AggregatorV3Interface public priceFeed;

    function permitAction(
        address owner,
        address target,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) external pure returns (address) {
        bytes32 digest = keccak256(abi.encodePacked(owner, target));
        return ecrecover(digest, v, r, s);
    }

    function quote() external view returns (int256) {
        (, int256 price,,,) = priceFeed.latestRoundData();
        return price;
    }
}
""".strip(),
            "language": "solidity",
        }
    )
    result = tool.run(payload)

    issues = result["result_data"]["issues"]
    notes = result["result_data"]["notes"]
    assert any(item.startswith("signature_replay_review_required:permitAction") for item in issues)
    assert any(item.startswith("oracle_staleness_review_required:quote") for item in issues)
    assert any(item.startswith("signature_validation_surface:permitAction") for item in notes)
    assert any(item.startswith("oracle_dependency_review:quote") for item in notes)


def test_contract_pattern_check_tool_flags_collateral_and_liquidation_review_signals() -> None:
    tool = ContractPatternCheckTool()
    payload = tool.validate_payload(
        {
            "contract_code": """
pragma solidity ^0.8.20;
interface AggregatorV3Interface {
    function latestRoundData() external view returns (uint80, int256, uint256, uint256, uint80);
}
interface IPair { function getReserves() external view returns (uint112, uint112, uint32); }
contract CollateralLiquidationSurface {
    AggregatorV3Interface public priceFeed;
    mapping(address => uint256) public collateral;
    mapping(address => uint256) public debt;

    function liquidate(address account) external {
        (, int256 price,,,) = priceFeed.latestRoundData();
        uint256 quote = uint256(price);
        collateral[account] = collateral[account] > quote ? collateral[account] - quote : 0;
        debt[account] = 0;
    }

    function collateralRatio(address pair) external view returns (uint256) {
        (uint112 reserve0, uint112 reserve1,) = IPair(pair).getReserves();
        return uint256(reserve1) * 1e18 / uint256(reserve0);
    }
}
""".strip(),
            "language": "solidity",
        }
    )
    result = tool.run(payload)

    issues = result["result_data"]["issues"]
    notes = result["result_data"]["notes"]
    assert any(item.startswith("collateral_ratio_review_required:liquidate") for item in issues)
    assert any(item.startswith("liquidation_without_fresh_price_review:liquidate") for item in issues)
    assert any(item.startswith("reserve_spot_dependency_review_required:collateralRatio") for item in issues)
    assert any(item.startswith("collateral_management_review:liquidate") for item in notes)
    assert any(item.startswith("liquidation_surface_review:liquidate") for item in notes)
    assert any(item.startswith("reserve_dependency_review:collateralRatio") for item in notes)


def test_contract_surface_tool_reports_reserve_fee_and_debt_surfaces() -> None:
    tool = ContractSurfaceTool()
    payload = tool.validate_payload(
        {
            "contract_code": """
pragma solidity ^0.8.20;
contract ProtocolAccountingSurface {
    uint256 public protocolReserves;
    uint256 public reserveBuffer;
    uint256 public insuranceFund;
    mapping(address => uint256) public debt;
    uint256 public totalDebt;

    function skimProtocolFee(address payable treasury, uint256 amount) external {
        (bool ok,) = treasury.call{value: amount}("");
        require(ok, "send failed");
    }

    function socializeBadDebt(address account, uint256 amount) external {
        debt[account] = debt[account] > amount ? debt[account] - amount : 0;
        totalDebt = totalDebt > amount ? totalDebt - amount : 0;
        reserveBuffer = reserveBuffer > amount ? reserveBuffer - amount : 0;
        insuranceFund = insuranceFund > amount ? insuranceFund - amount : 0;
    }

    function accrueBorrowDebt(address account, uint256 amount) external {
        debt[account] += amount;
        totalDebt += amount;
    }

    function syncReserves(uint256 amount) external {
        protocolReserves += amount;
    }
}
""".strip(),
            "language": "solidity",
        }
    )
    result = tool.run(payload)
    data = result["result_data"]

    assert "skimProtocolFee" in data["fee_collection_functions"]
    assert "socializeBadDebt" in data["reserve_buffer_functions"]
    assert "accrueBorrowDebt" in data["debt_accounting_functions"]
    assert "socializeBadDebt" in data["bad_debt_socialization_functions"]
    assert "syncReserves" in data["reserve_accounting_functions"]
    assert "fee_collection_surface_present" in data["issues"]
    assert "reserve_buffer_surface_present" in data["issues"]
    assert "reserve_accounting_surface_present" in data["issues"]
    assert "debt_accounting_surface_present" in data["issues"]
    assert "bad_debt_socialization_surface_present" in data["issues"]


def test_contract_pattern_check_tool_flags_accounting_review_signals() -> None:
    tool = ContractPatternCheckTool()
    payload = tool.validate_payload(
        {
            "contract_code": """
pragma solidity ^0.8.20;
contract AccountingSurface {
    mapping(address => uint256) public balances;
    mapping(address => bool) public claimed;

    function withdraw(uint256 amount) external {
        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok, "send failed");
        balances[msg.sender] -= amount;
    }

    function claim() external {
        (bool ok,) = msg.sender.call{value: 1 ether}("");
        require(ok, "send failed");
        claimed[msg.sender] = true;
    }
}
""".strip(),
            "language": "solidity",
        }
    )
    result = tool.run(payload)

    issues = result["result_data"]["issues"]
    notes = result["result_data"]["notes"]
    assert any(item.startswith("accounting_update_after_external_call:withdraw") for item in issues)
    assert any(item.startswith("withdrawal_without_balance_validation:withdraw") for item in issues)
    assert any(item.startswith("accounting_update_after_external_call:claim") for item in issues)
    assert any(item.startswith("accounting_surface_review:withdraw") for item in notes)
    assert result["result_data"]["priority_counts"]["high"] >= 2


def test_contract_pattern_check_tool_flags_reserve_fee_and_debt_review_signals() -> None:
    tool = ContractPatternCheckTool()
    payload = tool.validate_payload(
        {
            "contract_code": """
pragma solidity ^0.8.20;
contract ReserveFeeDebtSurface {
    uint256 public protocolReserves;
    uint256 public reserveBuffer;
    uint256 public insuranceFund;
    mapping(address => uint256) public debt;
    uint256 public totalDebt;

    function skimProtocolFee(address payable treasury, uint256 amount) external {
        (bool ok,) = treasury.call{value: amount}("");
        require(ok, "send failed");
    }

    function socializeBadDebt(address account, uint256 amount) external {
        debt[account] = debt[account] > amount ? debt[account] - amount : 0;
        totalDebt = totalDebt > amount ? totalDebt - amount : 0;
        reserveBuffer = reserveBuffer > amount ? reserveBuffer - amount : 0;
        insuranceFund = insuranceFund > amount ? insuranceFund - amount : 0;
    }

    function accrueBorrowDebt(address account, uint256 amount) external {
        debt[account] += amount;
        totalDebt += amount;
    }
}
""".strip(),
            "language": "solidity",
        }
    )
    result = tool.run(payload)

    issues = result["result_data"]["issues"]
    notes = result["result_data"]["notes"]
    assert any(item.startswith("protocol_fee_without_reserve_sync_review:skimProtocolFee") for item in issues)
    assert any(item.startswith("reserve_accounting_drift_review_required:skimProtocolFee") for item in issues)
    assert any(item.startswith("bad_debt_socialization_review_required:socializeBadDebt") for item in issues)
    assert any(item.startswith("debt_state_transition_review_required:accrueBorrowDebt") for item in issues)
    assert any(item.startswith("protocol_fee_review:skimProtocolFee") for item in notes)
    assert any(item.startswith("bad_debt_socialization_review:socializeBadDebt") for item in notes)
    assert any(item.startswith("debt_accounting_review:accrueBorrowDebt") for item in notes)
    assert result["result_data"]["priority_counts"]["high"] >= 2


def test_contract_pattern_check_tool_flags_liquidation_fee_review_signals() -> None:
    tool = ContractPatternCheckTool()
    payload = tool.validate_payload(
        {
            "contract_code": """
pragma solidity ^0.8.20;
interface AggregatorV3Interface {
    function latestRoundData() external view returns (uint80, int256, uint256, uint256, uint80);
}
contract LiquidationFeeSurface {
    AggregatorV3Interface public priceFeed;
    mapping(address => uint256) public collateral;
    mapping(address => uint256) public debt;
    mapping(address => uint256) public rewards;

    function liquidate(address account) external {
        (, int256 price,, uint256 updatedAt,) = priceFeed.latestRoundData();
        require(block.timestamp - updatedAt <= 1 hours, "stale");
        require(collateral[account] * uint256(price) < debt[account] * 1e18, "healthy");
        uint256 liquidationBonus = debt[account] / 5;
        rewards[msg.sender] += liquidationBonus;
        collateral[account] = collateral[account] > uint256(price) + liquidationBonus
            ? collateral[account] - uint256(price) - liquidationBonus
            : 0;
        debt[account] = 0;
    }
}
""".strip(),
            "language": "solidity",
        }
    )
    result = tool.run(payload)

    issues = result["result_data"]["issues"]
    notes = result["result_data"]["notes"]
    assert any(item.startswith("liquidation_fee_allocation_review_required:liquidate") for item in issues)
    assert any(item.startswith("liquidation_fee_review:liquidate") for item in notes)


def test_contract_pattern_check_tool_flags_proxy_and_storage_review_signals() -> None:
    tool = ContractPatternCheckTool()
    payload = tool.validate_payload(
        {
            "contract_code": """
pragma solidity ^0.8.20;
contract NaiveProxy {
    address public implementation;

    fallback() external payable {
        (bool ok,) = implementation.delegatecall(msg.data);
        require(ok, "delegate failed");
    }

    function upgradeTo(address newImplementation) external {
        implementation = newImplementation;
    }
}
""".strip(),
            "language": "solidity",
        }
    )
    result = tool.run(payload)

    issues = result["result_data"]["issues"]
    notes = result["result_data"]["notes"]
    assert any(item.startswith("proxy_fallback_delegatecall_review_required:fallback") for item in issues)
    assert any(item.startswith("proxy_storage_collision_review_required:fallback") for item in issues)
    assert any(item.startswith("proxy_delegate_surface:fallback") for item in notes)
    assert result["result_data"]["priority_counts"]["high"] >= 1


def test_contract_pattern_check_tool_flags_authorization_review_signals() -> None:
    tool = ContractPatternCheckTool()
    payload = tool.validate_payload(
        {
            "contract_code": """
pragma solidity ^0.8.20;
contract AuthorizationSurface {
    mapping(address => bool) public operators;
    bool public paused;
    address public owner;

    function grantRole(address operator) external {
        operators[operator] = true;
    }

    function pause() external {
        paused = true;
    }

    function setOperator(address operator, bool enabled) external {
        operators[operator] = enabled;
    }

    function mint(address to, uint256 amount) external {
        owner = to;
    }
}
""".strip(),
            "language": "solidity",
        }
    )
    result = tool.run(payload)

    issues = result["result_data"]["issues"]
    notes = result["result_data"]["notes"]
    assert any(item.startswith("unguarded_role_management_surface:grantRole") for item in issues)
    assert any(item.startswith("unguarded_pause_control_surface:pause") for item in issues)
    assert any(item.startswith("unguarded_privileged_state_change:mint") for item in issues)
    assert any(item.startswith("role_management_surface:grantRole") for item in notes)
    assert any(item.startswith("pause_control_surface:pause") for item in notes)


def test_contract_pattern_check_tool_flags_asset_flow_review_signals() -> None:
    tool = ContractPatternCheckTool()
    payload = tool.validate_payload(
        {
            "contract_code": """
pragma solidity ^0.8.20;
interface IERC20 { function transfer(address to, uint256 amount) external returns (bool); }
contract AssetFlowSurface {
    mapping(address => uint256) public balances;
    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }
    function claim(uint256 amount) external {
        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok, "send failed");
        balances[msg.sender] -= amount;
    }
    function sweep(address token, address to, uint256 amount) external {
        IERC20(token).transfer(to, amount);
    }
}
""".strip(),
            "language": "solidity",
        }
    )
    result = tool.run(payload)

    issues = result["result_data"]["issues"]
    notes = result["result_data"]["notes"]
    assert "asset_exit_without_balance_validation" in issues
    assert "unguarded_rescue_or_sweep_flow" in issues
    assert any(item.startswith("unguarded_rescue_or_sweep_surface:sweep") for item in issues)
    assert "cross_function_fund_flow_present" in notes
    assert any(item.startswith("deposit_flow_review:deposit") for item in notes)
    assert any(item.startswith("asset_exit_flow_review:claim") for item in notes)


def test_contract_pattern_check_tool_flags_vault_share_review_signals() -> None:
    tool = ContractPatternCheckTool()
    payload = tool.validate_payload(
        {
            "contract_code": """
pragma solidity ^0.8.20;
interface IERC20 { function transfer(address to, uint256 amount) external returns (bool); }
contract VaultShareSurface {
    IERC20 public assetToken;
    mapping(address => uint256) public shares;
    uint256 public totalSupply;

    function mint(uint256 sharesAmount) external {
        shares[msg.sender] += sharesAmount;
        totalSupply += sharesAmount;
    }

    function redeem(uint256 sharesAmount) external {
        bool ok = assetToken.transfer(msg.sender, sharesAmount);
        require(ok, "transfer failed");
        shares[msg.sender] -= sharesAmount;
        totalSupply -= sharesAmount;
    }
}
""".strip(),
            "language": "solidity",
        }
    )
    result = tool.run(payload)

    issues = result["result_data"]["issues"]
    notes = result["result_data"]["notes"]
    assert any(item.startswith("share_mint_without_asset_backing_review:mint") for item in issues)
    assert any(item.startswith("share_redeem_without_share_validation:redeem") for item in issues)
    assert any(item.startswith("share_accounting_review:mint") for item in notes)
    assert "share_accounting_flow_present" in notes
    assert result["result_data"]["priority_counts"]["high"] >= 2


def test_parser_supports_smart_contract_cli_flags() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "--domain",
            "smart_contract_audit",
            "--contract-file",
            "contracts/Vault.sol",
            "--contract-root",
            "contracts",
            "--contract-language",
            "solidity",
            "Audit the contract for low-level call review surfaces.",
        ]
    )

    assert args.domain == "smart_contract_audit"
    assert args.contract_file == "contracts/Vault.sol"
    assert args.contract_root == "contracts"
    assert args.contract_language == "solidity"


def test_parser_supports_inline_contract_code_flag() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "--domain",
            "smart_contract_audit",
            "--contract-code",
            "pragma solidity ^0.8.20; contract InlineVault {}",
            "Audit the contract for bounded static review signals.",
        ]
    )

    assert args.domain == "smart_contract_audit"
    assert args.contract_code.startswith("pragma solidity")
    assert args.contract_file is None


def test_orchestrator_can_run_bounded_smart_contract_session() -> None:
    run_root = Path(".test_runs") / make_id("contract")
    config = AppConfig.model_validate(
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
            "log_level": "WARNING",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )
    orchestrator = build_orchestrator(config)
    seed_text = build_smart_contract_seed(
        idea_text="Audit the contract for externally reachable review surfaces and risky low-level calls.",
        contract_code=SAMPLE_CONTRACT,
        language="solidity",
        source_label="contracts/Vault.sol",
    )

    session = orchestrator.run_session(seed_text=seed_text, author="contract-test")

    assert session.research_target is not None
    assert session.research_target.target_kind == "smart_contract"
    assert session.jobs
    tool_names = [job.tool_name for job in session.jobs]
    assert session.jobs[0].tool_name in {
        "contract_compile_tool",
        "contract_parser_tool",
        "contract_surface_tool",
        "contract_pattern_check_tool",
        "slither_audit_tool",
    }
    assert "contract_parser_tool" in tool_names
    assert "contract_surface_tool" in tool_names
    assert "contract_pattern_check_tool" in tool_names
    assert session.evidence
    assert session.evidence[0].target_kind == "smart_contract"
    assert session.report is not None
    assert session.report.contract_overview
    assert session.report.contract_priority_findings
    assert (
        session.report.contract_compile_summary
        or session.report.contract_surface_summary
        or session.report.contract_static_findings
        or session.report.contract_testbed_findings
    )
    assert session.report.contract_review_focus
    assert session.report.contract_remediation_guidance
    assert session.report.contract_manual_review_items
    assert "contract_remediation_validation" in session.model_dump()["report"]
    assert any("contract_" in item for item in session.report.local_experiment_summary)
    assert session.session_file_path is not None
    session_payload = json.loads(Path(session.session_file_path).read_text(encoding="utf-8"))
    assert session_payload["report"]["contract_overview"]
    assert "contract_compile_summary" in session_payload["report"]
    assert "contract_surface_summary" in session_payload["report"]
    assert "contract_priority_findings" in session_payload["report"]
    assert "contract_static_findings" in session_payload["report"]
    assert "contract_testbed_findings" in session_payload["report"]
    assert "contract_remediation_validation" in session_payload["report"]
    assert "contract_remediation_guidance" in session_payload["report"]


def test_orchestrator_can_run_repo_scoped_smart_contract_session(tmp_path: Path) -> None:
    repo_root = tmp_path / "sample_repo"
    contracts_dir = repo_root / "contracts"
    contracts_dir.mkdir(parents=True)
    (contracts_dir / "SharedBase.sol").write_text(
        """
pragma solidity ^0.8.20;
contract SharedBase { address internal owner; }
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
    source_path = contracts_dir / "Vault.sol"
    source_path.write_text(
        """
pragma solidity ^0.8.20;
import "./SharedBase.sol";

contract Vault is SharedBase {
    mapping(address => uint256) public balances;

    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }

    function withdraw(uint256 amount) external {
        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok, "send failed");
        balances[msg.sender] -= amount;
    }
}
""".strip(),
        encoding="utf-8",
    )
    (contracts_dir / "Proxy.sol").write_text(
        """
pragma solidity ^0.8.24;
import "./SharedBase.sol";
import "./ProxyLogic.sol";
contract Proxy is SharedBase { ProxyLogic public logic; }
""".strip(),
        encoding="utf-8",
    )

    run_root = Path(".test_runs") / make_id("contractrepo")
    config = AppConfig.model_validate(
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
            "log_level": "WARNING",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )
    orchestrator = build_orchestrator(config)
    seed_text = build_smart_contract_seed(
        idea_text="Audit the repository scope for multi-file contract review, delegatecall surfaces, and candidate files.",
        contract_code=SAMPLE_CONTRACT,
        language="solidity",
        source_label=str(source_path.resolve()),
        contract_root=str(repo_root.resolve()),
    )

    session = orchestrator.run_session(seed_text=seed_text, author="contract-repo-test")

    tool_names = [job.tool_name for job in session.jobs]
    assert "contract_inventory_tool" in tool_names
    assert tool_names.index("contract_inventory_tool") < tool_names.index("contract_parser_tool")
    assert session.report is not None
    assert session.report.contract_inventory_summary
    assert session.report.contract_protocol_map
    assert session.report.contract_protocol_invariants
    assert session.report.contract_signal_consensus
    assert session.report.contract_validation_matrix
    assert session.report.contract_benchmark_posture
    assert session.report.contract_repo_priorities
    assert session.report.contract_repo_triage
    assert session.report.contract_toolchain_alignment
    assert session.report.contract_review_queue
    assert session.report.contract_residual_risk
    assert session.report.contract_exit_criteria
    assert any("Scoped contract root:" in item for item in session.report.contract_inventory_summary)
    assert any("Candidate review files:" in item for item in session.report.contract_inventory_summary)
    assert any("Entrypoint review files:" in item for item in session.report.contract_inventory_summary)
    assert any("Pragma summary:" in item for item in session.report.contract_inventory_summary)
    assert any("import graph:" in item.lower() for item in session.report.contract_inventory_summary)
    assert any("shared dependency files:" in item.lower() for item in session.report.contract_inventory_summary)
    assert any("entrypoint flows:" in item.lower() for item in session.report.contract_inventory_summary)
    assert any("review lanes:" in item.lower() for item in session.report.contract_inventory_summary)
    assert any("risk family lanes:" in item.lower() for item in session.report.contract_inventory_summary)
    assert any("function-family priorities:" in item.lower() for item in session.report.contract_inventory_summary)
    assert any("risk-linked files:" in item.lower() for item in session.report.contract_inventory_summary)
    assert any("entrypoints:" in item.lower() for item in session.report.contract_protocol_map)
    assert any("authority / upgrade contour:" in item.lower() or "asset / accounting contour:" in item.lower() for item in session.report.contract_protocol_map)
    assert any("shared hubs:" in item.lower() or "casebook fit:" in item.lower() for item in session.report.contract_protocol_map)
    assert any("invariant:" in item.lower() and "current support:" in item.lower() for item in session.report.contract_protocol_invariants)
    assert any("consensus on" in item.lower() and "support=" in item.lower() for item in session.report.contract_signal_consensus)
    assert any("posture=" in item.lower() and "support=" in item.lower() for item in session.report.contract_validation_matrix)
    assert any("benchmark posture" in item.lower() and "support=" in item.lower() for item in session.report.contract_benchmark_posture)
    assert any("repo lane:" in item.lower() or "repo scope:" in item.lower() for item in session.report.contract_repo_priorities)
    assert any("supporting signals:" in item.lower() for item in session.report.contract_repo_priorities)
    assert any("proxy.sol" in item.lower() or "vault.sol" in item.lower() for item in session.report.contract_repo_priorities)
    assert any("start repo review from" in item.lower() or "top repo family" in item.lower() for item in session.report.contract_repo_triage)
    assert any("bounded repo casebook" in item.lower() or "risk-linked files" in item.lower() for item in session.report.contract_repo_triage)
    assert any("lane alignment for" in item.lower() and "support=" in item.lower() for item in session.report.contract_toolchain_alignment)
    assert any("no family-matched bounded casebook" in item.lower() or "no foundry structural pass" in item.lower() or "no echidna replay" in item.lower() for item in session.report.contract_toolchain_alignment)
    assert any("queue 1:" in item.lower() and "next replay:" in item.lower() for item in session.report.contract_review_queue)
    assert any("residual risk" in item.lower() and "status=" in item.lower() for item in session.report.contract_residual_risk)
    assert any("exit criterion for" in item.lower() and "should still replay cleanly" in item.lower() for item in session.report.contract_exit_criteria)
    assert any("re-run compile" in item.lower() or "hardening" in item.lower() or "storage-slot" in item.lower() or "delegatecall" in item.lower() for item in session.report.contract_remediation_guidance)
    assert any("function families" in item.lower() or "risk-family lanes" in item.lower() or "review lanes" in item.lower() or "entrypoint" in item.lower() or "candidate files" in item.lower() or "repository" in item.lower() or "risky files" in item.lower() for item in session.report.contract_review_focus)
    assert any("function families" in item.lower() or "risk-family lanes" in item.lower() or "review lanes" in item.lower() or "entrypoint" in item.lower() or "candidate files" in item.lower() or "repository" in item.lower() or "risky files" in item.lower() for item in session.report.contract_manual_review_items)
    assert session.session_file_path is not None
    session_payload = json.loads(Path(session.session_file_path).read_text(encoding="utf-8"))
    assert session_payload["report"]["contract_inventory_summary"]
    assert session_payload["report"]["contract_protocol_map"]
    assert session_payload["report"]["contract_protocol_invariants"]
    assert session_payload["report"]["contract_signal_consensus"]
    assert session_payload["report"]["contract_validation_matrix"]
    assert session_payload["report"]["contract_benchmark_posture"]
    assert session_payload["report"]["contract_repo_priorities"]
    assert session_payload["report"]["contract_repo_triage"]
    assert session_payload["report"]["contract_toolchain_alignment"]
    assert session_payload["report"]["contract_review_queue"]
    assert session_payload["report"]["contract_residual_risk"]
    assert session_payload["report"]["contract_exit_criteria"]
    assert session_payload["report"]["contract_casebook_gaps"]
    assert "contract_review_focus" in session_payload["report"]
    assert "contract_remediation_guidance" in session_payload["report"]
    assert "contract_manual_review_items" in session_payload["report"]


def test_orchestrator_prefers_compile_path_for_compile_focused_contract_seed() -> None:
    run_root = Path(".test_runs") / make_id("contractcompile")
    config = AppConfig.model_validate(
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
            "log_level": "WARNING",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )
    orchestrator = build_orchestrator(config)
    seed_text = build_smart_contract_seed(
        idea_text="Compile the contract locally, inspect pragma compatibility, and report any compiler-facing issues.",
        contract_code=SAMPLE_CONTRACT,
        language="solidity",
        source_label="contracts/Vault.sol",
    )

    session = orchestrator.run_session(seed_text=seed_text, author="contract-compile-test")

    assert session.jobs
    assert session.jobs[0].tool_name == "contract_compile_tool"
    tool_names = [job.tool_name for job in session.jobs]
    assert "contract_parser_tool" in tool_names
    assert "contract_surface_tool" in tool_names
    assert "contract_pattern_check_tool" in tool_names
    assert session.report is not None
    assert session.report.contract_compile_summary


def test_orchestrator_can_select_slither_for_detector_focused_contract_seed() -> None:
    run_root = Path(".test_runs") / make_id("contractslither")
    config = AppConfig.model_validate(
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
            "log_level": "WARNING",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )
    orchestrator = build_orchestrator(config)
    seed_text = build_smart_contract_seed(
        idea_text="Use static analyzer detectors to inspect the contract for reentrancy and tx.origin review signals.",
        contract_code=SAMPLE_CONTRACT,
        language="solidity",
        source_label="contracts/Vault.sol",
    )

    session = orchestrator.run_session(seed_text=seed_text, author="contract-slither-test")

    assert session.jobs
    assert session.jobs[0].tool_name == "slither_audit_tool"
    tool_names = [job.tool_name for job in session.jobs]
    assert "contract_parser_tool" in tool_names
    assert "contract_surface_tool" in tool_names
    assert "contract_pattern_check_tool" in tool_names
    assert session.report is not None
    assert session.report.contract_static_findings


def test_orchestrator_can_select_foundry_for_foundry_focused_contract_seed(monkeypatch) -> None:
    def fake_resolve_local_binary(binary: str) -> str | None:
        if binary == "forge":
            return "forge"
        if binary == "solc":
            return "solc"
        if binary == "slither":
            return "slither"
        return None

    def fake_run(
        args,
        *,
        capture_output,
        text,
        encoding,
        timeout,
        check,
        input=None,
    ):
        if "--version" in args:
            if args[0] == "forge":
                return subprocess.CompletedProcess(
                    args=args,
                    returncode=0,
                    stdout="forge 1.0.0",
                    stderr="",
                )
            if args[0] == "slither":
                return subprocess.CompletedProcess(
                    args=args,
                    returncode=0,
                    stdout="slither 0.10.4",
                    stderr="",
                )
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout="solc, the solidity compiler commandline interface\nVersion: 0.8.20",
                stderr="",
            )
        if len(args) >= 2 and args[1] == "--standard-json":
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout=json.dumps(
                    {
                        "contracts": {
                            "Vault.sol": {
                                "Vault": {
                                    "abi": [],
                                    "evm": {"bytecode": {"object": "0x00"}},
                                }
                            }
                        },
                        "sources": {
                            "Vault.sol": {
                                "ast": {"nodeType": "SourceUnit"},
                            }
                        },
                    }
                ),
                stderr="",
            )
        if args and args[0] == "slither":
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout=json.dumps(
                    {
                        "results": {
                            "detectors": [
                                {
                                    "check": "controlled-delegatecall",
                                    "impact": "medium",
                                    "confidence": "medium",
                                    "description": "bounded detector finding",
                                }
                            ]
                        }
                    }
                ),
                stderr="",
            )
        if len(args) >= 2 and args[1] == "build":
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout="build completed",
                stderr="",
            )
        if len(args) >= 4 and args[1] == "inspect" and args[3] == "methodIdentifiers":
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout=json.dumps({"ping()": "5c36b186"}),
                stderr="",
            )
        if len(args) >= 4 and args[1] == "inspect" and args[3] == "storageLayout":
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout=json.dumps({"storage": [{"slot": "0", "label": "owner"}]}),
                stderr="",
            )
        raise AssertionError(f"Unexpected subprocess args: {args}")

    monkeypatch.setattr(contract_compile_runner_module, "resolve_local_binary", fake_resolve_local_binary)
    monkeypatch.setattr(contract_compile_runner_module, "resolve_managed_solc_binary", lambda **_: (None, None))
    monkeypatch.setattr(contract_compile_runner_module.subprocess, "run", fake_run)
    monkeypatch.setattr(foundry_runner_module, "resolve_local_binary", fake_resolve_local_binary)
    monkeypatch.setattr(foundry_runner_module, "resolve_managed_solc_binary", lambda **_: (None, None))
    monkeypatch.setattr(foundry_runner_module.subprocess, "run", fake_run)
    monkeypatch.setattr(slither_runner_module, "resolve_local_binary", fake_resolve_local_binary)
    monkeypatch.setattr(slither_runner_module, "resolve_managed_solc_binary", lambda **_: (None, None))
    monkeypatch.setattr(slither_runner_module.subprocess, "run", fake_run)

    run_root = Path(".test_runs") / make_id("contractfoundry")
    config = AppConfig.model_validate(
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
            "log_level": "WARNING",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )
    orchestrator = build_orchestrator(config)
    seed_text = build_smart_contract_seed(
        idea_text="Use Foundry to inspect storage layout and method identifiers for bounded manual review.",
        contract_code=SAMPLE_CONTRACT,
        language="solidity",
        source_label="contracts/Vault.sol",
    )

    session = orchestrator.run_session(seed_text=seed_text, author="contract-foundry-test")

    assert session.jobs
    assert session.jobs[0].tool_name == "foundry_audit_tool"
    tool_names = [job.tool_name for job in session.jobs]
    assert "foundry_audit_tool" in tool_names
    assert session.report is not None
    assert any("Foundry reviewed" in item for item in session.report.contract_static_findings)


def test_orchestrator_can_select_echidna_for_invariant_focused_contract_seed(monkeypatch) -> None:
    def fake_resolve_local_binary(binary: str) -> str | None:
        if binary in {"echidna", "slither", "forge", "solc"}:
            return binary
        return None

    def fake_run(
        args,
        *,
        capture_output,
        text,
        encoding,
        timeout,
        check,
        input=None,
    ):
        if "--version" in args:
            if args[0] == "echidna":
                return subprocess.CompletedProcess(
                    args=args,
                    returncode=0,
                    stdout="echidna 2.2.2",
                    stderr="",
                )
            if args[0] == "forge":
                return subprocess.CompletedProcess(
                    args=args,
                    returncode=0,
                    stdout="forge 1.0.0",
                    stderr="",
                )
            if args[0] == "slither":
                return subprocess.CompletedProcess(
                    args=args,
                    returncode=0,
                    stdout="0.11.5",
                    stderr="",
                )
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout="solc, the solidity compiler commandline interface\nVersion: 0.8.20",
                stderr="",
            )
        if "--standard-json" in args:
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout=json.dumps(
                    {
                        "contracts": {"Contract.sol": {"VaultHarness": {"abi": []}}},
                        "sources": {"Contract.sol": {"ast": {"nodeType": "SourceUnit"}}},
                        "errors": [],
                    }
                ),
                stderr="",
            )
        if "--json" in args:
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout=json.dumps({"results": {"detectors": []}}),
                stderr="",
            )
        if len(args) >= 2 and args[1] == "build":
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout="build completed",
                stderr="",
            )
        if len(args) >= 4 and args[1] == "inspect" and args[3] == "methodIdentifiers":
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout=json.dumps({"echidna_owner_is_not_zero()": "12345678"}),
                stderr="",
            )
        if len(args) >= 4 and args[1] == "inspect" and args[3] == "storageLayout":
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout=json.dumps({"storage": [{"slot": "0", "label": "owner"}]}),
                stderr="",
            )
        if "--contract" in args and "--config" in args:
            return subprocess.CompletedProcess(
                args=args,
                returncode=1,
                stdout=json.dumps(
                    {
                        "success": False,
                        "tests": [
                            {"name": "echidna_owner_is_not_zero", "status": "passed"},
                            {"name": "echidna_only_owner_can_set", "status": "solved"},
                        ],
                    }
                ),
                stderr="",
            )
        raise AssertionError(f"Unexpected subprocess args: {args}")

    monkeypatch.setattr(contract_compile_runner_module, "resolve_local_binary", fake_resolve_local_binary)
    monkeypatch.setattr(contract_compile_runner_module, "resolve_managed_solc_binary", lambda **_: (None, None))
    monkeypatch.setattr(contract_compile_runner_module.subprocess, "run", fake_run)
    monkeypatch.setattr(slither_runner_module, "resolve_local_binary", fake_resolve_local_binary)
    monkeypatch.setattr(slither_runner_module, "resolve_managed_solc_binary", lambda **_: (None, None))
    monkeypatch.setattr(slither_runner_module.subprocess, "run", fake_run)
    monkeypatch.setattr(foundry_runner_module, "resolve_local_binary", fake_resolve_local_binary)
    monkeypatch.setattr(foundry_runner_module, "resolve_managed_solc_binary", lambda **_: (None, None))
    monkeypatch.setattr(foundry_runner_module.subprocess, "run", fake_run)
    monkeypatch.setattr(echidna_runner_module, "resolve_local_binary", fake_resolve_local_binary)
    monkeypatch.setattr(echidna_runner_module, "resolve_managed_solc_binary", lambda **_: (None, None))
    monkeypatch.setattr(echidna_runner_module.subprocess, "run", fake_run)

    run_root = Path(".test_runs") / make_id("contractechidna")
    config = AppConfig.model_validate(
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
            "log_level": "WARNING",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )
    orchestrator = build_orchestrator(config)
    seed_text = build_smart_contract_seed(
        idea_text="Use Echidna to review invariants and bounded counterexamples for ownership transitions.",
        contract_code="""
pragma solidity ^0.8.20;
contract VaultHarness {
    address public owner;
    constructor() { owner = msg.sender; }
    function setOwner(address newOwner) external { owner = newOwner; }
    function echidna_owner_is_not_zero() public returns (bool) { return owner != address(0); }
    function echidna_only_owner_can_set() public returns (bool) { return false; }
}
""".strip(),
        language="solidity",
        source_label="contracts/VaultHarness.sol",
    )

    session = orchestrator.run_session(seed_text=seed_text, author="contract-echidna-test")

    tool_names = [job.tool_name for job in session.jobs]
    assert session.jobs
    assert session.jobs[0].tool_name == "echidna_audit_tool"
    assert "echidna_audit_tool" in tool_names
    assert session.report is not None
    assert any("Echidna ran" in item for item in session.report.contract_static_findings)
    assert any("Echidna failing checks" in item for item in session.report.contract_manual_review_items)


def test_orchestrator_prefers_pattern_path_for_token_and_assembly_review_seed() -> None:
    run_root = Path(".test_runs") / make_id("contractpattern")
    config = AppConfig.model_validate(
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
            "log_level": "WARNING",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )
    orchestrator = build_orchestrator(config)
    seed_text = build_smart_contract_seed(
        idea_text="Inspect ERC20 transfer surfaces and inline assembly review areas.",
        contract_code="""
pragma solidity ^0.8.20;
interface IERC20 { function transfer(address to, uint256 amount) external returns (bool); }
contract TokenAssemblySurface {
    function sweep(address token, address to, uint256 amount) external {
        IERC20(token).transfer(to, amount);
    }
    function rawStore(address newOwner) external {
        assembly {
            sstore(0, newOwner)
        }
    }
}
""".strip(),
        language="solidity",
        source_label="contracts/TokenAssemblySurface.sol",
    )

    session = orchestrator.run_session(seed_text=seed_text, author="contract-pattern-test")

    assert session.jobs
    assert session.jobs[0].tool_name in {"contract_pattern_check_tool", "contract_surface_tool"}
    tool_names = [job.tool_name for job in session.jobs]
    assert "contract_parser_tool" in tool_names
    assert "contract_pattern_check_tool" in tool_names
    assert "contract_surface_tool" in tool_names
    assert "contract_testbed_tool" in tool_names


def test_orchestrator_can_add_state_machine_testbed_for_relevant_contract_seed() -> None:
    run_root = Path(".test_runs") / make_id("contractstate")
    config = AppConfig.model_validate(
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
            "log_level": "WARNING",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )
    orchestrator = build_orchestrator(config)
    seed_text = build_smart_contract_seed(
        idea_text="Review state machine transitions and status updates around external calls.",
        contract_code="""
pragma solidity ^0.8.20;
contract WorkflowSurface {
    uint256 public status;
    function execute(address target) external {
        (bool ok,) = target.call("");
        require(ok, "call failed");
        status = 2;
    }
}
""".strip(),
        language="solidity",
        source_label="contracts/WorkflowSurface.sol",
    )

    session = orchestrator.run_session(seed_text=seed_text, author="contract-state-test")

    tool_names = [job.tool_name for job in session.jobs]
    assert "contract_pattern_check_tool" in tool_names
    assert "contract_testbed_tool" in tool_names
    assert session.report is not None
    assert session.report.contract_testbed_findings
    assert any("state-machine" in item.lower() or "state transitions" in item.lower() for item in session.report.contract_review_focus)


def test_orchestrator_can_add_accounting_testbed_for_relevant_contract_seed() -> None:
    run_root = Path(".test_runs") / make_id("contractaccounting")
    config = AppConfig.model_validate(
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
            "log_level": "WARNING",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )
    orchestrator = build_orchestrator(config)
    seed_text = build_smart_contract_seed(
        idea_text="Review balance accounting, claim-state ordering, and withdrawal-order consistency around external value flow.",
        contract_code="""
pragma solidity ^0.8.20;
contract AccountingSurface {
    mapping(address => uint256) public balances;
    mapping(address => bool) public claimed;
    function withdraw(uint256 amount) external {
        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok, "send failed");
        balances[msg.sender] -= amount;
    }
    function claim() external {
        (bool ok,) = msg.sender.call{value: 1 ether}("");
        require(ok, "send failed");
        claimed[msg.sender] = true;
    }
}
""".strip(),
        language="solidity",
        source_label="contracts/AccountingSurface.sol",
    )

    session = orchestrator.run_session(seed_text=seed_text, author="contract-accounting-test")

    tool_names = [job.tool_name for job in session.jobs]
    assert "contract_pattern_check_tool" in tool_names
    assert "contract_testbed_tool" in tool_names
    assert session.report is not None
    assert session.report.contract_priority_findings
    assert session.report.contract_testbed_findings
    assert session.report.contract_remediation_validation
    assert session.report.contract_remediation_follow_up
    assert any(
        "balance validation" in item.lower()
        or "accounting update ordering" in item.lower()
        or "state-transition ordering" in item.lower()
        for item in session.report.contract_remediation_validation
    )
    assert any(
        "asset-flow" in item.lower()
        or "balance, claim-state" in item.lower()
        or "bounded testbed" in item.lower()
        for item in session.report.contract_remediation_follow_up
    )
    assert any("accounting" in item.lower() or "balance" in item.lower() for item in session.report.contract_review_focus)
    assert any("balance" in item.lower() or "accounting" in item.lower() or "external value transfer" in item.lower() for item in session.report.contract_remediation_guidance)


def test_orchestrator_can_add_proxy_storage_testbed_for_relevant_contract_seed() -> None:
    run_root = Path(".test_runs") / make_id("contractproxystorage")
    config = AppConfig.model_validate(
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
            "log_level": "WARNING",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )
    orchestrator = build_orchestrator(config)
    seed_text = build_smart_contract_seed(
        idea_text="Review proxy fallback delegation, storage layout assumptions, and implementation-slot update paths.",
        contract_code="""
pragma solidity ^0.8.20;
contract NaiveProxy {
    address public implementation;
    fallback() external payable {
        (bool ok,) = implementation.delegatecall(msg.data);
        require(ok, "delegate failed");
    }
    function upgradeTo(address newImplementation) external {
        implementation = newImplementation;
    }
}
""".strip(),
        language="solidity",
        source_label="contracts/NaiveProxy.sol",
    )

    session = orchestrator.run_session(seed_text=seed_text, author="contract-proxy-storage-test")

    tool_names = [job.tool_name for job in session.jobs]
    assert "contract_pattern_check_tool" in tool_names
    assert "contract_testbed_tool" in tool_names
    assert session.report is not None
    assert session.report.contract_testbed_findings
    assert any("proxy" in item.lower() or "storage" in item.lower() for item in session.report.contract_review_focus)
    assert any("implementation" in item.lower() or "storage-slot" in item.lower() or "delegatecall" in item.lower() for item in session.report.contract_remediation_guidance)
    assert any("storage" in item.lower() or "proxy" in item.lower() for item in session.report.contract_manual_review_items)


def test_orchestrator_can_add_repo_casebook_for_repo_scoped_contract_seed() -> None:
    run_root = Path(".test_runs") / make_id("contractrepocasebook")
    repo_root = run_root / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "Proxy.sol").write_text(
        """
pragma solidity ^0.8.20;
import "./StorageSlotLib.sol";
contract Proxy {
    bytes32 internal constant _IMPLEMENTATION_SLOT = keccak256("eip1967.proxy.implementation");
    fallback() external payable {
        address impl = StorageSlotLib.getAddress(_IMPLEMENTATION_SLOT);
        (bool ok,) = impl.delegatecall(msg.data);
        require(ok, "delegate failed");
    }
    function upgradeTo(address newImplementation) external {
        StorageSlotLib.setAddress(_IMPLEMENTATION_SLOT, newImplementation);
    }
}
""".strip(),
        encoding="utf-8",
    )
    (repo_root / "StorageSlotLib.sol").write_text(
        """
pragma solidity ^0.8.20;
library StorageSlotLib {
    function getAddress(bytes32 slot) internal view returns (address value) {
        assembly { value := sload(slot) }
    }
    function setAddress(bytes32 slot, address value) internal {
        assembly { sstore(slot, value) }
    }
}
""".strip(),
        encoding="utf-8",
    )

    config = AppConfig.model_validate(
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
            "log_level": "WARNING",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )
    orchestrator = build_orchestrator(config)
    seed_text = build_smart_contract_seed(
        idea_text="Audit the repository for proxy upgrade, delegatecall, and storage-slot review lanes across the scoped codebase.",
        contract_code=(repo_root / "Proxy.sol").read_text(encoding="utf-8"),
        language="solidity",
        source_label=str((repo_root / "Proxy.sol").resolve()),
        contract_root=str(repo_root.resolve()),
    )

    session = orchestrator.run_session(seed_text=seed_text, author="contract-repo-casebook-test")

    tool_names = [job.tool_name for job in session.jobs]
    assert "contract_inventory_tool" in tool_names
    assert "contract_testbed_tool" in tool_names
    assert session.report is not None
    assert session.report.contract_testbed_findings
    assert any("repo casebook" in item.lower() for item in session.report.contract_testbed_findings)
    assert session.report.contract_casebook_coverage
    assert session.report.contract_casebook_coverage_matrix
    assert session.report.contract_casebook_case_studies
    assert session.report.contract_casebook_priority_cases
    assert session.report.contract_casebook_gaps
    assert session.report.contract_casebook_benchmark_support
    assert session.report.contract_casebook_triage
    assert session.report.contract_toolchain_alignment
    assert session.report.contract_review_queue
    assert session.report.contract_residual_risk
    assert session.report.contract_exit_criteria
    assert session.report.contract_protocol_map
    assert session.report.contract_protocol_invariants
    assert session.report.contract_signal_consensus
    assert session.report.contract_validation_matrix
    assert session.report.contract_benchmark_posture
    assert session.report.contract_repo_triage
    assert any("coverage=" in item.lower() for item in session.report.contract_casebook_coverage)
    assert any("matched cases=" in item.lower() for item in session.report.contract_casebook_coverage)
    assert any("casebook matrix for repo_upgrade_casebook" in item.lower() for item in session.report.contract_casebook_coverage_matrix)
    assert any("case study repo_upgrade_casebook" in item.lower() for item in session.report.contract_casebook_case_studies)
    assert any("validated controls=" in item.lower() for item in session.report.contract_casebook_case_studies)
    assert any("priority case proxy_delegatecall_upgrade_lane" in item.lower() for item in session.report.contract_casebook_priority_cases)
    assert any("casebook gap scan for repo_upgrade_casebook" in item.lower() for item in session.report.contract_casebook_gaps)
    assert any("benchmark support for repo_upgrade_casebook" in item.lower() for item in session.report.contract_casebook_benchmark_support)
    assert any("compile" in item.lower() and "slither" in item.lower() for item in session.report.contract_casebook_benchmark_support)
    assert any("primary casebook triage for repo_upgrade_casebook" in item.lower() for item in session.report.contract_casebook_triage)
    assert any("benchmark posture for repo_upgrade_casebook" in item.lower() for item in session.report.contract_casebook_triage)
    assert any("authority / upgrade contour:" in item.lower() or "casebook fit: repo_upgrade_casebook" in item.lower() for item in session.report.contract_protocol_map)
    assert any("upgrade or control invariant:" in item.lower() or "proxy or storage invariant:" in item.lower() for item in session.report.contract_protocol_invariants)
    assert any("consensus on upgrade or control" in item.lower() or "consensus on proxy or storage" in item.lower() for item in session.report.contract_signal_consensus)
    assert any("family=upgrade or control" in item.lower() or "family=proxy or storage" in item.lower() for item in session.report.contract_validation_matrix)
    assert any("repo_upgrade_casebook" in item for item in session.report.contract_benchmark_posture)
    assert any("lane alignment for" in item.lower() and "support=" in item.lower() for item in session.report.contract_toolchain_alignment)
    assert any("repo-casebook" in item.lower() for item in session.report.contract_toolchain_alignment)
    assert any("queue 1:" in item.lower() and "matched case=proxy_delegatecall_upgrade_lane" in item.lower() for item in session.report.contract_review_queue)
    assert any("residual risk" in item.lower() and "proxy_delegatecall_upgrade_lane" in item.lower() for item in session.report.contract_residual_risk)
    assert any("exit criterion for" in item.lower() and "proxy_delegatecall_upgrade_lane" in item.lower() for item in session.report.contract_exit_criteria)
    assert any("bounded repo casebook" in item.lower() for item in session.report.contract_repo_triage)
    assert any("top repo family" in item.lower() or "secondary pass" in item.lower() for item in session.report.contract_repo_triage)
    assert session.report.contract_remediation_validation
    assert session.report.contract_remediation_follow_up
    assert any("weakens" in item.lower() or "clears" in item.lower() for item in session.report.contract_remediation_validation)
    assert any("repo-scale" in item.lower() or "proxy and upgrade" in item.lower() for item in session.report.contract_remediation_validation)
    assert any("re-check repo lane" in item.lower() for item in session.report.contract_remediation_follow_up)
    assert any("repo casebook" in item.lower() for item in session.report.contract_remediation_follow_up)
    assert any("proxy" in item.lower() or "storage" in item.lower() for item in session.report.contract_review_focus)
    assert any("repo lane:" in item.lower() or "repo scope:" in item.lower() for item in session.report.contract_repo_priorities)
    assert any("implementation" in item.lower() or "storage-slot" in item.lower() or "delegatecall" in item.lower() for item in session.report.contract_remediation_guidance)


def test_orchestrator_can_add_protocol_accounting_repo_casebook_for_repo_scoped_contract_seed() -> None:
    run_root = Path(".test_runs") / make_id("contractrepoprotocol")
    repo_root = run_root / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "LendingPool.sol").write_text(
        """
pragma solidity ^0.8.20;
import "./DebtLedger.sol";
import "./FeeController.sol";
contract LendingPool {
    DebtLedger public ledger;
    FeeController public fees;
    function borrow(uint256 amount) external { ledger.accrueDebt(msg.sender, amount); }
    function skimProtocolFees(address payable treasury, uint256 amount) external { fees.skimProtocolFee(treasury, amount); }
}
""".strip(),
        encoding="utf-8",
    )
    (repo_root / "DebtLedger.sol").write_text(
        """
pragma solidity ^0.8.20;
contract DebtLedger {
    mapping(address => uint256) public debt;
    uint256 public totalDebt;
    function accrueDebt(address account, uint256 amount) external {
        debt[account] += amount;
        totalDebt += amount;
    }
}
""".strip(),
        encoding="utf-8",
    )
    (repo_root / "FeeController.sol").write_text(
        """
pragma solidity ^0.8.20;
contract FeeController {
    uint256 public protocolReserves;
    function skimProtocolFee(address payable treasury, uint256 amount) external {
        (bool ok,) = treasury.call{value: amount}("");
        require(ok, "send failed");
    }
}
""".strip(),
        encoding="utf-8",
    )

    config = AppConfig.model_validate(
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
            "log_level": "WARNING",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )
    orchestrator = build_orchestrator(config)
    seed_text = build_smart_contract_seed(
        idea_text="Audit the repository for protocol fee skimming, reserve synchronization, and debt accounting review lanes across the scoped codebase.",
        contract_code=(repo_root / "LendingPool.sol").read_text(encoding="utf-8"),
        language="solidity",
        source_label=str((repo_root / "LendingPool.sol").resolve()),
        contract_root=str(repo_root.resolve()),
    )

    session = orchestrator.run_session(seed_text=seed_text, author="contract-repo-protocol-casebook-test")

    tool_names = [job.tool_name for job in session.jobs]
    assert "contract_inventory_tool" in tool_names
    assert "contract_testbed_tool" in tool_names
    assert session.report is not None
    assert session.report.contract_casebook_coverage
    assert session.report.contract_casebook_coverage_matrix
    assert session.report.contract_casebook_case_studies
    assert session.report.contract_casebook_priority_cases
    assert session.report.contract_casebook_gaps
    assert session.report.contract_casebook_benchmark_support
    assert session.report.contract_casebook_triage
    assert session.report.contract_toolchain_alignment
    assert session.report.contract_review_queue
    assert session.report.contract_residual_risk
    assert session.report.contract_exit_criteria
    assert session.report.contract_protocol_map
    assert session.report.contract_protocol_invariants
    assert session.report.contract_signal_consensus
    assert session.report.contract_validation_matrix
    assert session.report.contract_benchmark_posture
    assert session.report.contract_repo_triage
    assert any("repo_protocol_accounting_casebook" in item for item in session.report.contract_casebook_coverage)
    assert any("casebook matrix for repo_protocol_accounting_casebook" in item.lower() for item in session.report.contract_casebook_coverage_matrix)
    assert any("priority case protocol_fee_and_debt_lane" in item.lower() for item in session.report.contract_casebook_priority_cases)
    assert any("casebook gap scan for repo_protocol_accounting_casebook" in item.lower() for item in session.report.contract_casebook_gaps)
    assert any("repo_protocol_accounting_casebook" in item for item in session.report.contract_casebook_benchmark_support)
    assert any("repo_protocol_accounting_casebook" in item for item in session.report.contract_casebook_triage)
    assert any("asset / accounting contour:" in item.lower() or "pricing / collateral contour:" in item.lower() or "casebook fit: repo_protocol_accounting_casebook" in item.lower() for item in session.report.contract_protocol_map)
    assert any("protocol-fee, reserve-buffer, or debt-accounting invariant:" in item.lower() or "collateral invariant:" in item.lower() for item in session.report.contract_protocol_invariants)
    assert any("consensus on protocol-fee, reserve-buffer, or debt-accounting" in item.lower() or "consensus on collateral" in item.lower() for item in session.report.contract_signal_consensus)
    assert any("family=protocol-fee, reserve-buffer, or debt-accounting" in item.lower() or "family=collateral, liquidation, or liquidation-fee" in item.lower() for item in session.report.contract_validation_matrix)
    assert any("repo_protocol_accounting_casebook" in item for item in session.report.contract_benchmark_posture)
    assert any("lane alignment for" in item.lower() and "support=" in item.lower() for item in session.report.contract_toolchain_alignment)
    assert any("repo-casebook" in item.lower() for item in session.report.contract_toolchain_alignment)
    assert any("queue 1:" in item.lower() and "matched case=protocol_fee_and_debt_lane" in item.lower() for item in session.report.contract_review_queue)
    assert any("residual risk" in item.lower() and "protocol_fee_and_debt_lane" in item.lower() for item in session.report.contract_residual_risk)
    assert any("exit criterion for" in item.lower() and "protocol_fee_and_debt_lane" in item.lower() for item in session.report.contract_exit_criteria)
    assert any("protocol" in item.lower() or "debt" in item.lower() or "reserve" in item.lower() for item in session.report.contract_review_focus)
    assert any("repo lane:" in item.lower() for item in session.report.contract_repo_priorities)
    assert any("reserve" in item.lower() or "debt" in item.lower() or "protocol-fee" in item.lower() for item in session.report.contract_repo_triage)
    assert any("protocol-fee" in item.lower() or "reserve synchronization" in item.lower() or "debt-accounting" in item.lower() for item in session.report.contract_remediation_follow_up)


def test_orchestrator_can_add_stablecoin_collateral_repo_casebook_for_repo_scoped_contract_seed() -> None:
    run_root = Path(".test_runs") / make_id("contractrepostablecoin")
    repo_root = run_root / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "MintController.sol").write_text(
        """
pragma solidity ^0.8.20;
import "./OracleAdapter.sol";
import "./DebtBook.sol";
import "./ReservePool.sol";
contract MintController {
    OracleAdapter public oracle;
    DebtBook public debtBook;
    ReservePool public reserves;
    function mintAgainstCollateral(uint256 amount) external {
        require(oracle.latestPrice() > 0, "price");
        debtBook.mint(msg.sender, amount);
    }
    function redeem(uint256 amount) external {
        reserves.redeem(msg.sender, amount);
    }
    function liquidate(address account) external {
        debtBook.liquidate(account);
    }
}
""".strip(),
        encoding="utf-8",
    )
    (repo_root / "OracleAdapter.sol").write_text(
        """
pragma solidity ^0.8.20;
contract OracleAdapter {
    uint256 public price;
    function latestPrice() external view returns (uint256) {
        return price;
    }
}
""".strip(),
        encoding="utf-8",
    )
    (repo_root / "DebtBook.sol").write_text(
        """
pragma solidity ^0.8.20;
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
    (repo_root / "ReservePool.sol").write_text(
        """
pragma solidity ^0.8.20;
contract ReservePool {
    uint256 public reserveBuffer;
    function redeem(address account, uint256 amount) external {
        (bool ok,) = account.call{value: amount}("");
        require(ok, "redeem");
        reserveBuffer -= amount;
    }
}
""".strip(),
        encoding="utf-8",
    )

    config = AppConfig.model_validate(
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
            "log_level": "WARNING",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )
    orchestrator = build_orchestrator(config)
    seed_text = build_smart_contract_seed(
        idea_text="Audit the repository for stablecoin mint-against-collateral, redemption buffer, peg-protection, reserve, and liquidation review lanes across the scoped codebase.",
        contract_code=(repo_root / "MintController.sol").read_text(encoding="utf-8"),
        language="solidity",
        source_label=str((repo_root / "MintController.sol").resolve()),
        contract_root=str(repo_root.resolve()),
    )

    session = orchestrator.run_session(seed_text=seed_text, author="contract-repo-stablecoin-casebook-test")

    assert session.report is not None
    assert any("repo_stablecoin_collateral_casebook" in item for item in session.report.contract_casebook_coverage)
    assert any("stablecoin and collateral archetype" in item.lower() for item in session.report.contract_casebook_case_studies)
    assert any("repo_stablecoin_collateral_casebook" in item.lower() for item in session.report.contract_casebook_triage)
    assert any("casebook fit: repo_stablecoin_collateral_casebook" in item.lower() or "pricing / collateral contour:" in item.lower() for item in session.report.contract_protocol_map)
    assert any("family=oracle or price-dependent" in item.lower() or "family=collateral, liquidation, or liquidation-fee" in item.lower() or "family=protocol-fee, reserve-buffer, or debt-accounting" in item.lower() for item in session.report.contract_validation_matrix)


def test_orchestrator_can_add_vault_permission_repo_casebook_for_repo_scoped_contract_seed() -> None:
    run_root = Path(".test_runs") / make_id("contractrepovaultperm")
    repo_root = run_root / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "VaultRouter.sol").write_text(
        """
pragma solidity ^0.8.20;
import "./PermitModule.sol";
import "./VaultAccounting.sol";
contract VaultRouter {
    PermitModule public permits;
    VaultAccounting public vault;
    function depositWithPermit(address owner, uint256 assets, uint256 deadline, uint8 v, bytes32 r, bytes32 s) external {
        permits.usePermit(owner, address(this), assets, deadline, v, r, s);
        vault.depositFor(owner, assets);
    }
    function redeem(uint256 shares) external {
        vault.redeemTo(msg.sender, shares);
    }
}
""".strip(),
        encoding="utf-8",
    )
    (repo_root / "PermitModule.sol").write_text(
        """
pragma solidity ^0.8.20;
contract PermitModule {
    function usePermit(address owner, address spender, uint256 value, uint256 deadline, uint8 v, bytes32 r, bytes32 s) external pure returns (address) {
        bytes32 digest = keccak256(abi.encodePacked(owner, spender, value));
        return ecrecover(digest, v, r, s);
    }
}
""".strip(),
        encoding="utf-8",
    )
    (repo_root / "VaultAccounting.sol").write_text(
        """
pragma solidity ^0.8.20;
contract VaultAccounting {
    mapping(address => uint256) public shares;
    uint256 public totalAssets;
    function depositFor(address owner, uint256 assets) external {
        shares[owner] += assets;
        totalAssets += assets;
    }
    function redeemTo(address owner, uint256 shareAmount) external {
        (bool ok,) = owner.call{value: shareAmount}("");
        require(ok, "send failed");
        shares[owner] -= shareAmount;
        totalAssets -= shareAmount;
    }
}
""".strip(),
        encoding="utf-8",
    )

    config = AppConfig.model_validate(
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
            "log_level": "WARNING",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )
    orchestrator = build_orchestrator(config)
    seed_text = build_smart_contract_seed(
        idea_text="Audit the repository for vault share accounting, permit replay, allowance handling, and redeem review lanes across the scoped codebase.",
        contract_code=(repo_root / "VaultRouter.sol").read_text(encoding="utf-8"),
        language="solidity",
        source_label=str((repo_root / "VaultRouter.sol").resolve()),
        contract_root=str(repo_root.resolve()),
    )

    session = orchestrator.run_session(seed_text=seed_text, author="contract-repo-vault-permission-casebook-test")

    assert session.report is not None
    assert session.report.contract_casebook_coverage
    assert session.report.contract_casebook_coverage_matrix
    assert session.report.contract_casebook_case_studies
    assert session.report.contract_casebook_priority_cases
    assert session.report.contract_casebook_triage
    assert session.report.contract_protocol_map
    assert session.report.contract_protocol_invariants
    assert session.report.contract_signal_consensus
    assert session.report.contract_validation_matrix
    assert session.report.contract_benchmark_posture
    assert session.report.contract_toolchain_alignment
    assert session.report.contract_review_queue
    assert session.report.contract_residual_risk
    assert session.report.contract_exit_criteria
    assert any("repo_vault_permission_casebook" in item for item in session.report.contract_casebook_coverage)
    assert any("casebook matrix for repo_vault_permission_casebook" in item.lower() for item in session.report.contract_casebook_coverage_matrix)
    assert any("families=" in item.lower() and "token or allowance" in item.lower() for item in session.report.contract_casebook_coverage_matrix)
    assert any("repo_vault_permission_casebook" in item.lower() for item in session.report.contract_casebook_case_studies)
    assert any("case study families:" in item.lower() and "signature or permit" in item.lower() for item in session.report.contract_casebook_case_studies)
    assert any("vault_permit_share_lane" in item.lower() for item in session.report.contract_casebook_priority_cases)
    assert any("casebook fit: repo_vault_permission_casebook" in item.lower() or "asset / accounting contour:" in item.lower() for item in session.report.contract_protocol_map)
    assert any("vault or share-accounting invariant:" in item.lower() or "signature or permit invariant:" in item.lower() for item in session.report.contract_protocol_invariants)
    assert any("consensus on vault or share-accounting" in item.lower() or "consensus on signature or permit" in item.lower() for item in session.report.contract_signal_consensus)
    assert any("family=vault or share-accounting" in item.lower() or "family=signature or permit" in item.lower() for item in session.report.contract_validation_matrix)
    assert any("repo_vault_permission_casebook" in item for item in session.report.contract_benchmark_posture)
    assert any("permit" in item.lower() and "repo-casebook" in item.lower() for item in session.report.contract_toolchain_alignment)
    assert any("permit" in item.lower() and "bounded testbed" in item.lower() for item in session.report.contract_review_queue)
    assert any("residual risk" in item.lower() and "signature or permit" in item.lower() for item in session.report.contract_residual_risk)
    assert any("permit" in item.lower() and "repo-casebook" in item.lower() for item in session.report.contract_exit_criteria)


def test_orchestrator_can_add_authorization_flow_testbed_for_relevant_contract_seed() -> None:
    run_root = Path(".test_runs") / make_id("contractauthflow")
    config = AppConfig.model_validate(
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
            "log_level": "WARNING",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )
    orchestrator = build_orchestrator(config)
    seed_text = build_smart_contract_seed(
        idea_text="Review role grants, operator paths, guardian authority, and pause controls for externally reachable privileged flows.",
        contract_code="""
pragma solidity ^0.8.20;
contract AuthorizationSurface {
    mapping(address => bool) public operators;
    bool public paused;
    function grantRole(address operator) external {
        operators[operator] = true;
    }
    function pause() external {
        paused = true;
    }
}
""".strip(),
        language="solidity",
        source_label="contracts/AuthorizationSurface.sol",
    )

    session = orchestrator.run_session(seed_text=seed_text, author="contract-auth-flow-test")

    tool_names = [job.tool_name for job in session.jobs]
    assert "contract_pattern_check_tool" in tool_names
    assert "contract_testbed_tool" in tool_names
    assert session.report is not None
    assert session.report.contract_testbed_findings
    assert any("authorization" in item.lower() or "pause" in item.lower() or "role" in item.lower() for item in session.report.contract_review_focus)
    assert any("authorization" in item.lower() or "pause" in item.lower() or "role" in item.lower() for item in session.report.contract_manual_review_items)


def test_orchestrator_can_add_asset_flow_testbed_for_relevant_contract_seed() -> None:
    run_root = Path(".test_runs") / make_id("contractassetflow")
    config = AppConfig.model_validate(
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
            "log_level": "WARNING",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )
    orchestrator = build_orchestrator(config)
    seed_text = build_smart_contract_seed(
        idea_text="Review deposit, claim, withdraw, rescue, and sweep fund flows for externally reachable asset movement risks.",
        contract_code="""
pragma solidity ^0.8.20;
interface IERC20 { function transfer(address to, uint256 amount) external returns (bool); }
contract AssetFlowSurface {
    mapping(address => uint256) public balances;
    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }
    function claim(uint256 amount) external {
        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok, "send failed");
        balances[msg.sender] -= amount;
    }
    function sweep(address token, address to, uint256 amount) external {
        IERC20(token).transfer(to, amount);
    }
}
""".strip(),
        language="solidity",
        source_label="contracts/AssetFlowSurface.sol",
    )

    session = orchestrator.run_session(seed_text=seed_text, author="contract-asset-flow-test")

    tool_names = [job.tool_name for job in session.jobs]
    assert "contract_pattern_check_tool" in tool_names
    assert "contract_testbed_tool" in tool_names
    assert session.report is not None
    assert session.report.contract_testbed_findings
    assert any("asset" in item.lower() or "fund" in item.lower() or "deposit" in item.lower() for item in session.report.contract_review_focus)
    assert any("rescue" in item.lower() or "sweep" in item.lower() or "asset" in item.lower() for item in session.report.contract_manual_review_items)


def test_orchestrator_can_add_vault_share_testbed_for_relevant_contract_seed() -> None:
    run_root = Path(".test_runs") / make_id("contractvaultshare")
    config = AppConfig.model_validate(
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
            "log_level": "WARNING",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )
    orchestrator = build_orchestrator(config)
    seed_text = build_smart_contract_seed(
        idea_text="Review ERC4626-style vault share mint, redeem, and asset conversion assumptions.",
        contract_code="""
pragma solidity ^0.8.20;
interface IERC20 { function transfer(address to, uint256 amount) external returns (bool); }
interface IERC20In { function transferFrom(address from, address to, uint256 amount) external returns (bool); }
contract VaultShareSurface {
    IERC20 public assetToken;
    mapping(address => uint256) public shares;
    uint256 public totalSupply;
    uint256 public totalAssets;
    function previewDeposit(uint256 assets) public pure returns (uint256) {
        return assets;
    }
    function deposit(uint256 assets) external {
        bool ok = IERC20In(address(assetToken)).transferFrom(msg.sender, address(this), assets);
        require(ok, "transfer failed");
        uint256 mintedShares = previewDeposit(assets);
        shares[msg.sender] += mintedShares;
        totalSupply += mintedShares;
        totalAssets += assets;
    }
    function redeem(uint256 sharesAmount) external {
        bool ok = assetToken.transfer(msg.sender, sharesAmount);
        require(ok, "transfer failed");
        shares[msg.sender] -= sharesAmount;
        totalSupply -= sharesAmount;
        totalAssets -= sharesAmount;
    }
}
""".strip(),
        language="solidity",
        source_label="contracts/VaultShareSurface.sol",
    )

    session = orchestrator.run_session(seed_text=seed_text, author="contract-vault-share-test")

    tool_names = [job.tool_name for job in session.jobs]
    assert "contract_pattern_check_tool" in tool_names
    assert "contract_testbed_tool" in tool_names
    assert session.report is not None
    assert session.report.contract_testbed_findings
    assert any("vault share" in item.lower() or "asset-share conversion" in item.lower() for item in session.report.contract_review_focus)
    assert any("share" in item.lower() or "conversion" in item.lower() for item in session.report.contract_manual_review_items)


def test_orchestrator_can_add_signature_testbed_for_relevant_contract_seed() -> None:
    run_root = Path(".test_runs") / make_id("contractsignature")
    config = AppConfig.model_validate(
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
            "log_level": "WARNING",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )
    orchestrator = build_orchestrator(config)
    seed_text = build_smart_contract_seed(
        idea_text="Review permit-style signature flows, nonce handling, and replay protection around ecrecover.",
        contract_code="""
pragma solidity ^0.8.20;
contract PermitSurface {
    function permitAction(address owner, address target, uint8 v, bytes32 r, bytes32 s) external pure returns (address) {
        bytes32 digest = keccak256(abi.encodePacked(owner, target));
        return ecrecover(digest, v, r, s);
    }
}
""".strip(),
        language="solidity",
        source_label="contracts/PermitSurface.sol",
    )

    session = orchestrator.run_session(seed_text=seed_text, author="contract-signature-test")

    tool_names = [job.tool_name for job in session.jobs]
    assert "contract_pattern_check_tool" in tool_names
    assert "contract_testbed_tool" in tool_names
    assert session.report is not None
    assert session.report.contract_testbed_findings
    assert any("signature" in item.lower() or "replay" in item.lower() for item in session.report.contract_review_focus)


def test_orchestrator_can_add_collateral_liquidation_testbed_for_relevant_contract_seed() -> None:
    run_root = Path(".test_runs") / make_id("contractcollateralliquidation")
    config = AppConfig.model_validate(
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
            "log_level": "WARNING",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )
    orchestrator = build_orchestrator(config)
    seed_text = build_smart_contract_seed(
        idea_text="Review collateral ratios, liquidation thresholds, reserve-derived pricing, and health-factor assumptions for the contract.",
        contract_code="""
pragma solidity ^0.8.20;
interface AggregatorV3Interface {
    function latestRoundData() external view returns (uint80, int256, uint256, uint256, uint80);
}
contract LiquidationSurface {
    AggregatorV3Interface public priceFeed;
    mapping(address => uint256) public collateral;
    mapping(address => uint256) public debt;

    function liquidate(address account) external {
        (, int256 price,,,) = priceFeed.latestRoundData();
        uint256 quote = uint256(price);
        collateral[account] = collateral[account] > quote ? collateral[account] - quote : 0;
        debt[account] = 0;
    }
}
""".strip(),
        language="solidity",
        source_label="contracts/LiquidationSurface.sol",
    )

    session = orchestrator.run_session(seed_text=seed_text, author="contract-collateral-liquidation-test")

    tool_names = [job.tool_name for job in session.jobs]
    assert "contract_pattern_check_tool" in tool_names
    assert "contract_testbed_tool" in tool_names
    assert session.report is not None
    assert session.report.contract_testbed_findings
    assert any(
        "collateral" in item.lower() or "liquidation" in item.lower() or "health-factor" in item.lower()
        for item in session.report.contract_review_focus
    )
    assert any(
        "collateral-ratio" in item.lower() or "liquidation" in item.lower() or "reserve" in item.lower()
        for item in session.report.contract_remediation_guidance
    )
    assert any(
        "collateral" in item.lower() or "liquidation" in item.lower() or "reserve" in item.lower()
        for item in session.report.contract_manual_review_items
    )


def test_orchestrator_can_add_reserve_fee_accounting_testbed_for_relevant_contract_seed() -> None:
    run_root = Path(".test_runs") / make_id("contractreservefee")
    config = AppConfig.model_validate(
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
            "log_level": "WARNING",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )
    orchestrator = build_orchestrator(config)
    seed_text = build_smart_contract_seed(
        idea_text="Review protocol fee skimming, reserve synchronization, and debt accounting assumptions for the contract.",
        contract_code="""
pragma solidity ^0.8.20;
contract ReserveFeeDebtSurface {
    uint256 public protocolReserves;
    mapping(address => uint256) public debt;
    uint256 public totalDebt;

    function skimProtocolFee(address payable treasury, uint256 amount) external {
        (bool ok,) = treasury.call{value: amount}("");
        require(ok, "send failed");
    }

    function accrueBorrowDebt(address account, uint256 amount) external {
        debt[account] += amount;
        totalDebt += amount;
    }
}
""".strip(),
        language="solidity",
        source_label="contracts/ReserveFeeDebtSurface.sol",
    )

    session = orchestrator.run_session(seed_text=seed_text, author="contract-reserve-fee-test")

    tool_names = [job.tool_name for job in session.jobs]
    assert "contract_pattern_check_tool" in tool_names
    assert "contract_testbed_tool" in tool_names
    assert session.report is not None
    assert session.report.contract_testbed_findings
    assert any(
        "protocol-fee" in item.lower() or "reserve synchronization" in item.lower() or "debt-state" in item.lower()
        for item in session.report.contract_review_focus
    )
    assert any(
        "reserve synchronization" in item.lower() or "debt-accounting" in item.lower() or "protocol-fee" in item.lower()
        for item in session.report.contract_remediation_guidance
    )
    assert any(
        "protocol-fee" in item.lower() or "debt-accounting" in item.lower() or "reserve-accounting" in item.lower()
        for item in session.report.contract_manual_review_items
    )


def test_orchestrator_uses_builtin_only_stack_for_vyper_contract_seed() -> None:
    run_root = Path(".test_runs") / make_id("contractvyper")
    config = AppConfig.model_validate(
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
            "log_level": "WARNING",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )
    orchestrator = build_orchestrator(config)
    seed_text = build_smart_contract_seed(
        idea_text="Audit the contract for reachable functions, ownership flow, and review-worthy access surfaces.",
        contract_code=VYPER_SAMPLE,
        language="vyper",
        source_label="contracts/Wallet.vy",
    )

    session = orchestrator.run_session(seed_text=seed_text, author="contract-vyper-test")

    tool_names = [job.tool_name for job in session.jobs]
    assert tool_names
    assert "contract_parser_tool" in tool_names
    assert "contract_surface_tool" in tool_names
    assert "contract_pattern_check_tool" in tool_names
    assert "contract_compile_tool" not in tool_names
    assert "slither_audit_tool" not in tool_names
