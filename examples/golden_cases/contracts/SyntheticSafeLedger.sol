// SPDX-License-Identifier: UNLICENSED
pragma solidity 0.8.20;

contract SyntheticSafeLedger {
    address public immutable owner;
    mapping(address => uint256) public balances;

    constructor() {
        owner = msg.sender;
    }

    function credit(address account, uint256 amount) external {
        require(msg.sender == owner, "owner only");
        require(account != address(0), "zero account");
        balances[account] += amount;
    }

    function debit(address account, uint256 amount) external {
        require(msg.sender == owner, "owner only");
        require(balances[account] >= amount, "insufficient balance");
        balances[account] -= amount;
    }
}
