from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from app.tools.smart_contract_utils import (
    build_contract_outline,
    detect_contract_patterns,
    prioritize_contract_issues,
    summarize_contract_surface,
)


def _ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = str(value).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


class ContractTestbedRunner:
    """Run built-in bounded smart-contract review corpora locally."""

    def __init__(self, *, enabled: bool = True) -> None:
        self.enabled = enabled

    def is_available(self) -> bool:
        return self.enabled

    def run_testbed(self, *, testbed_name: str, case_limit: int = 8) -> dict[str, Any]:
        if not self.enabled:
            return self._result(
                status="unavailable",
                conclusion="The built-in smart-contract testbed layer is disabled in the current configuration.",
                notes=["Enable local_research.smart_contract_testbeds_enabled to allow bounded local contract testbed sweeps."],
                result_data={"testbed_name": testbed_name, "case_count": 0, "anomaly_count": 0, "cases": []},
            )

        handlers = {
            "reentrancy_review_corpus": self._reentrancy_review_corpus,
            "access_control_corpus": self._access_control_corpus,
            "authorization_flow_corpus": self._authorization_flow_corpus,
            "dangerous_call_corpus": self._dangerous_call_corpus,
            "upgrade_surface_corpus": self._upgrade_surface_corpus,
            "upgrade_validation_corpus": self._upgrade_validation_corpus,
            "time_entropy_corpus": self._time_entropy_corpus,
            "token_interaction_corpus": self._token_interaction_corpus,
            "approval_review_corpus": self._approval_review_corpus,
            "accounting_review_corpus": self._accounting_review_corpus,
            "asset_flow_corpus": self._asset_flow_corpus,
            "vault_share_corpus": self._vault_share_corpus,
            "proxy_storage_corpus": self._proxy_storage_corpus,
            "assembly_review_corpus": self._assembly_review_corpus,
            "state_machine_corpus": self._state_machine_corpus,
            "signature_review_corpus": self._signature_review_corpus,
            "oracle_review_corpus": self._oracle_review_corpus,
            "collateral_liquidation_corpus": self._collateral_liquidation_corpus,
            "reserve_fee_accounting_corpus": self._reserve_fee_accounting_corpus,
            "loop_payout_corpus": self._loop_payout_corpus,
            "repo_upgrade_casebook": self._repo_upgrade_casebook,
            "repo_asset_flow_casebook": self._repo_asset_flow_casebook,
            "repo_oracle_casebook": self._repo_oracle_casebook,
            "repo_protocol_accounting_casebook": self._repo_protocol_accounting_casebook,
            "repo_vault_permission_casebook": self._repo_vault_permission_casebook,
            "repo_governance_timelock_casebook": self._repo_governance_timelock_casebook,
            "repo_rewards_distribution_casebook": self._repo_rewards_distribution_casebook,
            "repo_stablecoin_collateral_casebook": self._repo_stablecoin_collateral_casebook,
            "repo_amm_liquidity_casebook": self._repo_amm_liquidity_casebook,
            "repo_bridge_custody_casebook": self._repo_bridge_custody_casebook,
            "repo_staking_rebase_casebook": self._repo_staking_rebase_casebook,
            "repo_keeper_auction_casebook": self._repo_keeper_auction_casebook,
            "repo_treasury_vesting_casebook": self._repo_treasury_vesting_casebook,
            "repo_insurance_recovery_casebook": self._repo_insurance_recovery_casebook,
        }
        if testbed_name not in handlers:
            return self._result(
                status="invalid_input",
                conclusion="The requested smart-contract testbed name is not supported by the local bounded testbed layer.",
                notes=["Use a supported built-in smart-contract testbed name."],
                result_data={"testbed_name": testbed_name, "case_count": 0, "anomaly_count": 0, "cases": []},
            )

        cases = handlers[testbed_name]()[: max(1, min(case_limit, 16))]
        anomaly_case_ids = [str(case["case_id"]) for case in cases if case.get("anomaly_detected")]
        issue_type_counts = self._issue_type_counts(cases)
        anomaly_count = len(anomaly_case_ids)
        repo_case_count = sum(1 for case in cases if case.get("repo_case"))
        matched_review_lane_count = sum(len(case.get("matched_review_lanes", [])) for case in cases)
        matched_risk_family_lane_count = sum(len(case.get("matched_risk_family_lanes", [])) for case in cases)
        matched_function_priority_count = sum(len(case.get("matched_function_family_priorities", [])) for case in cases)
        matched_case_ids = [
            str(case.get("case_id") or "").strip()
            for case in cases
            if case.get("repo_case")
            and (
                case.get("matched_review_lanes")
                or case.get("matched_risk_family_lanes")
                or case.get("matched_function_family_priorities")
            )
        ]
        matched_case_ids = _ordered_unique(matched_case_ids)
        remediation_validation = self._build_remediation_validation(cases)
        return self._result(
            status="ok" if anomaly_count == 0 else "observed_issue",
            conclusion=(
                "The bounded smart-contract testbed sweep found no review-bearing anomaly signal."
                if anomaly_count == 0
                else "The bounded smart-contract testbed sweep surfaced review-bearing cases."
            ),
            notes=["This runner executes only built-in local smart-contract review corpora."],
            result_data={
                "testbed_name": testbed_name,
                "case_count": len(cases),
                "anomaly_count": anomaly_count,
                "anomaly_case_ids": anomaly_case_ids,
                "repo_case_count": repo_case_count,
                "matched_review_lane_count": matched_review_lane_count,
                "matched_risk_family_lane_count": matched_risk_family_lane_count,
                "matched_function_priority_count": matched_function_priority_count,
                "matched_case_count": len(matched_case_ids),
                "matched_case_ids": matched_case_ids,
                "repo_casebook_coverage": self._build_repo_casebook_coverage(
                    testbed_name=testbed_name,
                    repo_case_count=repo_case_count,
                    matched_case_ids=matched_case_ids,
                    matched_review_lane_count=matched_review_lane_count,
                    matched_risk_family_lane_count=matched_risk_family_lane_count,
                    matched_function_priority_count=matched_function_priority_count,
                ),
                "validation_group_count": len({str(case.get('variant_group')).strip() for case in cases if str(case.get('variant_group') or '').strip()}),
                "validated_group_count": len(remediation_validation),
                "remediation_validation": remediation_validation,
                "issue_type_counts": issue_type_counts,
                "cases": cases,
            },
        )

    def _reentrancy_review_corpus(self) -> list[dict[str, Any]]:
        return [
            self._build_contract_case(
                case_id="unsafe_withdraw_after_call",
                variant_group="withdrawal_ordering",
                variant_role="signal",
                validation_focus="withdraw ordering and reentrancy-adjacent sequencing",
                contract_code="""
pragma solidity ^0.8.20;
contract UnsafeVault {
    mapping(address => uint256) public balances;
    function withdraw(uint256 amount) external {
        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok, "send failed");
        balances[msg.sender] -= amount;
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="checks_effects_interactions_first",
                variant_group="withdrawal_ordering",
                variant_role="control",
                validation_focus="withdraw ordering and reentrancy-adjacent sequencing",
                contract_code="""
pragma solidity ^0.8.20;
contract SaferVault {
    mapping(address => uint256) public balances;
    function withdraw(uint256 amount) external {
        balances[msg.sender] -= amount;
        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok, "send failed");
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="non_reentrant_guarded_withdraw",
                variant_group="withdrawal_ordering",
                variant_role="control",
                validation_focus="withdraw ordering and reentrancy-adjacent sequencing",
                contract_code="""
pragma solidity ^0.8.20;
contract GuardedVault {
    mapping(address => uint256) public balances;
    modifier nonReentrant() { _; }
    function withdraw(uint256 amount) external nonReentrant {
        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok, "send failed");
        balances[msg.sender] -= amount;
    }
}
""".strip(),
            ),
        ]

    def _access_control_corpus(self) -> list[dict[str, Any]]:
        return [
            self._build_contract_case(
                case_id="unguarded_admin_setter",
                variant_group="owner_authority_boundary",
                variant_role="signal",
                validation_focus="owner and admin authority boundaries",
                contract_code="""
pragma solidity ^0.8.20;
contract AdminSurface {
    address public owner;
    function adminSetOwner(address newOwner) external {
        owner = newOwner;
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="guarded_owner_setter",
                variant_group="owner_authority_boundary",
                variant_role="control",
                validation_focus="owner and admin authority boundaries",
                contract_code="""
pragma solidity ^0.8.20;
contract GuardedAdminSurface {
    address public owner;
    modifier onlyOwner() { _; }
    function setOwner(address newOwner) external onlyOwner {
        owner = newOwner;
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="public_initializer",
                contract_code="""
pragma solidity ^0.8.20;
contract InitializableSurface {
    address public owner;
    function initialize(address newOwner) external {
        owner = newOwner;
    }
}
""".strip(),
            ),
        ]

    def _authorization_flow_corpus(self) -> list[dict[str, Any]]:
        return [
            self._build_contract_case(
                case_id="unguarded_role_grant_and_pause",
                variant_group="role_pause_authority",
                variant_role="signal",
                validation_focus="role, operator, and pause authority boundaries",
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
            ),
            self._build_contract_case(
                case_id="guarded_role_grant_and_pause",
                variant_group="role_pause_authority",
                variant_role="control",
                validation_focus="role, operator, and pause authority boundaries",
                contract_code="""
pragma solidity ^0.8.20;
contract GuardedAuthorizationSurface {
    address public owner;
    mapping(address => bool) public operators;
    bool public paused;
    modifier onlyOwner() { _; }

    function grantRole(address operator) external onlyOwner {
        operators[operator] = true;
    }

    function pause() external onlyOwner {
        paused = true;
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="role_guarded_operator_update",
                variant_group="role_pause_authority",
                variant_role="control",
                validation_focus="role, operator, and pause authority boundaries",
                contract_code="""
pragma solidity ^0.8.20;
contract RoleGuardedAuthorizationSurface {
    mapping(address => bool) public operators;
    function setOperator(address operator, bool enabled) external {
        require(hasRole(msg.sender), "role");
        operators[operator] = enabled;
    }
    function hasRole(address account) internal pure returns (bool) {
        return account != address(0);
    }
}
""".strip(),
            ),
        ]

    def _dangerous_call_corpus(self) -> list[dict[str, Any]]:
        return [
            self._build_contract_case(
                case_id="delegatecall_executor",
                contract_code="""
pragma solidity ^0.8.20;
contract DelegateSurface {
    function execute(address target, bytes calldata data) external {
        (bool ok,) = target.delegatecall(data);
        require(ok, "delegate failed");
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="tx_origin_gate",
                contract_code="""
pragma solidity ^0.8.20;
contract OriginGate {
    address public owner;
    function sweep() external {
        require(tx.origin == owner, "owner");
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="unguarded_selfdestruct",
                contract_code="""
pragma solidity ^0.8.20;
contract DestructSurface {
    function destroy(address payable target) external {
        selfdestruct(target);
    }
}
""".strip(),
            ),
        ]

    def _upgrade_surface_corpus(self) -> list[dict[str, Any]]:
        return [
            self._build_contract_case(
                case_id="unguarded_upgrade_to",
                variant_group="upgrade_authority",
                variant_role="signal",
                validation_focus="upgrade authority and implementation update boundaries",
                contract_code="""
pragma solidity ^0.8.20;
contract UpgradeSurface {
    address public implementation;
    function upgradeTo(address newImplementation) external {
        implementation = newImplementation;
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="guarded_upgrade_to",
                variant_group="upgrade_authority",
                variant_role="control",
                validation_focus="upgrade authority and implementation update boundaries",
                contract_code="""
pragma solidity ^0.8.20;
contract GuardedUpgradeSurface {
    address public implementation;
    modifier onlyOwner() { _; }
    function upgradeTo(address newImplementation) external onlyOwner {
        implementation = newImplementation;
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="delegatecall_router",
                contract_code="""
pragma solidity ^0.8.20;
contract UpgradeExecutor {
    function upgradeAndExecute(address implementation, bytes calldata data) external {
        (bool ok,) = implementation.delegatecall(data);
        require(ok, "delegate failed");
    }
}
""".strip(),
            ),
        ]

    def _time_entropy_corpus(self) -> list[dict[str, Any]]:
        return [
            self._build_contract_case(
                case_id="timestamp_entropy_lottery",
                contract_code="""
pragma solidity ^0.8.20;
contract TimestampLottery {
    address[] public players;
    function pickWinner() external view returns (uint256) {
        return uint256(keccak256(abi.encodePacked(block.timestamp, players.length))) % players.length;
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="blockhash_random_draw",
                contract_code="""
pragma solidity ^0.8.20;
contract BlockhashDraw {
    function draw(uint256 upper) external view returns (uint256) {
        return uint256(blockhash(block.number - 1)) % upper;
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="time_lock_release",
                contract_code="""
pragma solidity ^0.8.20;
contract Timelock {
    uint256 public unlockAt;
    function release() external view returns (bool) {
        return block.timestamp >= unlockAt;
    }
}
""".strip(),
            ),
        ]

    def _upgrade_validation_corpus(self) -> list[dict[str, Any]]:
        return [
            self._build_contract_case(
                case_id="upgrade_without_zero_or_code_check",
                variant_group="implementation_target_validation",
                variant_role="signal",
                validation_focus="implementation target validation",
                contract_code="""
pragma solidity ^0.8.20;
contract UpgradeValidationSurface {
    address public implementation;
    function upgradeTo(address newImplementation) external {
        implementation = newImplementation;
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="upgrade_with_zero_check_only",
                variant_group="implementation_target_validation",
                variant_role="control",
                validation_focus="implementation target validation",
                contract_code="""
pragma solidity ^0.8.20;
contract ZeroCheckedUpgradeSurface {
    address public implementation;
    function upgradeTo(address newImplementation) external {
        require(newImplementation != address(0), "zero");
        implementation = newImplementation;
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="upgrade_with_zero_and_code_check",
                variant_group="implementation_target_validation",
                variant_role="control",
                validation_focus="implementation target validation",
                contract_code="""
pragma solidity ^0.8.20;
contract CheckedUpgradeSurface {
    address public implementation;
    function upgradeTo(address newImplementation) external {
        require(newImplementation != address(0), "zero");
        require(newImplementation.code.length > 0, "no code");
        implementation = newImplementation;
    }
}
""".strip(),
            ),
        ]

    def _token_interaction_corpus(self) -> list[dict[str, Any]]:
        return [
            self._build_contract_case(
                case_id="unchecked_token_sweep",
                variant_group="token_transfer_validation",
                variant_role="signal",
                validation_focus="token transfer return-value validation",
                contract_code="""
pragma solidity ^0.8.20;
interface IERC20 { function transfer(address to, uint256 amount) external returns (bool); }
contract TokenSweep {
    function sweep(address token, address to, uint256 amount) external {
        IERC20(token).transfer(to, amount);
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="arbitrary_from_transfer",
                contract_code="""
pragma solidity ^0.8.20;
interface IERC20 { function transferFrom(address from, address to, uint256 amount) external returns (bool); }
contract RescueSurface {
    function rescue(address token, address from, address to, uint256 amount) external {
        IERC20(token).transferFrom(from, to, amount);
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="fee_token_deposit_without_balance_delta",
                variant_group="token_balance_delta_accounting",
                variant_role="signal",
                validation_focus="fee-on-transfer token balance-delta accounting",
                contract_code="""
pragma solidity ^0.8.20;
interface IERC20 { function transferFrom(address from, address to, uint256 amount) external returns (bool); }
contract FeeTokenVault {
    mapping(address => uint256) public shares;
    function deposit(address token, uint256 amount) external {
        require(IERC20(token).transferFrom(msg.sender, address(this), amount), "transfer");
        shares[msg.sender] += amount;
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="fee_token_deposit_with_balance_delta",
                variant_group="token_balance_delta_accounting",
                variant_role="control",
                validation_focus="fee-on-transfer token balance-delta accounting",
                contract_code="""
pragma solidity 0.8.20;
interface IERC20 {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}
contract GuardedFeeTokenVault {
    mapping(address => uint256) public shares;
    function deposit(address token, uint256 amount) external {
        uint256 balanceBefore = IERC20(token).balanceOf(address(this));
        require(IERC20(token).transferFrom(msg.sender, address(this), amount), "transfer");
        uint256 receivedAmount = IERC20(token).balanceOf(address(this)) - balanceBefore;
        shares[msg.sender] += receivedAmount;
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="checked_token_transfer",
                variant_group="token_transfer_validation",
                variant_role="control",
                validation_focus="token transfer return-value validation",
                contract_code="""
pragma solidity ^0.8.20;
interface IERC20 { function transfer(address to, uint256 amount) external returns (bool); }
contract CheckedSweep {
    function sweep(address token, address to, uint256 amount) external {
        bool ok = IERC20(token).transfer(to, amount);
        require(ok, "transfer failed");
    }
}
""".strip(),
            ),
        ]

    def _approval_review_corpus(self) -> list[dict[str, Any]]:
        return [
            self._build_contract_case(
                case_id="unchecked_direct_approve",
                variant_group="approval_return_handling",
                variant_role="signal",
                validation_focus="approval return-value handling and allowance transitions",
                contract_code="""
pragma solidity ^0.8.20;
interface IERC20 { function approve(address spender, uint256 amount) external returns (bool); }
contract ApprovalSurface {
    function approveSpender(address token, address spender, uint256 amount) external {
        IERC20(token).approve(spender, amount);
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="checked_direct_approve",
                variant_group="approval_return_handling",
                variant_role="control",
                validation_focus="approval return-value handling and allowance transitions",
                contract_code="""
pragma solidity ^0.8.20;
interface IERC20 { function approve(address spender, uint256 amount) external returns (bool); }
contract CheckedApprovalSurface {
    function approveSpender(address token, address spender, uint256 amount) external {
        bool ok = IERC20(token).approve(spender, amount);
        require(ok, "approve failed");
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="allowance_rescue_flow",
                contract_code="""
pragma solidity ^0.8.20;
interface IERC20 { function approve(address spender, uint256 amount) external returns (bool); function transferFrom(address from, address to, uint256 amount) external returns (bool); }
contract AllowanceRescueSurface {
    function rescue(address token, address from, address spender, address to, uint256 amount) external {
        IERC20(token).approve(spender, amount);
        IERC20(token).transferFrom(from, to, amount);
    }
}
""".strip(),
            ),
        ]

    def _accounting_review_corpus(self) -> list[dict[str, Any]]:
        return [
            self._build_contract_case(
                case_id="withdraw_after_call_without_balance_check",
                variant_group="accounting_exit_ordering",
                variant_role="signal",
                validation_focus="balance validation and accounting update ordering",
                contract_code="""
pragma solidity ^0.8.20;
contract AccountingSurface {
    mapping(address => uint256) public balances;
    function withdraw(uint256 amount) external {
        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok, "send failed");
        balances[msg.sender] -= amount;
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="claim_marked_after_transfer",
                contract_code="""
pragma solidity ^0.8.20;
contract ClaimSurface {
    mapping(address => bool) public claimed;
    function claim() external {
        (bool ok,) = msg.sender.call{value: 1 ether}("");
        require(ok, "send failed");
        claimed[msg.sender] = true;
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="checked_withdraw_before_transfer",
                variant_group="accounting_exit_ordering",
                variant_role="control",
                validation_focus="balance validation and accounting update ordering",
                contract_code="""
pragma solidity 0.8.20;
contract CheckedAccountingSurface {
    mapping(address => uint256) public balances;
    function withdraw(uint256 amount) external {
        require(balances[msg.sender] >= amount, "insufficient");
        balances[msg.sender] -= amount;
        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok, "send failed");
    }
}
""".strip(),
            ),
        ]

    def _asset_flow_corpus(self) -> list[dict[str, Any]]:
        return [
            self._build_contract_case(
                case_id="deposit_and_unguarded_sweep",
                variant_group="asset_exit_authority",
                variant_role="signal",
                validation_focus="asset exit and sweep authority",
                contract_code="""
pragma solidity ^0.8.20;
interface IERC20 { function transfer(address to, uint256 amount) external returns (bool); }
contract AssetFlowSurface {
    mapping(address => uint256) public balances;
    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }
    function sweep(address token, address to, uint256 amount) external {
        IERC20(token).transfer(to, amount);
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="deposit_and_claim_without_balance_validation",
                contract_code="""
pragma solidity ^0.8.20;
contract ClaimFlowSurface {
    mapping(address => uint256) public balances;
    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }
    function claim(uint256 amount) external {
        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok, "send failed");
        balances[msg.sender] -= amount;
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="guarded_rescue_with_validation",
                variant_group="asset_exit_authority",
                variant_role="control",
                validation_focus="asset exit and sweep authority",
                contract_code="""
pragma solidity 0.8.20;
interface IERC20 { function transfer(address to, uint256 amount) external returns (bool); }
contract GuardedAssetFlowSurface {
    mapping(address => uint256) public balances;
    modifier onlyOwner() { _; }
    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }
    function withdraw(uint256 amount) external {
        require(balances[msg.sender] >= amount, "insufficient");
        balances[msg.sender] -= amount;
        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok, "send failed");
    }
    function rescue(address token, address to, uint256 amount) external onlyOwner {
        bool ok = IERC20(token).transfer(to, amount);
        require(ok, "transfer failed");
    }
}
""".strip(),
            ),
        ]

    def _vault_share_corpus(self) -> list[dict[str, Any]]:
        return [
            self._build_contract_case(
                case_id="mint_shares_without_asset_backing",
                variant_group="vault_share_accounting",
                variant_role="signal",
                validation_focus="vault share backing and redemption validation",
                contract_code="""
pragma solidity ^0.8.20;
contract FreeMintVault {
    mapping(address => uint256) public shares;
    uint256 public totalSupply;
    function mint(uint256 sharesAmount) external {
        shares[msg.sender] += sharesAmount;
        totalSupply += sharesAmount;
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="redeem_without_share_validation",
                contract_code="""
pragma solidity ^0.8.20;
interface IERC20 { function transfer(address to, uint256 amount) external returns (bool); }
contract UnsafeRedeemVault {
    IERC20 public assetToken;
    mapping(address => uint256) public shares;
    uint256 public totalSupply;
    function redeem(uint256 sharesAmount) external {
        bool ok = assetToken.transfer(msg.sender, sharesAmount);
        require(ok, "transfer failed");
        shares[msg.sender] -= sharesAmount;
        totalSupply -= sharesAmount;
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="previewed_guarded_vault",
                variant_group="vault_share_accounting",
                variant_role="control",
                validation_focus="vault share backing and redemption validation",
                contract_code="""
pragma solidity 0.8.20;
interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
}
contract GuardedVault {
    IERC20 public assetToken;
    mapping(address => uint256) public shares;
    uint256 public totalSupply;
    uint256 public totalAssets;
    function previewDeposit(uint256 assets) public pure returns (uint256) {
        return assets;
    }
    function convertToAssets(uint256 sharesAmount) public pure returns (uint256) {
        return sharesAmount;
    }
    function deposit(uint256 assets) external {
        require(assets > 0, "zero");
        bool ok = assetToken.transferFrom(msg.sender, address(this), assets);
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
        uint256 assets = convertToAssets(sharesAmount);
        totalAssets -= assets;
        bool ok = assetToken.transfer(msg.sender, assets);
        require(ok, "transfer failed");
    }
}
""".strip(),
            ),
        ]

    def _proxy_storage_corpus(self) -> list[dict[str, Any]]:
        return [
            self._build_contract_case(
                case_id="naive_proxy_fallback_delegatecall",
                contract_code="""
pragma solidity ^0.8.20;
contract NaiveProxy {
    address public implementation;
    fallback() external payable {
        (bool ok,) = implementation.delegatecall(msg.data);
        require(ok, "delegate failed");
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="erc1967_slot_upgrade_surface",
                contract_code="""
pragma solidity ^0.8.20;
contract SlotProxy {
    bytes32 internal constant _IMPLEMENTATION_SLOT = bytes32(uint256(keccak256("eip1967.proxy.implementation")) - 1);
    fallback() external payable {
        address impl;
        assembly {
            impl := sload(_IMPLEMENTATION_SLOT)
        }
        (bool ok,) = impl.delegatecall(msg.data);
        require(ok, "delegate failed");
    }
    function upgradeTo(address newImplementation) external {
        require(newImplementation != address(0), "zero");
        require(newImplementation.code.length > 0, "no code");
        assembly {
            sstore(_IMPLEMENTATION_SLOT, newImplementation)
        }
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="guarded_implementation_setter_without_proxy",
                contract_code="""
pragma solidity 0.8.20;
contract SimpleUpgradeableSurface {
    address public implementation;
    modifier onlyOwner() { _; }
    function upgradeTo(address newImplementation) external onlyOwner {
        require(newImplementation != address(0), "zero");
        require(newImplementation.code.length > 0, "no code");
        implementation = newImplementation;
    }
}
""".strip(),
            ),
        ]

    def _assembly_review_corpus(self) -> list[dict[str, Any]]:
        return [
            self._build_contract_case(
                case_id="assembly_storage_write",
                contract_code="""
pragma solidity ^0.8.20;
contract AssemblyStore {
    function setOwner(address newOwner) external {
        assembly {
            sstore(0, newOwner)
        }
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="assembly_delegate_router",
                contract_code="""
pragma solidity ^0.8.20;
contract AssemblyRouter {
    function route(address target, bytes calldata data) external returns (bytes memory output) {
        assembly {
            let ptr := mload(0x40)
            calldatacopy(ptr, data.offset, data.length)
            let success := delegatecall(gas(), target, ptr, data.length, 0, 0)
            if iszero(success) { revert(0, 0) }
            output := ptr
        }
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="no_assembly_helper",
                contract_code="""
pragma solidity ^0.8.20;
contract PlainHelper {
    function ping() external pure returns (uint256) {
        return 1;
    }
}
""".strip(),
            ),
        ]

    def _state_machine_corpus(self) -> list[dict[str, Any]]:
        return [
            self._build_contract_case(
                case_id="status_update_after_external_call",
                variant_group="state_transition_ordering",
                variant_role="signal",
                validation_focus="state-transition ordering around external calls",
                contract_code="""
pragma solidity ^0.8.20;
contract StateMachineSurface {
    enum Status { Idle, Executing, Done }
    Status public status;
    function execute(address target) external {
        (bool ok,) = target.call("");
        require(ok, "call failed");
        status = Status.Done;
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="status_update_before_external_call",
                variant_group="state_transition_ordering",
                variant_role="control",
                validation_focus="state-transition ordering around external calls",
                contract_code="""
pragma solidity ^0.8.20;
contract SaferStateMachineSurface {
    enum Status { Idle, Executing, Done }
    Status public status;
    function execute(address target) external {
        status = Status.Executing;
        status = Status.Done;
        (bool ok,) = target.call("");
        require(ok, "call failed");
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="phase_transition_without_external_call",
                contract_code="""
pragma solidity ^0.8.20;
contract PhaseMachineSurface {
    uint256 public phase;
    function advance() external {
        phase = phase + 1;
    }
}
""".strip(),
            ),
        ]

    def _signature_review_corpus(self) -> list[dict[str, Any]]:
        return [
            self._build_contract_case(
                case_id="permit_without_nonce_or_deadline",
                variant_group="signature_replay_controls",
                variant_role="signal",
                validation_focus="signature replay and nonce controls",
                contract_code="""
pragma solidity ^0.8.20;
contract SignatureSurface {
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
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="permit_with_nonce_and_deadline",
                variant_group="signature_replay_controls",
                variant_role="control",
                validation_focus="signature replay and nonce controls",
                contract_code="""
pragma solidity 0.8.20;
contract CheckedSignatureSurface {
    mapping(address => uint256) public nonces;
    function permitAction(
        address owner,
        address target,
        uint256 nonce,
        uint256 deadline,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) external returns (address) {
        require(block.timestamp <= deadline, "expired");
        require(nonce == nonces[owner]++, "nonce");
        bytes32 digest = keccak256(abi.encodePacked(owner, target, nonce, deadline));
        return ecrecover(digest, v, r, s);
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="used_digest_registry_signature_flow",
                contract_code="""
pragma solidity 0.8.20;
contract UsedDigestSignatureSurface {
    mapping(bytes32 => bool) public usedDigests;
    function executeSigned(
        address owner,
        address target,
        bytes32 digest,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) external returns (address) {
        require(!usedDigests[digest], "used");
        usedDigests[digest] = true;
        bytes32 payload = keccak256(abi.encodePacked(owner, target, digest));
        return ecrecover(payload, v, r, s);
    }
}
""".strip(),
            ),
        ]

    def _oracle_review_corpus(self) -> list[dict[str, Any]]:
        return [
            self._build_contract_case(
                case_id="price_feed_without_staleness_check",
                variant_group="oracle_freshness_controls",
                variant_role="signal",
                validation_focus="oracle freshness and staleness controls",
                contract_code="""
pragma solidity ^0.8.20;
interface AggregatorV3Interface {
    function latestRoundData() external view returns (uint80, int256, uint256, uint256, uint80);
}
contract OracleSurface {
    AggregatorV3Interface public priceFeed;
    function quote() external view returns (int256) {
        (, int256 price,,,) = priceFeed.latestRoundData();
        return price;
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="price_feed_with_staleness_check",
                variant_group="oracle_freshness_controls",
                variant_role="control",
                validation_focus="oracle freshness and staleness controls",
                contract_code="""
pragma solidity 0.8.20;
interface AggregatorV3Interface {
    function latestRoundData() external view returns (uint80, int256, uint256, uint256, uint80);
}
contract CheckedOracleSurface {
    AggregatorV3Interface public priceFeed;
    uint256 public maxDelay = 1 hours;
    function quote() external view returns (int256) {
        (, int256 price,, uint256 updatedAt,) = priceFeed.latestRoundData();
        require(block.timestamp - updatedAt <= maxDelay, "stale");
        return price;
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="oracle_price_math_without_decimal_scaling",
                variant_group="oracle_decimal_scaling",
                variant_role="signal",
                validation_focus="oracle decimal scaling and price precision",
                contract_code="""
pragma solidity ^0.8.20;
interface AggregatorV3Interface {
    function latestRoundData() external view returns (uint80, int256, uint256, uint256, uint80);
}
contract PriceMathSurface {
    AggregatorV3Interface public priceFeed;
    function quote(uint256 amount) external view returns (uint256) {
        (, int256 price,, uint256 updatedAt,) = priceFeed.latestRoundData();
        require(price > 0, "bad price");
        require(updatedAt != 0, "stale");
        return amount * uint256(price) / 1 ether;
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="oracle_price_math_with_decimal_scaling",
                variant_group="oracle_decimal_scaling",
                variant_role="control",
                validation_focus="oracle decimal scaling and price precision",
                contract_code="""
pragma solidity 0.8.20;
interface AggregatorV3Interface {
    function latestRoundData() external view returns (uint80, int256, uint256, uint256, uint80);
    function decimals() external view returns (uint8);
}
contract GuardedPriceMathSurface {
    AggregatorV3Interface public priceFeed;
    function quote(uint256 amount) external view returns (uint256) {
        (uint80 roundId, int256 price,, uint256 updatedAt, uint80 answeredInRound) = priceFeed.latestRoundData();
        require(price > 0, "bad price");
        require(updatedAt != 0 && answeredInRound >= roundId, "stale");
        uint8 decimals = priceFeed.decimals();
        return amount * uint256(price) / (10 ** decimals);
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="reserve_spot_price_without_window",
                contract_code="""
pragma solidity ^0.8.20;
interface IPair { function getReserves() external view returns (uint112, uint112, uint32); }
contract ReserveOracleSurface {
    function quote(address pair) external view returns (uint256) {
        (uint112 reserve0, uint112 reserve1,) = IPair(pair).getReserves();
        return uint256(reserve1) * 1e18 / uint256(reserve0);
    }
}
""".strip(),
            ),
        ]

    def _collateral_liquidation_corpus(self) -> list[dict[str, Any]]:
        return [
            self._build_contract_case(
                case_id="liquidation_without_fresh_price_or_health_check",
                variant_group="liquidation_price_controls",
                variant_role="signal",
                validation_focus="collateral ratio and liquidation price controls",
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
            ),
            self._build_contract_case(
                case_id="liquidation_with_fresh_price_and_health_check",
                variant_group="liquidation_price_controls",
                variant_role="control",
                validation_focus="collateral ratio and liquidation price controls",
                contract_code="""
pragma solidity ^0.8.20;
interface AggregatorV3Interface {
    function latestRoundData() external view returns (uint80, int256, uint256, uint256, uint80);
}
contract GuardedLiquidationSurface {
    AggregatorV3Interface public priceFeed;
    mapping(address => uint256) public collateral;
    mapping(address => uint256) public debt;
    uint256 public maxDelay = 1 hours;

    function liquidate(address account) external {
        (, int256 price,, uint256 updatedAt,) = priceFeed.latestRoundData();
        require(block.timestamp - updatedAt <= maxDelay, "stale");
        require(collateral[account] * uint256(price) < debt[account] * 1e18, "healthy");
        collateral[account] = collateral[account] > uint256(price) ? collateral[account] - uint256(price) : 0;
        debt[account] = 0;
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="collateral_ratio_from_spot_reserves",
                variant_group="reserve_price_controls",
                variant_role="signal",
                validation_focus="reserve-derived collateral and liquidation pricing assumptions",
                contract_code="""
pragma solidity ^0.8.20;
interface IPair { function getReserves() external view returns (uint112, uint112, uint32); }
contract ReserveCollateralSurface {
    function collateralRatio(address pair) external view returns (uint256) {
        (uint112 reserve0, uint112 reserve1,) = IPair(pair).getReserves();
        return uint256(reserve1) * 1e18 / uint256(reserve0);
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="collateral_ratio_with_reserve_window_check",
                variant_group="reserve_price_controls",
                variant_role="control",
                validation_focus="reserve-derived collateral and liquidation pricing assumptions",
                contract_code="""
pragma solidity ^0.8.20;
interface IPair { function getReserves() external view returns (uint112, uint112, uint32); }
contract WindowedReserveCollateralSurface {
    uint32 public minWindow = 30 minutes;
    function collateralRatio(address pair, uint32 window) external view returns (uint256) {
        require(window >= minWindow, "window");
        (uint112 reserve0, uint112 reserve1, uint32 lastTimestamp) = IPair(pair).getReserves();
        require(block.timestamp - lastTimestamp <= window, "stale reserve");
        return uint256(reserve1) * 1e18 / uint256(reserve0);
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="liquidation_bonus_without_fee_cap",
                variant_group="liquidation_fee_controls",
                variant_role="signal",
                validation_focus="liquidation bonus and fee-allocation controls",
                contract_code="""
pragma solidity ^0.8.20;
interface AggregatorV3Interface {
    function latestRoundData() external view returns (uint80, int256, uint256, uint256, uint80);
}
contract LiquidationFeeSurface {
    AggregatorV3Interface public priceFeed;
    mapping(address => uint256) public collateral;
    mapping(address => uint256) public debt;
    mapping(address => uint256) public liquidatorRewards;

    function liquidate(address account) external {
        (, int256 price,, uint256 updatedAt,) = priceFeed.latestRoundData();
        require(block.timestamp - updatedAt <= 1 hours, "stale");
        require(collateral[account] * uint256(price) < debt[account] * 1e18, "healthy");
        uint256 liquidationBonus = debt[account] / 5;
        liquidatorRewards[msg.sender] += liquidationBonus;
        collateral[account] = collateral[account] > uint256(price) + liquidationBonus
            ? collateral[account] - uint256(price) - liquidationBonus
            : 0;
        debt[account] = 0;
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="liquidation_bonus_with_fee_cap",
                variant_group="liquidation_fee_controls",
                variant_role="control",
                validation_focus="liquidation bonus and fee-allocation controls",
                contract_code="""
pragma solidity ^0.8.20;
interface AggregatorV3Interface {
    function latestRoundData() external view returns (uint80, int256, uint256, uint256, uint80);
}
contract GuardedLiquidationFeeSurface {
    AggregatorV3Interface public priceFeed;
    mapping(address => uint256) public collateral;
    mapping(address => uint256) public debt;
    mapping(address => uint256) public liquidatorRewards;
    uint256 public maxLiquidationBonusBps = 1000;

    function liquidate(address account, uint256 bonusBps) external {
        (, int256 price,, uint256 updatedAt,) = priceFeed.latestRoundData();
        require(block.timestamp - updatedAt <= 1 hours, "stale");
        require(collateral[account] * uint256(price) < debt[account] * 1e18, "healthy");
        require(bonusBps <= maxLiquidationBonusBps, "bonus");
        uint256 liquidationBonus = debt[account] * bonusBps / 10_000;
        liquidatorRewards[msg.sender] += liquidationBonus;
        collateral[account] = collateral[account] > uint256(price) + liquidationBonus
            ? collateral[account] - uint256(price) - liquidationBonus
            : 0;
        debt[account] = 0;
    }
}
""".strip(),
            ),
        ]

    def _reserve_fee_accounting_corpus(self) -> list[dict[str, Any]]:
        return [
            self._build_contract_case(
                case_id="protocol_fee_skim_without_reserve_sync",
                variant_group="protocol_fee_reserve_sync",
                variant_role="signal",
                validation_focus="protocol-fee and reserve-synchronization controls",
                contract_code="""
pragma solidity ^0.8.20;
contract FeeReserveSurface {
    uint256 public protocolReserves;
    function skimProtocolFee(address payable treasury, uint256 amount) external {
        (bool ok,) = treasury.call{value: amount}("");
        require(ok, "send failed");
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="protocol_fee_skim_with_reserve_sync",
                variant_group="protocol_fee_reserve_sync",
                variant_role="control",
                validation_focus="protocol-fee and reserve-synchronization controls",
                contract_code="""
pragma solidity ^0.8.20;
contract GuardedFeeReserveSurface {
    uint256 public protocolReserves;
    function skimProtocolFee(address payable treasury, uint256 amount) external {
        require(protocolReserves >= amount, "reserve");
        protocolReserves -= amount;
        (bool ok,) = treasury.call{value: amount}("");
        require(ok, "send failed");
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="debt_accrual_without_reserve_or_health_validation",
                variant_group="debt_state_controls",
                variant_role="signal",
                validation_focus="debt-state transitions and reserve-accounting assumptions",
                contract_code="""
pragma solidity ^0.8.20;
contract DebtAccountingSurface {
    mapping(address => uint256) public debt;
    uint256 public totalDebt;
    function accrueBorrowDebt(address account, uint256 amount) external {
        debt[account] += amount;
        totalDebt += amount;
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="debt_accrual_with_health_and_reserve_validation",
                variant_group="debt_state_controls",
                variant_role="control",
                validation_focus="debt-state transitions and reserve-accounting assumptions",
                contract_code="""
pragma solidity ^0.8.20;
contract GuardedDebtAccountingSurface {
    mapping(address => uint256) public debt;
    mapping(address => uint256) public collateral;
    uint256 public totalDebt;
    uint256 public reserveFactor;
    function accrueBorrowDebt(address account, uint256 amount) external {
        require(collateral[account] >= debt[account] + amount, "health factor");
        require(reserveFactor <= 1e18, "reserve factor");
        debt[account] += amount;
        totalDebt += amount;
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="bad_debt_socialization_without_buffer_checks",
                variant_group="bad_debt_socialization_controls",
                variant_role="signal",
                validation_focus="bad-debt socialization and reserve-buffer coverage",
                contract_code="""
pragma solidity ^0.8.20;
contract BadDebtSocializationSurface {
    mapping(address => uint256) public debt;
    uint256 public totalDebt;
    uint256 public reserveBuffer;
    uint256 public insuranceFund;

    function socializeBadDebt(address account, uint256 amount) external {
        debt[account] = debt[account] > amount ? debt[account] - amount : 0;
        totalDebt = totalDebt > amount ? totalDebt - amount : 0;
        reserveBuffer = reserveBuffer > amount ? reserveBuffer - amount : 0;
        insuranceFund = insuranceFund > amount ? insuranceFund - amount : 0;
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="bad_debt_socialization_with_buffer_checks",
                variant_group="bad_debt_socialization_controls",
                variant_role="control",
                validation_focus="bad-debt socialization and reserve-buffer coverage",
                contract_code="""
pragma solidity ^0.8.20;
contract GuardedBadDebtSocializationSurface {
    mapping(address => uint256) public debt;
    uint256 public totalDebt;
    uint256 public reserveBuffer;
    uint256 public insuranceFund;
    uint256 public maxWriteoff;

    function socializeBadDebt(address account, uint256 amount) external {
        require(amount <= debt[account], "bad debt");
        require(amount <= maxWriteoff, "cap");
        require(reserveBuffer + insuranceFund >= amount, "coverage");
        debt[account] -= amount;
        totalDebt -= amount;
        if (reserveBuffer >= amount) {
            reserveBuffer -= amount;
        } else {
            uint256 shortfall = amount - reserveBuffer;
            reserveBuffer = 0;
            insuranceFund -= shortfall;
        }
    }
}
""".strip(),
            ),
        ]

    def _loop_payout_corpus(self) -> list[dict[str, Any]]:
        return [
            self._build_contract_case(
                case_id="batch_payout_external_call_loop",
                contract_code="""
pragma solidity ^0.8.20;
contract BatchPayoutSurface {
    function distribute(address[] calldata recipients, uint256 amount) external {
        for (uint256 i = 0; i < recipients.length; i++) {
            (bool ok,) = recipients[i].call{value: amount}("");
            require(ok, "send failed");
        }
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="looped_state_update_without_external_call",
                contract_code="""
pragma solidity 0.8.20;
contract BatchAccountingSurface {
    mapping(address => uint256) public balances;
    function credit(address[] calldata recipients, uint256 amount) external {
        for (uint256 i = 0; i < recipients.length; i++) {
            balances[recipients[i]] += amount;
        }
    }
}
""".strip(),
            ),
            self._build_contract_case(
                case_id="batch_token_transfer_loop",
                contract_code="""
pragma solidity ^0.8.20;
interface IERC20 { function transfer(address to, uint256 amount) external returns (bool); }
contract BatchTokenSurface {
    function distribute(address token, address[] calldata recipients, uint256 amount) external {
        for (uint256 i = 0; i < recipients.length; i++) {
            IERC20(token).transfer(recipients[i], amount);
        }
    }
}
""".strip(),
            ),
        ]

    def _repo_upgrade_casebook(self) -> list[dict[str, Any]]:
        return [
            self._build_repo_case(
                case_id="proxy_delegatecall_upgrade_lane",
                variant_group="repo_proxy_upgrade_lane",
                variant_role="signal",
                validation_focus="repo-scale proxy and upgrade lanes",
                repo_files={
                    "Proxy.sol": """
pragma solidity ^0.8.20;
import "./ProxyStorage.sol";
import "./StorageSlotLib.sol";
contract Proxy is ProxyStorage {
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
                    "ProxyStorage.sol": """
pragma solidity ^0.8.20;
contract ProxyStorage {
    bytes32 internal constant _IMPLEMENTATION_SLOT = keccak256("eip1967.proxy.implementation");
}
""".strip(),
                    "StorageSlotLib.sol": """
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
                },
                expected_focus_keywords=["proxy", "delegatecall", "storage", "upgrade", "implementation"],
            ),
            self._build_repo_case(
                case_id="guarded_proxy_upgrade_lane",
                variant_group="repo_proxy_upgrade_lane",
                variant_role="control",
                validation_focus="repo-scale proxy and upgrade lanes",
                repo_files={
                    "Proxy.sol": """
pragma solidity ^0.8.20;
import "./Admin.sol";
import "./StorageSlotLib.sol";
contract Proxy is Admin {
    bytes32 internal constant _IMPLEMENTATION_SLOT = keccak256("eip1967.proxy.implementation");
    fallback() external payable {
        address impl = StorageSlotLib.getAddress(_IMPLEMENTATION_SLOT);
        (bool ok,) = impl.delegatecall(msg.data);
        require(ok, "delegate failed");
    }
    function upgradeTo(address newImplementation) external onlyOwner {
        require(newImplementation != address(0), "zero");
        require(newImplementation.code.length > 0, "no code");
        StorageSlotLib.setAddress(_IMPLEMENTATION_SLOT, newImplementation);
    }
}
""".strip(),
                    "Admin.sol": """
pragma solidity ^0.8.20;
contract Admin {
    address public owner = msg.sender;
    modifier onlyOwner() {
        require(msg.sender == owner, "owner");
        _;
    }
}
""".strip(),
                    "StorageSlotLib.sol": """
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
                },
                expected_focus_keywords=["proxy", "upgrade", "storage", "implementation"],
            ),
            self._build_repo_case(
                case_id="initializer_and_implementation_lane",
                repo_files={
                    "VaultProxy.sol": """
pragma solidity ^0.8.20;
import "./VaultStorage.sol";
contract VaultProxy is VaultStorage {
    function initialize(address newImplementation, address newOwner) external {
        implementation = newImplementation;
        owner = newOwner;
    }
    fallback() external payable {
        (bool ok,) = implementation.delegatecall(msg.data);
        require(ok, "delegate failed");
    }
}
""".strip(),
                    "VaultStorage.sol": """
pragma solidity ^0.8.20;
contract VaultStorage {
    address public implementation;
    address public owner;
}
""".strip(),
                },
                expected_focus_keywords=["proxy", "initializer", "delegatecall", "implementation"],
            ),
        ]

    def _repo_asset_flow_casebook(self) -> list[dict[str, Any]]:
        return [
            self._build_repo_case(
                case_id="vault_claim_and_rescue_lane",
                variant_group="repo_asset_flow_lane",
                variant_role="signal",
                validation_focus="repo-scale asset-flow and rescue lanes",
                repo_files={
                    "Vault.sol": """
pragma solidity ^0.8.20;
import "./AssetFlowLib.sol";
import "./SweepFacet.sol";
contract Vault {
    mapping(address => uint256) public balances;
    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }
    function claim(uint256 amount) external {
        AssetFlowLib.claim(balances, msg.sender, amount);
    }
    function rescue(address token, address to, uint256 amount) external {
        SweepFacet.sweep(token, to, amount);
    }
}
""".strip(),
                    "AssetFlowLib.sol": """
pragma solidity ^0.8.20;
library AssetFlowLib {
    function claim(mapping(address => uint256) storage balances, address account, uint256 amount) internal {
        (bool ok,) = account.call{value: amount}("");
        require(ok, "send failed");
        balances[account] -= amount;
    }
}
""".strip(),
                    "SweepFacet.sol": """
pragma solidity ^0.8.20;
interface IERC20 { function transfer(address to, uint256 amount) external returns (bool); }
library SweepFacet {
    function sweep(address token, address to, uint256 amount) internal {
        IERC20(token).transfer(to, amount);
    }
}
""".strip(),
                },
                expected_focus_keywords=["asset", "claim", "withdraw", "sweep", "rescue", "deposit"],
            ),
            self._build_repo_case(
                case_id="guarded_vault_asset_lane",
                variant_group="repo_asset_flow_lane",
                variant_role="control",
                validation_focus="repo-scale asset-flow and rescue lanes",
                repo_files={
                    "Vault.sol": """
pragma solidity ^0.8.20;
import "./Auth.sol";
import "./AssetFlowLib.sol";
contract Vault is Auth {
    mapping(address => uint256) public balances;
    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }
    function claim(uint256 amount) external {
        AssetFlowLib.claim(balances, msg.sender, amount);
    }
    function rescue(address token, address to, uint256 amount) external onlyOwner {
        AssetFlowLib.safeSweep(token, to, amount);
    }
}
""".strip(),
                    "Auth.sol": """
pragma solidity ^0.8.20;
contract Auth {
    address public owner = msg.sender;
    modifier onlyOwner() {
        require(msg.sender == owner, "owner");
        _;
    }
}
""".strip(),
                    "AssetFlowLib.sol": """
pragma solidity ^0.8.20;
interface IERC20 { function transfer(address to, uint256 amount) external returns (bool); }
library AssetFlowLib {
    function claim(mapping(address => uint256) storage balances, address account, uint256 amount) internal {
        balances[account] -= amount;
        (bool ok,) = account.call{value: amount}("");
        require(ok, "send failed");
    }
    function safeSweep(address token, address to, uint256 amount) internal {
        bool ok = IERC20(token).transfer(to, amount);
        require(ok, "transfer failed");
    }
}
""".strip(),
                },
                expected_focus_keywords=["asset", "claim", "rescue", "sweep", "withdraw"],
            ),
            self._build_repo_case(
                case_id="share_redeem_and_exit_lane",
                repo_files={
                    "Vault.sol": """
pragma solidity ^0.8.20;
import "./ShareMath.sol";
contract Vault {
    mapping(address => uint256) public shares;
    uint256 public totalAssets;
    function redeem(uint256 shareAmount) external {
        uint256 assets = ShareMath.toAssets(shareAmount);
        (bool ok,) = msg.sender.call{value: assets}("");
        require(ok, "send failed");
        shares[msg.sender] -= shareAmount;
        totalAssets -= assets;
    }
}
""".strip(),
                    "ShareMath.sol": """
pragma solidity ^0.8.20;
library ShareMath {
    function toAssets(uint256 shareAmount) internal pure returns (uint256) {
        return shareAmount;
    }
}
""".strip(),
                },
                expected_focus_keywords=["vault", "share", "redeem", "asset", "withdraw"],
            ),
        ]

    def _repo_oracle_casebook(self) -> list[dict[str, Any]]:
        return [
            self._build_repo_case(
                case_id="stale_oracle_liquidation_lane",
                variant_group="repo_oracle_lane",
                variant_role="signal",
                validation_focus="repo-scale oracle freshness and liquidation lanes",
                repo_files={
                    "LiquidationManager.sol": """
pragma solidity ^0.8.20;
import "./PriceOracleLib.sol";
contract LiquidationManager {
    function canLiquidate(address feed) external view returns (bool) {
        return PriceOracleLib.quote(feed) < 1e18;
    }
}
""".strip(),
                    "PriceOracleLib.sol": """
pragma solidity ^0.8.20;
interface AggregatorV3Interface {
    function latestRoundData() external view returns (uint80, int256, uint256, uint256, uint80);
}
library PriceOracleLib {
    function quote(address feed) internal view returns (int256) {
        (, int256 price,,,) = AggregatorV3Interface(feed).latestRoundData();
        return price;
    }
}
""".strip(),
                },
                expected_focus_keywords=["oracle", "price", "liquidation", "collateral", "stale"],
            ),
            self._build_repo_case(
                case_id="fresh_oracle_liquidation_lane",
                variant_group="repo_oracle_lane",
                variant_role="control",
                validation_focus="repo-scale oracle freshness and liquidation lanes",
                repo_files={
                    "LiquidationManager.sol": """
pragma solidity ^0.8.20;
import "./PriceOracleLib.sol";
contract LiquidationManager {
    uint256 public maxDelay = 1 hours;
    function canLiquidate(address feed) external view returns (bool) {
        return PriceOracleLib.quote(feed, maxDelay) < 1e18;
    }
}
""".strip(),
                    "PriceOracleLib.sol": """
pragma solidity ^0.8.20;
interface AggregatorV3Interface {
    function latestRoundData() external view returns (uint80, int256, uint256, uint256, uint80);
}
library PriceOracleLib {
    function quote(address feed, uint256 maxDelay) internal view returns (int256) {
        (, int256 price,, uint256 updatedAt,) = AggregatorV3Interface(feed).latestRoundData();
        require(block.timestamp - updatedAt <= maxDelay, "stale");
        return price;
    }
}
""".strip(),
                },
                expected_focus_keywords=["oracle", "price", "liquidation", "collateral"],
            ),
            self._build_repo_case(
                case_id="spot_reserve_collateral_lane",
                repo_files={
                    "CollateralManager.sol": """
pragma solidity ^0.8.20;
import "./ReserveOracleLib.sol";
contract CollateralManager {
    function collateralRatio(address pair) external view returns (uint256) {
        return ReserveOracleLib.quote(pair);
    }
}
""".strip(),
                    "ReserveOracleLib.sol": """
pragma solidity ^0.8.20;
interface IPair { function getReserves() external view returns (uint112, uint112, uint32); }
library ReserveOracleLib {
    function quote(address pair) internal view returns (uint256) {
        (uint112 reserve0, uint112 reserve1,) = IPair(pair).getReserves();
        return uint256(reserve1) * 1e18 / uint256(reserve0);
    }
}
""".strip(),
                },
                expected_focus_keywords=["oracle", "price", "collateral", "reserve"],
            ),
        ]

    def _repo_protocol_accounting_casebook(self) -> list[dict[str, Any]]:
        return [
            self._build_repo_case(
                case_id="protocol_fee_and_debt_lane",
                variant_group="repo_protocol_accounting_lane",
                variant_role="signal",
                validation_focus="repo-scale protocol-fee, reserve, and debt-accounting lanes",
                repo_files={
                    "LendingPool.sol": """
pragma solidity ^0.8.20;
import "./DebtLedger.sol";
import "./FeeController.sol";
contract LendingPool {
    DebtLedger public ledger;
    FeeController public fees;
    function borrow(uint256 amount) external {
        ledger.accrueDebt(msg.sender, amount);
    }
    function skimProtocolFees(address payable treasury, uint256 amount) external {
        fees.skimProtocolFee(treasury, amount);
    }
}
""".strip(),
                    "DebtLedger.sol": """
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
                    "FeeController.sol": """
pragma solidity ^0.8.20;
contract FeeController {
    uint256 public protocolReserves;
    function skimProtocolFee(address payable treasury, uint256 amount) external {
        (bool ok,) = treasury.call{value: amount}("");
        require(ok, "send failed");
    }
}
""".strip(),
                },
                expected_focus_keywords=["fee", "reserve", "debt", "accrual", "bad debt"],
            ),
            self._build_repo_case(
                case_id="guarded_protocol_fee_and_debt_lane",
                variant_group="repo_protocol_accounting_lane",
                variant_role="control",
                validation_focus="repo-scale protocol-fee, reserve, and debt-accounting lanes",
                repo_files={
                    "LendingPool.sol": """
pragma solidity ^0.8.20;
import "./DebtLedger.sol";
import "./FeeController.sol";
contract LendingPool {
    DebtLedger public ledger;
    FeeController public fees;
    mapping(address => uint256) public collateral;
    function borrow(uint256 amount) external {
        ledger.accrueDebt(msg.sender, amount, collateral[msg.sender]);
    }
    function skimProtocolFees(address payable treasury, uint256 amount) external {
        fees.skimProtocolFee(treasury, amount);
    }
}
""".strip(),
                    "DebtLedger.sol": """
pragma solidity ^0.8.20;
contract DebtLedger {
    mapping(address => uint256) public debt;
    uint256 public totalDebt;
    uint256 public reserveFactor = 5e17;
    function accrueDebt(address account, uint256 amount, uint256 backing) external {
        require(backing >= debt[account] + amount, "health factor");
        require(reserveFactor <= 1e18, "reserve factor");
        debt[account] += amount;
        totalDebt += amount;
    }
}
""".strip(),
                    "FeeController.sol": """
pragma solidity ^0.8.20;
contract FeeController {
    uint256 public protocolReserves;
    function skimProtocolFee(address payable treasury, uint256 amount) external {
        require(protocolReserves >= amount, "reserve");
        protocolReserves -= amount;
        (bool ok,) = treasury.call{value: amount}("");
        require(ok, "send failed");
    }
}
""".strip(),
                },
                expected_focus_keywords=["fee", "reserve", "debt", "accrual"],
            ),
            self._build_repo_case(
                case_id="bad_debt_writeoff_lane",
                repo_files={
                    "RiskEngine.sol": """
pragma solidity ^0.8.20;
import "./ReserveLedger.sol";
contract RiskEngine {
    ReserveLedger public ledger;
    function writeOffBadDebt(address account, uint256 amount) external {
        ledger.writeOffBadDebt(account, amount);
    }
}
""".strip(),
                    "ReserveLedger.sol": """
pragma solidity ^0.8.20;
contract ReserveLedger {
    mapping(address => uint256) public debt;
    uint256 public totalDebt;
    uint256 public protocolReserves;
    function writeOffBadDebt(address account, uint256 amount) external {
        debt[account] = debt[account] > amount ? debt[account] - amount : 0;
        totalDebt -= amount;
        protocolReserves = protocolReserves > amount ? protocolReserves - amount : 0;
    }
}
""".strip(),
                },
                expected_focus_keywords=["bad debt", "debt", "reserve"],
            ),
            self._build_repo_case(
                case_id="socialized_bad_debt_lane",
                variant_group="repo_bad_debt_socialization_lane",
                variant_role="signal",
                validation_focus="repo-scale reserve-buffer and bad-debt socialization lanes",
                repo_files={
                    "RiskEngine.sol": """
pragma solidity ^0.8.20;
import "./ReserveLedger.sol";
contract RiskEngine {
    ReserveLedger public ledger;
    function socializeBadDebt(address account, uint256 amount) external {
        ledger.socializeBadDebt(account, amount);
    }
}
""".strip(),
                    "ReserveLedger.sol": """
pragma solidity ^0.8.20;
contract ReserveLedger {
    mapping(address => uint256) public debt;
    uint256 public totalDebt;
    uint256 public reserveBuffer;
    uint256 public insuranceFund;
    function socializeBadDebt(address account, uint256 amount) external {
        debt[account] = debt[account] > amount ? debt[account] - amount : 0;
        totalDebt = totalDebt > amount ? totalDebt - amount : 0;
        reserveBuffer = reserveBuffer > amount ? reserveBuffer - amount : 0;
        insuranceFund = insuranceFund > amount ? insuranceFund - amount : 0;
    }
}
""".strip(),
                },
                expected_focus_keywords=["bad debt", "socialize", "reserve", "insurance", "buffer"],
            ),
            self._build_repo_case(
                case_id="guarded_socialized_bad_debt_lane",
                variant_group="repo_bad_debt_socialization_lane",
                variant_role="control",
                validation_focus="repo-scale reserve-buffer and bad-debt socialization lanes",
                repo_files={
                    "RiskEngine.sol": """
pragma solidity ^0.8.20;
import "./ReserveLedger.sol";
contract RiskEngine {
    ReserveLedger public ledger;
    function socializeBadDebt(address account, uint256 amount) external {
        ledger.socializeBadDebt(account, amount);
    }
}
""".strip(),
                    "ReserveLedger.sol": """
pragma solidity ^0.8.20;
contract ReserveLedger {
    mapping(address => uint256) public debt;
    uint256 public totalDebt;
    uint256 public reserveBuffer;
    uint256 public insuranceFund;
    uint256 public maxWriteoff;
    function socializeBadDebt(address account, uint256 amount) external {
        require(amount <= debt[account], "bad debt");
        require(amount <= maxWriteoff, "cap");
        require(reserveBuffer + insuranceFund >= amount, "coverage");
        debt[account] -= amount;
        totalDebt -= amount;
        if (reserveBuffer >= amount) {
            reserveBuffer -= amount;
        } else {
            uint256 shortfall = amount - reserveBuffer;
            reserveBuffer = 0;
            insuranceFund -= shortfall;
        }
    }
}
""".strip(),
                },
                expected_focus_keywords=["bad debt", "socialize", "reserve", "insurance", "buffer"],
            ),
        ]

    def _repo_vault_permission_casebook(self) -> list[dict[str, Any]]:
        return [
            self._build_repo_case(
                case_id="vault_permit_share_lane",
                variant_group="repo_vault_permission_lane",
                variant_role="signal",
                validation_focus="repo-scale vault, permit, and allowance lanes",
                repo_files={
                    "VaultRouter.sol": """
pragma solidity ^0.8.20;
import "./PermitModule.sol";
import "./VaultAccounting.sol";
contract VaultRouter {
    PermitModule public permits;
    VaultAccounting public vault;
    function depositWithPermit(
        address owner,
        uint256 assets,
        uint256 deadline,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) external {
        permits.usePermit(owner, address(this), assets, deadline, v, r, s);
        vault.depositFor(owner, assets);
    }
    function redeem(uint256 shares) external {
        vault.redeemTo(msg.sender, shares);
    }
}
""".strip(),
                    "PermitModule.sol": """
pragma solidity ^0.8.20;
contract PermitModule {
    function usePermit(
        address owner,
        address spender,
        uint256 value,
        uint256 deadline,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) external pure returns (address) {
        bytes32 digest = keccak256(abi.encodePacked(owner, spender, value));
        return ecrecover(digest, v, r, s);
    }
}
""".strip(),
                    "VaultAccounting.sol": """
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
                },
                expected_focus_keywords=["vault", "share", "permit", "signature", "allowance", "redeem"],
            ),
            self._build_repo_case(
                case_id="guarded_vault_permit_share_lane",
                variant_group="repo_vault_permission_lane",
                variant_role="control",
                validation_focus="repo-scale vault, permit, and allowance lanes",
                repo_files={
                    "VaultRouter.sol": """
pragma solidity ^0.8.20;
import "./PermitModule.sol";
import "./VaultAccounting.sol";
contract VaultRouter {
    PermitModule public permits;
    VaultAccounting public vault;
    function depositWithPermit(
        address owner,
        uint256 assets,
        uint256 nonce,
        uint256 deadline,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) external {
        permits.usePermit(owner, address(this), assets, nonce, deadline, v, r, s);
        vault.depositFor(owner, assets);
    }
    function redeem(uint256 shares) external {
        vault.redeemTo(msg.sender, shares);
    }
}
""".strip(),
                    "PermitModule.sol": """
pragma solidity ^0.8.20;
contract PermitModule {
    mapping(address => uint256) public nonces;
    function usePermit(
        address owner,
        address spender,
        uint256 value,
        uint256 nonce,
        uint256 deadline,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) external returns (address) {
        require(block.timestamp <= deadline, "expired");
        require(nonce == nonces[owner]++, "nonce");
        bytes32 digest = keccak256(abi.encodePacked(owner, spender, value, nonce, deadline));
        return ecrecover(digest, v, r, s);
    }
}
""".strip(),
                    "VaultAccounting.sol": """
pragma solidity ^0.8.20;
contract VaultAccounting {
    mapping(address => uint256) public shares;
    uint256 public totalAssets;
    function depositFor(address owner, uint256 assets) external {
        shares[owner] += assets;
        totalAssets += assets;
    }
    function redeemTo(address owner, uint256 shareAmount) external {
        require(shares[owner] >= shareAmount, "shares");
        shares[owner] -= shareAmount;
        totalAssets -= shareAmount;
        (bool ok,) = owner.call{value: shareAmount}("");
        require(ok, "send failed");
    }
}
""".strip(),
                },
                expected_focus_keywords=["vault", "share", "permit", "signature", "allowance", "redeem"],
            ),
            self._build_repo_case(
                case_id="allowance_router_lane",
                repo_files={
                    "Router.sol": """
pragma solidity ^0.8.20;
import "./TokenPullLib.sol";
contract Router {
    function pullAndDeposit(address token, address owner, uint256 assets) external {
        TokenPullLib.pull(token, owner, assets);
    }
}
""".strip(),
                    "TokenPullLib.sol": """
pragma solidity ^0.8.20;
interface IERC20 {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function approve(address spender, uint256 amount) external returns (bool);
}
library TokenPullLib {
    function pull(address token, address owner, uint256 assets) internal {
        IERC20(token).transferFrom(owner, address(this), assets);
        IERC20(token).approve(owner, assets);
    }
}
""".strip(),
                },
                expected_focus_keywords=["allowance", "approve", "transferfrom", "token", "vault"],
            ),
        ]

    def _repo_governance_timelock_casebook(self) -> list[dict[str, Any]]:
        return [
            self._build_repo_case(
                case_id="governance_execute_upgrade_lane",
                variant_group="repo_governance_timelock_lane",
                variant_role="signal",
                validation_focus="repo-scale governance, timelock, guardian, and upgrade execution lanes",
                repo_files={
                    "Governor.sol": """
pragma solidity ^0.8.20;
import "./Timelock.sol";
import "./ProxyAdmin.sol";
contract Governor {
    Timelock public timelock;
    ProxyAdmin public admin;
    function queueUpgrade(address implementation) external {
        timelock.queue(implementation);
    }
    function executeUpgrade(address implementation) external {
        admin.upgradeTo(implementation);
        timelock.execute(implementation);
    }
}
""".strip(),
                    "Timelock.sol": """
pragma solidity ^0.8.20;
contract Timelock {
    function queue(address implementation) external {
        implementation;
    }
    function execute(address implementation) external {
        implementation;
    }
}
""".strip(),
                    "ProxyAdmin.sol": """
pragma solidity ^0.8.20;
contract ProxyAdmin {
    address public implementation;
    function upgradeTo(address newImplementation) external {
        implementation = newImplementation;
    }
}
""".strip(),
                },
                expected_focus_keywords=[
                    "governance",
                    "timelock",
                    "upgrade",
                    "implementation",
                    "proxy",
                    "guardian",
                    "pause",
                ],
            ),
            self._build_repo_case(
                case_id="guarded_governance_execute_upgrade_lane",
                variant_group="repo_governance_timelock_lane",
                variant_role="control",
                validation_focus="repo-scale governance, timelock, guardian, and upgrade execution lanes",
                repo_files={
                    "Governor.sol": """
pragma solidity ^0.8.20;
import "./Timelock.sol";
contract Governor {
    Timelock public timelock;
    function queueUpgrade(address implementation, uint256 eta) external {
        timelock.queue(implementation, eta);
    }
}
""".strip(),
                    "Timelock.sol": """
pragma solidity ^0.8.20;
import "./ProxyAdmin.sol";
contract Timelock {
    address public governor;
    address public guardian;
    uint256 public minDelay;
    mapping(address => uint256) public queuedEta;
    ProxyAdmin public admin;
    modifier onlyGovernor() { require(msg.sender == governor, "governor"); _; }
    modifier onlyGuardian() { require(msg.sender == guardian, "guardian"); _; }
    function queue(address implementation, uint256 eta) external onlyGovernor {
        require(eta >= block.timestamp + minDelay, "delay");
        queuedEta[implementation] = eta;
    }
    function execute(address implementation) external onlyGovernor {
        require(queuedEta[implementation] != 0, "queued");
        require(block.timestamp >= queuedEta[implementation], "delay");
        admin.upgradeTo(implementation);
    }
    function pause() external onlyGuardian {}
}
""".strip(),
                    "ProxyAdmin.sol": """
pragma solidity ^0.8.20;
contract ProxyAdmin {
    address public implementation;
    address public timelock;
    modifier onlyTimelock() { require(msg.sender == timelock, "timelock"); _; }
    function upgradeTo(address newImplementation) external onlyTimelock {
        require(newImplementation != address(0), "zero");
        require(newImplementation.code.length > 0, "no code");
        implementation = newImplementation;
    }
}
""".strip(),
                },
                expected_focus_keywords=[
                    "governance",
                    "timelock",
                    "upgrade",
                    "implementation",
                    "proxy",
                    "guardian",
                    "pause",
                ],
            ),
            self._build_repo_case(
                case_id="guardian_pause_lane",
                repo_files={
                    "Guardian.sol": """
pragma solidity ^0.8.20;
import "./EmergencyBrake.sol";
contract Guardian {
    EmergencyBrake public brake;
    function pauseProtocol() external {
        brake.pause();
    }
    function unpauseProtocol() external {
        brake.unpause();
    }
}
""".strip(),
                    "EmergencyBrake.sol": """
pragma solidity ^0.8.20;
contract EmergencyBrake {
    bool public paused;
    function pause() external {
        paused = true;
    }
    function unpause() external {
        paused = false;
    }
}
""".strip(),
                },
                expected_focus_keywords=["guardian", "pause", "unpause", "governance", "timelock"],
            ),
        ]

    def _repo_rewards_distribution_casebook(self) -> list[dict[str, Any]]:
        return [
            self._build_repo_case(
                case_id="reward_index_claim_lane",
                variant_group="repo_reward_distribution_lane",
                variant_role="signal",
                validation_focus="repo-scale reward-index, emission, claim, and reserve-distribution lanes",
                repo_files={
                    "RewardsController.sol": """
pragma solidity ^0.8.20;
import "./VaultShares.sol";
contract RewardsController {
    mapping(address => uint256) public rewardDebt;
    uint256 public rewardIndex;
    uint256 public emissionRate;
    VaultShares public vault;
    function setEmissionRate(uint256 newRate) external {
        emissionRate = newRate;
    }
    function accrueReward(address account) external {
        rewardDebt[account] += vault.shares(account) * emissionRate;
        rewardIndex += emissionRate;
    }
    function claimRewards(uint256 amount) external {
        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok, "claim");
        rewardDebt[msg.sender] -= amount;
    }
}
""".strip(),
                    "VaultShares.sol": """
pragma solidity ^0.8.20;
contract VaultShares {
    mapping(address => uint256) public shares;
    function deposit(uint256 amount) external {
        shares[msg.sender] += amount;
    }
}
""".strip(),
                },
                expected_focus_keywords=["reward", "claim", "share", "emission", "reserve", "distribution", "accrual"],
            ),
            self._build_repo_case(
                case_id="guarded_reward_index_claim_lane",
                variant_group="repo_reward_distribution_lane",
                variant_role="control",
                validation_focus="repo-scale reward-index, emission, claim, and reserve-distribution lanes",
                repo_files={
                    "RewardsController.sol": """
pragma solidity ^0.8.20;
import "./VaultShares.sol";
contract RewardsController {
    mapping(address => uint256) public rewardDebt;
    uint256 public rewardIndex;
    uint256 public emissionRate;
    address public owner;
    VaultShares public vault;
    modifier onlyOwner() { require(msg.sender == owner, "owner"); _; }
    function setEmissionRate(uint256 newRate) external onlyOwner {
        emissionRate = newRate;
    }
    function accrueReward(address account) external {
        rewardDebt[account] += vault.shares(account) * emissionRate;
        rewardIndex += emissionRate;
    }
    function claimRewards(uint256 amount) external {
        require(rewardDebt[msg.sender] >= amount, "rewards");
        rewardDebt[msg.sender] -= amount;
        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok, "claim");
    }
}
""".strip(),
                    "VaultShares.sol": """
pragma solidity ^0.8.20;
contract VaultShares {
    mapping(address => uint256) public shares;
    function deposit(uint256 amount) external {
        shares[msg.sender] += amount;
    }
}
""".strip(),
                },
                expected_focus_keywords=["reward", "claim", "share", "emission", "reserve", "distribution", "accrual"],
            ),
            self._build_repo_case(
                case_id="reward_reserve_sweep_lane",
                repo_files={
                    "RewardsTreasury.sol": """
pragma solidity ^0.8.20;
contract RewardsTreasury {
    uint256 public rewardReserves;
    function sweepRewards(address payable sink, uint256 amount) external {
        (bool ok,) = sink.call{value: amount}("");
        require(ok, "send failed");
        rewardReserves -= amount;
    }
}
""".strip(),
                    "RewardsEmitter.sol": """
pragma solidity ^0.8.20;
contract RewardsEmitter {
    uint256 public emissionRate;
    function notifyRewardAmount(uint256 amount) external {
        emissionRate = amount;
    }
}
""".strip(),
                },
                expected_focus_keywords=["reward", "reserve", "distribution", "claim", "emission", "sweep"],
            ),
        ]

    def _repo_stablecoin_collateral_casebook(self) -> list[dict[str, Any]]:
        return [
            self._build_repo_case(
                case_id="stablecoin_mint_liquidation_lane",
                variant_group="repo_stablecoin_collateral_lane",
                variant_role="signal",
                validation_focus="repo-scale stablecoin mint, redemption, collateral, and liquidation lanes",
                repo_files={
                    "MintController.sol": """
pragma solidity ^0.8.20;
import "./OracleAdapter.sol";
import "./DebtBook.sol";
import "./CollateralVault.sol";
contract MintController {
    OracleAdapter public oracle;
    DebtBook public debtBook;
    CollateralVault public vault;
    function mintAgainstCollateral(uint256 amount) external {
        require(oracle.latestPrice() > 0, "price");
        debtBook.mint(msg.sender, amount);
        vault.lock(msg.sender, amount);
    }
    function liquidate(address account) external {
        debtBook.liquidate(account);
    }
}
""".strip(),
                    "OracleAdapter.sol": """
pragma solidity ^0.8.20;
contract OracleAdapter {
    uint256 public price;
    function latestPrice() external view returns (uint256) {
        return price;
    }
}
""".strip(),
                    "DebtBook.sol": """
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
                    "CollateralVault.sol": """
pragma solidity ^0.8.20;
contract CollateralVault {
    mapping(address => uint256) public collateral;
    function lock(address account, uint256 amount) external {
        collateral[account] += amount;
    }
}
""".strip(),
                },
                expected_focus_keywords=["stablecoin", "collateral", "liquidation", "oracle", "reserve", "debt", "redeem", "mint"],
            ),
            self._build_repo_case(
                case_id="guarded_stablecoin_mint_liquidation_lane",
                variant_group="repo_stablecoin_collateral_lane",
                variant_role="control",
                validation_focus="repo-scale stablecoin mint, redemption, collateral, and liquidation lanes",
                repo_files={
                    "MintController.sol": """
pragma solidity ^0.8.20;
import "./OracleAdapter.sol";
import "./DebtBook.sol";
import "./CollateralVault.sol";
contract MintController {
    OracleAdapter public oracle;
    DebtBook public debtBook;
    CollateralVault public vault;
    function mintAgainstCollateral(uint256 amount) external {
        (uint256 price, uint256 updatedAt) = oracle.latestRound();
        require(price > 0, "price");
        require(block.timestamp - updatedAt <= 1 hours, "stale");
        require(vault.collateralValue(msg.sender, price) >= amount * 2, "collateral");
        debtBook.mint(msg.sender, amount);
        vault.lock(msg.sender, amount);
    }
    function liquidate(address account) external {
        require(vault.healthFactor(account) < 1e18, "healthy");
        debtBook.liquidate(account);
    }
}
""".strip(),
                    "OracleAdapter.sol": """
pragma solidity ^0.8.20;
contract OracleAdapter {
    uint256 public price;
    uint256 public updatedAt;
    function latestRound() external view returns (uint256, uint256) {
        return (price, updatedAt);
    }
}
""".strip(),
                    "DebtBook.sol": """
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
                    "CollateralVault.sol": """
pragma solidity ^0.8.20;
contract CollateralVault {
    mapping(address => uint256) public collateral;
    function lock(address account, uint256 amount) external {
        collateral[account] += amount;
    }
    function collateralValue(address account, uint256 price) external view returns (uint256) {
        return collateral[account] * price;
    }
    function healthFactor(address account) external view returns (uint256) {
        return collateral[account] > 0 ? 5e17 : 2e18;
    }
}
""".strip(),
                },
                expected_focus_keywords=["stablecoin", "collateral", "liquidation", "oracle", "reserve", "debt", "redeem", "mint"],
            ),
            self._build_repo_case(
                case_id="stablecoin_redemption_buffer_lane",
                repo_files={
                    "Redeemer.sol": """
pragma solidity ^0.8.20;
import "./ReservePool.sol";
contract Redeemer {
    ReservePool public reservePool;
    function redeem(uint256 amount) external {
        reservePool.redeem(msg.sender, amount);
    }
}
""".strip(),
                    "ReservePool.sol": """
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
                },
                expected_focus_keywords=["stablecoin", "redeem", "reserve", "peg", "collateral", "debt"],
            ),
        ]

    def _repo_amm_liquidity_casebook(self) -> list[dict[str, Any]]:
        return [
            self._build_repo_case(
                case_id="amm_swap_fee_lane",
                variant_group="repo_amm_liquidity_lane",
                variant_role="signal",
                validation_focus="repo-scale AMM, liquidity, reserve, fee, and oracle-sync lanes",
                repo_files={
                    "Router.sol": """
pragma solidity ^0.8.20;
import "./Pool.sol";
contract Router {
    Pool public pool;
    function swapExactInput(uint256 amountIn) external {
        pool.swap(amountIn, 0);
    }
}
""".strip(),
                    "Pool.sol": """
pragma solidity ^0.8.20;
contract Pool {
    uint256 public reserve0;
    uint256 public reserve1;
    uint256 public feeGrowthGlobal;
    function swap(uint256 amountIn, uint256 minOut) external {
        uint256 amountOut = reserve0 == 0 ? amountIn : (amountIn * reserve1) / reserve0;
        require(amountOut >= minOut, "slippage");
        reserve0 += amountIn;
        (bool ok,) = msg.sender.call{value: amountOut}("");
        require(ok, "swap");
        reserve1 -= amountOut;
        feeGrowthGlobal += amountIn / 100;
    }
    function addLiquidity(uint256 amount0, uint256 amount1) external {
        reserve0 += amount0;
        reserve1 += amount1;
    }
}
""".strip(),
                    "OracleSync.sol": """
pragma solidity ^0.8.20;
contract OracleSync {
    uint256 public price;
    uint256 public updatedAt;
    function sync(uint256 newPrice) external {
        price = newPrice;
        updatedAt = block.timestamp;
    }
}
""".strip(),
                },
                expected_focus_keywords=["amm", "liquidity", "swap", "reserve", "fee", "oracle", "twap", "router"],
            ),
            self._build_repo_case(
                case_id="guarded_amm_swap_fee_lane",
                variant_group="repo_amm_liquidity_lane",
                variant_role="control",
                validation_focus="repo-scale AMM, liquidity, reserve, fee, and oracle-sync lanes",
                repo_files={
                    "Router.sol": """
pragma solidity ^0.8.20;
import "./Pool.sol";
contract Router {
    Pool public pool;
    function swapExactInput(uint256 amountIn, uint256 minOut) external {
        pool.swap(amountIn, minOut);
    }
}
""".strip(),
                    "Pool.sol": """
pragma solidity ^0.8.20;
import "./OracleSync.sol";
contract Pool {
    uint256 public reserve0;
    uint256 public reserve1;
    uint256 public feeGrowthGlobal;
    OracleSync public oracle;
    function swap(uint256 amountIn, uint256 minOut) external {
        (uint256 spot, uint256 updatedAt) = oracle.latest();
        require(spot > 0, "oracle");
        require(block.timestamp - updatedAt <= 10 minutes, "stale");
        uint256 amountOut = reserve0 == 0 ? amountIn : (amountIn * reserve1) / reserve0;
        require(amountOut >= minOut, "slippage");
        reserve0 += amountIn;
        reserve1 -= amountOut;
        feeGrowthGlobal += amountIn / 100;
        (bool ok,) = msg.sender.call{value: amountOut}("");
        require(ok, "swap");
    }
    function addLiquidity(uint256 amount0, uint256 amount1) external {
        reserve0 += amount0;
        reserve1 += amount1;
    }
}
""".strip(),
                    "OracleSync.sol": """
pragma solidity ^0.8.20;
contract OracleSync {
    uint256 public price;
    uint256 public updatedAt;
    function latest() external view returns (uint256, uint256) {
        return (price, updatedAt);
    }
}
""".strip(),
                },
                expected_focus_keywords=["amm", "liquidity", "swap", "reserve", "fee", "oracle", "twap", "router"],
            ),
            self._build_repo_case(
                case_id="lp_burn_reserve_lane",
                repo_files={
                    "LiquidityPool.sol": """
pragma solidity ^0.8.20;
contract LiquidityPool {
    uint256 public reserve0;
    uint256 public reserve1;
    mapping(address => uint256) public lpBalance;
    function mint(uint256 amount0, uint256 amount1) external {
        reserve0 += amount0;
        reserve1 += amount1;
        lpBalance[msg.sender] += amount0 + amount1;
    }
    function burn(uint256 shares) external {
        (bool ok,) = msg.sender.call{value: shares}("");
        require(ok, "burn");
        lpBalance[msg.sender] -= shares;
        reserve0 -= shares / 2;
        reserve1 -= shares / 2;
    }
}
""".strip(),
                },
                expected_focus_keywords=["amm", "liquidity", "lp", "burn", "reserve", "fee", "swap"],
            ),
        ]

    def _repo_bridge_custody_casebook(self) -> list[dict[str, Any]]:
        return [
            self._build_repo_case(
                case_id="bridge_finalize_message_lane",
                variant_group="repo_bridge_custody_lane",
                variant_role="signal",
                validation_focus="repo-scale bridge, custody, message-validation, and replay-protection lanes",
                repo_files={
                    "BridgePortal.sol": """
pragma solidity ^0.8.20;
import "./MessageVerifier.sol";
import "./CustodyVault.sol";
contract BridgePortal {
    MessageVerifier public verifier;
    CustodyVault public custody;
    mapping(bytes32 => bool) public finalized;
    function finalizeWithdrawal(bytes32 messageId, address payable recipient, uint256 amount) external {
        require(verifier.validate(messageId), "proof");
        custody.release(recipient, amount);
        finalized[messageId] = true;
    }
}
""".strip(),
                    "MessageVerifier.sol": """
pragma solidity ^0.8.20;
contract MessageVerifier {
    function validate(bytes32 messageId) external pure returns (bool) {
        return messageId != bytes32(0);
    }
}
""".strip(),
                    "CustodyVault.sol": """
pragma solidity ^0.8.20;
contract CustodyVault {
    uint256 public lockedAssets;
    function release(address payable recipient, uint256 amount) external {
        (bool ok,) = recipient.call{value: amount}("");
        require(ok, "release");
        lockedAssets -= amount;
    }
}
""".strip(),
                },
                expected_focus_keywords=["bridge", "custody", "message", "proof", "validator", "relay", "nonce", "replay", "withdraw", "finalize"],
            ),
            self._build_repo_case(
                case_id="guarded_bridge_finalize_message_lane",
                variant_group="repo_bridge_custody_lane",
                variant_role="control",
                validation_focus="repo-scale bridge, custody, message-validation, and replay-protection lanes",
                repo_files={
                    "BridgePortal.sol": """
pragma solidity ^0.8.20;
import "./MessageVerifier.sol";
import "./CustodyVault.sol";
contract BridgePortal {
    MessageVerifier public verifier;
    CustodyVault public custody;
    mapping(bytes32 => bool) public finalized;
    address public relayer;
    modifier onlyRelayer() { require(msg.sender == relayer, "relayer"); _; }
    function finalizeWithdrawal(bytes32 messageId, address payable recipient, uint256 amount, bytes32 root) external onlyRelayer {
        require(!finalized[messageId], "done");
        require(verifier.verifyProof(messageId, root), "proof");
        finalized[messageId] = true;
        custody.release(recipient, amount);
    }
}
""".strip(),
                    "MessageVerifier.sol": """
pragma solidity ^0.8.20;
contract MessageVerifier {
    mapping(bytes32 => bool) public acceptedRoot;
    function verifyProof(bytes32 messageId, bytes32 root) external view returns (bool) {
        return messageId != bytes32(0) && acceptedRoot[root];
    }
}
""".strip(),
                    "CustodyVault.sol": """
pragma solidity ^0.8.20;
contract CustodyVault {
    uint256 public lockedAssets;
    address public portal;
    modifier onlyPortal() { require(msg.sender == portal, "portal"); _; }
    function release(address payable recipient, uint256 amount) external onlyPortal {
        lockedAssets -= amount;
        (bool ok,) = recipient.call{value: amount}("");
        require(ok, "release");
    }
}
""".strip(),
                },
                expected_focus_keywords=["bridge", "custody", "message", "proof", "validator", "relay", "nonce", "replay", "withdraw", "finalize"],
            ),
            self._build_repo_case(
                case_id="bridge_custody_rescue_lane",
                repo_files={
                    "CustodyAdmin.sol": """
pragma solidity ^0.8.20;
contract CustodyAdmin {
    function rescue(address token, address to, uint256 amount) external {
        token; to; amount;
    }
}
""".strip(),
                    "BridgeEscrow.sol": """
pragma solidity ^0.8.20;
contract BridgeEscrow {
    uint256 public lockedAssets;
    function deposit() external payable {
        lockedAssets += msg.value;
    }
}
""".strip(),
                },
                expected_focus_keywords=["bridge", "custody", "rescue", "sweep", "guardian", "validator", "relay"],
            ),
        ]

    def _repo_staking_rebase_casebook(self) -> list[dict[str, Any]]:
        return [
            self._build_repo_case(
                case_id="staking_rebase_claim_lane",
                variant_group="repo_staking_rebase_lane",
                variant_role="signal",
                validation_focus="repo-scale staking, rebase, reward-index, slash, and unstake-queue lanes",
                repo_files={
                    "StakingPool.sol": """
pragma solidity ^0.8.20;
import "./ValidatorRewards.sol";
contract StakingPool {
    mapping(address => uint256) public shares;
    mapping(address => uint256) public rewardDebt;
    uint256 public rebaseIndex;
    ValidatorRewards public rewards;
    function stake(uint256 amount) external {
        shares[msg.sender] += amount;
    }
    function rebase(uint256 delta) external {
        rebaseIndex += delta;
    }
    function claim(uint256 amount) external {
        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok, "claim");
        rewardDebt[msg.sender] += amount;
    }
}
""".strip(),
                    "ValidatorRewards.sol": """
pragma solidity ^0.8.20;
contract ValidatorRewards {
    uint256 public totalRewards;
    function notifyReward(uint256 amount) external {
        totalRewards += amount;
    }
}
""".strip(),
                },
                expected_focus_keywords=["staking", "rebase", "stake", "unstake", "reward", "share", "epoch", "slash", "queue", "validator"],
            ),
            self._build_repo_case(
                case_id="guarded_staking_rebase_claim_lane",
                variant_group="repo_staking_rebase_lane",
                variant_role="control",
                validation_focus="repo-scale staking, rebase, reward-index, slash, and unstake-queue lanes",
                repo_files={
                    "StakingPool.sol": """
pragma solidity ^0.8.20;
import "./ValidatorRewards.sol";
contract StakingPool {
    mapping(address => uint256) public shares;
    mapping(address => uint256) public rewardDebt;
    uint256 public rebaseIndex;
    address public keeper;
    ValidatorRewards public rewards;
    modifier onlyKeeper() { require(msg.sender == keeper, "keeper"); _; }
    function stake(uint256 amount) external {
        shares[msg.sender] += amount;
    }
    function rebase(uint256 delta) external onlyKeeper {
        rebaseIndex += delta;
    }
    function claim(uint256 amount) external {
        require(rewardDebt[msg.sender] >= amount, "rewards");
        rewardDebt[msg.sender] -= amount;
        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok, "claim");
    }
}
""".strip(),
                    "ValidatorRewards.sol": """
pragma solidity ^0.8.20;
contract ValidatorRewards {
    address public keeper;
    uint256 public totalRewards;
    modifier onlyKeeper() { require(msg.sender == keeper, "keeper"); _; }
    function notifyReward(uint256 amount) external onlyKeeper {
        totalRewards += amount;
    }
}
""".strip(),
                },
                expected_focus_keywords=["staking", "rebase", "stake", "unstake", "reward", "share", "epoch", "slash", "queue", "validator"],
            ),
            self._build_repo_case(
                case_id="unstake_queue_slash_lane",
                repo_files={
                    "WithdrawalQueue.sol": """
pragma solidity ^0.8.20;
contract WithdrawalQueue {
    mapping(address => uint256) public queuedShares;
    function queueWithdraw(uint256 shares) external {
        queuedShares[msg.sender] += shares;
    }
    function processSlash(address account, uint256 amount) external {
        queuedShares[account] -= amount;
    }
}
""".strip(),
                    "SlashManager.sol": """
pragma solidity ^0.8.20;
contract SlashManager {
    function slash(address validator, uint256 amount) external {
        validator; amount;
    }
}
""".strip(),
                },
                expected_focus_keywords=["staking", "unstake", "queue", "slash", "validator", "rebase", "share"],
            ),
        ]

    def _repo_keeper_auction_casebook(self) -> list[dict[str, Any]]:
        return [
            self._build_repo_case(
                case_id="keeper_liquidation_auction_lane",
                variant_group="repo_keeper_auction_lane",
                variant_role="signal",
                validation_focus="repo-scale keeper, auction, liquidation, oracle, and settlement lanes",
                repo_files={
                    "LiquidationManager.sol": """
pragma solidity ^0.8.20;
import "./AuctionHouse.sol";
import "./PriceOracle.sol";
contract LiquidationManager {
    AuctionHouse public auctionHouse;
    PriceOracle public oracle;
    function startAuction(address account, uint256 debt) external {
        require(oracle.latestPrice() > 0, "price");
        auctionHouse.start(account, debt);
    }
}
""".strip(),
                    "AuctionHouse.sol": """
pragma solidity ^0.8.20;
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
                    "PriceOracle.sol": """
pragma solidity ^0.8.20;
contract PriceOracle {
    uint256 public price;
    function latestPrice() external view returns (uint256) {
        return price;
    }
}
""".strip(),
                },
                expected_focus_keywords=["keeper", "auction", "liquidation", "settle", "bid", "oracle", "reward", "close factor"],
            ),
            self._build_repo_case(
                case_id="guarded_keeper_liquidation_auction_lane",
                variant_group="repo_keeper_auction_lane",
                variant_role="control",
                validation_focus="repo-scale keeper, auction, liquidation, oracle, and settlement lanes",
                repo_files={
                    "LiquidationManager.sol": """
pragma solidity ^0.8.20;
import "./AuctionHouse.sol";
import "./PriceOracle.sol";
contract LiquidationManager {
    AuctionHouse public auctionHouse;
    PriceOracle public oracle;
    function startAuction(address account, uint256 debt) external {
        (uint256 price, uint256 updatedAt) = oracle.latestRound();
        require(price > 0, "price");
        require(block.timestamp - updatedAt <= 10 minutes, "stale");
        auctionHouse.start(account, debt);
    }
}
""".strip(),
                    "AuctionHouse.sol": """
pragma solidity ^0.8.20;
contract AuctionHouse {
    mapping(address => uint256) public activeDebt;
    function start(address account, uint256 debt) external {
        activeDebt[account] = debt;
    }
    function settle(address payable keeper, address account, uint256 reward) external {
        activeDebt[account] = 0;
        (bool ok,) = keeper.call{value: reward}("");
        require(ok, "settle");
    }
}
""".strip(),
                    "PriceOracle.sol": """
pragma solidity ^0.8.20;
contract PriceOracle {
    uint256 public price;
    uint256 public updatedAt;
    function latestRound() external view returns (uint256, uint256) {
        return (price, updatedAt);
    }
}
""".strip(),
                },
                expected_focus_keywords=["keeper", "auction", "liquidation", "settle", "bid", "oracle", "reward", "close factor"],
            ),
            self._build_repo_case(
                case_id="keeper_incentive_buffer_lane",
                repo_files={
                    "KeeperRewards.sol": """
pragma solidity ^0.8.20;
contract KeeperRewards {
    uint256 public reserveBuffer;
    function payKeeper(address payable keeper, uint256 reward) external {
        (bool ok,) = keeper.call{value: reward}("");
        require(ok, "reward");
        reserveBuffer -= reward;
    }
}
""".strip(),
                    "AuctionParameters.sol": """
pragma solidity ^0.8.20;
contract AuctionParameters {
    uint256 public keeperRewardBps;
    function setKeeperRewardBps(uint256 nextBps) external {
        keeperRewardBps = nextBps;
    }
}
""".strip(),
                },
                expected_focus_keywords=["keeper", "auction", "reward", "reserve", "buffer", "liquidation"],
            ),
        ]

    def _repo_treasury_vesting_casebook(self) -> list[dict[str, Any]]:
        return [
            self._build_repo_case(
                case_id="treasury_release_and_sweep_lane",
                variant_group="repo_treasury_vesting_lane",
                variant_role="signal",
                validation_focus="repo-scale treasury, vesting, release, sweep, and timelock authority lanes",
                repo_files={
                    "Treasury.sol": """
pragma solidity ^0.8.20;
import "./VestingVault.sol";
contract Treasury {
    VestingVault public vesting;
    function sweep(address payable sink, uint256 amount) external {
        (bool ok,) = sink.call{value: amount}("");
        require(ok, "sweep");
    }
    function releaseVested(address beneficiary) external {
        vesting.release(beneficiary);
    }
}
""".strip(),
                    "VestingVault.sol": """
pragma solidity ^0.8.20;
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
                },
                expected_focus_keywords=["treasury", "vesting", "release", "sweep", "timelock", "beneficiary", "cliff", "schedule"],
            ),
            self._build_repo_case(
                case_id="guarded_treasury_release_and_sweep_lane",
                variant_group="repo_treasury_vesting_lane",
                variant_role="control",
                validation_focus="repo-scale treasury, vesting, release, sweep, and timelock authority lanes",
                repo_files={
                    "Treasury.sol": """
pragma solidity ^0.8.20;
import "./VestingVault.sol";
contract Treasury {
    VestingVault public vesting;
    address public timelock;
    modifier onlyTimelock() { require(msg.sender == timelock, "timelock"); _; }
    function sweep(address payable sink, uint256 amount) external onlyTimelock {
        (bool ok,) = sink.call{value: amount}("");
        require(ok, "sweep");
    }
    function releaseVested(address beneficiary) external onlyTimelock {
        vesting.release(beneficiary);
    }
}
""".strip(),
                    "VestingVault.sol": """
pragma solidity ^0.8.20;
contract VestingVault {
    mapping(address => uint256) public releasable;
    function release(address beneficiary) external {
        uint256 amount = releasable[beneficiary];
        releasable[beneficiary] = 0;
        (bool ok,) = payable(beneficiary).call{value: amount}("");
        require(ok, "release");
    }
}
""".strip(),
                },
                expected_focus_keywords=["treasury", "vesting", "release", "sweep", "timelock", "beneficiary", "cliff", "schedule"],
            ),
            self._build_repo_case(
                case_id="vesting_schedule_adjust_lane",
                repo_files={
                    "VestingScheduler.sol": """
pragma solidity ^0.8.20;
contract VestingScheduler {
    mapping(address => uint256) public vestingEnd;
    function setSchedule(address beneficiary, uint256 endAt) external {
        vestingEnd[beneficiary] = endAt;
    }
}
""".strip(),
                    "TreasuryGovernance.sol": """
pragma solidity ^0.8.20;
contract TreasuryGovernance {
    function queueScheduleUpdate(address scheduler, address beneficiary, uint256 endAt) external {
        scheduler; beneficiary; endAt;
    }
}
""".strip(),
                },
                expected_focus_keywords=["treasury", "vesting", "schedule", "beneficiary", "timelock", "governance"],
            ),
        ]

    def _repo_insurance_recovery_casebook(self) -> list[dict[str, Any]]:
        return [
            self._build_repo_case(
                case_id="insurance_absorb_deficit_lane",
                variant_group="repo_insurance_recovery_lane",
                variant_role="signal",
                validation_focus="repo-scale insurance, deficit, recovery, reserve-buffer, and settlement lanes",
                repo_files={
                    "InsuranceFund.sol": """
pragma solidity ^0.8.20;
contract InsuranceFund {
    uint256 public reserves;
    function absorbDeficit(uint256 amount) external {
        reserves -= amount;
    }
    function recover(address payable sink, uint256 amount) external {
        (bool ok,) = sink.call{value: amount}("");
        require(ok, "recover");
        reserves -= amount;
    }
}
""".strip(),
                    "DeficitManager.sol": """
pragma solidity ^0.8.20;
contract DeficitManager {
    uint256 public badDebt;
    function socializeLoss(uint256 amount) external {
        badDebt += amount;
    }
}
""".strip(),
                },
                expected_focus_keywords=["insurance", "recovery", "deficit", "bad debt", "reserve", "buffer", "settlement", "socialize"],
            ),
            self._build_repo_case(
                case_id="guarded_insurance_absorb_deficit_lane",
                variant_group="repo_insurance_recovery_lane",
                variant_role="control",
                validation_focus="repo-scale insurance, deficit, recovery, reserve-buffer, and settlement lanes",
                repo_files={
                    "InsuranceFund.sol": """
pragma solidity ^0.8.20;
contract InsuranceFund {
    uint256 public reserves;
    address public guardian;
    modifier onlyGuardian() { require(msg.sender == guardian, "guardian"); _; }
    function absorbDeficit(uint256 amount) external onlyGuardian {
        reserves -= amount;
    }
    function recover(address payable sink, uint256 amount) external onlyGuardian {
        reserves -= amount;
        (bool ok,) = sink.call{value: amount}("");
        require(ok, "recover");
    }
}
""".strip(),
                    "DeficitManager.sol": """
pragma solidity ^0.8.20;
contract DeficitManager {
    uint256 public badDebt;
    function socializeLoss(uint256 amount) external {
        badDebt += amount;
    }
}
""".strip(),
                },
                expected_focus_keywords=["insurance", "recovery", "deficit", "bad debt", "reserve", "buffer", "settlement", "socialize"],
            ),
            self._build_repo_case(
                case_id="emergency_settlement_lane",
                repo_files={
                    "EmergencySettlement.sol": """
pragma solidity ^0.8.20;
contract EmergencySettlement {
    bool public settled;
    function settleSystem() external {
        settled = true;
    }
}
""".strip(),
                    "RecoveryManager.sol": """
pragma solidity ^0.8.20;
contract RecoveryManager {
    uint256 public reserveBuffer;
    function refillBuffer(uint256 amount) external {
        reserveBuffer += amount;
    }
}
""".strip(),
                },
                expected_focus_keywords=["insurance", "recovery", "settlement", "reserve", "buffer", "guardian", "deficit"],
            ),
        ]

    def _build_repo_case(
        self,
        *,
        case_id: str,
        repo_files: dict[str, str],
        expected_focus_keywords: list[str],
        variant_group: str | None = None,
        variant_role: str | None = None,
        validation_focus: str | None = None,
    ) -> dict[str, Any]:
        from app.tools.builtin.contract_inventory_tool import ContractInventoryTool

        inventory_tool = ContractInventoryTool()
        file_issues: dict[str, list[str]] = {}
        contract_units: list[str] = []
        matched_review_lanes: list[str] = []
        matched_risk_family_lanes: list[str] = []
        matched_function_family_priorities: list[str] = []

        with tempfile.TemporaryDirectory(prefix="ez_casebook_") as temp_dir:
            root_path = Path(temp_dir)
            for relative_path, contract_code in repo_files.items():
                destination = root_path / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(contract_code.strip(), encoding="utf-8")

            inventory_result = inventory_tool.run({"root_path": str(root_path), "max_files": 64})
            inventory_data = inventory_result["result_data"]

        for relative_path, contract_code in repo_files.items():
            outline = build_contract_outline(contract_code=contract_code.strip(), language="solidity")
            issues, _ = detect_contract_patterns(outline)
            if issues:
                file_issues[relative_path] = issues
            contract_units.extend(outline.contract_names)

        prioritized_issues = prioritize_contract_issues(
            [issue for issues in file_issues.values() for issue in issues]
        )
        issue_strings = [str(item.get("issue", "")).strip() for item in prioritized_issues if isinstance(item, dict)]
        normalized_keywords = [keyword.strip().lower() for keyword in expected_focus_keywords if keyword.strip()]

        matched_review_lanes = self._match_repo_case_lines(
            inventory_data.get("entrypoint_review_lanes"),
            normalized_keywords,
        )
        matched_risk_family_lanes = self._match_repo_case_lines(
            inventory_data.get("risk_family_lane_summaries"),
            normalized_keywords,
        )
        matched_function_family_priorities = self._match_repo_case_lines(
            inventory_data.get("entrypoint_function_family_priorities"),
            normalized_keywords,
        )

        return {
            "case_id": case_id,
            "repo_case": True,
            "variant_group": variant_group,
            "variant_role": variant_role,
            "validation_focus": validation_focus,
            "repo_file_count": len(repo_files),
            "contract_names": _ordered_unique(contract_units),
            "candidate_files": _ordered_unique(list(inventory_data.get("candidate_files", []))),
            "entrypoint_candidates": _ordered_unique(list(inventory_data.get("entrypoint_candidates", []))),
            "matched_review_lanes": matched_review_lanes,
            "matched_risk_family_lanes": matched_risk_family_lanes,
            "matched_function_family_priorities": matched_function_family_priorities,
            "issues": _ordered_unique(issue_strings),
            "notes": [
                f"repo files={len(repo_files)}",
                "This built-in casebook models bounded repo-scale review rather than a single-file sweep.",
            ],
            "anomaly_detected": bool(issue_strings),
        }

    def _build_contract_case(
        self,
        *,
        case_id: str,
        contract_code: str,
        variant_group: str | None = None,
        variant_role: str | None = None,
        validation_focus: str | None = None,
    ) -> dict[str, Any]:
        outline = build_contract_outline(contract_code=contract_code, language="solidity")
        summary = summarize_contract_surface(outline)
        issues, notes = detect_contract_patterns(outline)
        return {
            "case_id": case_id,
            "variant_group": variant_group,
            "variant_role": variant_role,
            "validation_focus": validation_focus,
            "contract_names": outline.contract_names,
            "function_count": summary["function_count"],
            "public_functions": summary["public_functions"],
            "external_functions": summary["external_functions"],
            "payable_functions": summary["payable_functions"],
            "privileged_functions": summary["privileged_functions"],
            "initializer_functions": summary["initializer_functions"],
            "state_changing_functions": summary["state_changing_functions"],
            "unguarded_state_changing_functions": summary["unguarded_state_changing_functions"],
            "low_level_call_functions": summary["low_level_call_functions"],
            "constructor_present": summary["constructor_present"],
            "fallback_present": summary["fallback_present"],
            "receive_present": summary["receive_present"],
            "risk_flags": summary["risk_flags"],
            "issues": issues,
            "notes": notes,
            "anomaly_detected": bool(issues),
        }

    def _build_remediation_validation(self, cases: list[dict[str, Any]]) -> list[str]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for case in cases:
            group = str(case.get("variant_group") or "").strip()
            if not group:
                continue
            grouped.setdefault(group, []).append(case)

        items: list[str] = []
        for group_name, grouped_cases in grouped.items():
            signal_cases = [case for case in grouped_cases if str(case.get("variant_role") or "").strip() == "signal"]
            control_cases = [case for case in grouped_cases if str(case.get("variant_role") or "").strip() == "control"]
            if not signal_cases or not control_cases:
                continue

            signal_case = max(signal_cases, key=self._validation_case_score)
            control_case = min(control_cases, key=self._validation_case_score)
            signal_score = self._validation_case_score(signal_case)
            control_score = self._validation_case_score(control_case)
            if control_score >= signal_score:
                continue

            focus = str(control_case.get("validation_focus") or signal_case.get("validation_focus") or group_name).strip()
            signal_name = str(signal_case.get("case_id") or "signal_case").strip()
            control_name = str(control_case.get("case_id") or "control_case").strip()
            if control_score <= 0:
                items.append(
                    f"Bounded remediation validation for {focus}: {control_name} clears the strongest local signal relative to {signal_name} ({signal_score} -> {control_score})."
                )
            else:
                items.append(
                    f"Bounded remediation validation for {focus}: {control_name} weakens the strongest local signal relative to {signal_name} ({signal_score} -> {control_score})."
                )
        return _ordered_unique(items)[:6]

    def _build_repo_casebook_coverage(
        self,
        *,
        testbed_name: str,
        repo_case_count: int,
        matched_case_ids: list[str],
        matched_review_lane_count: int,
        matched_risk_family_lane_count: int,
        matched_function_priority_count: int,
    ) -> list[str]:
        if repo_case_count <= 0:
            return []

        matched_case_count = len(matched_case_ids)
        if matched_case_count >= repo_case_count:
            coverage_label = "full"
        elif matched_case_count >= max(1, repo_case_count // 2 + (repo_case_count % 2)):
            coverage_label = "partial"
        elif matched_case_count > 0:
            coverage_label = "minimal"
        else:
            coverage_label = "none"

        line = (
            f"Repo casebook coverage for {testbed_name}: matched cases={matched_case_count}/{repo_case_count}; "
            f"review lanes={matched_review_lane_count}; risk-family lanes={matched_risk_family_lane_count}; "
            f"function-family priorities={matched_function_priority_count}; coverage={coverage_label}."
        )
        if matched_case_ids:
            line += f" Matched cases: {', '.join(matched_case_ids[:4])}."
        return [line]

    @staticmethod
    def _validation_case_score(case: dict[str, Any]) -> int:
        issue_count = len([issue for issue in case.get("issues", []) if str(issue).strip()])
        lane_count = len(case.get("matched_review_lanes", [])) if isinstance(case.get("matched_review_lanes"), list) else 0
        function_priority_count = (
            len(case.get("matched_function_family_priorities", []))
            if isinstance(case.get("matched_function_family_priorities"), list)
            else 0
        )
        anomaly_bonus = 1 if case.get("anomaly_detected") else 0
        return issue_count * 10 + lane_count * 3 + function_priority_count + anomaly_bonus

    @staticmethod
    def _match_repo_case_lines(lines: Any, expected_keywords: list[str]) -> list[str]:
        if not isinstance(lines, list) or not expected_keywords:
            return []
        matched: list[str] = []
        for line in lines:
            text = str(line).strip()
            lowered = text.lower()
            if any(keyword in lowered for keyword in expected_keywords):
                matched.append(text)
        return _ordered_unique(matched)[:4]

    def _issue_type_counts(self, cases: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for case in cases:
            for issue in case.get("issues", []):
                counts[str(issue)] = counts.get(str(issue), 0) + 1
        return counts

    def _result(
        self,
        *,
        status: str,
        conclusion: str,
        notes: list[str],
        result_data: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "status": status,
            "conclusion": conclusion,
            "notes": notes,
            "deterministic": True,
            "result_data": result_data,
        }
