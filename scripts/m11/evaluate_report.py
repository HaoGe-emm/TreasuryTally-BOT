"""Evaluate any strict UploadedReport against a confirmed TaskSpec and live read-only RPC evidence."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT))
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from scripts.m11.input_policy import (  # noqa: E402
    read_bounded_report,
    safe_error_reason,
    validate_read_options,
    validate_task_scope,
)
from scripts.m11.preflight import load_task_spec  # noqa: E402
from trust_receipt.chain import RpcReferenceEvidenceProvider  # noqa: E402
from trust_receipt.hashing import submission_hash  # noqa: E402
from trust_receipt.models import ServiceSubmission  # noqa: E402
from trust_receipt.services.upload import parse_report  # noqa: E402
from trust_receipt.verification import verify_submission  # noqa: E402


def evaluate_report(
    *,
    rpc_url: str,
    task_spec_path: Path,
    report_path: Path,
    confirmations: int = 2,
    timeout_seconds: float = 30,
    evidence_provider: Any | None = None,
) -> dict[str, Any]:
    """Run the existing deterministic engine without assuming an expected outcome."""
    validate_read_options(timeout_seconds=timeout_seconds, confirmations=confirmations)
    task = load_task_spec(task_spec_path)
    validate_task_scope(task)
    payload = read_bounded_report(report_path.resolve())
    report = parse_report(payload)
    created_at = datetime.now(UTC)
    unsigned = ServiceSubmission(
        schema_version="1.0",
        submission_id=f"m11-cli:{task.task_id}:{created_at.isoformat()}",
        task_id=task.task_id,
        service_id="uploaded-report-intake",
        service_version="m11-cli-1.0",
        attempt=1,
        claimed_total_base_units=report.claimed_total_base_units,
        claimed_count=report.claimed_count,
        transfers=report.transfers,
        report_text=payload.decode("utf-8"),
        created_at=created_at,
        report_hash="0x" + "0" * 64,
        signature=None,
    )
    submission = unsigned.model_copy(update={"report_hash": submission_hash(unsigned)})
    provider = evidence_provider or RpcReferenceEvidenceProvider(
        rpc_url,
        expected_chain_id=task.chain_id,
        timeout_seconds=timeout_seconds,
        confirmations=confirmations,
    )
    evidence = provider.fetch(task)
    started_at = datetime.now(UTC)
    result = verify_submission(
        task,
        submission,
        evidence,
        run_id=f"m11-cli-run:{task.task_id}:{created_at.isoformat()}",
        started_at=started_at,
        finished_at=datetime.now(UTC),
    )
    return {
        "task_id": task.task_id,
        "spec_hash": task.spec_hash,
        "report_path": str(report_path.resolve()),
        "read_only": True,
        "outcome": result.outcome.value,
        "reference_complete": result.reference_complete,
        "evidence_sufficient": result.evidence_sufficient,
        "calculated_total_base_units": result.calculated_total_base_units,
        "calculated_count": result.calculated_count,
        "inconclusive_reason": result.inconclusive_reason,
        "findings": [
            {
                "finding_id": finding.finding_id,
                "finding_type": finding.finding_type.value,
                "violated_rule": finding.violated_rule,
                "evidence_refs": list(finding.evidence_refs),
            }
            for finding in result.findings
        ],
        "evidence_diagnostics": [
            {
                **diagnostic.model_dump(mode="json"),
                "detail": (
                    "Independent reference read failed; check RPC availability and task scope."
                    if diagnostic.status in {"INCOMPLETE", "DEGRADED"}
                    else diagnostic.detail
                ),
            }
            for diagnostic in getattr(provider, "diagnostics", ())
        ],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rpc-url",
        default=os.environ.get("M11_RPC_URL") or os.environ.get("ETH_RPC_URL"),
        help="Sepolia JSON-RPC URL; defaults to M11_RPC_URL then ETH_RPC_URL",
    )
    parser.add_argument("--task-spec", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--confirmations", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=float, default=30)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.rpc_url:
        print(json.dumps({
            "ok": False,
            "status": "BLOCKED",
            "reason": "missing --rpc-url, M11_RPC_URL, or ETH_RPC_URL",
        }, indent=2))
        return 2
    try:
        result = evaluate_report(
            rpc_url=args.rpc_url,
            task_spec_path=args.task_spec,
            report_path=args.report,
            confirmations=args.confirmations,
            timeout_seconds=args.timeout_seconds,
        )
    except Exception as error:
        print(json.dumps({
            "ok": False,
            "status": "INCONCLUSIVE",
            "error_type": type(error).__name__,
            "reason": safe_error_reason(error),
        }, indent=2))
        return 1
    conclusive = result["outcome"] != "INCONCLUSIVE"
    print(json.dumps({"ok": conclusive, **result}, indent=2))
    return 0 if conclusive else 1


if __name__ == "__main__":
    raise SystemExit(main())
