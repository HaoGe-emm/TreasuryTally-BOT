"""Artifact authoring with the loader-selected bundled Python dependencies."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3] / "src"))

from trust_receipt.reporting import BusinessReportView, export_docx, export_html, export_pdf, graph_png
from trust_receipt.reporting.renderer import EChartsRenderer


def main():
    directory = Path(sys.argv[1])
    renderer = EChartsRenderer(node_path=sys.argv[2] if len(sys.argv) > 2 else None,
                               modules_path=sys.argv[3] if len(sys.argv) > 3 else None)
    for source in sorted(directory.glob("*.view.json")):
        view = BusinessReportView.model_validate_json(source.read_bytes())
        stem = source.name.removesuffix(".view.json")
        if len(sys.argv) > 4 and stem not in sys.argv[4].split(","):
            continue
        for suffix, builder in (("docx", export_docx), ("pdf", export_pdf), ("html", export_html), ("png", graph_png)):
            payload = builder(view, renderer=renderer)
            (directory / f"{stem}.{suffix}").write_bytes(payload)
            print(stem, suffix, len(payload))


if __name__ == "__main__":
    main()
