"""Check the unsigned BOT Demo signing preview against upstream models and EIP-712."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

from eth_account.messages import encode_typed_data
from eth_utils import keccak

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from trust_receipt.commitments.eip712 import (  # noqa: E402
    EMPTY_SIGNATURE,
    TASK_FIELDS,
    _domain,
    _task_message,
)
from trust_receipt.hashing import task_spec_hash  # noqa: E402
from trust_receipt.models import (  # noqa: E402
    CommitmentAnchor,
    CommitmentAnchorStatus,
    TaskCommitment,
    TaskSpec,
)


def main() -> None:
    demo = ROOT / "web3-demo/public/bot677-demo"
    task = TaskSpec.model_validate_json((demo / "task-spec.json").read_text(encoding="utf-8"))
    preview = json.loads((demo / "task-commitment-preview.json").read_text(encoding="utf-8"))
    if task.chain_id != 677 or task_spec_hash(task) != task.spec_hash:
        raise ValueError("TaskSpec model/hash mismatch")
    if preview["status"] != "UNSIGNED_PREVIEW" or not preview["demo_data"]:
        raise ValueError("Preview must remain an unsigned Demo")
    if preview["task_spec_hash"] != task.spec_hash or preview["message"]["specHash"] != task.spec_hash:
        raise ValueError("Preview TaskSpec binding mismatch")
    service_id = "treasurytally-bot-internal-demo-20261016"
    requester = "0x89F415bb42e356E8b892C10B05522e0a8Ef151F3"
    service_signer = "0xb6bF6a936F529650992B71e2DeB79E80Fd3da71B"
    if preview["service_signer"] != service_signer or preview["message"]["requester"] != requester:
        raise ValueError("Requester/serviceSigner mismatch")
    if preview["message"]["serviceId"] != service_id or preview["message"]["taskId"] != task.task_id:
        raise ValueError("Task/service ID mismatch")
    expected_service_hash = "0x" + hashlib.sha256(service_id.encode("utf-8")).hexdigest()
    if preview["service_id_hash"] != expected_service_hash:
        raise ValueError("Service ID hash mismatch")
    message = preview["message"]
    commitment = TaskCommitment(
        commitment_version="1.0",
        commitment_id=message["commitmentId"],
        task_id=task.task_id,
        spec_hash=task.spec_hash,
        requester_address=requester,
        service_id=service_id,
        created_at=datetime.fromisoformat(message["createdAt"]),
        expires_at=None,
        signature_scheme="EIP712",
        signature=EMPTY_SIGNATURE,
        anchor=CommitmentAnchor(chain_id=677, status=CommitmentAnchorStatus.NOT_SUBMITTED),
    )
    if _task_message(commitment) != message:
        raise ValueError("Preview differs from upstream TaskCommitment message")
    expected_types = {
        "EIP712Domain": [
            {"name": "name", "type": "string"},
            {"name": "version", "type": "string"},
            {"name": "chainId", "type": "uint256"},
        ],
        "TaskCommitment": TASK_FIELDS,
    }
    if preview["domain"] != _domain(677) or preview["types"] != expected_types:
        raise ValueError("Preview EIP-712 domain/types mismatch")
    if preview["primaryType"] != "TaskCommitment" or "verifyingContract" in preview["domain"]:
        raise ValueError("Preview EIP-712 primaryType/domain mismatch")
    typed = {key: preview[key] for key in ("domain", "types", "primaryType", "message")}
    signable = encode_typed_data(full_message=typed)
    typed_digest = "0x" + keccak(b"\x19" + signable.version + signable.header + signable.body).hex()
    if typed_digest != preview["typed_data_digest"]:
        raise ValueError("Python EIP-712 digest mismatch")
    if "signature" in preview or "taskDigest" in preview:
        raise ValueError("Unsigned preview must not contain a signature or taskDigest")
    print(json.dumps({"scope": "UNSIGNED BOT 677 DEMO PREVIEW",
                      "spec_hash": task.spec_hash, "service_id_hash": expected_service_hash,
                      "eip712_digest": typed_digest, "python_model_check": "passed"}, indent=2))


if __name__ == "__main__":
    main()
