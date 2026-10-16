"""Append-only private commitment and evidence snapshots, without storing keys."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from trust_receipt.commitments import verify_delivery_commitment, verify_task_commitment
from trust_receipt.hashing import canonical_json_bytes, stable_hash
from trust_receipt.models import CommitmentAnchorStatus, DeliveryCommitment, TaskCommitment
from trust_receipt.models.base import DomainModel, EvmAddress
from trust_receipt.verification import ReferenceEvidence, verify_submission


class CommitmentSnapshot(DomainModel):
    task_commitment: TaskCommitment
    delivery_commitment: DeliveryCommitment
    expected_signer: EvmAddress


class M8ArtifactStore:
    def __init__(self, database: Path) -> None:
        self._database = database
        database.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS m8_artifacts (
                submission_id TEXT NOT NULL,
                kind TEXT NOT NULL CHECK (kind IN ('commitment', 'evidence')),
                body TEXT NOT NULL,
                body_hash TEXT NOT NULL,
                PRIMARY KEY (submission_id, kind)
            )""")

    def _connect(self):
        return sqlite3.connect(self._database)

    def _append(self, submission_id: str, kind: str, value: DomainModel) -> None:
        body = canonical_json_bytes(value).decode("utf-8")
        with closing(self._connect()) as connection, connection:
            existing = connection.execute(
                "SELECT body FROM m8_artifacts WHERE submission_id=? AND kind=?", (submission_id, kind),
            ).fetchone()
            if existing is not None:
                if existing[0] != body:
                    raise ValueError("M8 snapshots are immutable and cannot be replaced")
                return
            connection.execute(
                "INSERT INTO m8_artifacts VALUES (?, ?, ?, ?)",
                (submission_id, kind, body, stable_hash(value)),
            )

    def _read(self, submission_id: str, kind: str, model):
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT body, body_hash FROM m8_artifacts WHERE submission_id=? AND kind=?", (submission_id, kind),
            ).fetchone()
        if row is None:
            return None
        value = model.model_validate_json(row[0])
        if stable_hash(value) != row[1]:
            raise ValueError("M8 private snapshot content hash mismatch")
        return value

    def save_commitments(self, snapshot: CommitmentSnapshot) -> None:
        self._append(snapshot.delivery_commitment.submission_id, "commitment", snapshot)

    def save_evidence(self, submission_id: str, evidence: ReferenceEvidence) -> None:
        self._append(submission_id, "evidence", evidence)

    def restore(self, task, execution) -> tuple[CommitmentSnapshot | None, ReferenceEvidence | None]:
        submission = execution.submission
        snapshot = self._read(submission.submission_id, "commitment", CommitmentSnapshot)
        evidence = self._read(submission.submission_id, "evidence", ReferenceEvidence)
        if snapshot is not None and (
            snapshot.task_commitment.anchor.status is not CommitmentAnchorStatus.NOT_SUBMITTED
            or
            snapshot.expected_signer.lower() != execution.receipt.service_identity.identity_reference.lower()
            or not verify_task_commitment(snapshot.task_commitment, task)
            or not verify_delivery_commitment(
                snapshot.delivery_commitment, snapshot.task_commitment, submission,
                expected_signer=snapshot.expected_signer,
            )
        ):
            raise ValueError("M8 restored commitment signature or identity link is invalid")
        if evidence is not None:
            manifest = execution.receipt.evidence_manifest
            if len(evidence.streams) != len(manifest) or any(
                stable_hash(stream) != descriptor.content_hash
                or stream.source.source != descriptor.source
                for stream, descriptor in zip(evidence.streams, manifest, strict=True)
            ):
                raise ValueError("M8 restored evidence does not match the receipt manifest")
            result = execution.result
            replayed = verify_submission(
                task, submission, evidence, run_id=result.run_id,
                started_at=result.started_at, finished_at=result.finished_at,
                verifier_version=result.verifier_version,
            )
            if replayed != result:
                raise ValueError("M8 restored evidence cannot reproduce the stored verification result")
        return snapshot, evidence
