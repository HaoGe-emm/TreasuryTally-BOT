"""Unified automatic intake: model roles, deterministic original values, private provenance."""

# ruff: noqa: RUF001

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from trust_receipt.hashing import content_hash
from trust_receipt.services.conversion_storage import _retain
from trust_receipt.services.header_recognition import (
    HeaderRecognition,
    HeaderRecognizer,
    bind_roles,
    build_header_recognizer,
)
from trust_receipt.services.report_conversion import (
    ALIASES,
    CONSTANT_FIELDS,
    ConversionInputError,
    ReportConversionCandidate,
    _header_key,
    convert_report_table,
    read_report_table,
)
from trust_receipt.services.upload import MAX_REPORT_BYTES, UploadedReport, parse_report

__all__ = ["HeaderRecognizer", "RecognizedReport", "build_header_recognizer",
           "persist_recognized_report", "recognize_report"]


class RecognizedReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    original_hash: str
    original_filename: str
    input_format: Literal["json", "csv", "xlsx", "unsupported"]
    recognition_mode: Literal["strict-json", "live-model", "offline-test", "unconfigured"]
    model_id: str | None = None
    report: UploadedReport | None = None
    json_payload: bytes | None = None
    conversion: ReportConversionCandidate | None = None
    recognition: HeaderRecognition | None = None
    issues: tuple[str, ...] = ()
    missing_fields: tuple[str, ...] = ()
    clarifications: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    amount_unit: Literal["base", "token"] | None = None

    @property
    def ready(self) -> bool:
        return self.report is not None and self.json_payload is not None and not (
            self.issues or self.missing_fields or self.clarifications
        )


def recognize_report(
    payload: bytes, filename: str, recognizer: HeaderRecognizer | None, *,
    constants: dict[str, str] | None = None, amount_unit: Literal["base", "token"] | None = None,
    previous: RecognizedReport | None = None,
) -> RecognizedReport:
    """A validated recognition can be reused only with the same file/provider.

    It is re-bound to actual safe column indices each time; no row values are model owned.
    The UI must invalidate its recognition cache on file/provider changes.
    """
    kind = Path(filename).suffix.lower().lstrip(".")
    kind = kind if kind in {"json", "csv", "xlsx"} else "unsupported"
    base = {
        "original_hash": content_hash(payload), "original_filename": filename, "input_format": kind,
        "recognition_mode": "strict-json" if kind == "json" else recognizer.mode if recognizer else "unconfigured",
        "model_id": recognizer.model_id if recognizer and kind != "json" else None, "amount_unit": amount_unit,
    }
    if amount_unit not in (None, "base", "token"):
        base["amount_unit"] = None
        return RecognizedReport(**base, issues=("金额单位只允许 base 或 token。",))
    if constants and any(key not in CONSTANT_FIELDS or not isinstance(value, str) for key, value in constants.items()):
        return RecognizedReport(**base, issues=("整表补充仅允许文本链编号、代币地址和精度。",))
    if not payload or len(payload) > MAX_REPORT_BYTES or not filename or len(filename) > 255 or "\x00" in filename:
        return RecognizedReport(**base, issues=("文件必须非空、文件名有效且大小不超过 1 MB。",))
    if kind == "json":
        try:
            report = parse_report(payload)
            return RecognizedReport(**base, report=report, json_payload=payload)
        except ValueError:
            return RecognizedReport(**base, issues=("JSON 不符合严格报表契约，请检查字段、金额、来源和记录上限。",))
    try:
        table = read_report_table(payload, filename)
    except (ValueError, OSError) as error:
        return RecognizedReport(**base, issues=(str(error),))
    if recognizer is None:
        return RecognizedReport(**base, issues=("请配置并选择真实模型以识别表格；不会回退离线样例。",))
    try:
        if previous is None or previous.recognition is None:
            recognition, _ = recognizer.recognize(table)
        else:
            # Validate a cached output with the same safe index boundary, without a new call.
            from trust_receipt.services.header_recognition import model_headers

            if (
                previous.original_hash != base["original_hash"] or previous.original_filename != filename
                or previous.model_id != recognizer.model_id or previous.recognition_mode != recognizer.mode
            ):
                raise ConversionInputError("缓存识别不属于当前文件或模型，请重新识别。")
            recognition = HeaderRecognition.model_validate_json(previous.recognition.model_dump_json(), strict=True)
            indices = [item.column_index for item in recognition.columns]
            if len(indices) != len(set(indices)) or set(indices) != {i for i, _ in model_headers(table)}:
                raise ConversionInputError("缓存识别与当前文件列不一致。")
        mapping, ambiguous = bind_roles(table, recognition)
    except ConversionInputError as error:
        return RecognizedReport(**base, issues=(str(error),))
    except Exception as error:
        timeout = isinstance(error, TimeoutError) or type(error).__name__ in {
            "APITimeoutError", "ReadTimeout", "ConnectTimeout",
        }
        message = "模型识别超时，请显式重试。" if timeout else "模型识别失败或输出无效，请检查模型配置后显式重试。"
        return RecognizedReport(**base, issues=(message,))
    base["recognition"] = recognition
    if ambiguous:
        return RecognizedReport(
            **base, clarifications=("原表存在字段歧义，请修正相关列名后重新上传：" + ", ".join(ambiguous),),
        )
    if "claimed_total_base_units" in mapping:
        total_label = _header_key(mapping["claimed_total_base_units"])
        if (
            total_label not in {_header_key(alias) for alias in ALIASES["claimed_total_base_units"]}
            and not any(unit in total_label for unit in ("baseunits", "最小单位", "wei"))
        ):
            return RecognizedReport(**base, clarifications=("原声明总额单位不明确，请在原表注明最小单位。",))
    field = "amount_base_units" if "amount_base_units" in mapping else "amount" if "amount" in mapping else None
    if field:
        label = mapping[field]
        explicit = {_header_key(alias) for alias in ALIASES[field]}
        if _header_key(label) not in explicit:
            if amount_unit is None:
                return RecognizedReport(**base, clarifications=("amount_unit",))
            if amount_unit not in {"base", "token"}:
                return RecognizedReport(**base, issues=("金额单位只允许 base 或 token。",))
            mapping.pop(field)
            mapping["amount_base_units" if amount_unit == "base" else "amount"] = label
        elif amount_unit is not None:
            expected = "base" if field == "amount_base_units" else "token"
            if amount_unit != expected:
                return RecognizedReport(**base, issues=("补充金额单位与原表明确单位冲突。",))
    converted = convert_report_table(table, mapping, constants)
    warnings = ["报表读取不代表链上通过；原声明与重复事件保持不变，作者身份仍未验证。"]
    if converted.derived_fields:
        warnings.append("未提供的摘要由明细计算，不是服务商原声明；请在范围确认时核对来源。")
    if "amount" in mapping:
        warnings.append("代币单位金额按明确精度精确缩放，没有四舍五入。")
    if "block_hash" not in mapping:
        warnings.append("原表无区块哈希，保留 null；没有从链上补写交付。")
    if recognizer.mode == "offline-test":
        warnings.append("离线 mock 识别测试，不是真实模型或链上证据。")
    return RecognizedReport(
        **base, conversion=converted, report=converted.report,
        json_payload=converted.json_payload if converted.ready else None,
        issues=converted.issues, missing_fields=converted.missing_fields,
        warnings=tuple(warnings),
    )


def persist_recognized_report(original: bytes, result: RecognizedReport, directory: Path) -> bytes:
    """Automatic private intake only; no user-adoption fiction, signer, task or attempt."""
    if not result.ready or content_hash(original) != result.original_hash:
        raise ConversionInputError("识别尚未完成或原文件已变化，不能继续。")
    if parse_report(result.json_payload) != result.report:
        raise ConversionInputError("内部结构化报表不一致。")
    _retain(original, directory / "recognition-originals", result.input_format)
    normalized_hash = _retain(result.json_payload, directory / "recognition-json", "json")
    manifest = result.model_dump(mode="json", exclude={"report", "json_payload", "conversion"})
    manifest.update({
        "normalized_hash": normalized_hash, "original_author_verified": False,
        "field_mapping": result.conversion.field_mapping if result.conversion else {},
        "user_constants": result.conversion.constants if result.conversion else {},
        "derived_fields": result.conversion.derived_fields if result.conversion else (),
    })
    _retain(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode(),
        directory / "recognition-provenance", "json",
    )
    return result.json_payload
