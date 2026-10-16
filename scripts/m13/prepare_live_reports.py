"""Create two strict UploadedReport files from a configured real Sepolia transfer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from trust_receipt.chain.rpc import EvmRpcProbe  # noqa: E402
from trust_receipt.hashing import canonical_json_bytes, content_hash  # noqa: E402
from trust_receipt.integrations.config import M0Settings  # noqa: E402
from trust_receipt.models import EvidenceSource  # noqa: E402
from trust_receipt.services.upload import UploadedReport  # noqa: E402


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=PROJECT_ROOT / ".env")
    parser.add_argument("--output-directory", type=Path, required=True)
    return parser.parse_args()


def _report(records) -> bytes:
    service_records = tuple(record.model_copy(update={"source": EvidenceSource.SERVICE}) for record in records)
    report = UploadedReport(
        schema_version="1.0",
        claimed_total_base_units=str(sum(int(record.amount_base_units) for record in service_records)),
        claimed_count=len(service_records),
        transfers=service_records,
    )
    return canonical_json_bytes(report) + b"\n"


def main() -> int:
    args = _arguments()
    settings = M0Settings.load(args.env_file)
    missing = settings.missing_for_rpc()
    if missing:
        raise RuntimeError("missing real RPC rehearsal configuration: " + ", ".join(missing))
    output = args.output_directory.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("output directory must be empty")

    probe = EvmRpcProbe(
        settings.rpc_url_value(),
        expected_chain_id=settings.chain_id,
        timeout_seconds=settings.rpc_timeout_seconds,
    )
    known = probe.probe_transfer(
        token_address=settings.test_token_address or "",
        from_block=settings.test_from_block or 0,
        to_block=settings.test_to_block or 0,
        expected_transaction_hash=settings.test_transfer_tx_hash or "",
    ).transfer
    pages = probe.fetch_transfer_pages(
        token_address=known.token_address,
        from_block=settings.test_from_block or 0,
        to_block=settings.test_to_block or 0,
    )
    records = tuple(
        record
        for page in pages
        for record in page
        if record.from_address.lower() == known.from_address.lower()
        and record.to_address.lower() == known.to_address.lower()
    )
    if not 1 <= len(records) <= 200:
        raise RuntimeError("configured live scope must contain between 1 and 200 matching transfers")

    changed_first = records[0].model_copy(
        update={"amount_base_units": str(int(records[0].amount_base_units) + 1)}
    )
    faulty_payload = _report((changed_first, *records[1:]))
    corrected_payload = _report(records)
    faulty_path = output / "faulty-live-report.json"
    corrected_path = output / "corrected-live-report.json"
    faulty_path.write_bytes(faulty_payload)
    corrected_path.write_bytes(corrected_payload)
    task_request = (
        f"On Sepolia chain {settings.chain_id}, verify ERC-20 {known.token_address}. "
        f"The sole treasury is {known.from_address}, the sole recipient is {known.to_address}, "
        f"the inclusive block range is {settings.test_from_block} through {settings.test_to_block}, "
        "and there are no exclusion rules."
    )
    summary = {
        "mode": "real-sepolia-read-only",
        "task_request": task_request,
        "record_count": len(records),
        "faulty_report": str(faulty_path),
        "faulty_content_hash": content_hash(faulty_payload),
        "corrected_report": str(corrected_path),
        "corrected_content_hash": content_hash(corrected_payload),
        "mutation": "first transfer amount increased by one base unit",
    }
    (output / "rehearsal.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
