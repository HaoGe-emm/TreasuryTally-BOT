"""Whitelisted verification-plan operations that AI may propose."""

from typing import Literal

from pydantic import Field, JsonValue

from trust_receipt.models.base import DomainModel, Identifier
from trust_receipt.models.enums import AggregationRuleType, CheckType, ClaimType, FilterType, QueryType


class Claim(DomainModel):
    claim_id: Identifier
    claim_type: ClaimType
    value: JsonValue


class ApprovedQuery(DomainModel):
    query_id: Identifier
    query_type: QueryType
    arguments: dict[str, JsonValue]


class ApprovedFilter(DomainModel):
    filter_id: Identifier
    filter_type: FilterType
    arguments: dict[str, JsonValue]


class ApprovedAggregationRule(DomainModel):
    aggregation_id: Identifier
    aggregation_type: AggregationRuleType
    arguments: dict[str, JsonValue]


class ApprovedCheck(DomainModel):
    check_id: Identifier
    check_type: CheckType
    arguments: dict[str, JsonValue]


class VerificationPlan(DomainModel):
    schema_version: Literal["1.0"]
    plan_id: Identifier
    task_id: Identifier
    claims: tuple[Claim, ...] = Field(min_length=1)
    queries: tuple[ApprovedQuery, ...] = Field(min_length=1)
    filters: tuple[ApprovedFilter, ...] = Field(min_length=1)
    aggregation_rules: tuple[ApprovedAggregationRule, ...] = Field(min_length=1)
    checks: tuple[ApprovedCheck, ...] = Field(min_length=1)
    plan_version: Identifier
