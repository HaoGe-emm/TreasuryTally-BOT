"""Local M11 CLI input limits and safe diagnostic messages."""

from __future__ import annotations

import math
from pathlib import Path

from trust_receipt.models import TaskSpec
from trust_receipt.services.upload import MAX_REPORT_BYTES


def validate_read_options(*, timeout_seconds: float, confirmations: int = 2) -> None:
    if not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 30:
        raise ValueError("timeout_seconds must be finite and in (0, 30]")
    if isinstance(confirmations, bool) or not isinstance(confirmations, int) or not 0 <= confirmations <= 128:
        raise ValueError("confirmations must be an integer in [0, 128]")


def validate_task_scope(task: TaskSpec) -> None:
    if task.chain_id != 11_155_111:
        raise ValueError("M11 supports Sepolia chain_id=11155111")


def read_bounded_report(path: Path) -> bytes:
    with path.open("rb") as stream:
        payload = stream.read(MAX_REPORT_BYTES + 1)
    if not payload or len(payload) > MAX_REPORT_BYTES:
        raise ValueError("report must be nonempty and at most 1 MB")
    return payload


def safe_error_reason(error: Exception) -> str:
    """Do not echo validation input, RPC URLs, authentication, or exception bodies."""
    if isinstance(error, OSError):
        return "Unable to read an input file or reach the configured RPC."
    if isinstance(error, ValueError):
        return "Input validation or reference inventory verification failed; check scope, hash, and strict JSON."
    return "Read-only verification failed; independent evidence is unavailable."
