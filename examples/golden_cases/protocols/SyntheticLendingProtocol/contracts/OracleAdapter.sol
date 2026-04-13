// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.24;

/// @notice Synthetic oracle fixture for repo-scale golden-case inventory.
/// @dev Not production code and not an exploitable target.
contract OracleAdapter {
    address public admin;
    int256 public lastPrice;
    uint256 public updatedAt;
    uint256 public staleAfter;

    modifier onlyAdmin() {
        require(msg.sender == admin, "only admin");
        _;
    }

    constructor(int256 initialPrice, uint256 initialStaleAfter) {
        admin = msg.sender;
        lastPrice = initialPrice;
        updatedAt = block.timestamp;
        staleAfter = initialStaleAfter;
    }

    function latestRoundData()
        external
        view
        returns (uint80 roundId, int256 answer, uint256 startedAt, uint256 timestamp, uint80 answeredInRound)
    {
        return (1, lastPrice, updatedAt, updatedAt, 1);
    }

    function isStale() external view returns (bool) {
        return block.timestamp > updatedAt + staleAfter;
    }

    function setPrice(int256 nextPrice) external onlyAdmin {
        require(nextPrice > 0, "bad price");
        lastPrice = nextPrice;
        updatedAt = block.timestamp;
    }
}
