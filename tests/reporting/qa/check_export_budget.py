"""Real document post-Node contention check, with no fake output artifacts."""

import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[3] / "src"))

from trust_receipt.reporting import (
    BusinessReportView,
    docx_export,
    export_docx,
    export_html,
    export_pdf,
    graph_png,
    html_export,
)
from trust_receipt.reporting.renderer import EChartsRenderer, ExportUnavailable


def main():
    from reportlab.platypus import SimpleDocTemplate

    view = BusinessReportView.model_validate_json(Path(sys.argv[1]).read_bytes())
    before = view.model_dump_json()
    renderer = EChartsRenderer(node_path=sys.argv[2], modules_path=sys.argv[3])
    stages = [
        (export_docx, docx_export, "_embed_font", b"PK"),
        (export_pdf, SimpleDocTemplate, "build", b"%PDF-"),
        (export_html, html_export, "report_sections", b"<!doctype html>"),
    ]
    for builder, owner, name, magic in stages:
        entered, finish = threading.Event(), threading.Event()
        original = getattr(owner, name)

        def late_stage(*args, _entered=entered, _finish=finish, _original=original, **kwargs):
            _entered.set()
            assert _finish.wait(timeout=5), "contention probe did not finish"
            return _original(*args, **kwargs)

        with patch.object(owner, name, late_stage), ThreadPoolExecutor(max_workers=2) as pool:
            export = pool.submit(builder, view, renderer=renderer)
            try:
                assert entered.wait(timeout=30), "real post-Node document stage not reached"
                assert renderer._slots.acquire(blocking=False), "Node permit still held"
                renderer._slots.release()
                contender = pool.submit(graph_png, view, renderer=renderer)
                try:
                    contender.result(timeout=1)
                except ExportUnavailable as error:
                    assert str(error) == "EXPORT_UNAVAILABLE: export busy"
                else:
                    raise AssertionError("second export entered post-Node document stage")
            finally:
                finish.set()
            assert export.result(timeout=30).startswith(magic)
        # A different thread from the finished builder can enter again.
        with renderer.export_slot():
            pass
        assert view.model_dump_json() == before
        print(f"PASSED real {builder.__name__} post-Node stage {name}, immediate busy, release, unchanged view")


if __name__ == "__main__":
    main()
