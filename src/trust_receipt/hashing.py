"""Canonical JSON and stable hashes for portable domain artifacts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from enum import Enum
from typing import Any

from pydantic import BaseModel


class CanonicalJsonError(ValueError):
    """Raised when a value cannot be represented by the project canonical form."""


def _json_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _json_value(value.model_dump(mode="json"))
    if isinstance(value, Enum):
        return _json_value(value.value)
    if isinstance(value, float):
        raise CanonicalJsonError("float values are forbidden in canonical JSON")
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise CanonicalJsonError("canonical JSON object keys must be strings")
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_value(item) for item in value]
    raise CanonicalJsonError(f"unsupported canonical JSON value: {type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize JSON data deterministically without accepting binary floats."""
    normalized = _json_value(value)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def stable_hash(value: Any) -> str:
    """Return a tagged SHA-256 digest of the canonical JSON representation."""
    return "0x" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def content_hash(payload: bytes) -> str:
    """Return the tagged SHA-256 digest of exact published bytes."""
    return "0x" + hashlib.sha256(payload).hexdigest()


def hash_model(model: BaseModel, *, exclude: frozenset[str] = frozenset()) -> str:
    return stable_hash(model.model_dump(mode="json", exclude=exclude))


def task_spec_hash(task: BaseModel) -> str:
    return hash_model(task, exclude=frozenset({"spec_hash"}))


def submission_hash(submission: BaseModel) -> str:
    return hash_model(submission, exclude=frozenset({"report_hash", "signature"}))


def receipt_hash(receipt: BaseModel) -> str:
    return hash_model(receipt, exclude=frozenset({"receipt_hash"}))


def verify_task_spec_hash(task: BaseModel) -> bool:
    return task_spec_hash(task) == getattr(task, "spec_hash", None)


def verify_submission_hash(submission: BaseModel) -> bool:
    return submission_hash(submission) == getattr(submission, "report_hash", None)


def verify_receipt_hash(receipt: BaseModel) -> bool:
    return receipt_hash(receipt) == getattr(receipt, "receipt_hash", None)
