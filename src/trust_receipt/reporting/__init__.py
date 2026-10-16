"""Stable receipt-bound business reports and in-memory export adapters."""

from typing import TYPE_CHECKING

from trust_receipt.reporting.docx_export import export_docx
from trust_receipt.reporting.graphics import graph_png, graph_svg
from trust_receipt.reporting.html_export import export_html
from trust_receipt.reporting.models import BusinessReportView, ReportAttemptInput
from trust_receipt.reporting.pdf_export import export_pdf
from trust_receipt.reporting.renderer import EChartsRenderer, ExportUnavailable

if TYPE_CHECKING:
    from trust_receipt.reporting.projection import build_business_report


def __getattr__(name: str):
    if name == "build_business_report":
        from trust_receipt.reporting.projection import build_business_report

        return build_business_report
    raise AttributeError(name)


__all__ = [
    "BusinessReportView",
    "EChartsRenderer",
    "ExportUnavailable",
    "ReportAttemptInput",
    "build_business_report",
    "export_docx",
    "export_html",
    "export_pdf",
    "graph_png",
    "graph_svg",
]
