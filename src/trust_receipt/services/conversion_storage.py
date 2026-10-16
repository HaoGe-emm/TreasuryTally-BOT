"""Private provenance retention after an explicit UI confirmation."""

# Chinese user-facing punctuation is intentional.
# ruff: noqa: RUF001

import json
from pathlib import Path

from trust_receipt.hashing import content_hash
from trust_receipt.services.report_conversion import ReportConversionCandidate
from trust_receipt.services.report_table import ConversionInputError


def _retain(payload: bytes, directory: Path, suffix: str) -> str:
    digest = content_hash(payload)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{digest[2:]}.{suffix}"
    try:
        with path.open("xb") as stream:
            stream.write(payload)
    except FileExistsError:
        if path.read_bytes() != payload:
            raise ConversionInputError("转换留档已损坏或内容哈希冲突。") from None
    return digest


def persist_confirmed_conversion(
    original: bytes, candidate: ReportConversionCandidate, directory: Path, *, confirmed: bool,
) -> bytes:
    """The boolean is a caller guard, not an authorization token.

    Only the UI after a deliberate user confirmation may call this method.
    It has no signing, workflow, model, network, public upload or write-chain capability.
    """
    if confirmed is not True or not candidate.ready:
        raise ConversionInputError("请先核对完整预览并确认采用；不会自动留为正式交付。")
    if content_hash(original) != candidate.original_hash:
        raise ConversionInputError("原文件已变化，需重新转换和确认。")
    normalized = candidate.json_payload
    _retain(original, directory / "conversion-originals", candidate.input_format)
    normalized_hash = _retain(normalized, directory / "conversion-json", "json")
    manifest = candidate.model_dump(exclude={"report"})
    manifest["normalized_hash"] = normalized_hash
    manifest["original_author_verified"] = False
    _retain(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"),
        directory / "conversion-provenance", "json",
    )
    return normalized
