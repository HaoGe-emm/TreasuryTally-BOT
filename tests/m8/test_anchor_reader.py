from types import SimpleNamespace

import pytest
from eth_abi import encode
from hexbytes import HexBytes
from web3 import Web3
from web3.exceptions import TransactionNotFound

from trust_receipt.commitments.anchor import DedicatedAnchorReader
from trust_receipt.commitments.eip712 import task_commitment_hash
from trust_receipt.hashing import content_hash
from trust_receipt.models import CommitmentAnchorStatus
from trust_receipt.orchestration.m8 import M8CommitmentWorkflow

ADDRESS = "0x" + "11" * 20
TX = "0x" + "22" * 32
BLOCK = HexBytes("0x" + "33" * 32)
CODE = b"candidate runtime bytecode"


class FakeEth:
    chain_id = 11_155_111
    block_number = 101

    def __init__(self, receipt, sender):
        self.receipt = receipt
        self.sender = sender

    def get_code(self, address):
        assert address == ADDRESS
        return CODE

    def get_transaction_receipt(self, transaction_hash):
        assert transaction_hash == TX
        if self.receipt is None:
            raise TransactionNotFound("transaction not found")
        return self.receipt

    def get_transaction(self, _):
        return {"to": ADDRESS, "from": self.sender}

    def get_block(self, _):
        return {"hash": BLOCK}

    def contract(self, **kwargs):
        return Web3().eth.contract(**kwargs)


@pytest.fixture
def anchored_task(m5_components):
    _, candidate, _, workflow, service = m5_components
    task = workflow.confirm_task(candidate)
    commitment = M8CommitmentWorkflow().commit_task(task, service.service_id)
    commitment = commitment.model_copy(update={"anchor": commitment.anchor.model_copy(update={
        "status": CommitmentAnchorStatus.SUBMITTED, "transaction_hash": TX,
    })})
    topics = [
        Web3.keccak(text="TaskAnchored(bytes32,address,address,bytes32,bytes32)"),
        HexBytes(task_commitment_hash(commitment)),
        HexBytes(encode(["address"], [commitment.requester_address])),
        HexBytes(encode(["address"], [service.signer_address])),
    ]
    log = {
        "address": ADDRESS, "topics": topics,
        "data": HexBytes(encode(["bytes32", "bytes32"], [
            HexBytes(task.spec_hash), HexBytes(content_hash(service.service_id.encode())),
        ])),
        "blockNumber": 100, "blockHash": BLOCK, "transactionHash": HexBytes(TX),
        "transactionIndex": 0, "logIndex": 0,
    }
    receipt = {"status": 1, "blockNumber": 100, "blockHash": BLOCK,
               "transactionHash": HexBytes(TX), "logs": [log]}
    eth = FakeEth(receipt, commitment.requester_address)
    reader = DedicatedAnchorReader(
        SimpleNamespace(eth=eth), chain_id=task.chain_id, contract_address=ADDRESS,
        runtime_code_hash=content_hash(CODE), confirmations=2,
    )
    return reader, eth, task, commitment, service


def test_readback_confirms_exact_task_bindings(anchored_task):
    reader, _, task, commitment, service = anchored_task
    result = reader.read_task_anchor(commitment, task=task, expected_signer=service.signer_address)
    assert result.status is CommitmentAnchorStatus.CONFIRMED
    assert result.block_number == 100


@pytest.mark.parametrize("mutation", ["chain", "code", "sender", "event", "missing", "ambiguous", "status"])
def test_readback_rejects_inconsistent_provenance(anchored_task, mutation):
    reader, eth, task, commitment, service = anchored_task
    if mutation == "chain":
        eth.chain_id = 1
    elif mutation == "code":
        reader._code_hash = "0x" + "00" * 32
    elif mutation == "sender":
        eth.sender = ADDRESS
    elif mutation == "event":
        eth.receipt["logs"][0]["topics"][1] = HexBytes("0x" + "00" * 32)
    elif mutation == "missing":
        eth.receipt["logs"] = []
    elif mutation == "ambiguous":
        eth.receipt["logs"] *= 2
    elif mutation == "status":
        eth.receipt["status"] = 2
    with pytest.raises(ValueError):
        reader.read_task_anchor(commitment, task=task, expected_signer=service.signer_address)


@pytest.mark.parametrize("mutation", ["unknown", "depth", "reorg", "reverted"])
def test_unknown_pending_and_reorg_never_become_confirmed(anchored_task, mutation):
    reader, eth, task, commitment, service = anchored_task
    if mutation == "unknown":
        eth.receipt = None
    elif mutation == "depth":
        eth.block_number = 100
    elif mutation == "reorg":
        eth.receipt["blockHash"] = HexBytes("0x" + "00" * 32)
    elif mutation == "reverted":
        eth.receipt["status"] = 0
    result = reader.read_task_anchor(commitment, task=task, expected_signer=service.signer_address)
    expected = CommitmentAnchorStatus.FAILED if mutation == "reverted" else CommitmentAnchorStatus.SUBMITTED
    assert result.status is expected
