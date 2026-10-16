from types import SimpleNamespace

import pytest

from trust_receipt.hashing import canonical_json_bytes, content_hash
from trust_receipt.m9 import PublicReceiptReference, PublicReferenceKind, build_public_bundle, verify_public_reference
from trust_receipt.m9.feedback import ERC8004PublicResolver
from trust_receipt.publishing import authorize_public_receipt

REGISTRY = "0x" + "11" * 20
REVIEWER = "0x" + "22" * 20
TX = "0x" + "ab" * 32


def _resolver(two_attempts, *, altered=None, latest=102, include_bundle=True):
    public = authorize_public_receipt(two_attempts.second_receipt)
    payload = canonical_json_bytes(public) + b"\n"
    args = {
        "clientAddress": REVIEWER, "agentId": 10691, "feedbackIndex": 1,
        "feedbackURI": "https://public.test/receipt.json",
        "feedbackHash": bytes.fromhex(content_hash(payload)[2:]),
        "tag1": "trust-receipt", "tag2": "PASS", "value": 1, "valueDecimals": 0,
    }
    args.update(altered or {})
    tx_receipt = {"status": 1, "blockNumber": 100, "blockHash": b"a" * 32,
                  "transactionHash": bytes.fromhex(TX[2:])}
    eth = SimpleNamespace(
        chain_id=11155111, block_number=latest,
        get_code=lambda address: b"deployed-code",
        get_transaction_receipt=lambda tx: tx_receipt,
        get_transaction=lambda tx: {"to": REGISTRY, "from": REVIEWER},
        get_block=lambda block: {"hash": b"a" * 32},
        contract=lambda address, abi: SimpleNamespace(events=SimpleNamespace(
            NewFeedback=lambda: SimpleNamespace(process_receipt=lambda receipt: [
                {"address": REGISTRY, "args": args},
            ]),
        )),
    )
    bundle = build_public_bundle(
        (two_attempts.first_receipt, two_attempts.second_receipt), authorized=True,
    )
    return ERC8004PublicResolver(
        rpc_url="https://unused.test", reputation_registry=REGISTRY, chain_id=11155111,
        attempt=2, reader=SimpleNamespace(fetch=lambda uri: payload), web3=SimpleNamespace(eth=eth),
        bundle_payload=canonical_json_bytes(bundle) if include_bundle else None,
    )


def test_feedback_reads_chain_event_and_public_history_before_verifying_repair(two_attempts):
    result = verify_public_reference(
        PublicReceiptReference(PublicReferenceKind.FEEDBACK_TRANSACTION, TX), _resolver(two_attempts),
    )
    assert result.status.value == "VERIFIED"
    assert result.resolution.value == "FIXED"
    assert any(ref.startswith("registry-service:") for ref in result.evidence_refs)


@pytest.mark.parametrize("altered", [
    {"clientAddress": REGISTRY}, {"tag2": "FAIL"}, {"value": -1},
    {"feedbackHash": b"z" * 32},
])
def test_feedback_conflicting_event_or_content_is_invalid(two_attempts, altered):
    result = verify_public_reference(
        PublicReceiptReference(PublicReferenceKind.FEEDBACK_TRANSACTION, TX),
        _resolver(two_attempts, altered=altered),
    )
    assert result.status.value == "INVALID"


def test_feedback_missing_parent_or_confirmations_is_inconclusive(two_attempts):
    for resolver in (_resolver(two_attempts, latest=100), _resolver(two_attempts, include_bundle=False)):
        result = verify_public_reference(PublicReceiptReference(PublicReferenceKind.FEEDBACK_TRANSACTION, TX), resolver)
        assert result.status.value == "INCONCLUSIVE"
