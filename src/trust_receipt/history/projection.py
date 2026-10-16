"""Rebuild service-history facts exclusively from independently replayed receipts."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from trust_receipt.history.models import (
    HistoryCategory,
    ManualServiceSelection,
    ReceiptSourceRef,
    RevisionResolution,
    ServiceComparison,
    ServiceHistoryProjection,
    ServiceTaskFact,
)
from trust_receipt.history.ports import NoReceiptRevisions, ReceiptRevisionPort
from trust_receipt.models.enums import VerificationOutcome
from trust_receipt.models.receipts import Receipt
from trust_receipt.receipts import replay_receipt


@dataclass(frozen=True)
class ReceiptHistoryInput:
    """Stable adapter input; task type and source are explicit, never inferred."""

    receipt: Receipt
    task_type: str
    source_ref: str | None = None


def _verified_source(
    item: ReceiptHistoryInput,
    revisions: ReceiptRevisionPort,
) -> ReceiptSourceRef | None:
    receipt = item.receipt
    if not item.task_type or not replay_receipt(receipt).valid:
        return None
    publication = receipt.publication
    revision = revisions.get_revision(receipt.receipt_hash)
    if revision is not None and revision.receipt_hash != receipt.receipt_hash:
        raise ValueError("revision adapter returned a link for a different receipt")
    return ReceiptSourceRef(
        receipt_hash=receipt.receipt_hash,
        receipt_id=receipt.receipt_id,
        task_id=receipt.task_spec.task_id,
        service_id=receipt.service_identity.service_id,
        task_type=item.task_type,
        outcome=receipt.verification_result.outcome,
        delivery_at=receipt.created_at,
        verified_at=receipt.verification_result.finished_at,
        source_ref=item.source_ref or publication.uri or f"receipt:{receipt.receipt_hash}",
        public_uri=publication.uri,
        feedback_transaction_hash=publication.transaction_hash,
        revision=revision,
    )


def _fact_for_task(refs: list[ReceiptSourceRef]) -> ServiceTaskFact:
    ordered = sorted(refs, key=lambda ref: (ref.delivery_at, ref.receipt_hash))
    primary = ordered[-1]
    if primary.outcome is VerificationOutcome.PASS:
        revision_marks_fix = primary.revision is not None and primary.revision.resolution in {
            RevisionResolution.FIXED,
            RevisionResolution.RESUBMITTED,
        }
        prior_non_pass = any(ref.outcome is not VerificationOutcome.PASS for ref in ordered[:-1])
        category = HistoryCategory.FIXED_PASS if revision_marks_fix or prior_non_pass else HistoryCategory.FIRST_PASS
    else:
        category = (
            HistoryCategory.FAIL
            if primary.outcome is VerificationOutcome.FAIL
            else HistoryCategory.INCONCLUSIVE
        )
    return ServiceTaskFact(
        task_id=primary.task_id,
        service_id=primary.service_id,
        task_type=primary.task_type,
        category=category,
        latest_delivery_at=ordered[-1].delivery_at,
        primary_receipt_hash=primary.receipt_hash,
        receipt_refs=tuple(ordered),
    )


def project_service_histories(
    inputs: Iterable[ReceiptHistoryInput],
    *,
    revision_port: ReceiptRevisionPort | None = None,
) -> tuple[ServiceHistoryProjection, ...]:
    """Ignore invalid receipts and produce independently recomputable projections."""
    revisions = revision_port or NoReceiptRevisions()
    items = tuple(inputs)
    verified = {item.receipt.receipt_hash: item for item in items if replay_receipt(item.receipt).valid}
    grouped: dict[tuple[str, str, str], list[ReceiptSourceRef]] = defaultdict(list)
    names: dict[str, str] = {}
    seen_receipts: dict[str, tuple[str, str, str]] = {}
    for item in items:
        source = _verified_source(item, revisions)
        if source is None:
            continue
        link = source.revision
        if link is not None and link.parent_receipt_hash is not None:
            parent = verified.get(link.parent_receipt_hash)
            if (
                parent is None
                or link.supersedes_receipt_hash != link.parent_receipt_hash
                or parent.task_type != item.task_type
                or parent.receipt.task_spec != item.receipt.task_spec
                or parent.receipt.verification_result.outcome is VerificationOutcome.PASS
                or parent.receipt.created_at > item.receipt.created_at
            ):
                continue
        elif link is not None and link.resolution is not RevisionResolution.ORIGINAL:
            continue
        context = (source.service_id, source.task_type, source.task_id)
        previous_context = seen_receipts.get(source.receipt_hash)
        if previous_context is not None:
            if previous_context != context:
                raise ValueError("the same receipt cannot be assigned to multiple history contexts")
            continue
        seen_receipts[source.receipt_hash] = context
        receipt = item.receipt
        names[source.service_id] = receipt.service_identity.name
        grouped[context].append(source)

    facts_by_projection: dict[tuple[str, str], list[ServiceTaskFact]] = defaultdict(list)
    for (service_id, task_type, _task_id), refs in grouped.items():
        facts_by_projection[(service_id, task_type)].append(_fact_for_task(refs))

    projections: list[ServiceHistoryProjection] = []
    for (service_id, task_type), facts in sorted(facts_by_projection.items()):
        ordered_facts = sorted(facts, key=lambda fact: (fact.latest_delivery_at, fact.task_id))
        refs = tuple(
            sorted(
                (ref for fact in ordered_facts for ref in fact.receipt_refs),
                key=lambda ref: (ref.delivery_at, ref.receipt_hash),
            )
        )
        projections.append(
            ServiceHistoryProjection(
                service_id=service_id,
                service_name=names[service_id],
                task_type=task_type,
                verified_task_count=len(ordered_facts),
                first_pass_count=sum(fact.category is HistoryCategory.FIRST_PASS for fact in ordered_facts),
                fixed_pass_count=sum(fact.category is HistoryCategory.FIXED_PASS for fact in ordered_facts),
                fail_count=sum(fact.category is HistoryCategory.FAIL for fact in ordered_facts),
                inconclusive_count=sum(fact.category is HistoryCategory.INCONCLUSIVE for fact in ordered_facts),
                verifiable_receipt_count=len(refs),
                latest_delivery_at=max((ref.delivery_at for ref in refs), default=None),
                latest_verified_at=max((ref.verified_at for ref in refs), default=None),
                receipt_refs=refs,
                task_facts=tuple(ordered_facts),
            )
        )
    return tuple(projections)


def compare_services(
    histories: Iterable[ServiceHistoryProjection],
    *,
    task_type: str,
    service_ids: tuple[str, str],
    service_names: dict[str, str] | None = None,
) -> ServiceComparison:
    by_key = {(history.service_id, history.task_type): history for history in histories}
    def history_for(service_id: str) -> ServiceHistoryProjection:
        existing = by_key.get((service_id, task_type))
        if existing is not None:
            return existing
        return ServiceHistoryProjection(
            service_id=service_id, service_name=(service_names or {}).get(service_id, service_id),
            task_type=task_type, verified_task_count=0, first_pass_count=0, fixed_pass_count=0,
            fail_count=0, inconclusive_count=0, verifiable_receipt_count=0,
            latest_delivery_at=None, latest_verified_at=None, receipt_refs=(), task_facts=(),
        )
    services = (history_for(service_ids[0]), history_for(service_ids[1]))
    return ServiceComparison(task_type=task_type, services=services)


def record_manual_selection(
    comparison: ServiceComparison,
    *,
    selected_service_id: str,
    selected_at: datetime,
    rationale: str | None = None,
) -> ManualServiceSelection:
    considered = tuple(service.service_id for service in comparison.services)
    if selected_service_id not in considered:
        raise ValueError("selected service must be one of the compared services")
    return ManualServiceSelection(
        task_type=comparison.task_type,
        selected_service_id=selected_service_id,
        considered_service_ids=considered,
        selected_at=selected_at,
        rationale=rationale,
    )
