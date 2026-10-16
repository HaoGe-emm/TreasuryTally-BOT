"""Offline HTML report with escaped data, inline visual, no scripts or requests."""

from html import escape

from trust_receipt.reporting.graphics import graph_svg
from trust_receipt.reporting.layout import report_sections, validate_export_view
from trust_receipt.reporting.models import BusinessReportView
from trust_receipt.reporting.renderer import EChartsRenderer


def export_html(view: BusinessReportView, *, renderer: EChartsRenderer) -> bytes:
    with renderer.export_slot():
        return _export_html(view, renderer=renderer)


def _export_html(view: BusinessReportView, *, renderer: EChartsRenderer) -> bytes:
    validate_export_view(view)
    parts = [
        '<!doctype html><html lang="zh-CN"><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta http-equiv="Content-Security-Policy" '
        'content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;">',
        f"<title>{escape(view.title)}</title>",
        "<style>body{background:#15171c;color:#f5f5f5;font:16px/1.7 sans-serif;"
        "max-width:960px;margin:auto;padding:24px}"
        "h1{font-size:24px}h2{font-size:20px;margin-top:32px}p,td{overflow-wrap:anywhere}"
        "table{border-collapse:collapse;width:100%}td,th{border:1px solid #555;padding:8px;text-align:left}"
        "svg{max-width:540px}th{background:#25282e}"
        "@media print{body{background:white;color:black}th{background:#eee}}</style>",
        f"<body><h1>{escape(view.title)}</h1>",
        graph_svg(view, renderer=renderer),
    ]
    for section in report_sections(view):
        parts.append(f"<section><h2>{escape(section.title)}</h2>")
        parts.extend(f"<p>{escape(text)}</p>" for text in section.paragraphs)
        if section.headers:
            parts.append(
                "<table><thead><tr>"
                + "".join(f"<th>{escape(h)}</th>" for h in section.headers)
                + "</tr></thead><tbody>"
            )
            for row in section.rows:
                parts.append("<tr>" + "".join(f"<td>{escape(value)}</td>" for value in row) + "</tr>")
            parts.append("</tbody></table>")
        parts.append("</section>")
    parts.append("</body></html>")
    return "".join(parts).encode("utf-8")
