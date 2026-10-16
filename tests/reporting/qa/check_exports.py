"""Bundled read-only format/parity/privacy tests; visual inspection remains a separate gate."""

import json
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).parents[3] / "src"))

from PIL import Image
from pypdf import PdfReader

from trust_receipt.reporting import BusinessReportView, export_html, graph_svg
from trust_receipt.reporting.layout import validate_export_view
from trust_receipt.reporting.renderer import EChartsRenderer


def compact(text):
    return re.sub(r"\s+", "", text)


def main():
    directory = Path(sys.argv[1])
    renderer = EChartsRenderer(node_path=sys.argv[2] if len(sys.argv) > 2 else None,
                               modules_path=sys.argv[3] if len(sys.argv) > 3 else None)
    results = []
    for source in sorted(directory.glob("*.view.json")):
        view = BusinessReportView.model_validate_json(source.read_bytes())
        stem = source.name.removesuffix(".view.json")
        with ZipFile(directory / f"{stem}.docx") as doc:
            xml = ET.fromstring(doc.read("word/document.xml"))
            doc_text = "".join(xml.itertext())
            assert "word/fonts/report.odttf" in doc.namelist()
            assert not any(
                'TargetMode="External"' in doc.read(n).decode() for n in doc.namelist() if n.endswith(".rels")
            )
        pdf = PdfReader(directory / f"{stem}.pdf")
        assert 1 <= len(pdf.pages) <= 50
        pdf_text = "\n".join(page.extract_text() for page in pdf.pages)
        html = (directory / f"{stem}.html").read_text(encoding="utf-8")
        for text in (
            view.conclusion,
            view.spec_hash,
            view.current.receipt_hash,
            view.current.claimed.display,
            view.scope.token.full,
            view.source_mode_label,
        ):
            assert compact(text) in compact(doc_text), (stem, "docx", text)
            assert compact(text) in compact(pdf_text), (stem, "pdf", text)
            assert text in html, (stem, "html", text)
        for row in view.current.flow_rows:
            assert compact(row.event_ref) in compact(doc_text)
            assert compact(row.event_ref) in compact(pdf_text)
            assert row.event_ref in html
        if view.previous:
            for text in (view.previous.receipt_hash, "FAIL", "PASS"):
                assert text in doc_text and text in pdf_text and text in html
        with Image.open(directory / f"{stem}.png") as picture:
            assert picture.format == "PNG" and picture.width == 1440
        bad = view.model_copy(update={"title": '<script>alert(1)</script><img src="https://secret.invalid">'})
        escaped = export_html(bad, renderer=renderer).decode()
        assert "<script>" not in escaped and "<img src=" not in escaped
        assert "&lt;script&gt;" in escaped
        svg = graph_svg(bad, renderer=renderer)
        assert "foreignObject" not in svg and "<script" not in svg
        for text in ("API_KEY=", "private_key", "Authorization:", "report_text", "file://"):
            assert text not in html and text not in doc_text and text not in pdf_text
        with_exception = view.model_copy(update={"title": "x" * 4097})
        try:
            validate_export_view(with_exception)
        except ValueError:
            pass
        else:
            raise AssertionError("oversized text accepted")
        results.append(
            {
                "sample": stem,
                "pdf_pages": len(pdf.pages),
                "full_flow_rows": len(view.current.flow_rows),
                "parity": "PASSED",
                "visual_qa": "NOT_ASSERTED_BY_THIS_SCRIPT",
            }
        )
    (directory / "export-checks.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
