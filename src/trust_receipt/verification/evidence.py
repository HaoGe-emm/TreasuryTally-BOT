"""Explicit pagination and source completeness for reference evidence."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import StrictBool, model_validator

from trust_receipt.models.base import DomainModel, NonEmptyText
from trust_receipt.models.enums import EvidenceSource
from trust_receipt.models.transfers import TransferRecord
from trust_receipt.models.verification import SourceDescriptor


class ReferencePage(DomainModel):
    cursor: NonEmptyText | None
    next_cursor: NonEmptyText | None
    transfers: tuple[TransferRecord, ...]


class ReferenceStream(DomainModel):
    """One source's complete query for the entire confirmed task scope."""

    source: SourceDescriptor
    pages: tuple[ReferencePage, ...]

    @model_validator(mode="after")
    def check_source_labels(self) -> ReferenceStream:
        if self.source.source is EvidenceSource.SERVICE:
            raise ValueError("reference source cannot be service")
        if any(record.source is not self.source.source for page in self.pages for record in page.transfers):
            raise ValueError("page transfer source must match stream source")
        return self


class ReferenceEvidence(DomainModel):
    streams: tuple[ReferenceStream, ...]
    evidence_sufficient: StrictBool
    insufficiency_reason: NonEmptyText | None

    @model_validator(mode="after")
    def require_reason_for_known_shortfall(self) -> ReferenceEvidence:
        if not self.evidence_sufficient and self.insufficiency_reason is None:
            raise ValueError("insufficient evidence requires a reason")
        if self.evidence_sufficient and self.insufficiency_reason is not None:
            raise ValueError("sufficient evidence cannot include an insufficiency reason")
        return self


@dataclass(frozen=True)
class CollectedReference:
    transfers: tuple[TransferRecord, ...]
    sources: tuple[SourceDescriptor, ...]
    complete: bool
    sufficient: bool
    reason: str | None


def collect_reference(evidence: ReferenceEvidence) -> CollectedReference:
    """Accept only explicit, contiguous pagination ending with no next cursor."""
    transfers: list[TransferRecord] = []
    reasons: list[str] = []
    complete = True
    sources = tuple(stream.source for stream in evidence.streams)
    if not evidence.streams:
        complete = False
        reasons.append("No reference evidence streams were supplied")
    for stream in evidence.streams:
        if not stream.source.complete:
            complete = False
            reasons.append(f"Reference source {stream.source.source_id} is incomplete")
        if not stream.pages:
            complete = False
            reasons.append(f"Reference source {stream.source.source_id} has no page")
            continue
        expected_cursor: str | None = None
        seen_cursors: set[str] = set()
        for page_number, page in enumerate(stream.pages):
            if page_number > 0 and expected_cursor is None:
                complete = False
                reasons.append(f"Reference source {stream.source.source_id} has a page after the terminal page")
                break
            if page.cursor != expected_cursor:
                complete = False
                reasons.append(f"Reference source {stream.source.source_id} has a pagination gap")
                break
            if page.cursor is not None:
                if page.cursor in seen_cursors:
                    complete = False
                    reasons.append(f"Reference source {stream.source.source_id} repeats a cursor")
                    break
                seen_cursors.add(page.cursor)
            transfers.extend(page.transfers)
            expected_cursor = page.next_cursor
        else:
            if expected_cursor is not None:
                complete = False
                reasons.append(f"Reference source {stream.source.source_id} has an unfinished next cursor")
    if not evidence.evidence_sufficient:
        reasons.append(evidence.insufficiency_reason or "Reference evidence is insufficient")
    return CollectedReference(
        transfers=tuple(transfers),
        sources=sources,
        complete=complete,
        sufficient=evidence.evidence_sufficient,
        reason="; ".join(reasons) or None,
    )
