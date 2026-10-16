"""Bounded, non-executing readers for original report tables."""

# Chinese user-facing punctuation is intentional.
# ruff: noqa: RUF001

from __future__ import annotations

import csv
import io
import posixpath
import re
import zipfile
from dataclasses import dataclass, replace
from pathlib import PurePath
from xml.etree import ElementTree as ET

from trust_receipt.hashing import content_hash
from trust_receipt.services.upload import MAX_REPORT_BYTES

MAX_ROWS = 200
MAX_COLUMNS = 64
MAX_CELL_CHARS = 4096
MAX_XML_BYTES = 1_000_000
MAX_EXPANDED_BYTES = 4_000_000
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


class ConversionInputError(ValueError):
    """Unsupported or unsafe input, before any candidate is constructed."""


@dataclass(frozen=True)
class ReportTable:
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    input_format: str
    encoding: str
    original_hash: str
    numeric_excel_cells: frozenset[tuple[int, int]] = frozenset()
    original_filename: str = ""


def _table(headers, rows, payload, kind, encoding, numeric=frozenset()) -> ReportTable:
    headers = tuple(str(value).strip() for value in headers)
    if not headers or len(headers) > MAX_COLUMNS or any(not value for value in headers):
        raise ConversionInputError("表头不能为空，最多允许 64 列。")
    if len(set(headers)) != len(headers):
        raise ConversionInputError("表头存在重复列名，请先改为不同名称。")
    rows = tuple(tuple(row) for row in rows)
    if not rows or len(rows) > MAX_ROWS:
        raise ConversionInputError("表格需包含 1–200 行明细；不会截断或抽样。")
    if any(len(row) != len(headers) for row in rows):
        raise ConversionInputError("明细行与表头列数不一致，请检查分隔符或缺失单元格。")
    if any(len(value) > MAX_CELL_CHARS for row in (headers, *rows) for value in row):
        raise ConversionInputError("单元格过长（上限 4096 字符）。")
    return ReportTable(headers, rows, kind, encoding, content_hash(payload), numeric)


def _csv(payload: bytes) -> ReportTable:
    try:
        text = payload.decode("utf-8-sig")
        encoding = "utf-8-sig"
    except UnicodeDecodeError:
        try:
            text = payload.decode("gb18030")
            encoding = "gb18030"
        except UnicodeDecodeError as error:
            raise ConversionInputError("CSV 编码需为 UTF-8 或 GB18030。") from error
    if "\x00" in text:
        raise ConversionInputError("不支持含 NUL 的 CSV（请另存为 UTF-8）。")
    try:
        try:
            dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.reader(io.StringIO(text, newline=""), dialect=dialect, strict=True)
        headers = next(reader, ())
        rows = []
        for row in reader:
            if not row or all(not value.strip() for value in row):
                continue
            rows.append(tuple(value.strip() for value in row))
            if len(rows) > MAX_ROWS:
                raise ConversionInputError("超过 200 行明细；不会截断或抽样。")
    except csv.Error as error:
        raise ConversionInputError("CSV 格式无效，请检查引号与分隔符。") from error
    return _table(headers, rows, payload, "csv", encoding)


def _xml(archive: zipfile.ZipFile, name: str):
    # Bound decompression too: ZIP directory sizes are untrusted metadata.
    with archive.open(name) as stream:
        data = stream.read(MAX_XML_BYTES + 1)
    if len(data) > MAX_XML_BYTES or b"\x00" in data or re.search(br"<!\s*(?:DOCTYPE|ENTITY)\b", data, re.I):
        raise ConversionInputError("Excel XML 过大或包含不允许的实体声明。")
    try:
        return ET.fromstring(data)
    except ET.ParseError as error:
        raise ConversionInputError("Excel XML 无效。") from error


def _column(reference: str) -> int:
    match = re.fullmatch(r"([A-Z]{1,2})([1-9][0-9]*)", reference)
    if not match:
        raise ConversionInputError("Excel 单元格坐标无效。")
    value = 0
    for letter in match[1]:
        value = value * 26 + ord(letter) - ord("A") + 1
    if value > MAX_COLUMNS:
        raise ConversionInputError("Excel 最多支持 64 列。")
    return value - 1


def _string(container) -> str:
    if container is None:
        raise ConversionInputError("Excel 文本单元格缺少内容。")
    parts = []
    for child in container:
        if child.tag == f"{{{NS['s']}}}t":
            parts.append(child.text or "")
        elif child.tag == f"{{{NS['s']}}}r":
            parts.extend(item.text or "" for item in child.findall("s:t", NS))
        elif child.tag == f"{{{NS['s']}}}rPh":
            raise ConversionInputError("不支持带注音文字的 Excel 单元格，请导出 CSV。")
    return "".join(parts)


def _xlsx(payload: bytes) -> ReportTable:
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            entries = archive.infolist()
            names = archive.namelist()
            if len(names) != len(set(names)) or len(entries) > 128:
                raise ConversionInputError("Excel 包存在重复成员或成员过多。")
            if any(item.flag_bits & 1 for item in entries):
                raise ConversionInputError("不支持加密 Excel 文件。")
            if any(item.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED} for item in entries):
                raise ConversionInputError("Excel 只支持标准 stored/deflate ZIP 压缩。")
            if sum(item.file_size for item in entries) > MAX_EXPANDED_BYTES:
                raise ConversionInputError("Excel 解压后超过 4 MB。")
            if any(item.file_size > MAX_XML_BYTES for item in entries):
                raise ConversionInputError("Excel 单个成员超过 1 MB。")
            if any("vba" in name.lower() or name.lower().endswith(".bin") for name in names):
                raise ConversionInputError("不支持宏或二进制 Excel 内容。")
            for name in names:
                if name.endswith(".rels"):
                    for relation in _xml(archive, name):
                        if relation.tag != f"{{{REL_NS}}}Relationship":
                            raise ConversionInputError("Excel 关系命名空间无效。")
                        if relation.get("TargetMode", "").lower() == "external":
                            raise ConversionInputError("不支持 Excel 外部链接。")
            workbook = _xml(archive, "xl/workbook.xml")
            sheets = workbook.findall("s:sheets/s:sheet", NS)
            worksheets = [name for name in names if name.startswith("xl/worksheets/") and name.endswith(".xml")]
            if len(sheets) != 1 or len(worksheets) != 1 or sheets[0].get("state", "visible") != "visible":
                raise ConversionInputError("请使用仅含一个可见工作表的 XLSX，不会忽略其他工作表。")
            relations = _xml(archive, "xl/_rels/workbook.xml.rels")
            sheet_id = sheets[0].get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            targets = [item.get("Target", "") for item in relations if item.get("Id") == sheet_id]
            if len(targets) != 1:
                raise ConversionInputError("Excel 工作表关系无效。")
            target = targets[0]
            target = posixpath.normpath(target.lstrip("/") if target.startswith("/") else "xl/" + target)
            if target != worksheets[0]:
                raise ConversionInputError("Excel 工作表关系与文件不一致。")
            shared = []
            if "xl/sharedStrings.xml" in names:
                strings = _xml(archive, "xl/sharedStrings.xml")
                if strings.tag != f"{{{NS['s']}}}sst" or any(item.tag != f"{{{NS['s']}}}si" for item in strings):
                    raise ConversionInputError("Excel 共享字符串结构无效。")
                shared = [_string(item) for item in strings]
            formats = ["0"]
            if "xl/styles.xml" in names:
                formats = [
                    item.get("numFmtId", "0")
                    for item in _xml(archive, "xl/styles.xml").findall("s:cellXfs/s:xf", NS)
                ]
            data = _xml(archive, target)
            sheet_data = data.findall("s:sheetData", NS)
            if data.tag != f"{{{NS['s']}}}worksheet" or len(sheet_data) != 1:
                raise ConversionInputError("Excel 工作表结构或命名空间无效。")
            if any(item.tag != f"{{{NS['s']}}}row" for item in sheet_data[0]):
                raise ConversionInputError("Excel 明细行命名空间或结构无效；不会跳过未知行。")
            if data.find("s:mergeCells", NS) is not None:
                raise ConversionInputError("请取消 Excel 合并单元格，保证每行明细独立完整。")
            rows, numeric = [], set()
            previous_row = 0
            for row in data.findall("s:sheetData/s:row", NS):
                row_number = row.get("r", "")
                if not row_number.isdigit() or int(row_number) <= previous_row:
                    raise ConversionInputError("Excel 行坐标重复或乱序。")
                previous_row = int(row_number)
                if any(item.tag != f"{{{NS['s']}}}c" for item in row):
                    raise ConversionInputError("Excel 单元格命名空间或结构无效；不会忽略未知单元格。")
                cells, numeric_columns = {}, set()
                for cell in row.findall("s:c", NS):
                    if any(child.tag.rsplit("}", 1)[-1] == "f" for child in cell):
                        raise ConversionInputError("Excel 含公式；请导出原始值并核对后另存为文本单元格。")
                    column = _column(cell.get("r", ""))
                    if int(re.search(r"[0-9]+$", cell.get("r", ""))[0]) != previous_row:
                        raise ConversionInputError("Excel 单元格与行坐标不一致。")
                    if column in cells:
                        raise ConversionInputError("Excel 存在重复单元格坐标。")
                    kind = cell.get("t", "n")
                    value = cell.findtext("s:v", default="", namespaces=NS)
                    if kind == "s":
                        if not value.isdigit() or int(value) >= len(shared):
                            raise ConversionInputError("Excel 共享字符串索引无效。")
                        value = shared[int(value)]
                    elif kind == "inlineStr":
                        value = _string(cell.find("s:is", NS))
                    elif kind in {"n", "str"}:
                        if kind == "n" and value:
                            style = cell.get("s", "0")
                            if not style.isdigit() or int(style) >= len(formats) or formats[int(style)] != "0":
                                raise ConversionInputError(
                                    "数值单元格只支持 General 格式；日期或其他数值格式请改用文本。"
                                )
                            numeric_columns.add(column)
                    else:
                        raise ConversionInputError("不支持 Excel 日期、布尔或错误类型单元格。")
                    cells[column] = value.strip()
                if not cells or not any(cells.values()):
                    continue
                if len(rows) >= MAX_ROWS + 1:
                    raise ConversionInputError("Excel 超过 200 行明细；不会截断。")
                width = max(cells) + 1
                rows.append(tuple(cells.get(index, "") for index in range(width)))
                if len(rows) > 1:
                    numeric.update((len(rows) - 2, column) for column in numeric_columns)
            if not rows:
                raise ConversionInputError("Excel 工作表为空。")
            headers = rows[0]
            padded = [row + ("",) * (len(headers) - len(row)) for row in rows[1:]]
            return _table(headers, padded, payload, "xlsx", "ooxml", frozenset(numeric))
    except ConversionInputError:
        raise
    except (zipfile.BadZipFile, KeyError, ValueError, AttributeError, RuntimeError, OSError) as error:
        raise ConversionInputError("无法读取 XLSX；请检查文件完整性，或导出 CSV。") from error


def read_report_table(payload: bytes, filename: str) -> ReportTable:
    if not payload or len(payload) > MAX_REPORT_BYTES:
        raise ConversionInputError("报表必须非空且不超过 1 MB。")
    if not filename or len(filename) > 255 or "\x00" in filename:
        raise ConversionInputError("文件名为空、过长或无效。")
    suffix = PurePath(filename).suffix.lower()
    if suffix == ".csv":
        return replace(_csv(payload), original_filename=filename)
    if suffix == ".xlsx":
        return replace(_xlsx(payload), original_filename=filename)
    raise ConversionInputError("自动转换仅支持 CSV 或单工作表 XLSX；JSON 请使用原上传入口。")
