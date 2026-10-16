"""UI cache identity only; never grants scope, attempt or publication authority."""

from __future__ import annotations

import json
from collections.abc import MutableMapping

from trust_receipt.hashing import content_hash


def report_input_identity(
    original: bytes, filename: str, provider: str,
    constants: dict[str, str], amount_unit: str | None,
) -> str:
    return content_hash(json.dumps(
        [content_hash(original), filename, provider, constants, amount_unit],
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8"))


def reset_report_input(state: MutableMapping, namespace: str) -> None:
    """Drop successful and failed recognition caches without touching task history."""
    for suffix in ("source", "result", "retained", "problem_fields"):
        state.pop(f"{namespace}:recognition:{suffix}", None)
    answers = f"{namespace}:recognition:answer:"
    for key in tuple(state):
        if isinstance(key, str) and key.startswith(answers):
            state.pop(key, None)


def track_report_input(state: MutableMapping, namespace: str, source_identity: str) -> None:
    if state.get(f"{namespace}:recognition:source") != source_identity:
        reset_report_input(state, namespace)
        state[f"{namespace}:recognition:source"] = source_identity
