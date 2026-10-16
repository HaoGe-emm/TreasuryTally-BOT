from __future__ import annotations

from datetime import UTC, datetime

import pytest

from trust_receipt.history import (
    HistoryCategory,
    ReceiptHistoryInput,
    ReceiptRevisionLink,
    RevisionResolution,
    compare_services,
    project_service_histories,
    record_manual_selection,
)


class RevisionMap:
    def __init__(self, links=()):
        self._links = {link.receipt_hash: link for link in links}

    def get_revision(self, receipt_hash: str):
        return self._links.get(receipt_hash)


def test_projection_recomputes_task_counts_and_ignores_unverified_receipts(make_receipt) -> None:
    first_pass = make_receipt(
        receipt_id="a-first", task_id="task-1", service_id="a", outcome="PASS", created_at="2026-10-01T00:00:00Z"
    )
    failed = make_receipt(
        receipt_id="a-fail", task_id="task-2", service_id="a", outcome="FAIL", created_at="2026-10-02T00:00:00Z"
    )
    fixed = make_receipt(
        receipt_id="a-fixed", task_id="task-2", service_id="a", outcome="PASS", created_at="2026-10-03T00:00:00Z"
    )
    inconclusive = make_receipt(
        receipt_id="a-unknown",
        task_id="task-3",
        service_id="a",
        outcome="INCONCLUSIVE",
        created_at="2026-10-04T00:00:00Z",
    )
    tampered = first_pass.model_copy(update={"receipt_id": "tampered"})

    histories = project_service_histories(
        ReceiptHistoryInput(receipt=receipt, task_type="grant-report")
        for receipt in (first_pass, failed, fixed, inconclusive, tampered)
    )

    assert len(histories) == 1
    history = histories[0]
    assert history.verified_task_count == 3
    assert history.first_pass_count == 1
    assert history.fixed_pass_count == 1
    assert history.fail_count == 0
    assert history.inconclusive_count == 1
    assert history.verifiable_receipt_count == 4
    assert {ref.receipt_hash for ref in history.sources_for(HistoryCategory.FIXED_PASS)} == {
        failed.receipt_hash,
        fixed.receipt_hash,
    }
    assert "tampered" not in {ref.receipt_id for ref in history.receipt_refs}


def test_duplicate_verified_input_does_not_inflate_receipt_count(make_receipt) -> None:
    receipt = make_receipt(
        receipt_id="a-first",
        task_id="task-1",
        service_id="a",
        outcome="PASS",
        created_at="2026-10-01T00:00:00Z",
    )
    item = ReceiptHistoryInput(receipt=receipt, task_type="grant-report")

    history = project_service_histories((item, item))[0]

    assert history.verified_task_count == 1
    assert history.verifiable_receipt_count == 1


def test_task_types_are_isolated_and_inconclusive_is_not_negative(make_receipt) -> None:
    unknown = make_receipt(
        receipt_id="unknown",
        task_id="task-1",
        service_id="a",
        outcome="INCONCLUSIVE",
        created_at="2026-10-01T00:00:00Z",
    )
    failed = make_receipt(
        receipt_id="failed", task_id="task-2", service_id="a", outcome="FAIL", created_at="2026-10-02T00:00:00Z"
    )
    histories = project_service_histories(
        (
            ReceiptHistoryInput(receipt=unknown, task_type="grant-report"),
            ReceiptHistoryInput(receipt=failed, task_type="treasury-report"),
        )
    )

    assert [(item.task_type, item.fail_count, item.inconclusive_count) for item in histories] == [
        ("grant-report", 0, 1),
        ("treasury-report", 1, 0),
    ]


def test_m9_revision_port_can_mark_a_verified_pass_as_fixed(make_receipt) -> None:
    parent = make_receipt(
        receipt_id="parent", task_id="task-1", service_id="a", outcome="FAIL", created_at="2026-10-02T00:00:00Z"
    )
    fixed = make_receipt(
        receipt_id="fixed", task_id="task-1", service_id="a", outcome="PASS", created_at="2026-10-03T00:00:00Z"
    )
    link = ReceiptRevisionLink(
        receipt_hash=fixed.receipt_hash,
        parent_receipt_hash=parent.receipt_hash,
        supersedes_receipt_hash=parent.receipt_hash,
        resolution=RevisionResolution.FIXED,
    )
    history = project_service_histories(
        (
            ReceiptHistoryInput(receipt=parent, task_type="grant-report"),
            ReceiptHistoryInput(receipt=fixed, task_type="grant-report"),
        ),
        revision_port=RevisionMap((link,)),
    )[0]

    assert history.fixed_pass_count == 1
    assert history.first_pass_count == 0
    assert history.receipt_refs[-1].revision == link


def test_two_service_comparison_requires_explicit_manual_choice(make_receipt) -> None:
    a = make_receipt(
        receipt_id="a", task_id="task-a", service_id="a", outcome="PASS", created_at="2026-10-01T00:00:00Z"
    )
    b = make_receipt(
        receipt_id="b", task_id="task-b", service_id="b", outcome="FAIL", created_at="2026-10-02T00:00:00Z"
    )
    histories = project_service_histories(
        ReceiptHistoryInput(receipt=receipt, task_type="grant-report") for receipt in (a, b)
    )
    comparison = compare_services(histories, task_type="grant-report", service_ids=("a", "b"))
    selection = record_manual_selection(
        comparison,
        selected_service_id="b",
        selected_at=datetime(2026, 10, 7, tzinfo=UTC),
        rationale="Manual fit assessment outside the receipt statistics.",
    )

    assert selection.selected_service_id == "b"
    assert selection.considered_service_ids == ("a", "b")
    with pytest.raises(ValueError, match="one of the compared services"):
        record_manual_selection(
            comparison,
            selected_service_id="c",
            selected_at=datetime(2026, 10, 7, tzinfo=UTC),
        )
