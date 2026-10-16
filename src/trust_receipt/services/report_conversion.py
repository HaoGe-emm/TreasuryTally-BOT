"""Deterministic conversion candidates, never reference evidence or verdicts."""

# Chinese user-facing punctuation is intentional.
# ruff: noqa: RUF001

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from trust_receipt.models import TransferRecord
from trust_receipt.services.report_table import (
    ConversionInputError,
    ReportTable,
    read_report_table,
)
from trust_receipt.services.upload import UploadedReport, parse_report

__all__ = [
    "CONSTANT_FIELDS", "CONVERSION_FIELDS", "ConversionInputError", "ReportConversionCandidate",
    "ReportTable", "convert_report_table", "read_report_table", "suggest_field_mapping",
]

ALIASES = {
    "chain_id": ("chain_id", "chainid", "链ID", "链编号"),
    "token_address": ("token_address", "tokenaddress", "代币地址", "代币合约", "代币合约地址"),
    "transaction_hash": ("transaction_hash", "transactionhash", "tx_hash", "txhash", "交易哈希"),
    "log_index": ("log_index", "logindex", "日志序号", "日志索引"),
    "block_number": ("block_number", "blocknumber", "block", "区块", "区块号", "区块高度"),
    "block_hash": ("block_hash", "blockhash", "区块哈希"),
    "from_address": ("from_address", "fromaddress", "from", "付款地址", "付款账户", "发送地址"),
    "to_address": ("to_address", "toaddress", "to", "收款地址", "收款账户", "接收地址"),
    "amount_base_units": ("amount_base_units", "amountbaseunits", "金额最小单位", "最小单位金额"),
    "amount": ("amount_token_units", "token_amount", "代币单位金额", "金额代币单位"),
    "token_decimals": ("token_decimals", "tokendecimals", "decimals", "代币精度", "精度"),
    "claimed_total_base_units": ("claimed_total_base_units", "声明总额最小单位"),
    "claimed_count": ("claimed_count", "声明笔数", "声明数量"),
    "source": ("source", "来源"),
}
CONVERSION_FIELDS = tuple(ALIASES)
CONSTANT_FIELDS = ("chain_id", "token_address", "token_decimals")
REQUIRED_FIELDS = (
    "chain_id", "token_address", "transaction_hash", "log_index", "block_number",
    "from_address", "to_address", "token_decimals",
)


class ReportConversionCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    conversion_version: Literal["1.0"] = "1.0"
    input_format: Literal["csv", "xlsx"]
    encoding: str
    original_hash: str
    original_filename: str
    field_mapping: dict[str, str]
    constants: dict[str, str]
    report: UploadedReport | None = None
    missing_fields: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    derived_fields: tuple[str, ...] = ()

    @property
    def ready(self) -> bool:
        return self.report is not None and not self.missing_fields and not self.issues

    @property
    def derived_summary(self) -> bool:
        return bool(self.derived_fields)

    @property
    def json_payload(self) -> bytes:
        if not self.ready or self.report is None:
            raise ConversionInputError("转换候选尚不完整，不能作为正式交付。")
        return self.report.model_dump_json(indent=2).encode("utf-8")


def _header_key(value: str) -> str:
    return re.sub(r"[\s_\-()（）]", "", value).casefold()


def suggest_field_mapping(table: ReportTable) -> dict[str, str]:
    keys = [_header_key(header) for header in table.headers]
    if len(set(keys)) != len(keys):
        raise ConversionInputError("表头归一化后冲突，请先修改列名；不会静默选取某一列。")
    result = {}
    for field, aliases in ALIASES.items():
        allowed = {_header_key(alias) for alias in aliases}
        matches = [header for header in table.headers if _header_key(header) in allowed]
        if len(matches) > 1:
            raise ConversionInputError(f"字段 {field} 匹配多个列，请明确列名或人工映射。")
        if matches:
            result[field] = matches[0]
    return result


def _integer(value: str) -> int:
    if not re.fullmatch(r"(?:0|[1-9][0-9]{0,255})", value):
        raise ConversionInputError("需要无符号十进制整数，不接受浮点或科学计数法。")
    return int(value)


def _amount(value: str, decimals: int) -> str:
    if not 0 <= decimals <= 255:
        raise ConversionInputError("代币精度需在 0–255。")
    if not re.fullmatch(r"(?:0|[1-9][0-9]{0,255})(?:\.[0-9]{1,255})?", value):
        raise ConversionInputError("金额需为十进制文本，不接受千位分隔、负数或科学计数法。")
    whole, _, fraction = value.partition(".")
    if any(character != "0" for character in fraction[decimals:]):
        raise ConversionInputError("金额小数位超出代币精度，不能四舍五入。")
    return str(int(whole) * 10**decimals + int((fraction[:decimals].ljust(decimals, "0")) or "0"))


def convert_report_table(
    table: ReportTable, mapping: dict[str, str] | None = None, constants: dict[str, str] | None = None,
) -> ReportConversionCandidate:
    constants = dict(constants or {})
    issues, warnings, derived = [], [], []
    try:
        if mapping is None:
            selected = suggest_field_mapping(table)
        else:
            keys = [_header_key(header) for header in table.headers]
            if len(set(keys)) != len(keys):
                raise ConversionInputError("表头归一化后冲突，请先修改列名。")
            selected = dict(mapping)
    except ConversionInputError as error:
        selected = dict(mapping or {})
        issues.append(str(error))
    if any(key not in CONVERSION_FIELDS or value not in table.headers for key, value in selected.items()):
        issues.append("映射包含未知字段或不存在的列。")
    if len(set(selected.values())) != len(selected.values()):
        issues.append("同一列不能同时映射到多个字段。")
    if any(key not in CONSTANT_FIELDS or not isinstance(value, str) for key, value in constants.items()):
        issues.append("全表补充只允许文本 chain_id、token_address、token_decimals。")
    if set(selected) & set(constants):
        issues.append("同一字段同时存在表格列与全表常量，请只保留一个来源。")
    if "amount" in selected and "amount_base_units" in selected:
        issues.append("同时存在两种金额列，请明确选择单位，不能静默选取。")
    available = set(selected) | set(constants)
    missing = tuple(field for field in REQUIRED_FIELDS if field not in available)
    if not {"amount", "amount_base_units"} & set(selected):
        missing = (*missing, "amount_base_units_or_amount")
    base = {
        "input_format": table.input_format, "encoding": table.encoding, "original_hash": table.original_hash,
        "original_filename": table.original_filename,
        "field_mapping": selected, "constants": constants, "missing_fields": missing,
    }
    if issues or missing:
        return ReportConversionCandidate(**base, issues=tuple(issues))

    indexes = {field: table.headers.index(header) for field, header in selected.items()}

    def value(row, field):
        return row[indexes[field]] if field in indexes else constants.get(field, "")

    def text_amount(row_index, field, raw):
        if (row_index, indexes[field]) in table.numeric_excel_cells:
            raise ConversionInputError("Excel 金额必须使用文本单元格，避免已发生的浮点精度损失。")
        return raw

    records = []
    for row_index, row in enumerate(table.rows):
        try:
            record = {field: value(row, field) for field in REQUIRED_FIELDS}
            for field in ("chain_id", "log_index", "block_number", "token_decimals"):
                record[field] = _integer(record[field])
            if "amount_base_units" in indexes:
                raw_amount = text_amount(row_index, "amount_base_units", value(row, "amount_base_units"))
                amount = str(_integer(raw_amount))
            else:
                raw_amount = text_amount(row_index, "amount", value(row, "amount"))
                amount = _amount(raw_amount, record["token_decimals"])
            record.update({
                "amount_base_units": amount,
                "block_hash": value(row, "block_hash") or None,
                "source": value(row, "source") if "source" in indexes else "service",
            })
            records.append(TransferRecord.model_validate(record))
        except (ConversionInputError, ValidationError) as error:
            detail = (
                str(error) if isinstance(error, ConversionInputError)
                else "必需字段为空、类型不合法或地址/哈希格式无效。"
            )
            issues.append(f"第 {row_index + 1} 行：{detail}")
    if issues:
        return ReportConversionCandidate(**base, issues=tuple(issues))
    units = {(item.chain_id, item.token_address.lower(), item.token_decimals) for item in records}
    if len(units) != 1:
        return ReportConversionCandidate(**base, issues=("仅支持单链、单代币、同一精度的报表，不能混合汇总。",))

    def declared(field, computed):
        if field not in indexes:
            derived.append(field)
            return computed
        values = {value(row, field) for row in table.rows if value(row, field)}
        if len(values) != 1:
            raise ConversionInputError(f"{field} 声明为空或冲突；不会用明细计算值覆盖。")
        for row_index, row in enumerate(table.rows):
            if field == "claimed_total_base_units" and value(row, field):
                text_amount(row_index, field, value(row, field))
        return _integer(next(iter(values)))

    try:
        total = declared("claimed_total_base_units", sum(int(item.amount_base_units) for item in records))
        count = declared("claimed_count", len(records))
        report = UploadedReport(
            schema_version="1.0", claimed_total_base_units=str(total), claimed_count=count, transfers=tuple(records),
        )
        # Exercise the same byte-level boundary used by normal upload intake.
        parse_report(report.model_dump_json().encode("utf-8"))
    except (ConversionInputError, ValidationError, ValueError) as error:
        detail = str(error) if isinstance(error, ConversionInputError) else "规范 JSON 未通过原上传契约校验。"
        return ReportConversionCandidate(**base, issues=(detail,))
    if derived:
        warnings.append("未提供的声明摘要由上传明细计算，不代表服务商原声明；请核对并明确采用。")
    if "amount" in indexes:
        warnings.append("代币单位金额已按显式精度转换为最小单位整数，没有四舍五入。")
    if "block_hash" not in indexes:
        warnings.append("原表没有区块哈希，保留为 null；未从链上补写原交付。")
    warnings.append("转换只整理格式，不代表链上核验通过；重复行和原声明差异保持不变。")
    return ReportConversionCandidate(
        **base, report=report, warnings=tuple(warnings), derived_fields=tuple(derived),
    )
