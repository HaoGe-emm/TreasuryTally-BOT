"""Generate labelled offline QA views; never reads .env, RPC, private reports or users."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3] / "src"))
sys.path.insert(0, str(Path(__file__).parents[3]))

from tests.reporting.conftest import report_input
from trust_receipt.m9.revisions import build_receipt_revision
from trust_receipt.models import EvidenceSource
from trust_receipt.reporting import build_business_report
from trust_receipt.verification.scope import scope_violation


def corrected(fixture):
    records = tuple(
        record.model_copy(update={"source": EvidenceSource.SERVICE})
        for record in fixture.reference.transfers
        if scope_violation(fixture.task_spec, record) is None
    )
    submission = fixture.submission.model_copy(
        update={
            "transfers": records,
            "claimed_count": len(records),
            "claimed_total_base_units": "110000",
        }
    )
    return fixture.model_copy(update={"submission": submission})


def two_hundred(fixture):
    example = fixture.reference.transfers[0]
    records = tuple(
        example.model_copy(
            update={
                "transaction_hash": "0x" + f"{index + 1:064x}",
                "log_index": index,
                "block_number": fixture.task_spec.start_block,
                "from_address": fixture.task_spec.treasury_addresses[0],
                "to_address": fixture.task_spec.recipient_addresses[0],
                "amount_base_units": "1",
                "token_decimals": 18,
            }
        )
        for index in range(200)
    )
    reference = fixture.reference.model_copy(update={"transfers": records})
    submission = fixture.submission.model_copy(
        update={
            "transfers": tuple(record.model_copy(update={"source": EvidenceSource.SERVICE}) for record in records),
            "claimed_count": 200,
            "claimed_total_base_units": "200",
        }
    )
    return fixture.model_copy(update={"reference": reference, "submission": submission})


def stress_amounts(fixture, decimals):
    records = tuple(
        record.model_copy(
            update={"amount_base_units": str(10**76 + 123) if decimals == 18 and index == 0 else "1",
                    "token_decimals": decimals}
        )
        for index, record in enumerate(fixture.reference.transfers)
    )
    eligible = tuple(record for record in records if scope_violation(fixture.task_spec, record) is None)
    submission = fixture.submission.model_copy(
        update={
            "transfers": tuple(record.model_copy(update={"source": EvidenceSource.SERVICE}) for record in eligible),
            "claimed_count": len(eligible),
            "claimed_total_base_units": str(sum(int(record.amount_base_units) for record in eligible)),
        }
    )
    return fixture.model_copy(update={"reference": fixture.reference.model_copy(update={"transfers": records}),
                                      "submission": submission})


def main():
    output = Path(sys.argv[1])
    output.mkdir(parents=True, exist_ok=True)
    first = report_input()
    after = report_input(attempt=2, transform=corrected)
    parent = build_receipt_revision(first.receipt, attempt=1)
    child = build_receipt_revision(after.receipt, attempt=2, parent=parent)
    base = {
        "fail": first,
        "pass": report_input(transform=corrected),
        "inconclusive": report_input("insufficient-evidence-page"),
        "tiny-200": report_input(transform=two_hundred),
        "large-amount": report_input(transform=lambda fixture: stress_amounts(fixture, 18)),
        "decimals-255": report_input(transform=lambda fixture: stress_amounts(fixture, 255)),
    }
    views = {
        name: build_business_report(item.receipt, item.submission, fund_flow=item.fund_flow, source_mode="fixture")
        for name, item in base.items()
    }
    views["repair"] = build_business_report(
        after.receipt,
        after.submission,
        fund_flow=after.fund_flow,
        previous=first,
        revisions=(parent, child),
        source_mode="fixture",
    )
    for name, view in views.items():
        (output / f"{name}.view.json").write_text(view.model_dump_json(indent=2), encoding="utf-8")
        print(name, view.outcome.value, len(view.current.flow_rows))


if __name__ == "__main__":
    main()
