from __future__ import annotations

import pytest

from trust_receipt.services import FaultMode, TeamControlledReportService
from trust_receipt.storage.sqlite import RepositoryStateError, SQLiteRepository


def test_attempt_is_append_only_and_cannot_be_overwritten(
    tmp_path, hashed_task, eligible_service_records, fixed_time, private_key_a
) -> None:
    repository = SQLiteRepository(tmp_path / "attempts.db")
    repository.add_task(hashed_task)
    assert repository.request_attempt(hashed_task.task_id) == 1
    service = TeamControlledReportService(
        service_id="service-a",
        private_key=private_key_a,
        records_provider=lambda task: eligible_service_records,
        fault_by_attempt={1: FaultMode.OMIT_LAST_TRANSFER},
        clock=lambda: fixed_time,
    )
    delivery = service.submit(hashed_task, attempt=1)
    repository.save_delivery(delivery)

    with pytest.raises(RepositoryStateError):
        repository.save_delivery(delivery)
    stored = repository.get_attempt(hashed_task.task_id, 1)
    assert stored.submission == delivery.submission
    assert stored.verification_result is None
