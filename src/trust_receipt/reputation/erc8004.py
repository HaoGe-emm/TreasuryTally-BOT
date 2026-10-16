"""ERC-8004 registry verification and deliberately non-retrying feedback write."""

from __future__ import annotations

from enum import StrEnum

from agent0_sdk import SDK
from pydantic import BaseModel, ConfigDict
from web3 import Web3

from trust_receipt.chain.rpc import EvmRpcProbe
from trust_receipt.integrations.errors import IntegrationError, IntegrationErrorCode


class ChainWriteState(StrEnum):
    NOT_SUBMITTED = "NOT_SUBMITTED"
    SUBMITTED = "SUBMITTED"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class RegistryReadResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    identity_registry: str
    reputation_registry: str
    validation_registry: str
    owner: str
    agent_uri: str


class FeedbackWriteResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    state: ChainWriteState
    transaction_hash: str | None = None
    block_number: int | None = None
    feedback_index: int | None = None
    reviewer: str | None = None
    error_code: IntegrationErrorCode | None = None


IDENTITY_READ_ABI = [
    {
        "inputs": [{"name": "tokenId", "type": "uint256"}],
        "name": "ownerOf",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "tokenId", "type": "uint256"}],
        "name": "tokenURI",
        "outputs": [{"name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function",
    },
]
REGISTRY_LINK_ABI = [
    {
        "inputs": [],
        "name": "getIdentityRegistry",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    }
]


def _numeric_agent_id(service_id: str) -> int:
    try:
        return int(service_id.rsplit(":", maxsplit=1)[-1])
    except ValueError as exc:
        raise IntegrationError(IntegrationErrorCode.CONFIGURATION, "AGENT0_SERVICE_ID is invalid") from exc


def _write_error_code(exc: Exception) -> IntegrationErrorCode:
    lowered = str(exc).lower()
    if "insufficient funds" in lowered:
        return IntegrationErrorCode.INSUFFICIENT_FUNDS
    if "revert" in lowered:
        return IntegrationErrorCode.TRANSACTION_REVERTED
    return IntegrationErrorCode.TRANSACTION_UNKNOWN


def verify_registries(
    rpc: EvmRpcProbe,
    *,
    identity_registry: str,
    reputation_registry: str,
    validation_registry: str,
    service_id: str,
) -> RegistryReadResult:
    addresses = [identity_registry, reputation_registry, validation_registry]
    for address in addresses:
        rpc.contract_code(address)
    identity = rpc.contract(identity_registry, IDENTITY_READ_ABI)
    expected_identity = Web3.to_checksum_address(identity_registry)
    for linked_registry in (reputation_registry, validation_registry):
        linked_identity = rpc.contract(linked_registry, REGISTRY_LINK_ABI).functions.getIdentityRegistry().call()
        if Web3.to_checksum_address(linked_identity) != expected_identity:
            raise IntegrationError(
                IntegrationErrorCode.CONTRACT_MISMATCH,
                "ERC-8004 registry points to an unexpected Identity Registry",
            )
    agent_id = _numeric_agent_id(service_id)
    try:
        owner = identity.functions.ownerOf(agent_id).call()
        uri = identity.functions.tokenURI(agent_id).call()
    except Exception as exc:
        raise IntegrationError(
            IntegrationErrorCode.CONTRACT_MISMATCH,
            f"ERC-8004 identity read failed: {type(exc).__name__}",
        ) from exc
    return RegistryReadResult(
        identity_registry=expected_identity,
        reputation_registry=Web3.to_checksum_address(reputation_registry),
        validation_registry=Web3.to_checksum_address(validation_registry),
        owner=owner,
        agent_uri=uri,
    )


def submit_neutral_test_feedback_once(
    *,
    chain_id: int,
    rpc_url: str,
    service_id: str,
    reviewer_private_key: str,
    registry_overrides: dict[int, dict[str, str]],
    confirmation_timeout_seconds: float = 120,
) -> FeedbackWriteResult:
    """Broadcast exactly once; callers must reconcile UNKNOWN by nonce/hash before retrying."""
    sdk = SDK(
        chainId=chain_id,
        rpcUrl=rpc_url,
        signer=reviewer_private_key,
        registryOverrides=registry_overrides,
    )
    reviewer = sdk.get_web3_client_for_chain(chain_id).w3.eth.account.from_key(reviewer_private_key).address
    try:
        transaction = sdk.giveFeedback(
            agentId=service_id,
            value=0,
            tag1="trust-receipt-m0",
            tag2="neutral-connectivity-test",
            endpoint="",
            feedbackFile=None,
        )
    except Exception as exc:
        code = _write_error_code(exc)
        raise IntegrationError(
            code,
            f"Feedback broadcast did not return a reliable handle: {type(exc).__name__}; do not resend automatically",
        ) from exc
    transaction_hash = getattr(transaction, "tx_hash", None) or getattr(transaction, "transaction_hash", None)
    try:
        confirmed = transaction.wait_confirmed(timeout=confirmation_timeout_seconds)
        feedback = confirmed.result
    except Exception as exc:
        code = _write_error_code(exc)
        state = ChainWriteState.FAILED if code is IntegrationErrorCode.TRANSACTION_REVERTED else ChainWriteState.UNKNOWN
        return FeedbackWriteResult(
            state=state,
            transaction_hash=str(transaction_hash) if transaction_hash else None,
            reviewer=reviewer,
            error_code=code,
        )
    feedback_id = getattr(feedback, "id", None)
    index = int(feedback_id[2]) if isinstance(feedback_id, tuple) and len(feedback_id) == 3 else None
    read_back = sdk.getFeedback(service_id, reviewer, index) if index is not None else None
    if (
        read_back is None
        or read_back.reviewer.lower() != reviewer.lower()
        or read_back.value != 0
        or read_back.tags != ["trust-receipt-m0", "neutral-connectivity-test"]
    ):
        raise IntegrationError(
            IntegrationErrorCode.INVALID_RESPONSE,
            "Confirmed neutral feedback did not match the on-chain read-back",
        )
    block_number = confirmed.receipt.get("blockNumber")
    return FeedbackWriteResult(
        state=ChainWriteState.CONFIRMED,
        transaction_hash=str(transaction_hash) if transaction_hash else None,
        block_number=block_number,
        feedback_index=index,
        reviewer=reviewer,
    )


def read_confirmed_neutral_feedback(
    *,
    chain_id: int,
    rpc_url: str,
    service_id: str,
    reviewer_address: str,
    feedback_index: int,
    transaction_hash: str,
    registry_overrides: dict[int, dict[str, str]],
) -> FeedbackWriteResult:
    """Read a known transaction and its stored feedback without broadcasting."""
    sdk = SDK(
        chainId=chain_id,
        rpcUrl=rpc_url,
        registryOverrides=registry_overrides,
    )
    client = sdk.get_web3_client_for_chain(chain_id)
    try:
        receipt = client.w3.eth.get_transaction_receipt(transaction_hash)
        latest_block = client.w3.eth.block_number
        feedback = sdk.getFeedback(service_id, reviewer_address, feedback_index)
    except Exception as exc:
        raise IntegrationError(
            IntegrationErrorCode.UNAVAILABLE,
            f"ERC-8004 feedback read failed: {type(exc).__name__}",
        ) from exc
    if receipt["status"] != 1:
        raise IntegrationError(IntegrationErrorCode.TRANSACTION_REVERTED, "Feedback transaction reverted")
    confirmations = latest_block - int(receipt["blockNumber"]) + 1
    if confirmations < 1:
        raise IntegrationError(IntegrationErrorCode.TRANSACTION_UNKNOWN, "Feedback transaction is not confirmed")
    if (
        feedback.reviewer.lower() != reviewer_address.lower()
        or feedback.value != 0
        or feedback.tags != ["trust-receipt-m0", "neutral-connectivity-test"]
        or feedback.isRevoked
    ):
        raise IntegrationError(
            IntegrationErrorCode.INVALID_RESPONSE,
            "Stored neutral feedback does not match the expected public evidence",
        )
    return FeedbackWriteResult(
        state=ChainWriteState.CONFIRMED,
        transaction_hash=transaction_hash,
        block_number=int(receipt["blockNumber"]),
        feedback_index=feedback_index,
        reviewer=reviewer_address,
    )
