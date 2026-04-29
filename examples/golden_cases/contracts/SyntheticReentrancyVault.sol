// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Synthetic review fixture for external-call ordering and reentrancy-adjacent lanes.
contract SyntheticReentrancyVault {
    mapping(address => uint256) public balances;
    bool public paused;
    address public owner;

    modifier onlyOwner() {
        require(msg.sender == owner, "not owner");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    receive() external payable {
        balances[msg.sender] += msg.value;
    }

    function deposit() external payable {
        require(!paused, "paused");
        balances[msg.sender] += msg.value;
    }

    function withdraw(uint256 amount) external {
        require(!paused, "paused");
        require(balances[msg.sender] >= amount, "insufficient");

        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok, "transfer failed");

        balances[msg.sender] -= amount;
    }

    function emergencyDrain(address payable recipient, uint256 amount) external onlyOwner {
        (bool ok,) = recipient.call{value: amount}("");
        require(ok, "drain failed");
    }

    function setPaused(bool newPaused) external onlyOwner {
        paused = newPaused;
    }
}
