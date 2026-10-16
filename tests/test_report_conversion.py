"""Conversion is a private, deterministic formatting step, not verification."""

import csv
import io
import json
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import pytest

from trust_receipt.hashing import content_hash
from trust_receipt.services.conversion_storage import persist_confirmed_conversion
from trust_receipt.services.report_conversion import (
    ConversionInputError,
    convert_report_table,
    read_report_table,
    suggest_field_mapping,
)
from trust_receipt.services.upload import parse_report

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/m14/conversion"
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"


def fixture_rows():
    return list(csv.reader(io.StringIO((FIXTURES / "wrong-declared-total.csv").read_text(encoding="utf-8"))))


def csv_payload(rows, encoding="utf-8", delimiter=","):
    stream = io.StringIO(newline="")
    csv.writer(stream, delimiter=delimiter).writerows(rows)
    return stream.getvalue().encode(encoding)


def candidate(rows=None):
    return convert_report_table(read_report_table(csv_payload(rows or fixture_rows()), "report.csv"))


def xlsx(rows, *, numeric=None, formula=None, extra=None, styles=None):
    numeric = numeric or set()
    sheet_rows = []
    for row_index, row in enumerate(rows):
        cells = []
        for column, value in enumerate(row):
            coordinate = f"{chr(65 + column)}{row_index + 1}"
            if (row_index, column) in numeric:
                cells.append(f'<c r="{coordinate}" s="0"><v>{escape(value)}</v></c>')
            else:
                cells.append(f'<c r="{coordinate}" t="inlineStr"><is><t>{escape(value)}</t></is></c>')
        sheet_rows.append(f'<row r="{row_index + 1}">{"".join(cells)}</row>')
    sheet = f'<worksheet xmlns="{NS}"><sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'
    if formula:
        sheet = sheet.replace("<is>", formula + "<is>", 1)
    members = {
        "xl/workbook.xml": (
            f'<workbook xmlns="{NS}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Report" sheetId="1" r:id="rId1"/></sheets></workbook>'
        ),
        "xl/_rels/workbook.xml.rels": (
            f'<Relationships xmlns="{REL}"><Relationship Id="rId1" Target="worksheets/sheet1.xml" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/></Relationships>'
        ),
        "xl/worksheets/sheet1.xml": sheet,
    }
    if styles:
        members["xl/styles.xml"] = f'<styleSheet xmlns="{NS}"><cellXfs><xf numFmtId="{styles}"/></cellXfs></styleSheet>'
    members.update(extra or {})
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, value in members.items():
            archive.writestr(name, value)
    return stream.getvalue()


def test_decimal_conversion_exact_and_original_filename():
    raw = (FIXTURES / "correct-token-units.csv").read_bytes()
    result = convert_report_table(read_report_table(raw, "原报表.csv"))
    assert result.ready and not result.derived_summary
    assert result.report.transfers[0].amount_base_units == "180674489737"
    assert result.report.claimed_total_base_units == "180674489737"
    assert result.original_filename == "原报表.csv"
    assert result.original_hash == content_hash(raw)
    assert parse_report(result.json_payload) == result.report


def test_wrong_claims_duplicates_order_are_preserved():
    rows = fixture_rows()
    rows.append(rows[1].copy())
    result = candidate(rows)
    assert result.ready
    assert result.report.claimed_total_base_units == "0"
    assert result.report.claimed_count == 0
    assert len(result.report.transfers) == 2
    assert result.report.transfers[0] == result.report.transfers[1]


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "gb18030"])
@pytest.mark.parametrize("delimiter", [",", ";", "\t"])
def test_encodings_and_delimiters(encoding, delimiter):
    rows = list(csv.reader(io.StringIO((FIXTURES / "correct-token-units.csv").read_text(encoding="utf-8"))))
    assert convert_report_table(read_report_table(csv_payload(rows, encoding, delimiter), "a.csv")).ready


@pytest.mark.parametrize("raw,name", [
    (b"", "a.csv"), (b"x" * 1_000_001, "a.csv"), (b"a\x00,b\n1,2", "a.csv"),
    (b'a,b\n"unterminated', "a.csv"), (b"a,b\n1,2,3", "a.csv"), (b"a,a\n1,2", "a.csv"),
    (b"a,\n1,2", "a.csv"), (b"a,b\n", "a.csv"), (b"{}", "a.json"), (b"bad", "a.xlsx"),
    (b"a,b\n1,2", ""), (b"a,b\n1,2", "a.xls"),
], ids=["empty", "oversize", "nul", "quotes", "width", "duplicate", "blank-header", "no-rows",
        "json", "broken-zip", "filename", "xls"])
def test_reader_rejects_unsafe_inputs(raw, name):
    with pytest.raises(ConversionInputError):
        read_report_table(raw, name)


@pytest.mark.parametrize("rows", [
    [["a"], *[["1"] for _ in range(201)]],
    [[str(i) for i in range(65)], ["1"] * 65],
    [["a"], ["x" * 4097]],
])
def test_limits_do_not_truncate(rows):
    with pytest.raises(ConversionInputError):
        read_report_table(csv_payload(rows), "a.csv")


@pytest.mark.parametrize("amount", ["1e18", "-1", "1,000", "1.0", "+1", "01"])
def test_integer_amount_rejects_lossy_notation(amount):
    rows = fixture_rows()
    rows[1][rows[0].index("amount_base_units")] = amount
    assert not candidate(rows).ready


def test_decimal_overprecision_not_rounded():
    rows = fixture_rows()
    index = rows[0].index("amount_base_units")
    rows[0][index] = "amount_token_units"
    rows[1][index] = "0.0000000000000000001"
    assert not candidate(rows).ready
    rows[1][index] = "1.0000000000000000000"
    assert candidate(rows).report.transfers[0].amount_base_units == "1000000000000000000"


def test_missing_event_identity_not_guessed_and_constants_restricted():
    rows = fixture_rows()
    index = rows[0].index("log_index")
    rows[0][index] = "unknown"
    table = read_report_table(csv_payload(rows), "a.csv")
    result = convert_report_table(table)
    assert "log_index" in result.missing_fields and not result.ready
    assert not convert_report_table(table, constants={"log_index": "128"}).ready
    with pytest.raises(ConversionInputError):
        _ = result.json_payload


def test_constants_and_derived_summary_explicit():
    rows = fixture_rows()
    constants = {}
    for field in ("chain_id", "token_address", "token_decimals", "claimed_count", "claimed_total_base_units"):
        index = rows[0].index(field)
        if field in ("chain_id", "token_address", "token_decimals"):
            constants[field] = rows[1][index]
        for row in rows:
            row.pop(index)
    result = convert_report_table(read_report_table(csv_payload(rows), "a.csv"), constants=constants)
    assert result.ready and result.derived_summary
    assert set(result.derived_fields) == {"claimed_count", "claimed_total_base_units"}
    assert result.report.claimed_count == 1 and result.warnings


@pytest.mark.parametrize("field,newvalue", [("source", "rpc"), ("transaction_hash", "bad"), ("chain_id", "1e7")])
def test_invalid_fields_block(field, newvalue):
    rows = fixture_rows()
    if field not in rows[0]:
        rows[0].append(field)
        rows[1].append(newvalue)
    else:
        rows[1][rows[0].index(field)] = newvalue
    assert not candidate(rows).ready


def test_mapping_collisions_and_ambiguous_units():
    rows = fixture_rows()
    rows[0].append("chainid")
    rows[1].append(rows[1][0])
    assert not candidate(rows).ready
    rows = fixture_rows()
    rows[0].append("amount_token_units")
    rows[1].append("1")
    table = read_report_table(csv_payload(rows), "a.csv")
    assert not convert_report_table(table).ready
    mapping = suggest_field_mapping(table)
    mapping.pop("amount")
    assert convert_report_table(table, mapping).ready
    mapping["unknown"] = rows[0][0]
    assert not convert_report_table(table, mapping).ready


def test_summary_conflict_not_overwritten():
    rows = fixture_rows()
    rows.append(rows[1].copy())
    rows[2][rows[0].index("claimed_count")] = "2"
    assert not candidate(rows).ready


def test_xlsx_text_and_integer_fields():
    rows = fixture_rows()
    numeric = {(1, rows[0].index(name)) for name in ("chain_id", "block_number", "log_index", "token_decimals")}
    result = convert_report_table(read_report_table(xlsx(rows, numeric=numeric), "a.xlsx"))
    assert result.ready and result.report == candidate(rows).report


@pytest.mark.parametrize("field", ["amount_base_units", "claimed_total_base_units"])
def test_excel_numeric_amount_never_trusted(field):
    rows = fixture_rows()
    result = convert_report_table(read_report_table(xlsx(rows, numeric={(1, rows[0].index(field))}), "a.xlsx"))
    assert not result.ready


@pytest.mark.parametrize("options", [
    {"formula": "<f>SUM(A1)</f>"}, {"formula": '<f xmlns="urn:wrong">SUM(A1)</f>'},
    {"extra": {"xl/vbaProject.bin": b"macro"}},
    {"extra": {"xl/worksheets/sheet2.xml": "<worksheet/>"}},
    {"extra": {"xl/large.xml": "x" * 1_000_001}},
    {"extra": {"xl/workbook.xml": '<!DOCTYPE x [<!ENTITY e "a">]><x>&e;</x>'}},
    {"extra": {"xl/workbook.xml": '<!DOCTYPE x [<!ENTITY e "a">]><x>&e;</x>'.encode("utf-16")}},
    {"extra": {"xl/_rels/external.rels": (
        f'<Relationships xmlns="{REL}"><Relationship TargetMode="External"/></Relationships>'
    )}},
    {"numeric": {(1, 0)}, "styles": "14"},
    {"numeric": {(1, 0)}, "styles": "165"},
])
def test_excel_unsafe_content_blocked(options):
    with pytest.raises(ConversionInputError):
        read_report_table(xlsx(fixture_rows(), **options), "a.xlsx")


def test_shared_strings_rich_text_and_bad_index():
    rows = fixture_rows()
    sheet = xlsx(rows)
    with zipfile.ZipFile(io.BytesIO(sheet)) as archive:
        xml = archive.read("xl/worksheets/sheet1.xml").decode()
    original = f'<c r="A1" t="inlineStr"><is><t>{rows[0][0]}</t></is></c>'
    shared = f'<sst xmlns="{NS}"><si><r><t>chain</t></r><r><t>_id</t></r></si></sst>'
    extra = {"xl/sharedStrings.xml": shared,
             "xl/worksheets/sheet1.xml": xml.replace(original, '<c r="A1" t="s"><v>0</v></c>')}
    assert convert_report_table(read_report_table(xlsx(rows, extra=extra), "a.xlsx")).ready
    extra["xl/worksheets/sheet1.xml"] = xml.replace(original, '<c r="A1" t="s"><v>99</v></c>')
    with pytest.raises(ConversionInputError):
        read_report_table(xlsx(rows, extra=extra), "a.xlsx")


def test_retention_requires_confirmation_and_raw_binding(tmp_path):
    raw = csv_payload(fixture_rows())
    result = candidate()
    for confirmed, original in [(False, raw), (True, raw + b"\n")]:
        with pytest.raises(ConversionInputError):
            persist_confirmed_conversion(original, result, tmp_path, confirmed=confirmed)
    assert not list(tmp_path.iterdir())
    normalized = persist_confirmed_conversion(raw, result, tmp_path, confirmed=True)
    assert parse_report(normalized) == result.report
    assert persist_confirmed_conversion(raw, result, tmp_path, confirmed=True) == normalized
    manifest = json.loads(next((tmp_path / "conversion-provenance").iterdir()).read_bytes())
    assert manifest["original_hash"] == content_hash(raw)
    assert manifest["normalized_hash"] == content_hash(normalized)
    assert manifest["original_author_verified"] is False
    assert next((tmp_path / "conversion-originals").iterdir()).read_bytes() == raw
    original_path = next((tmp_path / "conversion-originals").iterdir())
    original_path.write_bytes(b"corrupt")
    with pytest.raises(ConversionInputError):
        persist_confirmed_conversion(raw, result, tmp_path, confirmed=True)


@pytest.mark.parametrize("change", ["unknown-row", "unknown-cell", "duplicate-cell", "wrong-row", "merge"])
def test_xlsx_unknown_structure_never_silently_skips(change):
    rows = fixture_rows()
    with zipfile.ZipFile(io.BytesIO(xlsx(rows))) as archive:
        sheet = archive.read("xl/worksheets/sheet1.xml").decode()
    if change == "unknown-row":
        sheet = sheet.replace('<row r="2">', '<row xmlns="urn:unknown" r="2">')
    elif change == "unknown-cell":
        sheet = sheet.replace('<c r="A2"', '<c xmlns="urn:unknown" r="A2"')
    elif change == "duplicate-cell":
        sheet = sheet.replace('<row r="2">', '<row r="2"><c r="A2"><v>1</v></c>')
    elif change == "wrong-row":
        sheet = sheet.replace('<c r="A2"', '<c r="A3"')
    else:
        sheet = sheet.replace('</worksheet>', '<mergeCells><mergeCell ref="A1:B1"/></mergeCells></worksheet>')
    with pytest.raises(ConversionInputError):
        read_report_table(xlsx(rows, extra={"xl/worksheets/sheet1.xml": sheet}), "a.xlsx")


def test_zip_total_expansion_and_member_count():
    for extra in (
        {f"xl/unused{i}.xml": "x" * 999_000 for i in range(5)},
        {f"xl/unused{i}.xml": "x" for i in range(129)},
    ):
        with pytest.raises(ConversionInputError):
            read_report_table(xlsx(fixture_rows(), extra=extra), "a.xlsx")


def test_duplicate_zip_member_rejected():
    stream = io.BytesIO(xlsx(fixture_rows()))
    with pytest.warns(UserWarning), zipfile.ZipFile(stream, "a") as archive:
        archive.writestr("xl/workbook.xml", "<x/>")
    with pytest.raises(ConversionInputError):
        read_report_table(stream.getvalue(), "a.xlsx")


def test_mixed_units_blocked_not_partitioned():
    rows = fixture_rows()
    rows.append(rows[1].copy())
    rows[2][rows[0].index("token_decimals")] = "6"
    assert not candidate(rows).ready


def test_unlabeled_amount_requires_explicit_unit_selection():
    rows = fixture_rows()
    rows[0][rows[0].index("amount_base_units")] = "amount"
    table = read_report_table(csv_payload(rows), "a.csv")
    result = convert_report_table(table)
    assert not result.ready and "amount_base_units_or_amount" in result.missing_fields
    mapping = suggest_field_mapping(table)
    mapping["amount_base_units"] = "amount"
    assert convert_report_table(table, mapping).ready


def test_no_block_hash_is_null_not_reference_lookup():
    rows = fixture_rows()
    index = rows[0].index("block_hash")
    for row in rows:
        row.pop(index)
    result = candidate(rows)
    assert result.ready and result.report.transfers[0].block_hash is None and result.warnings


def test_unsupported_compression_rejected_before_decompression():
    stream = io.BytesIO(xlsx(fixture_rows()))
    with zipfile.ZipFile(stream, "a", compression=zipfile.ZIP_BZIP2) as archive:
        archive.writestr("xl/other.xml", "x")
    with pytest.raises(ConversionInputError):
        read_report_table(stream.getvalue(), "a.xlsx")
