"""Apply a confirmed task's transfer inclusion rules to both sides."""

from __future__ import annotations

from trust_receipt.models.enums import ExclusionRuleType, FindingType
from trust_receipt.models.tasks import TaskSpec
from trust_receipt.models.transfers import TransferRecord
from trust_receipt.verification.normalization import address_key


def scope_violation(task: TaskSpec, record: TransferRecord) -> FindingType | None:
    if record.chain_id != task.chain_id:
        return FindingType.EXTRA_TRANSFER
    if address_key(record.token_address) != address_key(task.token_address):
        return FindingType.WRONG_TOKEN
    if not task.start_block <= record.block_number <= task.end_block:
        return FindingType.OUT_OF_RANGE
    treasury = {address_key(address) for address in task.treasury_addresses}
    source = address_key(record.from_address)
    destination = address_key(record.to_address)
    internal_excluded = any(
        rule.rule_type is ExclusionRuleType.EXCLUDE_TREASURY_INTERNAL for rule in task.exclusion_rules
    )
    if internal_excluded and source in treasury and destination in treasury:
        return FindingType.EXCLUDED_INTERNAL_TRANSFER
    recipients = {address_key(address) for address in task.recipient_addresses}
    if source not in treasury or destination not in recipients:
        return FindingType.WRONG_DIRECTION
    return None
