"""Read-only ERC-8004 event resolution for independent public verification."""

from __future__ import annotations

from dataclasses import replace

from pydantic import ValidationError
from requests.exceptions import RequestException
from web3 import Web3
from web3.exceptions import TransactionNotFound, Web3Exception

from trust_receipt.m9.bundles import InvalidPublicEvidence, PublicBundleResolver
from trust_receipt.m9.models import PublicReferenceKind
from trust_receipt.m9.ports import PublicReceiptReference, ResolvedPublicReceipt
from trust_receipt.models.receipts import Receipt


class ERC8004PublicResolver:
    """No wallet, private workspace, write method, or model dependency."""

    def __init__(
        self, *, rpc_url: str, reputation_registry: str, chain_id: int,
        reader, attempt: int, bundle_payload: bytes | None = None,
        confirmations: int = 2, web3=None,
    ) -> None:
        self._web3 = web3 or Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 10}))
        self._registry = Web3.to_checksum_address(reputation_registry)
        self._chain_id = chain_id
        self._reader = reader
        self._attempt = attempt
        self._bundle = bundle_payload
        self._confirmations = confirmations

    def resolve(self, reference: PublicReceiptReference) -> ResolvedPublicReceipt:
        try:
            return self._resolve(reference)
        except InvalidPublicEvidence:
            raise
        except (Web3Exception, RequestException) as exc:
            raise OSError(f"feedback RPC unavailable: {type(exc).__name__}") from exc

    def _resolve(self, reference: PublicReceiptReference) -> ResolvedPublicReceipt:
        from agent0_sdk.core.contracts import REPUTATION_REGISTRY_ABI

        if reference.kind is not PublicReferenceKind.FEEDBACK_TRANSACTION:
            raise ValueError("ERC-8004 resolver requires a feedback transaction reference")
        if int(self._web3.eth.chain_id) != self._chain_id:
            raise InvalidPublicEvidence("RPC chain ID does not match the configured feedback network.")
        if not self._web3.eth.get_code(self._registry):
            raise InvalidPublicEvidence("Configured Reputation Registry has no deployed code.")
        try:
            tx_receipt = self._web3.eth.get_transaction_receipt(reference.value)
            transaction = self._web3.eth.get_transaction(reference.value)
        except TransactionNotFound as exc:
            raise LookupError("Feedback transaction is not available.") from exc
        if int(tx_receipt["status"]) != 1:
            raise InvalidPublicEvidence("Feedback transaction failed on chain.")
        block_number = int(tx_receipt["blockNumber"])
        if int(self._web3.eth.block_number) - block_number + 1 < self._confirmations:
            raise LookupError("Feedback transaction lacks the required confirmations.")
        canonical = self._web3.eth.get_block(block_number)
        if bytes(canonical["hash"]) != bytes(tx_receipt["blockHash"]):
            raise LookupError("Feedback transaction is not in the canonical chain.")
        observed_hash = Web3.to_hex(tx_receipt["transactionHash"])
        if observed_hash.lower() != reference.value.lower():
            raise InvalidPublicEvidence("RPC returned a different feedback transaction.")
        if (transaction.get("to") or "").lower() != self._registry.lower():
            raise InvalidPublicEvidence("Feedback transaction targets a different registry.")
        contract = self._web3.eth.contract(self._registry, abi=REPUTATION_REGISTRY_ABI)
        events = [
            event for event in contract.events.NewFeedback().process_receipt(tx_receipt)
            if event["address"].lower() == self._registry.lower()
        ]
        if len(events) != 1:
            raise InvalidPublicEvidence("Feedback transaction must contain exactly one registry event.")
        args = events[0]["args"]
        if args["clientAddress"].lower() != transaction["from"].lower():
            raise InvalidPublicEvidence("Feedback reviewer does not match the transaction sender.")
        payload = self._reader.fetch(args["feedbackURI"])
        try:
            receipt = Receipt.model_validate_json(payload)
        except ValidationError as exc:
            raise InvalidPublicEvidence("Feedback public bytes are not a valid Receipt.") from exc
        outcome = receipt.verification_result.outcome.value
        expected_value = {"PASS": 1, "FAIL": -1, "INCONCLUSIVE": 0}[outcome]
        if (
            args["tag1"] != "trust-receipt" or args["tag2"] != outcome
            or int(args["value"]) != expected_value or int(args["valueDecimals"]) != 0
        ):
            raise InvalidPublicEvidence("Feedback outcome or value does not match the public receipt.")
        resolved = ResolvedPublicReceipt(
            payload=payload, attempt=self._attempt,
            expected_content_hash=Web3.to_hex(args["feedbackHash"]),
            feedback_transaction_hash=reference.value, feedback_binding_verified=True,
            evidence_refs=(
                args["feedbackURI"], f"registry:{self._chain_id}:{self._registry}",
                f"registry-service:{self._chain_id}:{args['agentId']}",
                f"reviewer:{args['clientAddress']}", f"feedback-index:{args['feedbackIndex']}",
            ),
        )
        if self._bundle is not None:
            bundle = PublicBundleResolver(self._bundle, location="supplied-public-history").resolve(
                PublicReceiptReference(PublicReferenceKind.RECEIPT_HASH, receipt.receipt_hash),
            )
            if bundle.attempt != self._attempt:
                raise InvalidPublicEvidence("Feedback attempt does not match the public history.")
            resolved = replace(
                resolved, revision=bundle.revision, parent_revision=bundle.parent_revision,
                parent_receipt=bundle.parent_receipt,
                evidence_refs=(*resolved.evidence_refs, *bundle.evidence_refs),
            )
        return resolved
