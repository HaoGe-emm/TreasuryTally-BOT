"""Print-preview assets from the fixed ECharts worker; no Python drawing fallback."""

from importlib.resources import files

from trust_receipt.reporting.models import BusinessReportView
from trust_receipt.reporting.renderer import EChartsRenderer, ExportUnavailable


def font_bytes() -> bytes:
    try:
        return files("trust_receipt.reporting").joinpath("assets/ReportSans-Regular.ttf").read_bytes()
    except OSError as error:
        raise ExportUnavailable("EXPORT_UNAVAILABLE: report font missing") from error


def graph_svg(view: BusinessReportView, *, renderer: EChartsRenderer) -> str:
    with renderer.export_slot():
        return renderer.render(view).svg


def graph_png(view: BusinessReportView, *, renderer: EChartsRenderer) -> bytes:
    with renderer.export_slot():
        return renderer.render(view).png
