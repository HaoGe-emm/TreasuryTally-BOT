// SPDX-License-Identifier: MIT
pragma solidity 0.8.30;

/// @notice Review candidate only. No ERC-8004 identity, payment, or report validation.
contract CommitmentAnchor {
    struct Task {
        address requester;
        address serviceSigner;
    }

    // Requester namespace prevents third parties reserving another requester's digest.
    mapping(address => mapping(bytes32 => Task)) public tasks;
    mapping(address => mapping(bytes32 => mapping(uint8 => bool))) public delivered;

    event TaskAnchored(
        bytes32 indexed taskDigest, address indexed requester, address indexed serviceSigner,
        bytes32 specHash, bytes32 serviceIdHash
    );
    event DeliveryAnchored(
        bytes32 indexed taskDigest, address indexed serviceSigner, uint8 indexed attempt,
        address requester, bytes32 submissionIdHash, bytes32 reportHash, bytes32 deliveryDigest
    );

    error InvalidInput();
    error AlreadyAnchored();
    error Unauthorized();

    function anchorTask(
        bytes32 taskDigest, bytes32 specHash, bytes32 serviceIdHash, address serviceSigner
    ) external {
        if (taskDigest == bytes32(0) || specHash == bytes32(0) || serviceIdHash == bytes32(0)
            || serviceSigner == address(0)) revert InvalidInput();
        if (tasks[msg.sender][taskDigest].requester != address(0)) revert AlreadyAnchored();
        tasks[msg.sender][taskDigest] = Task(msg.sender, serviceSigner);
        emit TaskAnchored(taskDigest, msg.sender, serviceSigner, specHash, serviceIdHash);
    }

    function anchorDelivery(
        address requester, bytes32 taskDigest, uint8 attempt, bytes32 submissionIdHash,
        bytes32 reportHash, bytes32 deliveryDigest
    ) external {
        if (tasks[requester][taskDigest].serviceSigner != msg.sender) revert Unauthorized();
        if (attempt < 1 || attempt > 2 || submissionIdHash == bytes32(0)
            || reportHash == bytes32(0) || deliveryDigest == bytes32(0)) revert InvalidInput();
        if (delivered[requester][taskDigest][attempt]) revert AlreadyAnchored();
        delivered[requester][taskDigest][attempt] = true;
        emit DeliveryAnchored(taskDigest, msg.sender, attempt, requester, submissionIdHash, reportHash, deliveryDigest);
    }
}
