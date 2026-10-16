from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from trust_receipt.models import EvidenceSource, SourceDescriptor
from trust_receipt.verification import ReferenceEvidence, ReferencePage, ReferenceStream
from trust_receipt.verification.evidence import collect_reference


def source(*, complete: bool = True) -> SourceDescriptor:
    return SourceDescriptor(
        source=EvidenceSource.RPC,
        source_id="rpc-test",
        retrieved_at=datetime(2026, 10, 6, tzinfo=UTC),
        complete=complete,
        details={},
    )


def test_contiguous_pages_with_terminal_cursor_are_complete() -> None:
    pages = (
        ReferencePage(cursor=None, next_cursor="page-2", transfers=()),
        ReferencePage(cursor="page-2", next_cursor=None, transfers=()),
    )
    evidence = ReferenceEvidence(
        streams=(ReferenceStream(source=source(), pages=pages),),
        evidence_sufficient=True,
        insufficiency_reason=None,
    )

    collected = collect_reference(evidence)
    assert collected.complete
    assert collected.sufficient
    assert collected.reason is None


@pytest.mark.parametrize(
    "pages",
    [
        (),
        (ReferencePage(cursor=None, next_cursor="page-2", transfers=()),),
        (
            ReferencePage(cursor=None, next_cursor="page-2", transfers=()),
            ReferencePage(cursor="page-3", next_cursor=None, transfers=()),
        ),
        (
            ReferencePage(cursor=None, next_cursor="page-2", transfers=()),
            ReferencePage(cursor="page-2", next_cursor="page-2", transfers=()),
            ReferencePage(cursor="page-2", next_cursor=None, transfers=()),
        ),
        (
            ReferencePage(cursor=None, next_cursor=None, transfers=()),
            ReferencePage(cursor=None, next_cursor=None, transfers=()),
        ),
    ],
)
def test_missing_or_repeated_pages_cannot_be_marked_complete(pages: tuple[ReferencePage, ...]) -> None:
    evidence = ReferenceEvidence(
        streams=(ReferenceStream(source=source(), pages=pages),),
        evidence_sufficient=True,
        insufficiency_reason=None,
    )
    assert not collect_reference(evidence).complete


def test_known_evidence_shortfall_requires_a_reason() -> None:
    with pytest.raises(ValidationError, match="requires a reason"):
        ReferenceEvidence(streams=(), evidence_sufficient=False, insufficiency_reason=None)
