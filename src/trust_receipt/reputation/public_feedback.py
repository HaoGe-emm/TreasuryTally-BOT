"""ERC-8004 public-receipt feedback with explicit non-retrying write states."""

from __future__ import annotations

from dataclasses import dataclass

from eth_account import Account
from pydantic import SecretStr
from web3 import Web3

from trust_receipt.hashing import receipt_hash
from trust_receipt.integrations.config import SEPOLIA_CHAIN_ID
from trust_receipt.integrations.errors import IntegrationErrorCode
from trust_receipt.models.enums import PublicationChainStatus, VerificationOutcome
from trust_receipt.models.receipts import Receipt


@dataclass(frozen=True)
class FeedbackPreflight:
    chain_id: int
    service_id: str
    service_owner: str
    reviewer: str
    balance_wei: int
    nonce: int


def _numeric_service_id(service_id: str) -> int:
    try:
        return int(service_id.rsplit(":", 1)[-1])
    except ValueError as exc:
        raise ValueError("service_id must end with a numeric ERC-8004 token ID") from exc


def _rehash(receipt: Receipt, **publication_updates: object) -> Receipt:
    publication = receipt.publication.model_copy(update=publication_updates)
    draft = receipt.model_copy(
        update={"publication": publication, "receipt_hash": "0x" + "0" * 64}
    )
    return draft.model_copy(update={"receipt_hash": receipt_hash(draft)})


class ERC8004ReceiptFeedback:
    """Broadcast once, persist the nonce/hash, then reconcile without resending."""

    def __init__(
        self,
        *,
        rpc_url: str,
        chain_id: int,
        service_id: str,
        expected_service_owner: str,
        identity_registry: str,
        reputation_registry: str,
        reviewer_private_key: SecretStr,
        expected_reviewer: str | None = None,
        request_timeout_seconds: float = 30,
    ) -> None:
        self._web3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": request_timeout_seconds}))
        self._chain_id = chain_id
        self._service_id = service_id
        self._expected_owner = Web3.to_checksum_address(expected_service_owner)
        self._identity_address = Web3.to_checksum_address(identity_registry)
        self._reputation_address = Web3.to_checksum_address(reputation_registry)
        self._private_key = reviewer_private_key
        self._reviewer = Account.from_key(reviewer_private_key.get_secret_value()).address
        self._expected_reviewer = (
            Web3.to_checksum_address(expected_reviewer) if expected_reviewer else self._reviewer
        )

    def preflight(self) -> FeedbackPreflight:
        from agent0_sdk.core.contracts import IDENTITY_REGISTRY_ABI

        observed_chain = int(self._web3.eth.chain_id)
        if self._chain_id != SEPOLIA_CHAIN_ID or observed_chain != self._chain_id:
            raise ValueError(f"ERC-8004 write requires Sepolia chain_id={SEPOLIA_CHAIN_ID}")
        if self._reviewer != self._expected_reviewer:
            raise ValueError("reviewer private key does not match the configured reviewer address")
        if not self._web3.eth.get_code(self._reputation_address):
            raise ValueError("reputation registry has no contract code")
        identity = self._web3.eth.contract(self._identity_address, abi=IDENTITY_REGISTRY_ABI)
        owner = Web3.to_checksum_address(
            identity.functions.ownerOf(_numeric_service_id(self._service_id)).call()
        )
        if owner != self._expected_owner:
            raise ValueError("ERC-8004 service identity is not controlled by the expected owner")
        balance = int(self._web3.eth.get_balance(self._reviewer))
        if balance <= 0:
            raise ValueError("reviewer has no Sepolia ETH")
        nonce = int(self._web3.eth.get_transaction_count(self._reviewer, "pending"))
        return FeedbackPreflight(
            chain_id=observed_chain,
            service_id=self._service_id,
            service_owner=owner,
            reviewer=self._reviewer,
            balance_wei=balance,
            nonce=nonce,
        )

    def submit_once(self, receipt: Receipt) -> Receipt:
        from agent0_sdk.core.contracts import REPUTATION_REGISTRY_ABI

        publication = receipt.publication
        if (
            not publication.authorized
            or publication.uri is None
            or publication.content_hash is None
            or publication.chain_status is not PublicationChainStatus.NOT_SUBMITTED
        ):
            raise ValueError("receipt must be published and NOT_SUBMITTED before ERC-8004 write")
        preflight = self.preflight()
        outcome = receipt.verification_result.outcome
        value = {
            VerificationOutcome.PASS: 1,
            VerificationOutcome.FAIL: -1,
            VerificationOutcome.INCONCLUSIVE: 0,
        }[outcome]
        contract = self._web3.eth.contract(self._reputation_address, abi=REPUTATION_REGISTRY_ABI)
        try:
            latest = self._web3.eth.get_block("latest")
            priority = int(self._web3.eth.max_priority_fee)
            base_fee = int(latest.get("baseFeePerGas", 0))
            feedback_call = contract.functions.giveFeedback(
                _numeric_service_id(self._service_id),
                value,
                0,
                "trust-receipt",
                outcome.value,
                publication.uri,
                publication.uri,
                bytes.fromhex(publication.content_hash.removeprefix("0x")),
            )
            transaction_base = {
                "chainId": self._chain_id,
                "from": self._reviewer,
                "nonce": preflight.nonce,
                "maxPriorityFeePerGas": priority,
                "maxFeePerGas": base_fee * 2 + priority,
            }
            estimated_gas = int(feedback_call.estimate_gas(transaction_base))
            if estimated_gas <= 0 or estimated_gas > 2_000_000:
                raise ValueError("ERC-8004 gas estimate is outside the allowed range")
            gas_limit = estimated_gas + max(50_000, estimated_gas // 5)
            transaction = feedback_call.build_transaction(
                {**transaction_base, "gas": gas_limit}
            )
            signed = self._web3.eth.account.sign_transaction(
                transaction, private_key=self._private_key.get_secret_value()
            )
        except Exception as exc:
            return _rehash(
                receipt,
                chain_status=PublicationChainStatus.FAILED,
                chain_id=self._chain_id,
                reviewer_address=self._reviewer,
                transaction_nonce=preflight.nonce,
                error_code=IntegrationErrorCode.TRANSACTION_REVERTED.value,
                error_message=f"Transaction preparation failed: {type(exc).__name__}",
            )
        tx_hash = signed.hash.to_0x_hex()
        try:
            self._web3.eth.send_raw_transaction(signed.raw_transaction)
            error_code = None
            error_message = None
        except Exception as exc:
            # A transport failure after send may still have propagated. Persist the signed
            # hash and nonce as SUBMITTED; callers must reconcile and must not resend.
            error_code = IntegrationErrorCode.TRANSACTION_UNKNOWN.value
            error_message = f"Broadcast result uncertain: {type(exc).__name__}; do not resend"
        return _rehash(
            receipt,
            chain_status=PublicationChainStatus.SUBMITTED,
            chain_id=self._chain_id,
            reviewer_address=self._reviewer,
            transaction_nonce=preflight.nonce,
            transaction_hash=tx_hash,
            error_code=error_code,
            error_message=error_message,
        )

    def reconcile(self, receipt: Receipt) -> Receipt:
        from agent0_sdk.core.contracts import REPUTATION_REGISTRY_ABI

        publication = receipt.publication
        if publication.chain_status is not PublicationChainStatus.SUBMITTED:
            raise ValueError("only SUBMITTED publication can be reconciled")
        if publication.transaction_hash is None:
            return receipt
        try:
            transaction_receipt = self._web3.eth.get_transaction_receipt(publication.transaction_hash)
        except Exception:
            return receipt
        if int(transaction_receipt["status"]) != 1:
            return _rehash(
                receipt,
                chain_status=PublicationChainStatus.FAILED,
                error_code=IntegrationErrorCode.TRANSACTION_REVERTED.value,
                error_message="ERC-8004 feedback transaction reverted",
            )
        contract = self._web3.eth.contract(self._reputation_address, abi=REPUTATION_REGISTRY_ABI)
        events = contract.events.NewFeedback().process_receipt(transaction_receipt)
        if len(events) != 1:
            return _rehash(
                receipt,
                chain_status=PublicationChainStatus.FAILED,
                error_code=IntegrationErrorCode.INVALID_RESPONSE.value,
                error_message="ERC-8004 receipt did not contain exactly one NewFeedback event",
            )
        values = events[0]["args"]
        expected_hash = bytes.fromhex((publication.content_hash or "").removeprefix("0x"))
        valid = (
            int(values["agentId"]) == _numeric_service_id(self._service_id)
            and values["clientAddress"].lower() == self._reviewer.lower()
            and values["feedbackURI"] == publication.uri
            and bytes(values["feedbackHash"]) == expected_hash
            and values["tag1"] == "trust-receipt"
            and values["tag2"] == receipt.verification_result.outcome.value
        )
        if not valid:
            return _rehash(
                receipt,
                chain_status=PublicationChainStatus.FAILED,
                error_code=IntegrationErrorCode.INVALID_RESPONSE.value,
                error_message="on-chain feedback read-back did not match the public receipt",
            )
        return _rehash(
            receipt,
            chain_status=PublicationChainStatus.CONFIRMED,
            feedback_index=int(values["feedbackIndex"]),
            block_number=int(transaction_receipt["blockNumber"]),
            error_code=None,
            error_message=None,
        )
