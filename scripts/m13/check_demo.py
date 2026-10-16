"""Preflight the M13 demo and independently verify one public receipt."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from trust_receipt.hashing import content_hash  # noqa: E402
from trust_receipt.publishing import PublicationIntegrityError, verify_public_receipt  # noqa: E402
from trust_receipt.receipts import replay_receipt  # noqa: E402
from trust_receipt.services.upload import parse_report  # noqa: E402

MAX_DOWNLOAD_BYTES = 2_000_000
READY = "READY"
FAILED = "FAILED"
INCONCLUSIVE = "INCONCLUSIVE"


class NetworkUnavailable(RuntimeError):
    """The external bytes could not be obtained, so no verdict is possible."""


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str
    evidence: dict[str, object]


def _check(name: str, status: str, detail: str, **evidence: object) -> Check:
    return Check(name=name, status=status, detail=detail, evidence=evidence)


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    loopback_http = parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "::1", "localhost"}
    if parsed.scheme != "https" and not loopback_http:
        raise ValueError("URL must use HTTPS; HTTP is allowed only for a loopback rehearsal server")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URL user information is forbidden")
    if not parsed.hostname:
        raise ValueError("URL must include a host")


def _download(url: str, *, timeout_seconds: float, max_bytes: int) -> bytes:
    _validate_url(url)
    request = urllib.request.Request(url, headers={"User-Agent": "trust-receipt-m13-check/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            declared_length = response.headers.get("Content-Length")
            if declared_length is not None and int(declared_length) > max_bytes:
                raise ValueError("response exceeds the configured byte limit")
            payload = response.read(max_bytes + 1)
    except (TimeoutError, urllib.error.HTTPError, urllib.error.URLError, OSError) as error:
        raise NetworkUnavailable(f"external request failed: {type(error).__name__}") from error
    if len(payload) > max_bytes:
        raise ValueError("response exceeds the configured byte limit")
    return payload


def _read_receipt_bytes(args: argparse.Namespace) -> bytes:
    if args.receipt_file is not None:
        payload = args.receipt_file.read_bytes()
        if len(payload) > MAX_DOWNLOAD_BYTES:
            raise ValueError("receipt file exceeds the configured byte limit")
        return payload
    return _download(
        args.receipt_uri,
        timeout_seconds=args.timeout_seconds,
        max_bytes=MAX_DOWNLOAD_BYTES,
    )


def _verify_receipt(args: argparse.Namespace) -> Check:
    try:
        payload = _read_receipt_bytes(args)
    except NetworkUnavailable as error:
        return _check(
            "public_receipt",
            INCONCLUSIVE,
            str(error),
            service_reputation_effect="none",
        )
    except (OSError, ValueError) as error:
        return _check("public_receipt", FAILED, f"receipt input rejected: {error}")

    try:
        receipt = verify_public_receipt(payload, args.expected_content_hash)
        replay = replay_receipt(receipt)
        if not replay.valid:
            return _check(
                "public_receipt",
                FAILED,
                "receipt integrity or deterministic replay failed",
                receipt_hash_valid=replay.receipt_hash_valid,
                task_hash_valid=replay.task_hash_valid,
                links_valid=replay.links_valid,
                recorded_outcome=replay.recorded_outcome.value,
                recomputed_outcome=replay.recomputed_outcome.value,
            )
        if replay.recorded_outcome.value != args.expected_outcome:
            return _check(
                "public_receipt",
                FAILED,
                "receipt outcome does not match the rehearsed final outcome",
                expected_outcome=args.expected_outcome,
                recorded_outcome=replay.recorded_outcome.value,
            )
        return _check(
            "public_receipt",
            READY,
            "content hash, authorization, object links, and deterministic outcome replay are valid",
            receipt_id=receipt.receipt_id,
            receipt_hash=receipt.receipt_hash,
            task_hash=receipt.task_spec.spec_hash,
            outcome=replay.recorded_outcome.value,
            content_hash=content_hash(payload),
        )
    except (PublicationIntegrityError, ValueError) as error:
        return _check("public_receipt", FAILED, f"receipt verification failed: {error}")


def _check_report(name: str, path: Path) -> Check:
    try:
        payload = path.read_bytes()
        report = parse_report(payload)
    except (OSError, ValueError) as error:
        return _check(name, FAILED, f"uploaded report rejected: {error}")
    return _check(
        name,
        READY,
        "strict UploadedReport contract is valid",
        content_hash=content_hash(payload),
        claimed_total_base_units=report.claimed_total_base_units,
        claimed_count=report.claimed_count,
        transfer_count=len(report.transfers),
    )


def _check_report_pair(faulty: Check, corrected: Check) -> Check:
    if faulty.status != READY or corrected.status != READY:
        return _check("report_pair", FAILED, "both reports must pass the UploadedReport contract first")
    faulty_hash = faulty.evidence["content_hash"]
    corrected_hash = corrected.evidence["content_hash"]
    if faulty_hash == corrected_hash:
        return _check("report_pair", FAILED, "faulty and corrected reports have identical bytes")
    return _check(
        "report_pair",
        READY,
        "the two valid report versions have distinct content hashes",
        faulty_content_hash=faulty_hash,
        corrected_content_hash=corrected_hash,
    )


def _check_app(url: str, *, timeout_seconds: float) -> Check:
    try:
        payload = _download(url, timeout_seconds=timeout_seconds, max_bytes=64_000)
    except NetworkUnavailable as error:
        return _check(
            "application_entry",
            INCONCLUSIVE,
            str(error),
            service_reputation_effect="none",
        )
    except ValueError as error:
        return _check("application_entry", FAILED, f"application URL rejected: {error}")
    if not payload.strip():
        return _check("application_entry", FAILED, "application entry returned an empty response")
    return _check("application_entry", READY, "application entry returned non-empty content")


def _overall(checks: list[Check]) -> str:
    if any(check.status == FAILED for check in checks):
        return FAILED
    if any(check.status == INCONCLUSIVE for check in checks):
        return INCONCLUSIVE
    return READY


def _emit(mode: str, checks: list[Check], started: float) -> int:
    overall = _overall(checks)
    result = {
        "check_version": "1.0",
        "mode": mode,
        "overall_status": overall,
        "duration_seconds": round(time.monotonic() - started, 3),
        "checks": [asdict(check) for check in checks],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return {READY: 0, FAILED: 1, INCONCLUSIVE: 2}[overall]


def _add_receipt_arguments(parser: argparse.ArgumentParser) -> None:
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--receipt-file", type=Path)
    source.add_argument("--receipt-uri")
    parser.add_argument("--expected-content-hash", required=True)
    parser.add_argument(
        "--expected-outcome",
        choices=("PASS", "FAIL", "INCONCLUSIVE"),
        default="PASS",
    )
    parser.add_argument("--timeout-seconds", type=float, default=10.0)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    receipt = subparsers.add_parser("receipt", help="verify a public receipt in this fresh process")
    _add_receipt_arguments(receipt)

    preflight = subparsers.add_parser("preflight", help="check the complete M13 rehearsal prerequisites")
    preflight.add_argument("--app-url", required=True)
    preflight.add_argument("--faulty-report", type=Path, required=True)
    preflight.add_argument("--corrected-report", type=Path, required=True)
    _add_receipt_arguments(preflight)
    return parser.parse_args()


def main() -> int:
    started = time.monotonic()
    args = _arguments()
    if not 0 < args.timeout_seconds <= 60:
        return _emit(
            args.command,
            [_check("configuration", FAILED, "timeout must be greater than zero and at most 60 seconds")],
            started,
        )
    if args.command == "receipt":
        return _emit("independent-receipt", [_verify_receipt(args)], started)

    faulty = _check_report("faulty_report", args.faulty_report)
    corrected = _check_report("corrected_report", args.corrected_report)
    checks = [
        faulty,
        corrected,
        _check_report_pair(faulty, corrected),
        _check_app(args.app_url, timeout_seconds=args.timeout_seconds),
        _verify_receipt(args),
    ]
    return _emit("m13-preflight", checks, started)


if __name__ == "__main__":
    raise SystemExit(main())
