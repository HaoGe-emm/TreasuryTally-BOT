"""Validate browser/viem public test artifacts using unchanged upstream Python code."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from trust_receipt.commitments.eip712 import (  # noqa: E402
    task_commitment_hash,
    verify_delivery_commitment,
    verify_task_commitment,
)
from trust_receipt.hashing import stable_hash, submission_hash, task_spec_hash  # noqa: E402
from trust_receipt.models import DeliveryCommitment, ServiceSubmission, TaskCommitment, TaskSpec  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vector", type=Path)
    args = parser.parse_args()
    vector = json.loads(args.vector.read_text(encoding="utf-8"))
    task = TaskSpec.model_validate(vector["task"])
    commitment = TaskCommitment.model_validate(vector["task_commitment"])
    submission = ServiceSubmission.model_validate(vector["submission"])
    delivery = DeliveryCommitment.model_validate(vector["delivery_commitment"])
    assert task_spec_hash(task) == task.spec_hash == vector["specHash"]
    assert task_commitment_hash(commitment) == vector["taskDigest"]
    assert verify_task_commitment(commitment, task)
    assert submission_hash(submission) == submission.report_hash
    assert stable_hash(delivery) == vector["deliveryDigest"]
    assert verify_delivery_commitment(delivery, commitment, submission, expected_signer=delivery.signer_address)
    other_requester = commitment.model_copy(update={"requester_address": delivery.signer_address})
    assert not verify_task_commitment(other_requester, task)
    assert not verify_task_commitment(commitment, task.model_copy(update={"chain_id": 677}))
    assert not verify_task_commitment(commitment, task.model_copy(update={"end_block": task.end_block + 1}))
    print(json.dumps({"scope": "LOCAL DEMO PUBLIC VECTORS", "upstream_python_verification": "passed",
                      "task_spec_hash": task.spec_hash, "task_commitment_hash": vector["taskDigest"],
                      "delivery_commitment_hash": vector["deliveryDigest"],
                      "tampered_requester_chain_scope": "rejected"}, indent=2))


if __name__ == "__main__":
    main()
