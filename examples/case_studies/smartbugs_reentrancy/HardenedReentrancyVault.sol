// EllipticZero: https://github.com/ECD5A/EllipticZero
// Copyright (c) 2026 ECD5A
// SPDX-License-Identifier: LicenseRef-FSL-1.1-ALv2
// License terms: see LICENSE in the project root.

pragma solidity 0.8.24;

/// @notice Local hardening fixture for the SmartBugs reentrancy case study.
contract HardenedReentrancyVault {
    mapping(address => uint256) public balances;
    bool private withdrawalEntered;

    modifier nonReentrant() {
        require(!withdrawalEntered, "nested withdrawal");
        withdrawalEntered = true;
        _;
        withdrawalEntered = false;
    }

    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }

    function withdraw(uint256 amount) external nonReentrant {
        require(amount > 0, "zero amount");
        require(balances[msg.sender] >= amount, "insufficient balance");

        balances[msg.sender] -= amount;

        (bool transferred,) = msg.sender.call{value: amount}("");
        require(transferred, "transfer failed");
    }
}
