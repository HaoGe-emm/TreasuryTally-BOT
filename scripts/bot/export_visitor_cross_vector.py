"""Emit one ephemeral signed visitor Demo vector from the original Python model.

The generated test account key stays in process memory and is never printed or
stored. This is an algorithm test, not a mainnet wallet action.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from eth_account import Account
from eth_account.messages import encode_typed_data
from eth_utils import keccak

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from trust_receipt.commitments.eip712 import (  # noqa: E402
    TASK_FIELDS,
    _domain,
    _task_message,
    create_task_commitment,
    task_commitment_hash,
    verify_task_commitment,
)
from trust_receipt.hashing import task_spec_hash  # noqa: E402
from trust_receipt.models import TaskSpec  # noqa: E402


def main() -> None:
    account = Account.create()
    task = TaskSpec(
        schema_version="1.0",
        task_id="bot677-visitor-demo-cross-test-1",
        chain_id=677,
        token_address="0xaBabc7Ddc03e501d190C676BF3d92ef0e6e87a3C",
        treasury_addresses=(account.address,),
        recipient_addresses=("0xb6bF6a936F529650992B71e2DeB79E80Fd3da71B",),
        start_block=26879920,
        end_block=26879920,
        exclusion_rules=(),
        max_records=200,
        confirmed_at=datetime.fromisoformat("2026-10-17T00:00:00+00:00"),
        spec_hash="0x" + "00" * 32,
    )
    task = task.model_copy(update={"spec_hash": task_spec_hash(task)})
    commitment = create_task_commitment(
        task,
        service_id="treasurytally-bot-self-demo-v1",
        requester_private_key=account.key.hex(),
        created_at=task.confirmed_at,
        commitment_id="task-commitment-cross-test-1",
    )
    if not verify_task_commitment(commitment, task):
        raise ValueError("original Python signature recovery failed")
    message = _task_message(commitment)
    typed = {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
            ],
            "TaskCommitment": TASK_FIELDS,
        },
        "primaryType": "TaskCommitment",
        "domain": _domain(677),
        "message": message,
    }
    signable = encode_typed_data(full_message=typed)
    typed_digest = "0x" + keccak(b"\x19" + signable.version + signable.header + signable.body).hex()
    print(json.dumps({
        "task": task.model_dump(mode="json"),
        "message": message,
        "requester": account.address,
        "signature": commitment.signature,
        "typedDataDigest": typed_digest,
        "taskDigest": task_commitment_hash(commitment),
    }))


if __name__ == "__main__":
    main()
