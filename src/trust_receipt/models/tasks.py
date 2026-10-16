"""Confirmed task definition and its supported exclusion policy."""

from typing import Literal

from pydantic import Field, model_validator

from trust_receipt.models.base import (
    DomainModel,
    EvmAddress,
    Hex32,
    Identifier,
    NonEmptyText,
    NonNegativeInt,
    PositiveInt,
    UtcDatetime,
)
from trust_receipt.models.enums import ExclusionRuleType


class ExclusionRule(DomainModel):
    rule_id: Identifier
    rule_type: ExclusionRuleType
    reason: NonEmptyText


class TaskSpec(DomainModel):
    schema_version: Literal["1.0"]
    task_id: Identifier
    chain_id: PositiveInt
    token_address: EvmAddress
    treasury_addresses: tuple[EvmAddress, ...] = Field(min_length=1, max_length=2)
    recipient_addresses: tuple[EvmAddress, ...] = Field(min_length=1)
    start_block: NonNegativeInt
    end_block: NonNegativeInt
    exclusion_rules: tuple[ExclusionRule, ...]
    max_records: Literal[200]
    confirmed_at: UtcDatetime
    spec_hash: Hex32

    @model_validator(mode="after")
    def validate_scope(self) -> "TaskSpec":
        if self.start_block > self.end_block:
            raise ValueError("start_block must be less than or equal to end_block")
        for field_name, addresses in (
            ("treasury_addresses", self.treasury_addresses),
            ("recipient_addresses", self.recipient_addresses),
        ):
            comparison_keys = [address.lower() for address in addresses]
            if len(comparison_keys) != len(set(comparison_keys)):
                raise ValueError(f"{field_name} must be unique ignoring case")
        rule_ids = [rule.rule_id for rule in self.exclusion_rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("exclusion rule IDs must be unique")
        return self
