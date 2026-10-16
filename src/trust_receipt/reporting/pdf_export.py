"""Portable PDF with embedded Chinese TrueType font; no Office dependency."""

from html import escape
from io import BytesIO

from trust_receipt.reporting.graphics import font_bytes, graph_png
from trust_receipt.reporting.layout import report_sections, validate_export_view
from trust_receipt.reporting.models import BusinessReportView
from trust_receipt.reporting.renderer import EChartsRenderer, ExportUnavailable


def export_pdf(view: BusinessReportView, *, renderer: EChartsRenderer) -> bytes:
    with renderer.export_slot():
        return _export_pdf(view, renderer=renderer)


def _export_pdf(view: BusinessReportView, *, renderer: EChartsRenderer) -> bytes:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import (
            Image,
            KeepTogether,
            LongTable,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            TableStyle,
        )
    except ImportError as error:
        raise ExportUnavailable("EXPORT_UNAVAILABLE: PDF export dependency missing") from error

    validate_export_view(view)
    font_name = "TreasuryTallyReportSans"
    if font_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(font_name, BytesIO(font_bytes())))
    body = ParagraphStyle("body", fontName=font_name, fontSize=11, leading=16, spaceAfter=8, wordWrap="CJK")
    heading = ParagraphStyle("heading", parent=body, fontSize=14, leading=20, spaceBefore=14, keepWithNext=True)
    title = ParagraphStyle("title", parent=body, fontSize=22, leading=30, spaceAfter=16)
    cell = ParagraphStyle("cell", parent=body, fontSize=9.5, leading=14, spaceAfter=0)
    table_intro = ParagraphStyle("table_intro", parent=body, keepWithNext=True)

    def paragraph(text, style=body):
        return Paragraph(escape(text).replace("\n", "<br/>"), style)

    story = [paragraph(view.title, title)]
    for section in report_sections(view):
        if section.title == "完整账户索引" and len(section.paragraphs) <= 10:
            story.append(KeepTogether([
                paragraph(section.title, heading),
                *(paragraph(text) for text in section.paragraphs),
            ]))
            continue
        story.append(paragraph(section.title, heading))
        story.extend(paragraph(text, table_intro if section.headers else body) for text in section.paragraphs)
        if section.title == "资金流图例":
            image = Image(BytesIO(graph_png(view, renderer=renderer)))
            image.drawHeight *= (7 * inch) / image.drawWidth
            image.drawWidth = 7 * inch
            image.hAlign = "LEFT"
            story.append(image)
            story.append(Spacer(1, 8))
        if section.headers:
            data = [[paragraph(text, cell) for text in section.headers]]
            data.extend([paragraph(value, cell) for value in row] for row in section.rows)
            widths = (
                [2.6 * inch, 1.3 * inch, 3.1 * inch]
                if section.title == "完整资金流明细"
                else [7 * inch / len(section.headers)] * len(section.headers)
            )
            table = LongTable(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d9d9d9")),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 7),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            story.extend((table, Spacer(1, 8)))
    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
        title=view.title,
        author="TreasuryTally",
    )
    doc.build(story)
    return output.getvalue()
