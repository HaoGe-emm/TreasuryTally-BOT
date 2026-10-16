"""Unwired, read-only adapter for the undeployed dedicated anchor candidate."""

from __future__ import annotations

from web3 import Web3
from web3.exceptions import TransactionNotFound

from trust_receipt.commitments.eip712 import (
    task_commitment_hash,
    verify_delivery_commitment,
    verify_task_commitment,
)
from trust_receipt.hashing import content_hash, stable_hash
from trust_receipt.models import CommitmentAnchor, CommitmentAnchorStatus


def _event(name, fields):
    return {
        "type": "event", "name": name, "anonymous": False,
        "inputs": [{"name": key, "type": kind, "indexed": indexed} for key, kind, indexed in fields],
    }


ANCHOR_ABI = [
    _event("TaskAnchored", [
        ("taskDigest", "bytes32", True), ("requester", "address", True),
        ("serviceSigner", "address", True), ("specHash", "bytes32", False),
        ("serviceIdHash", "bytes32", False),
    ]),
    _event("DeliveryAnchored", [
        ("taskDigest", "bytes32", True), ("serviceSigner", "address", True),
        ("attempt", "uint8", True), ("requester", "address", False),
        ("submissionIdHash", "bytes32", False),
        ("reportHash", "bytes32", False), ("deliveryDigest", "bytes32", False),
    ]),
]


def _hex(value):
    return "0x" + bytes(value).hex()


class DedicatedAnchorReader:
    """No signer, send method, environment lookup, or automatic resubmission."""

    def __init__(self, web3, *, chain_id, contract_address, runtime_code_hash, confirmations=2):
        if confirmations < 1:
            raise ValueError("confirmation depth must be positive")
        self._web3 = web3
        self._chain_id = chain_id
        self._address = Web3.to_checksum_address(contract_address)
        self._code_hash = runtime_code_hash
        self._confirmations = confirmations

    def _read(self, anchor, event_name, expected, sender):
        if anchor.chain_id != self._chain_id or self._web3.eth.chain_id != self._chain_id:
            raise ValueError("anchor RPC chain mismatch")
        code = bytes(self._web3.eth.get_code(self._address))
        if not code or content_hash(code) != self._code_hash:
            raise ValueError("anchor runtime bytecode mismatch")
        if anchor.transaction_hash is None:
            if anchor.status is not CommitmentAnchorStatus.NOT_SUBMITTED:
                raise ValueError("submitted anchor requires a transaction hash for readback")
            return anchor
        pending = CommitmentAnchor(
            chain_id=self._chain_id, status=CommitmentAnchorStatus.SUBMITTED,
            transaction_hash=anchor.transaction_hash,
        )
        try:
            receipt = self._web3.eth.get_transaction_receipt(anchor.transaction_hash)
        except TransactionNotFound:
            return pending
        if receipt["blockNumber"] is None:
            return pending
        block = self._web3.eth.get_block(receipt["blockNumber"])
        if bytes(block["hash"]) != bytes(receipt["blockHash"]):
            return pending
        transaction = self._web3.eth.get_transaction(anchor.transaction_hash)
        if (
            _hex(receipt["transactionHash"]).lower() != anchor.transaction_hash.lower()
            or transaction["to"].lower() != self._address.lower()
            or transaction["from"].lower() != sender.lower()
        ):
            raise ValueError("anchor transaction provenance mismatch")
        if self._web3.eth.block_number - receipt["blockNumber"] + 1 < self._confirmations:
            return pending
        if receipt["status"] == 0:
            return pending.model_copy(update={"status": CommitmentAnchorStatus.FAILED})
        if receipt["status"] != 1:
            raise ValueError("unknown anchor receipt status")
        contract = self._web3.eth.contract(address=self._address, abi=ANCHOR_ABI)
        decoder = getattr(contract.events, event_name)()
        matches = []
        for log in receipt["logs"]:
            if log["address"].lower() != self._address.lower():
                continue
            # Ignore other events, but never suppress decoding errors for the expected topic.
            event_abi = next(item for item in ANCHOR_ABI if item["name"] == event_name)
            signature = event_name + "(" + ",".join(item["type"] for item in event_abi["inputs"]) + ")"
            if not log["topics"] or bytes(log["topics"][0]) != bytes(Web3.keccak(text=signature)):
                continue
            matches.append(decoder.process_log(log)["args"])
        if len(matches) != 1:
            raise ValueError("anchor event missing or ambiguous")
        actual = matches[0]
        for key, expected_value in expected.items():
            value = _hex(actual[key]) if isinstance(actual[key], bytes) else actual[key]
            if isinstance(value, str) and isinstance(expected_value, str):
                value, expected_value = value.lower(), expected_value.lower()
            if value != expected_value:
                raise ValueError(f"anchor event binding mismatch: {key}")
        return pending.model_copy(update={
            "status": CommitmentAnchorStatus.CONFIRMED, "block_number": receipt["blockNumber"],
        })

    def read_task_anchor(self, commitment, *, task, expected_signer):
        if not verify_task_commitment(commitment, task):
            raise ValueError("invalid task signature or spec binding")
        return self._read(commitment.anchor, "TaskAnchored", {
            "taskDigest": task_commitment_hash(commitment), "requester": commitment.requester_address,
            "serviceSigner": expected_signer, "specHash": commitment.spec_hash,
            "serviceIdHash": content_hash(commitment.service_id.encode()),
        }, commitment.requester_address)

    def read_delivery_anchor(self, commitment, *, task_commitment, submission, expected_signer, anchor):
        if not verify_delivery_commitment(
            commitment, task_commitment, submission, expected_signer=expected_signer,
        ):
            raise ValueError("invalid delivery signature or task binding")
        return self._read(anchor, "DeliveryAnchored", {
            "taskDigest": task_commitment_hash(task_commitment), "serviceSigner": expected_signer,
            "requester": task_commitment.requester_address,
            "attempt": commitment.attempt, "submissionIdHash": content_hash(commitment.submission_id.encode()),
            "reportHash": commitment.report_hash, "deliveryDigest": stable_hash(commitment),
        }, expected_signer)
