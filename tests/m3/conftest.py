from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from eth_account import Account

from trust_receipt.hashing import task_spec_hash
from trust_receipt.models.fixtures import FixtureCase
from trust_receipt.models.tasks import TaskSpec
from trust_receipt.models.transfers import TransferRecord
from trust_receipt.verification.evidence import ReferenceEvidence, ReferencePage, ReferenceStream
from trust_receipt.verification.scope import scope_violation


@pytest.fixture
def vertical_case() -> FixtureCase:
    path = Path(__file__).parents[2] / "fixtures" / "m1" / "cases" / "missing-transfer-vertical-slice.json"
    return FixtureCase.model_validate(json.loads(path.read_text(encoding="utf-8")))


@pytest.fixture
def hashed_task(vertical_case: FixtureCase) -> TaskSpec:
    task = vertical_case.task_spec.model_copy(update={"spec_hash": "0x" + "0" * 64})
    return task.model_copy(update={"spec_hash": task_spec_hash(task)})


@pytest.fixture
def eligible_service_records(vertical_case: FixtureCase) -> tuple[TransferRecord, ...]:
    return tuple(
        record
        for record in vertical_case.reference.transfers
        if scope_violation(vertical_case.task_spec, record) is None
    )


@pytest.fixture
def reference_evidence(vertical_case: FixtureCase) -> ReferenceEvidence:
    source = vertical_case.reference.sources[0]
    stream = ReferenceStream(
        source=source,
        pages=(ReferencePage(cursor=None, next_cursor=None, transfers=vertical_case.reference.transfers),),
    )
    return ReferenceEvidence(streams=(stream,), evidence_sufficient=True, insufficiency_reason=None)


@pytest.fixture
def fixed_time() -> datetime:
    return datetime(2026, 10, 6, 12, 0, tzinfo=UTC)


@pytest.fixture
def private_key_a() -> str:
    return Account.create().key.to_0x_hex()


@pytest.fixture
def private_key_b() -> str:
    return Account.create().key.to_0x_hex()
