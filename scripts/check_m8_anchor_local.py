"""Exercise the undeployed M8 candidate on a disposable loopback EVM, never Sepolia."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eth_account import Account  # noqa: E402
from web3 import Web3  # noqa: E402

from trust_receipt.commitments import create_delivery_commitment, create_task_commitment  # noqa: E402
from trust_receipt.commitments.anchor import DedicatedAnchorReader  # noqa: E402
from trust_receipt.commitments.eip712 import task_commitment_hash  # noqa: E402
from trust_receipt.hashing import content_hash, stable_hash, submission_hash, task_spec_hash  # noqa: E402
from trust_receipt.models import CommitmentAnchor, CommitmentAnchorStatus, ServiceSubmission  # noqa: E402
from trust_receipt.orchestration import load_vertical_demo_fixture  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rpc", default="http://127.0.0.1:18549")
    parser.add_argument("--artifacts", type=Path, default=ROOT / ".tmp" / "m8-solc")
    args = parser.parse_args()
    endpoint = urlparse(args.rpc)
    if endpoint.scheme != "http" or endpoint.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("only explicit loopback HTTP development RPC is allowed")
    web3 = Web3(Web3.HTTPProvider(args.rpc, request_kwargs={"timeout": 10}))
    if web3.eth.chain_id != 1337:
        raise ValueError("only disposable development chain 1337 is allowed")
    stem = "contracts_CommitmentAnchor_sol_CommitmentAnchor"
    abi = json.loads((args.artifacts / f"{stem}.abi").read_text())
    bytecode = (args.artifacts / f"{stem}.bin").read_text().strip()
    dev_account = web3.eth.accounts[0]
    deployment = web3.eth.contract(abi=abi, bytecode=bytecode).constructor().transact({"from": dev_account})
    deployed = web3.eth.wait_for_transaction_receipt(deployment)
    assert deployed.status == 1
    contract = web3.eth.contract(address=deployed.contractAddress, abi=abi)
    requester, service = Account.create(), Account.create()
    for address in (requester.address, service.address):
        web3.eth.wait_for_transaction_receipt(web3.eth.send_transaction({
            "from": dev_account, "to": address, "value": 10**18,
        }))

    def transact(function, signer):
        transaction = function.build_transaction({
            "from": signer.address, "chainId": 1337,
            "nonce": web3.eth.get_transaction_count(signer.address), "gas": 500_000,
        })
        signed = signer.sign_transaction(transaction)
        digest = web3.eth.send_raw_transaction(signed.raw_transaction)
        return web3.eth.wait_for_transaction_receipt(digest)

    fixture = load_vertical_demo_fixture(ROOT)
    task = fixture.task_spec.model_copy(update={"chain_id": 1337})
    task = task.model_copy(update={"spec_hash": task_spec_hash(task)})
    now = datetime.now(UTC)
    commitment = create_task_commitment(
        task, service_id="local-evm-service", requester_private_key=requester.key.to_0x_hex(), created_at=now,
    )
    task_digest = task_commitment_hash(commitment)
    task_call = contract.functions.anchorTask(
        task_digest, task.spec_hash, content_hash(commitment.service_id.encode()), service.address,
    )
    # A different namespace cannot reserve the legitimate requester's digest.
    assert web3.eth.wait_for_transaction_receipt(task_call.transact({"from": dev_account})).status == 1
    receipt = transact(task_call, requester)
    assert receipt.status == 1
    assert transact(task_call, requester).status == 0
    assert contract.functions.tasks(requester.address, task_digest).call()[1] == service.address
    reader = DedicatedAnchorReader(
        web3, chain_id=1337, contract_address=contract.address,
        runtime_code_hash=content_hash(bytes(web3.eth.get_code(contract.address))), confirmations=1,
    )
    anchored = commitment.model_copy(update={"anchor": CommitmentAnchor(
        chain_id=1337, status=CommitmentAnchorStatus.SUBMITTED,
        transaction_hash="0x" + bytes(receipt.transactionHash).hex(),
    )})
    read_task = reader.read_task_anchor(anchored, task=task, expected_signer=service.address)
    assert read_task.status is CommitmentAnchorStatus.CONFIRMED
    for attempt in (1, 2):
        unsigned = ServiceSubmission(
            schema_version="1.0", submission_id=f"local-only-{attempt}", task_id=task.task_id,
            service_id=commitment.service_id, service_version="local-only", attempt=attempt,
            claimed_total_base_units="0", claimed_count=0, transfers=(), report_text="{}",
            created_at=now, report_hash="0x" + "00" * 32, signature=None,
        )
        submission = unsigned.model_copy(update={"report_hash": submission_hash(unsigned)})
        delivery = create_delivery_commitment(
            commitment, submission, service_private_key=service.key.to_0x_hex(), accepted_at=now, submitted_at=now,
        )
        call = contract.functions.anchorDelivery(
            requester.address, task_digest, attempt, content_hash(submission.submission_id.encode()),
            delivery.report_hash, stable_hash(delivery),
        )
        assert transact(call, requester).status == 0
        delivered = transact(call, service)
        assert delivered.status == 1
        assert transact(call, service).status == 0
        anchor = CommitmentAnchor(chain_id=1337, status=CommitmentAnchorStatus.SUBMITTED,
                                  transaction_hash="0x" + bytes(delivered.transactionHash).hex())
        assert reader.read_delivery_anchor(
            delivery, task_commitment=commitment, submission=submission,
            expected_signer=service.address, anchor=anchor,
        ).status is CommitmentAnchorStatus.CONFIRMED
    invalid = contract.functions.anchorDelivery(
        requester.address, task_digest, 3, content_hash(b"invalid"), "0x" + "44" * 32, "0x" + "55" * 32,
    )
    assert transact(invalid, service).status == 0
    print("LOCAL SIMULATION ONLY: deployment, requester namespace, task/delivery readback, "
          "authorization, immutable attempts and limit passed")


if __name__ == "__main__":
    main()
