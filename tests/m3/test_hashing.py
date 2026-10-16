from __future__ import annotations

import pytest

from tests.contracts.samples import receipt_data, submission_data, task_data
from trust_receipt.hashing import (
    CanonicalJsonError,
    canonical_json_bytes,
    receipt_hash,
    stable_hash,
    submission_hash,
    task_spec_hash,
    verify_receipt_hash,
    verify_submission_hash,
    verify_task_spec_hash,
)
from trust_receipt.models.receipts import Receipt
from trust_receipt.models.submissions import ServiceSubmission
from trust_receipt.models.tasks import TaskSpec


def test_canonical_json_has_stable_key_order_and_rejects_float() -> None:
    assert canonical_json_bytes({"b": 2, "a": [True, "中"]}) == b'{"a":[true,"\xe4\xb8\xad"],"b":2}'
    assert stable_hash({"a": 1, "b": 2}) == stable_hash({"b": 2, "a": 1})
    with pytest.raises(CanonicalJsonError, match="float"):
        canonical_json_bytes({"amount": 0.1})


def test_task_submission_and_receipt_hashes_are_verifiable() -> None:
    raw_task = TaskSpec.model_validate(task_data())
    task = raw_task.model_copy(update={"spec_hash": task_spec_hash(raw_task)})
    assert verify_task_spec_hash(task)

    raw_submission = ServiceSubmission.model_validate(submission_data())
    submission = raw_submission.model_copy(update={"report_hash": submission_hash(raw_submission)})
    assert verify_submission_hash(submission)

    raw_receipt = receipt_data()
    raw_receipt["task_spec"] = task.model_dump(mode="json")
    raw_receipt["receipt_hash"] = "0x" + "0" * 64
    draft = Receipt.model_validate(raw_receipt)
    receipt = draft.model_copy(update={"receipt_hash": receipt_hash(draft)})
    assert verify_receipt_hash(receipt)

    assert not verify_task_spec_hash(task.model_copy(update={"end_block": task.end_block + 1}))
    assert not verify_submission_hash(submission.model_copy(update={"claimed_count": 99}))
