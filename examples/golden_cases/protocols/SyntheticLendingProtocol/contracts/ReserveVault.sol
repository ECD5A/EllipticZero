// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.24;

/// @notice Synthetic reserve fixture for repo-scale golden-case inventory.
/// @dev Not production code and not an exploitable target.
contract ReserveVault {
    address public admin;
    address public lendingPool;
    uint256 public totalReserves;
    uint256 public accruedFee;
    uint256 public reserveBuffer;

    modifier onlyAdmin() {
        require(msg.sender == admin, "only admin");
        _;
    }

    modifier onlyLendingPool() {
        require(msg.sender == lendingPool, "only pool");
        _;
    }

    constructor(uint256 initialReserveBuffer) payable {
        admin = msg.sender;
        reserveBuffer = initialReserveBuffer;
        totalReserves = msg.value;
    }

    function setLendingPool(address nextPool) external onlyAdmin {
        require(nextPool != address(0), "bad pool");
        lendingPool = nextPool;
    }

    function depositReserve() external payable onlyAdmin {
        totalReserves += msg.value;
    }

    function releaseCollateral(address payable account, uint256 amount) external onlyLendingPool {
        require(totalReserves >= reserveBuffer, "reserve buffer");
        require(amount <= address(this).balance, "insufficient reserve");
        (bool ok,) = account.call{value: amount}("");
        require(ok, "release failed");
    }

    function collectProtocolFee(uint256 amount) external onlyLendingPool {
        accruedFee += amount;
        totalReserves += amount;
    }

    function absorbBadDebt(uint256 amount) external onlyLendingPool {
        require(amount <= totalReserves, "reserve exceeded");
        totalReserves -= amount;
    }
}
