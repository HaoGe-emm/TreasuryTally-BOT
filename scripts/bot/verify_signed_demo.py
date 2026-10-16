"""Verify one local Demo wallet signature via upstream Python without persisting it."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

from eth_account import Account
from eth_account.messages import encode_typed_data
from eth_keys.exceptions import BadSignature
from eth_utils import keccak

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from trust_receipt.commitments.eip712 import (  # noqa: E402
    TASK_FIELDS,
    _task_message,
    task_commitment_hash,
    verify_task_commitment,
)
from trust_receipt.hashing import task_spec_hash  # noqa: E402
from trust_receipt.models import (  # noqa: E402
    CommitmentAnchor,
    CommitmentAnchorStatus,
    TaskCommitment,
    TaskSpec,
)


def main() -> None:
    raw_input = sys.stdin.buffer.read(4097)
    if len(raw_input) > 4096:
        raise ValueError("signature request is too large")
    request = json.loads(raw_input)
    if set(request) != {"signature"}:
        raise ValueError("expected only a signature")
    signature = request["signature"]
    if not isinstance(signature, str) or len(signature) != 132 or not signature.startswith("0x"):
        raise ValueError("invalid signature shape")
    demo = ROOT / "web3-demo/public/bot677-demo"
    task = TaskSpec.model_validate_json((demo / "task-spec.json").read_text(encoding="utf-8"))
    preview = json.loads((demo / "task-commitment-preview.json").read_text(encoding="utf-8"))
    if task.chain_id != 677 or task_spec_hash(task) != task.spec_hash or (
        preview["task_spec_hash"] != task.spec_hash
        or preview["message"]["specHash"] != task.spec_hash
        or preview["message"]["taskId"] != task.task_id
    ):
        raise ValueError("Demo TaskSpec binding mismatch")
    message = preview["message"]
    if (preview["status"] != "UNSIGNED_PREVIEW"
        or preview["domain"] != {"name": "TrustReceipt", "version": "1", "chainId": 677}
        or preview["types"] != {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
            ],
            "TaskCommitment": TASK_FIELDS,
        }
        or preview["primaryType"] != "TaskCommitment"
        or message["requester"].lower() != "0x89f415bb42e356e8b892c10b05522e0a8ef151f3"
        or message["serviceId"] != "treasurytally-bot-internal-demo-20261016"
        or preview["service_signer"].lower() != "0xb6bf6a936f529650992b71e2deb79e80fd3da71b"
        or preview["service_id_hash"] != "0x" + hashlib.sha256(message["serviceId"].encode()).hexdigest()
    ):
        raise ValueError("Demo signer or EIP-712 domain binding mismatch")
    commitment = TaskCommitment(
        commitment_version="1.0",
        commitment_id=message["commitmentId"],
        task_id=message["taskId"],
        spec_hash=message["specHash"],
        requester_address=message["requester"],
        service_id=message["serviceId"],
        created_at=datetime.fromisoformat(message["createdAt"]),
        expires_at=None,
        signature_scheme="EIP712",
        signature=signature,
        anchor=CommitmentAnchor(chain_id=677, status=CommitmentAnchorStatus.NOT_SUBMITTED),
    )
    if _task_message(commitment) != message:
        raise ValueError("TaskCommitment message differs from upstream model")
    if not verify_task_commitment(commitment, task):
        raise ValueError("upstream Python signature recovery or TaskSpec verification failed")
    typed = {key: preview[key] for key in ("domain", "types", "primaryType", "message")}
    signable = encode_typed_data(full_message=typed)
    typed_digest = "0x" + keccak(b"\x19" + signable.version + signable.header + signable.body).hex()
    if typed_digest != preview["typed_data_digest"]:
        raise ValueError("EIP-712 preview digest mismatch")
    recovered = Account.recover_message(signable, signature=signature)
    if recovered.lower() != message["requester"].lower():
        raise ValueError("recovered signer differs from requester")
    result = {
        "requester": recovered,
        "taskDigest": task_commitment_hash(commitment),
        "specHash": task.spec_hash,
        "serviceIdHash": preview["service_id_hash"],
        "serviceSigner": preview["service_signer"],
        "typedDataDigest": typed_digest,
        "scope": "LOCAL_PYTHON_SIGNATURE_CHECK_ONLY",
    }
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except (TypeError, ValueError, KeyError, json.JSONDecodeError, BadSignature) as exc:
        # Never print the raw signature or request body.
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        raise SystemExit(1) from None
