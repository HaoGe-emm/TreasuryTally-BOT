"""Strict bridge from the frozen M1 fixture format to the M2 engine."""

from collections import Counter

from trust_receipt.models import FixtureCase, VerificationResult
from trust_receipt.verification import ReferenceEvidence, ReferencePage, ReferenceStream, verify_submission


def run_case(case: FixtureCase) -> VerificationResult:
    reference = case.reference
    source_types = [source.source for source in reference.sources]
    if len(source_types) != len(set(source_types)):
        raise ValueError("Flat fixtures cannot disambiguate multiple descriptors of the same source type")
    if any(record.source not in source_types for record in reference.transfers):
        raise ValueError("Every fixture reference record must have a source descriptor")
    evidence = ReferenceEvidence(
        streams=tuple(
            ReferenceStream(
                source=source,
                pages=(
                    ReferencePage(
                        cursor=None,
                        next_cursor=None if reference.reference_complete else "unknown-continuation",
                        transfers=tuple(record for record in reference.transfers if record.source is source.source),
                    ),
                ),
            )
            for source in reference.sources
        ),
        evidence_sufficient=reference.evidence_sufficient,
        insufficiency_reason=reference.insufficiency_reason if not reference.evidence_sufficient else None,
    )
    return verify_submission(
        case.task_spec,
        case.submission,
        evidence,
        run_id=case.fixture_id,
        started_at=case.human_review.verified_at,
        finished_at=case.human_review.verified_at,
    )


def assert_expected(case: FixtureCase, result: VerificationResult) -> None:
    expected = case.expected
    assert result.outcome == expected.outcome, case.fixture_id
    assert result.calculated_total_base_units == expected.calculated_total_base_units, case.fixture_id
    assert result.calculated_count == expected.calculated_count, case.fixture_id
    expected_findings = Counter(
        (
            item.finding_type,
            item.severity,
            item.status,
            item.violated_rule,
            tuple(sorted({(chain, tx.lower(), index) for chain, tx, index in item.event_keys})),
        )
        for item in expected.findings
    )
    actual_findings = Counter()
    for item in result.findings:
        keys = set()
        for ref in item.evidence_refs:
            parts = ref.split(":")
            if len(parts) == 4 and parts[0] in {"rpc", "blockscout", "service"}:
                keys.add((int(parts[1]), parts[2].lower(), int(parts[3])))
        actual_findings[(item.finding_type, item.severity, item.status, item.violated_rule, tuple(sorted(keys)))] += 1
    assert actual_findings == expected_findings, case.fixture_id
