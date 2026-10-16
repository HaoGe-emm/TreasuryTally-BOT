"""Frozen request/response models for the M16 headless facade."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, StrictBool

from trust_receipt.agents import TaskSpecCandidate
from trust_receipt.models import Receipt, VerificationOutcome
from trust_receipt.models.base import DecimalIntegerString, DomainModel, NonNegativeInt

INTERFACE_VERSION = "1.0"
WorkspaceHandle = Annotated[str, Field(pattern=r"^ws_[A-Za-z0-9_-]{16,64}$")]
ChallengeId = Annotated[str, Field(pattern=r"^ch_[a-f0-9]{32}$")]
Sha256Hash = Annotated[str, Field(pattern=r"^0x[a-f0-9]{64}$")]


class HeadlessProfile(StrEnum):
    LIVE_READ_ONLY = "LIVE_READ_ONLY"
    FIXTURE_TEST_ONLY = "FIXTURE_TEST_ONLY"


class AuthorizationAction(StrEnum):
    CONFIRM_TASK = "CONFIRM_TASK"
    VERIFY_REPORT = "VERIFY_REPORT"


class AuthorizationState(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    CONSUMED = "CONSUMED"
    EXPIRED = "EXPIRED"


class TaskCandidateView(DomainModel):
    interface_version: Literal["1.0"] = INTERFACE_VERSION
    workspace_handle: WorkspaceHandle
    profile: HeadlessProfile
    fixture_test_only: StrictBool
    confirmation_state: Literal["UNCONFIRMED"] = "UNCONFIRMED"
    candidate_digest: Sha256Hash
    candidate: TaskSpecCandidate


class AuthorizationChallenge(DomainModel):
    interface_version: Literal["1.0"] = INTERFACE_VERSION
    challenge_id: ChallengeId
    workspace_handle: WorkspaceHandle
    action: AuthorizationAction
    payload_digest: Sha256Hash
    task_id: str | None = None
    task_spec_hash: Sha256Hash | None = None
    attempt: Annotated[int, Field(ge=1, le=2)] | None = None
    summary: Annotated[str, Field(min_length=1, max_length=500)]
    authorization_state: AuthorizationState
    expires_at: datetime


class ConfirmedTaskView(DomainModel):
    interface_version: Literal["1.0"] = INTERFACE_VERSION
    workspace_handle: WorkspaceHandle
    profile: HeadlessProfile
    fixture_test_only: StrictBool
    task_id: str
    spec_hash: Sha256Hash
    state: Literal["CONFIRMED"] = "CONFIRMED"
    idempotent_replay: StrictBool


class AttemptFindingView(DomainModel):
    finding_id: str
    finding_type: str
    severity: str
    violated_rule: str
    evidence_refs: tuple[str, ...]


class AttemptResultView(DomainModel):
    interface_version: Literal["1.0"] = INTERFACE_VERSION
    workspace_handle: WorkspaceHandle
    profile: HeadlessProfile
    fixture_test_only: StrictBool
    task_id: str
    spec_hash: Sha256Hash
    submission_id: str
    attempt: Annotated[int, Field(ge=1, le=2)]
    outcome: VerificationOutcome
    reference_complete: StrictBool
    evidence_sufficient: StrictBool
    calculated_total_base_units: DecimalIntegerString | None
    calculated_count: NonNegativeInt | None
    inconclusive_reason: str | None
    findings: tuple[AttemptFindingView, ...]
    evidence_diagnostics: tuple[dict, ...]
    receipt_hash: Sha256Hash
    idempotent_replay: StrictBool


class ReceiptView(DomainModel):
    interface_version: Literal["1.0"] = INTERFACE_VERSION
    workspace_handle: WorkspaceHandle
    profile: HeadlessProfile
    fixture_test_only: StrictBool
    task_id: str
    attempt: Annotated[int, Field(ge=1, le=2)]
    receipt: Receipt


class ReceiptReplayView(DomainModel):
    interface_version: Literal["1.0"] = INTERFACE_VERSION
    workspace_handle: WorkspaceHandle
    profile: HeadlessProfile
    fixture_test_only: StrictBool
    task_id: str
    attempt: Annotated[int, Field(ge=1, le=2)]
    receipt_hash: Sha256Hash
    spec_hash: Sha256Hash
    recorded_outcome: VerificationOutcome
    recomputed_outcome: VerificationOutcome
    links_valid: StrictBool
    valid: StrictBool
