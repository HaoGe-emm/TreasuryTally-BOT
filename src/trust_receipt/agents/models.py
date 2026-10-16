"""Provider-independent, strictly validated artifacts produced by the AI layer."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, JsonValue, model_validator

from trust_receipt.models.base import (
    DecimalIntegerString,
    DomainModel,
    EvmAddress,
    Identifier,
    NonEmptyText,
    NonNegativeInt,
    PositiveInt,
)
from trust_receipt.models.enums import ClaimType, VerificationOutcome
from trust_receipt.models.plans import Claim
from trust_receipt.models.tasks import ExclusionRule

TreasuryAddresses = Annotated[tuple[EvmAddress, ...], Field(min_length=1, max_length=2)]
RecipientAddresses = Annotated[tuple[EvmAddress, ...], Field(min_length=1)]


class TaskField(StrEnum):
    CHAIN_ID = "chain_id"
    TOKEN_ADDRESS = "token_address"
    TREASURY_ADDRESSES = "treasury_addresses"
    RECIPIENT_ADDRESSES = "recipient_addresses"
    START_BLOCK = "start_block"
    END_BLOCK = "end_block"
    EXCLUSION_RULES = "exclusion_rules"


class ClarificationTarget(StrEnum):
    CHAIN_ID = "chain_id"
    TOKEN_ADDRESS = "token_address"
    TREASURY_ADDRESSES = "treasury_addresses"
    RECIPIENT_ADDRESSES = "recipient_addresses"
    START_BLOCK = "start_block"
    END_BLOCK = "end_block"
    EXCLUSION_RULES = "exclusion_rules"
    CLAIMED_TOTAL = "claimed_total"
    CLAIMED_COUNT = "claimed_count"
    TRANSFER_SET = "transfer_set"


class ClarificationIssue(DomainModel):
    target: ClarificationTarget
    description: NonEmptyText
    options: tuple[NonEmptyText, ...] = Field(default=(), max_length=10)


class TaskSpecCandidate(DomainModel):
    """Unconfirmed task fields; identity, confirmation time, and hash are never model-owned."""

    schema_version: Literal["1.0"]
    candidate_id: Identifier
    chain_id: PositiveInt | None
    token_address: EvmAddress | None
    treasury_addresses: TreasuryAddresses | None
    recipient_addresses: RecipientAddresses | None
    start_block: NonNegativeInt | None
    end_block: NonNegativeInt | None
    exclusion_rules: tuple[ExclusionRule, ...] | None
    max_records: Literal[200]
    ambiguities: tuple[ClarificationIssue, ...]
    missing_fields: tuple[TaskField, ...]
    clarification_questions: tuple[NonEmptyText, ...]

    @model_validator(mode="after")
    def validate_candidate(self) -> TaskSpecCandidate:
        required = {
            TaskField.CHAIN_ID: self.chain_id,
            TaskField.TOKEN_ADDRESS: self.token_address,
            TaskField.TREASURY_ADDRESSES: self.treasury_addresses,
            TaskField.RECIPIENT_ADDRESSES: self.recipient_addresses,
            TaskField.START_BLOCK: self.start_block,
            TaskField.END_BLOCK: self.end_block,
            TaskField.EXCLUSION_RULES: self.exclusion_rules,
        }
        expected_missing = {field for field, value in required.items() if value is None}
        if set(self.missing_fields) != expected_missing or len(self.missing_fields) != len(expected_missing):
            raise ValueError("missing_fields must exactly identify every missing required task field")
        if self.treasury_addresses is not None:
            self._validate_addresses("treasury_addresses", self.treasury_addresses, maximum=2)
        if self.recipient_addresses is not None:
            self._validate_addresses("recipient_addresses", self.recipient_addresses)
        if self.start_block is not None and self.end_block is not None and self.start_block > self.end_block:
            raise ValueError("start_block must be less than or equal to end_block")
        if self.exclusion_rules is not None:
            rule_ids = [rule.rule_id for rule in self.exclusion_rules]
            if len(rule_ids) != len(set(rule_ids)):
                raise ValueError("exclusion rule IDs must be unique")
        unresolved = bool(expected_missing or self.ambiguities)
        if unresolved and not self.clarification_questions:
            raise ValueError("missing or ambiguous task fields require clarification_questions")
        if not unresolved and self.clarification_questions:
            raise ValueError("resolved task candidates cannot contain clarification_questions")
        return self

    @staticmethod
    def _validate_addresses(name: str, addresses: tuple[str, ...], maximum: int | None = None) -> None:
        if not addresses:
            raise ValueError(f"{name} must contain at least one address")
        if maximum is not None and len(addresses) > maximum:
            raise ValueError(f"{name} cannot contain more than {maximum} addresses")
        comparison_keys = [address.lower() for address in addresses]
        if len(comparison_keys) != len(set(comparison_keys)):
            raise ValueError(f"{name} must be unique ignoring case")

    @property
    def ready_for_confirmation(self) -> bool:
        return not self.missing_fields and not self.ambiguities


class ClaimExtraction(DomainModel):
    schema_version: Literal["1.0"]
    report_id: Identifier
    claims: tuple[Claim, ...]
    ambiguities: tuple[ClarificationIssue, ...]
    clarification_questions: tuple[NonEmptyText, ...]
    source_summary: NonEmptyText

    @model_validator(mode="after")
    def validate_claims(self) -> ClaimExtraction:
        claim_ids = [claim.claim_id for claim in self.claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("claim IDs must be unique")
        claim_types = [claim.claim_type for claim in self.claims]
        if len(claim_types) != len(set(claim_types)):
            raise ValueError("claim types must be unique; conflicting claims require clarification")
        if self.ambiguities and not self.clarification_questions:
            raise ValueError("ambiguous claims require clarification_questions")
        if not self.ambiguities and self.clarification_questions:
            raise ValueError("unambiguous claims cannot contain clarification_questions")
        if not self.claims and not self.ambiguities:
            raise ValueError("claim extraction requires at least one claim or ambiguity")
        for claim in self.claims:
            if claim.claim_type is ClaimType.CLAIMED_TOTAL:
                require_decimal_integer_string(claim.value, label="CLAIMED_TOTAL value")
            elif claim.claim_type is ClaimType.CLAIMED_COUNT:
                require_non_negative_int(claim.value, label="CLAIMED_COUNT value")
            elif claim.claim_type is ClaimType.TRANSFER_SET and not isinstance(claim.value, list):
                raise ValueError("TRANSFER_SET value must be a JSON array")
        return self


class FollowUpAction(StrEnum):
    NO_ACTION = "NO_ACTION"
    REFRESH_REFERENCE_EVIDENCE = "REFRESH_REFERENCE_EVIDENCE"
    CROSS_CHECK_REFERENCE_SOURCE = "CROSS_CHECK_REFERENCE_SOURCE"
    CONFIRM_TASK_SCOPE = "CONFIRM_TASK_SCOPE"
    REQUEST_RESUBMISSION = "REQUEST_RESUBMISSION"
    SWITCH_SERVICE = "SWITCH_SERVICE"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class FollowUpSuggestion(DomainModel):
    action: FollowUpAction
    rationale: NonEmptyText
    evidence_refs: tuple[Identifier, ...]


class FollowUpAdvice(DomainModel):
    schema_version: Literal["1.0"]
    outcome: VerificationOutcome
    suggestions: tuple[FollowUpSuggestion, ...] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def validate_actions_for_outcome(self) -> FollowUpAdvice:
        allowed = {
            VerificationOutcome.PASS: {FollowUpAction.NO_ACTION},
            VerificationOutcome.FAIL: {
                FollowUpAction.REQUEST_RESUBMISSION,
                FollowUpAction.SWITCH_SERVICE,
                FollowUpAction.MANUAL_REVIEW,
            },
            VerificationOutcome.INCONCLUSIVE: {
                FollowUpAction.REFRESH_REFERENCE_EVIDENCE,
                FollowUpAction.CROSS_CHECK_REFERENCE_SOURCE,
                FollowUpAction.CONFIRM_TASK_SCOPE,
                FollowUpAction.MANUAL_REVIEW,
            },
        }[self.outcome]
        if any(item.action not in allowed for item in self.suggestions):
            raise ValueError(f"follow-up action is not allowed for outcome={self.outcome.value}")
        return self


class FindingExplanation(DomainModel):
    finding_id: Identifier
    explanation: NonEmptyText
    evidence_refs: tuple[Identifier, ...] = Field(min_length=1)


class ResultExplanation(DomainModel):
    schema_version: Literal["1.0"]
    outcome: VerificationOutcome
    calculated_total_base_units: DecimalIntegerString | None
    calculated_count: NonNegativeInt | None
    summary: NonEmptyText
    finding_explanations: tuple[FindingExplanation, ...]


def require_non_negative_int(value: JsonValue, *, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def require_decimal_integer_string(value: JsonValue, *, label: str) -> str:
    return _validate_decimal_string(value, label=label)


def _validate_decimal_string(value: JsonValue, *, label: str) -> str:
    if not isinstance(value, str) or (value != "0" and (not value.isdigit() or value.startswith("0"))):
        raise ValueError(f"{label} must be a canonical unsigned decimal integer string")
    return value
