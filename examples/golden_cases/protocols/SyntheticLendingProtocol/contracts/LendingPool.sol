// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.24;

import "./OracleAdapter.sol";
import "./ReserveVault.sol";

/// @notice Synthetic lending protocol fixture for repo-scale golden-case inventory.
/// @dev Not production code and not an exploitable target.
contract LendingPool {
    address public admin;
    OracleAdapter public oracle;
    ReserveVault public reserveVault;

    uint256 public totalDebt;
    uint256 public totalReserves;
    uint256 public badDebt;
    uint256 public reserveFactor;
    uint256 public protocolFeeBps;
    uint256 public liquidationBonusBps;
    uint256 public closeFactorBps;

    mapping(address => uint256) public collateral;
    mapping(address => uint256) public debt;

    event CollateralDeposited(address indexed account, uint256 amount);
    event Borrowed(address indexed account, uint256 amount);
    event Repaid(address indexed account, uint256 amount);
    event Liquidated(address indexed liquidator, address indexed borrower, uint256 repaidAmount);

    modifier onlyAdmin() {
        require(msg.sender == admin, "only admin");
        _;
    }

    constructor(OracleAdapter initialOracle, ReserveVault initialReserveVault) {
        admin = msg.sender;
        oracle = initialOracle;
        reserveVault = initialReserveVault;
        reserveFactor = 1_000;
        protocolFeeBps = 50;
        liquidationBonusBps = 500;
        closeFactorBps = 5_000;
    }

    function depositCollateral() external payable {
        require(msg.value > 0, "zero collateral");
        collateral[msg.sender] += msg.value;
        totalReserves += msg.value;
        emit CollateralDeposited(msg.sender, msg.value);
    }

    function borrow(uint256 amount) external {
        require(amount > 0, "zero borrow");
        require(_healthFactorAfterBorrow(msg.sender, amount) >= 1e18, "health factor");

        debt[msg.sender] += amount;
        totalDebt += amount;
        totalReserves -= amount;

        (bool ok,) = payable(msg.sender).call{value: amount}("");
        require(ok, "borrow transfer failed");
        emit Borrowed(msg.sender, amount);
    }

    function repay() external payable {
        require(msg.value > 0, "zero repay");
        uint256 repayAmount = msg.value > debt[msg.sender] ? debt[msg.sender] : msg.value;
        uint256 protocolFee = (repayAmount * protocolFeeBps) / 10_000;

        debt[msg.sender] -= repayAmount;
        totalDebt -= repayAmount;
        totalReserves += repayAmount - protocolFee;
        reserveVault.collectProtocolFee(protocolFee);
        emit Repaid(msg.sender, repayAmount);
    }

    function liquidate(address borrower) external payable {
        require(msg.value > 0, "zero liquidation");
        require(_healthFactor(borrower) < 1e18, "healthy borrower");

        uint256 maxClose = (debt[borrower] * closeFactorBps) / 10_000;
        uint256 repayAmount = msg.value > maxClose ? maxClose : msg.value;
        uint256 bonus = (repayAmount * liquidationBonusBps) / 10_000;
        uint256 collateralOut = repayAmount + bonus;

        debt[borrower] -= repayAmount;
        totalDebt -= repayAmount;
        collateral[borrower] -= collateralOut;
        totalReserves += repayAmount;

        reserveVault.releaseCollateral(payable(msg.sender), collateralOut);
        emit Liquidated(msg.sender, borrower, repayAmount);
    }

    function accrueProtocolFee(uint256 amount) external onlyAdmin {
        reserveVault.collectProtocolFee(amount);
    }

    function absorbBadDebt(address borrower, uint256 amount) external onlyAdmin {
        require(amount <= debt[borrower], "debt exceeded");
        debt[borrower] -= amount;
        totalDebt -= amount;
        badDebt += amount;
        reserveVault.absorbBadDebt(amount);
    }

    function setOracle(OracleAdapter nextOracle) external onlyAdmin {
        require(address(nextOracle) != address(0), "bad oracle");
        oracle = nextOracle;
    }

    function getReserves() external view returns (uint256) {
        return totalReserves;
    }

    function _healthFactorAfterBorrow(address account, uint256 amount) internal view returns (uint256) {
        uint256 nextDebt = debt[account] + amount;
        if (nextDebt == 0) {
            return type(uint256).max;
        }
        return (collateral[account] * uint256(_latestPrice())) / nextDebt;
    }

    function _healthFactor(address account) internal view returns (uint256) {
        if (debt[account] == 0) {
            return type(uint256).max;
        }
        return (collateral[account] * uint256(_latestPrice())) / debt[account];
    }

    function _latestPrice() internal view returns (int256) {
        (, int256 answer,, uint256 updatedAt,) = oracle.latestRoundData();
        require(answer > 0, "bad oracle price");
        require(block.timestamp <= updatedAt + 1 hours, "stale oracle");
        return answer;
    }
}
