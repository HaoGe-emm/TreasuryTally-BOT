"""Pure construction of versioned, self-hashing receipts."""

from __future__ import annotations

from datetime import datetime

from trust_receipt.hashing import receipt_hash, stable_hash, verify_submission_hash, verify_task_spec_hash
from trust_receipt.models.enums import PublicationChainStatus
from trust_receipt.models.plans import VerificationPlan
from trust_receipt.models.receipts import EvidenceDescriptor, Publication, Receipt, ServiceIdentity
from trust_receipt.models.submissions import ServiceSubmission
from trust_receipt.models.tasks import TaskSpec
from trust_receipt.models.verification import VerificationResult
from trust_receipt.verification.evidence import ReferenceEvidence


def _event_reference(chain_id: int, transaction_hash: str, log_index: int) -> str:
    return f"{chain_id}:{transaction_hash.lower()}:{log_index}"


def _evidence_manifest(evidence: ReferenceEvidence) -> tuple[EvidenceDescriptor, ...]:
    descriptors: list[EvidenceDescriptor] = []
    for stream in evidence.streams:
        event_keys = sorted(
            {
                _event_reference(record.chain_id, record.transaction_hash, record.log_index)
                for page in stream.pages
                for record in page.transfers
            }
        )
        descriptors.append(
            EvidenceDescriptor(
                evidence_id=f"reference:{stream.source.source_id}",
                source=stream.source.source,
                content_hash=stable_hash(stream),
                uri=None,
                event_keys=tuple(event_keys),
            )
        )
    return tuple(descriptors)


def build_receipt(
    *,
    receipt_id: str,
    task: TaskSpec,
    submission: ServiceSubmission,
    service_identity: ServiceIdentity,
    plan: VerificationPlan,
    result: VerificationResult,
    evidence: ReferenceEvidence,
    created_at: datetime,
) -> Receipt:
    """Bind one immutable attempt to its plan, evidence manifest, and result."""
    if not verify_task_spec_hash(task):
        raise ValueError("task spec_hash does not match canonical task content")
    if not verify_submission_hash(submission):
        raise ValueError("submission report_hash does not match canonical submission content")
    if submission.task_id != task.task_id or plan.task_id != task.task_id or result.task_id != task.task_id:
        raise ValueError("receipt components must reference the same task")
    if result.submission_id != submission.submission_id:
        raise ValueError("verification result must reference the receipt submission")
    if service_identity.service_id != submission.service_id:
        raise ValueError("service identity must match the receipt submission")
    draft = Receipt(
        receipt_version="1.0",
        receipt_id=receipt_id,
        task_spec=task,
        service_identity=service_identity,
        submission_hash=submission.report_hash,
        verification_plan=plan,
        verification_result=result,
        evidence_manifest=_evidence_manifest(evidence),
        created_at=created_at,
        receipt_hash="0x" + "0" * 64,
        publication=Publication(
            authorized=False,
            uri=None,
            content_hash=None,
            transaction_hash=None,
            chain_status=PublicationChainStatus.NOT_SUBMITTED,
        ),
    )
    return draft.model_copy(update={"receipt_hash": receipt_hash(draft)})
