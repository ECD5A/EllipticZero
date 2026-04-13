// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.24;

interface ISyntheticToken {
    function approve(address spender, uint256 amount) external returns (bool);
}

/// @notice Synthetic fixture for bounded EllipticZero vault/permission review.
/// @dev Not production code and not an exploitable target.
contract SyntheticVault {
    address public owner;
    bool public paused;

    mapping(address => uint256) public balances;
    mapping(address => uint256) public shares;
    mapping(address => mapping(address => uint256)) public allowances;

    event Deposit(address indexed account, uint256 amount);
    event Redeem(address indexed account, uint256 sharesAmount);
    event OwnerChanged(address indexed previousOwner, address indexed nextOwner);

    modifier onlyOwner() {
        require(msg.sender == owner, "only owner");
        _;
    }

    modifier whenNotPaused() {
        require(!paused, "paused");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    function pause() external onlyOwner {
        paused = true;
    }

    function unpause() external onlyOwner {
        paused = false;
    }

    function deposit() external payable whenNotPaused {
        require(msg.value > 0, "zero deposit");
        balances[msg.sender] += msg.value;
        shares[msg.sender] += msg.value;
        emit Deposit(msg.sender, msg.value);
    }

    function redeem(uint256 sharesAmount) external whenNotPaused {
        require(shares[msg.sender] >= sharesAmount, "insufficient shares");
        shares[msg.sender] -= sharesAmount;
        balances[msg.sender] -= sharesAmount;

        (bool ok,) = msg.sender.call{value: sharesAmount}("");
        require(ok, "redeem transfer failed");
        emit Redeem(msg.sender, sharesAmount);
    }

    function permitStyleApprove(
        address signer,
        address spender,
        uint256 amount,
        bytes calldata signature
    ) external whenNotPaused {
        require(signer != address(0), "bad signer");
        require(spender != address(0), "bad spender");
        require(signature.length > 0, "missing signature");
        allowances[signer][spender] = amount;
    }

    function approveSpender(ISyntheticToken token, address spender, uint256 amount) external onlyOwner {
        require(spender != address(0), "bad spender");
        require(token.approve(spender, amount), "approve failed");
    }

    function recoverPermitSigner(
        bytes32 digest,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) external pure returns (address) {
        return ecrecover(digest, v, r, s);
    }

    function sweep(address payable target, uint256 amount) external onlyOwner {
        require(target != address(0), "bad target");
        (bool ok,) = target.call{value: amount}("");
        require(ok, "sweep failed");
    }

    function setOwner(address nextOwner) external onlyOwner {
        require(nextOwner != address(0), "bad owner");
        emit OwnerChanged(owner, nextOwner);
        owner = nextOwner;
    }
}
