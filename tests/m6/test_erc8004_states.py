from __future__ import annotations

from types import SimpleNamespace

import pytest
from eth_account import Account
from hexbytes import HexBytes
from pydantic import SecretStr

from tests.m6.test_publication import PROJECT_ROOT, _receipt
from trust_receipt.models import PublicationChainStatus
from trust_receipt.publishing import LocalDirectoryPublisher, publish_receipt
from trust_receipt.reputation import ERC8004ReceiptFeedback, FeedbackPreflight


class _Call:
    def __init__(self):
        self.estimated_with = None
        self.built_with = None

    def estimate_gas(self, transaction):
        self.estimated_with = transaction
        return 400_000

    def build_transaction(self, transaction):
        self.built_with = transaction
        return {**transaction, "to": "0x" + "33" * 20, "data": "0x", "value": 0}


class _Functions:
    def giveFeedback(self, *args):
        self.args = args
        self.call = _Call()
        return self.call


class _Contract:
    def __init__(self):
        self.functions = _Functions()


class _Account:
    def sign_transaction(self, transaction, *, private_key):
        return SimpleNamespace(hash=HexBytes("0x" + "44" * 32), raw_transaction=b"signed")


class _Eth:
    max_priority_fee = 1

    def __init__(self):
        self.account = _Account()
        self.send_calls = 0
        self.feedback_contract = _Contract()

    def contract(self, address, abi):
        return self.feedback_contract

    def get_block(self, block):
        return {"baseFeePerGas": 2}

    def send_raw_transaction(self, payload):
        self.send_calls += 1
        raise TimeoutError("ambiguous transport failure")

    def get_transaction_receipt(self, transaction_hash):
        raise RuntimeError("not indexed yet")


class _Web3:
    def __init__(self):
        self.eth = _Eth()


class _TestFeedback(ERC8004ReceiptFeedback):
    def preflight(self):
        return FeedbackPreflight(
            chain_id=11_155_111,
            service_id=self._service_id,
            service_owner="0x" + "55" * 20,
            reviewer=self._reviewer,
            balance_wei=1,
            nonce=9,
        )


def test_ambiguous_broadcast_stays_submitted_and_is_never_auto_resent(tmp_path):
    receipt, _ = _receipt(PROJECT_ROOT, tmp_path)
    published, _ = publish_receipt(receipt, LocalDirectoryPublisher(tmp_path / "public"))
    adapter = object.__new__(_TestFeedback)
    adapter._web3 = _Web3()
    adapter._chain_id = 11_155_111
    adapter._service_id = "11155111:10691"
    adapter._reviewer = Account.create().address
    adapter._reputation_address = "0x" + "66" * 20
    adapter._private_key = SecretStr("0x" + "77" * 32)

    submitted = adapter.submit_once(published)

    assert submitted.publication.chain_status is PublicationChainStatus.SUBMITTED
    assert submitted.publication.transaction_nonce == 9
    assert submitted.publication.transaction_hash == "0x" + "44" * 32
    assert submitted.publication.error_code == "TRANSACTION_UNKNOWN"
    call = adapter._web3.eth.feedback_contract.functions.call
    assert call.estimated_with["nonce"] == 9
    assert "gas" not in call.estimated_with
    assert call.built_with["gas"] == 480_000
    assert adapter._web3.eth.send_calls == 1
    assert adapter.reconcile(submitted) == submitted
    assert adapter._web3.eth.send_calls == 1
    with pytest.raises(ValueError, match="NOT_SUBMITTED"):
        adapter.submit_once(submitted)
    assert adapter._web3.eth.send_calls == 1
