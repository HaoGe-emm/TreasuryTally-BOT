"""Presentation helpers for strict report intake and business-facing results."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from trust_receipt.models import FindingType

STRICT_REPORT_TEMPLATE = {
    "schema_version": "1.0",
    "claimed_total_base_units": "0",
    "claimed_count": 0,
    "transfers": [],
}

FINDING_LABELS = {
    FindingType.MISSING_TRANSFER: ("报表漏记链上转账", "把这笔链上转账补入修正版报表。"),
    FindingType.EXTRA_TRANSFER: ("报表记录与链上证据不一致", "核对交易标识和区块，并删除或修正该记录。"),
    FindingType.DUPLICATE_TRANSFER: ("报表重复记账", "按链、交易哈希和日志序号去重。"),
    FindingType.EXCLUDED_INTERNAL_TRANSFER: ("内部互转被计入拨款", "按已确认规则从拨款金额中排除内部互转。"),
    FindingType.OUT_OF_RANGE: ("记录超出确认区块范围", "仅保留已确认起止区块内的记录。"),
    FindingType.WRONG_TOKEN: ("代币地址不在确认范围", "核对代币合约地址后修正记录。"),
    FindingType.WRONG_DIRECTION: ("资金方向与确认范围不符", "核对付款账户与收款对象。"),
    FindingType.AMOUNT_MISMATCH: ("报表金额与链上金额不符", "使用链上事件的整数最小单位修正金额。"),
    FindingType.DECIMAL_ERROR: ("代币精度或金额缩放错误", "按已确认 decimals 重新换算整数最小单位。"),
    FindingType.INSUFFICIENT_EVIDENCE: ("证据不足", "补齐独立证据后再核验，不据此判断服务对错。"),
}


@dataclass(frozen=True)
class AmountSummary:
    claimed: str
    verified: str
    difference: str
    direction: str
    decimals: int | None


def strict_template_bytes() -> bytes:
    return json.dumps(STRICT_REPORT_TEMPLATE, ensure_ascii=False, indent=2).encode("utf-8")


def contract_example_bytes(project_root: Path) -> bytes:
    """Build an UploadedReport from the existing synthetic contract fixture."""
    fixture_path = project_root / "fixtures" / "m1" / "cases" / "missing-transfer-vertical-slice.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    submission = fixture["submission"]
    report = {
        "schema_version": submission["schema_version"],
        "claimed_total_base_units": submission["claimed_total_base_units"],
        "claimed_count": submission["claimed_count"],
        "transfers": submission["transfers"],
    }
    return json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8")


def amount_summary(
    claimed: str, verified: str | None, *, decimals: int | None, units_comparable: bool = True,
) -> AmountSummary:
    if verified is None:
        return AmountSummary(claimed, "无法确定", "无法确定", "独立证据不足，暂时不能计算差额。", decimals)
    if not units_comparable:
        return AmountSummary(claimed, verified, "无法确定", "报表含不同代币或精度错误，请先核对金额单位。", decimals)
    delta = int(claimed) - int(verified)
    if delta > 0:
        direction = f"报表比链上有效金额多计 {delta} 个最小单位。"
    elif delta < 0:
        direction = f"报表比链上有效金额少计 {abs(delta)} 个最小单位。"
    else:
        direction = "报表金额与链上有效金额一致。"
    return AmountSummary(claimed, verified, str(delta), direction, decimals)


def format_token_amount(base_units: str, decimals: int | None) -> str:
    if decimals is None:
        return f"{base_units} 最小单位"
    value = int(base_units)
    if decimals == 0:
        return f"{value} 代币单位 ({base_units} 最小单位)"
    scale = 10**decimals
    whole, fraction = divmod(value, scale)
    fractional = f"{fraction:0{decimals}d}".rstrip("0")
    display = str(whole) if not fractional else f"{whole}.{fractional}"
    return f"{display} 代币单位 ({base_units} 最小单位, decimals={decimals})"


def finding_copy(finding_type: FindingType) -> tuple[str, str]:
    return FINDING_LABELS[finding_type]


def reference_decimals(evidence, token_address: str) -> int | None:
    """Use independent records only, never an uploaded report's decimal claim."""
    if evidence is None:
        return None
    scales = {
        record.token_decimals
        for stream in evidence.streams
        for page in stream.pages
        for record in page.transfers
        if record.token_address.lower() == token_address.lower()
    }
    return next(iter(scales)) if len(scales) == 1 else None
