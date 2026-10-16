"""Read-only Sepolia preflight for the fixed M11 demonstration case."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
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
from trust_receipt.chain.rpc import EvmRpcProbe  # noqa: E402
from trust_receipt.hashing import verify_task_spec_hash  # noqa: E402
from trust_receipt.models import EvidenceSource, TaskSpec, TransferRecord  # noqa: E402
from trust_receipt.services.upload import UploadedReport, parse_report  # noqa: E402
from trust_receipt.verification.scope import scope_violation  # noqa: E402

DEFAULT_CASE_DIRECTORY = REPOSITORY_ROOT / "fixtures" / "m11"


class PreflightError(ValueError):
    """The live chain no longer matches the committed M11 evidence inventory."""


@dataclass(frozen=True)
class CaseBundle:
    directory: Path
    manifest: dict[str, Any]
    task: TaskSpec
    error_report: UploadedReport
    corrected_report: UploadedReport
    reference_transfers: tuple[TransferRecord, ...]


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PreflightError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_float(value: str) -> None:
    raise PreflightError(f"floating-point JSON numbers are forbidden: {value}")


def _load_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_float=_reject_float,
            parse_constant=_reject_float,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PreflightError(f"cannot read strict JSON fixture {path.name}: {type(error).__name__}") from error


def _resolved_child(directory: Path, relative_path: str) -> Path:
    candidate = (directory / relative_path).resolve()
    try:
        candidate.relative_to(directory.resolve())
    except ValueError as error:
        raise PreflightError(f"fixture path escapes case directory: {relative_path}") from error
    return candidate


def _event_key(record: TransferRecord) -> list[int | str]:
    return [record.chain_id, record.transaction_hash, record.log_index]


def _without_source(record: TransferRecord) -> dict[str, Any]:
    return record.model_dump(mode="json", exclude={"source"})


def load_task_spec(path: Path) -> TaskSpec:
    task = TaskSpec.model_validate(_load_json(path.resolve()))
    if not verify_task_spec_hash(task):
        raise PreflightError("task spec_hash does not match the canonical task content")
    return task


def load_case_bundle(
    case_directory: Path = DEFAULT_CASE_DIRECTORY, *, manifest_filename: str = "case.json",
) -> CaseBundle:
    directory = case_directory.resolve()
    manifest = _load_json(_resolved_child(directory, manifest_filename))
    if not isinstance(manifest, dict):
        raise PreflightError("case.json must contain one JSON object")

    task = load_task_spec(_resolved_child(directory, str(manifest.get("task_spec"))))
    validate_task_scope(task)

    reports = manifest.get("reports")
    if not isinstance(reports, dict) or set(reports) != {"error", "corrected"}:
        raise PreflightError("reports must name exactly error and corrected fixtures")
    error_report = parse_report(read_bounded_report(_resolved_child(directory, str(reports["error"]))))
    corrected_report = parse_report(read_bounded_report(_resolved_child(directory, str(reports["corrected"]))))

    inventory_path = _resolved_child(directory, str(manifest.get("reference_inventory")))
    inventory = _load_json(inventory_path)
    if not isinstance(inventory, dict) or not isinstance(inventory.get("transfers"), list):
        raise PreflightError("reference inventory must contain a transfers array")
    reference_transfers = tuple(TransferRecord.model_validate(item) for item in inventory["transfers"])
    if any(record.source is not EvidenceSource.RPC for record in reference_transfers):
        raise PreflightError("reference inventory records must use source=rpc")

    expected = manifest.get("expected")
    if not isinstance(expected, dict):
        raise PreflightError("case expected values must be a JSON object")
    eligible = tuple(record for record in reference_transfers if scope_violation(task, record) is None)
    expected_keys = expected.get("eligible_event_keys")
    if [_event_key(record) for record in eligible] != expected_keys:
        raise PreflightError("eligible event keys do not match the committed expectation")
    if len(reference_transfers) != expected.get("raw_event_count"):
        raise PreflightError("raw event count does not match the committed expectation")
    if len(eligible) != expected.get("eligible_event_count"):
        raise PreflightError("eligible event count does not match the committed expectation")
    if str(sum(int(record.amount_base_units) for record in eligible)) != expected.get(
        "calculated_total_base_units"
    ):
        raise PreflightError("eligible amount total does not match the committed expectation")
    if corrected_report.claimed_count != len(eligible) or corrected_report.claimed_total_base_units != expected.get(
        "calculated_total_base_units"
    ):
        raise PreflightError("corrected report aggregate does not match the eligible reference events")
    if [_without_source(record) for record in corrected_report.transfers] != [
        _without_source(record) for record in eligible
    ]:
        raise PreflightError("corrected report transfer set does not match eligible reference events")

    return CaseBundle(
        directory=directory,
        manifest=manifest,
        task=task,
        error_report=error_report,
        corrected_report=corrected_report,
        reference_transfers=reference_transfers,
    )


def run_preflight(
    rpc_url: str,
    *,
    case_directory: Path = DEFAULT_CASE_DIRECTORY,
    manifest_filename: str = "case.json",
    timeout_seconds: float = 30,
    probe: EvmRpcProbe | None = None,
) -> dict[str, Any]:
    """Compare the fixed case inventory with a fresh, read-only RPC query."""
    bundle = load_case_bundle(case_directory, manifest_filename=manifest_filename)
    provenance = bundle.manifest["provenance"]
    confirmations = int(provenance["minimum_confirmations"])
    validate_read_options(timeout_seconds=timeout_seconds, confirmations=confirmations)
    rpc = probe or EvmRpcProbe(
        rpc_url,
        expected_chain_id=bundle.task.chain_id,
        timeout_seconds=timeout_seconds,
    )
    latest_block = rpc.latest_block()
    confirmed_tip = latest_block - confirmations
    if bundle.task.end_block > confirmed_tip:
        raise PreflightError(
            f"case end block {bundle.task.end_block} exceeds confirmed tip {confirmed_tip}"
        )
    pages = rpc.fetch_transfer_pages(
        token_address=bundle.task.token_address,
        from_block=bundle.task.start_block,
        to_block=bundle.task.end_block,
        page_size_blocks=2_000,
    )
    observed = tuple(record for page in pages for record in page)
    if [record.model_dump(mode="json") for record in observed] != [
        record.model_dump(mode="json") for record in bundle.reference_transfers
    ]:
        raise PreflightError("live RPC inventory differs from the committed event list")
    eligible = tuple(record for record in observed if scope_violation(bundle.task, record) is None)
    expected = bundle.manifest["expected"]
    total = str(sum(int(record.amount_base_units) for record in eligible))
    if total != expected["calculated_total_base_units"]:
        raise PreflightError("live eligible amount differs from the committed amount")

    return {
        "ok": True,
        "status": "COMPLETE",
        "read_only": True,
        "case_id": bundle.manifest["case_id"],
        "chain_id": bundle.task.chain_id,
        "latest_block": latest_block,
        "confirmed_tip": confirmed_tip,
        "range": [bundle.task.start_block, bundle.task.end_block],
        "rpc_pages": len(pages),
        "raw_event_count": len(observed),
        "eligible_event_count": len(eligible),
        "calculated_total_base_units": total,
        "token_decimals": expected["token_decimals"],
        "eligible_event_keys": [_event_key(record) for record in eligible],
        "error_report": {
            "claimed_count": bundle.error_report.claimed_count,
            "claimed_total_base_units": bundle.error_report.claimed_total_base_units,
            "expected_outcome": expected["error_outcome"],
        },
        "corrected_report": {
            "claimed_count": bundle.corrected_report.claimed_count,
            "claimed_total_base_units": bundle.corrected_report.claimed_total_base_units,
            "expected_outcome": expected["corrected_outcome"],
        },
        "evidence_links": {
            "transaction": provenance["block_explorer_transaction_url"],
            "block": provenance["block_explorer_block_url"],
        },
        "disclosure": bundle.manifest["disclosure"],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rpc-url",
        default=os.environ.get("M11_RPC_URL") or os.environ.get("ETH_RPC_URL"),
        help="Sepolia JSON-RPC URL; defaults to M11_RPC_URL then ETH_RPC_URL",
    )
    parser.add_argument("--case-directory", type=Path, default=DEFAULT_CASE_DIRECTORY)
    parser.add_argument("--case-manifest", default="case.json", help="Manifest path relative to case directory")
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
        result = run_preflight(
            args.rpc_url,
            case_directory=args.case_directory,
            manifest_filename=args.case_manifest,
            timeout_seconds=args.timeout_seconds,
        )
    except Exception as error:  # CLI boundary converts all evidence failures to a non-success state.
        print(json.dumps({
            "ok": False,
            "status": "INCONCLUSIVE",
            "error_type": type(error).__name__,
            "reason": safe_error_reason(error),
        }, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
