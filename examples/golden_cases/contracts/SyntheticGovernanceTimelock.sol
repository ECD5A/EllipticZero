// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.24;

/// @notice Synthetic fixture for bounded governance/timelock review.
/// @dev Not production code and not an exploitable target.
contract SyntheticGovernanceTimelock {
    address public admin;
    address public guardian;
    uint256 public delay;
    bool public paused;

    mapping(bytes32 => uint256) public queuedAt;

    event UpgradeQueued(bytes32 indexed operationId, address indexed implementation, uint256 eta);
    event UpgradeExecuted(bytes32 indexed operationId, address indexed implementation);
    event GuardianChanged(address indexed previousGuardian, address indexed nextGuardian);

    modifier onlyAdmin() {
        require(msg.sender == admin, "only admin");
        _;
    }

    constructor(address initialGuardian, uint256 initialDelay) {
        require(initialGuardian != address(0), "bad guardian");
        require(initialDelay >= 1 hours, "delay too short");
        admin = msg.sender;
        guardian = initialGuardian;
        delay = initialDelay;
    }

    function queueUpgrade(address implementation, bytes32 salt) external onlyAdmin returns (bytes32 operationId) {
        require(implementation != address(0), "bad implementation");
        operationId = keccak256(abi.encode(implementation, salt, block.chainid));
        queuedAt[operationId] = block.timestamp + delay;
        emit UpgradeQueued(operationId, implementation, queuedAt[operationId]);
    }

    function executeUpgrade(
        address implementation,
        bytes calldata payload,
        bytes32 salt
    ) external onlyAdmin returns (bytes memory result) {
        bytes32 operationId = keccak256(abi.encode(implementation, salt, block.chainid));
        require(queuedAt[operationId] != 0, "not queued");
        require(block.timestamp >= queuedAt[operationId], "timelock active");
        delete queuedAt[operationId];

        (bool ok, bytes memory output) = implementation.delegatecall(payload);
        require(ok, "delegatecall failed");
        emit UpgradeExecuted(operationId, implementation);
        return output;
    }

    function emergencyPause() external {
        require(msg.sender == guardian, "only guardian");
        paused = true;
    }

    function emergencyUnpause() external onlyAdmin {
        paused = false;
    }

    function setGuardian(address nextGuardian) external onlyAdmin {
        require(nextGuardian != address(0), "bad guardian");
        emit GuardianChanged(guardian, nextGuardian);
        guardian = nextGuardian;
    }

    function setDelay(uint256 nextDelay) external onlyAdmin {
        require(nextDelay >= 1 hours, "delay too short");
        delay = nextDelay;
    }
}
