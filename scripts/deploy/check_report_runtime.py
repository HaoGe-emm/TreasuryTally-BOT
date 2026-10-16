"""No-key Linux report runtime smoke; synthetic views only, no external requests."""

from __future__ import annotations

import argparse
import importlib.metadata
import io
import json
import os
import socket
import subprocess
import sys
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile


def check_isolation() -> None:
    # Parent retains socket capability for RPC; only the launched worker is restricted.
    with socket.socket():
        pass
    code = """import errno, runpy, socket
runpy.run_path('/opt/trust-receipt-renderer/renderer-node')['contain']()
pair = socket.socketpair()
for stream in pair:
    stream.close()
try:
    socket.socketpair(socket.AF_INET)
except OSError as e:
    assert e.errno == errno.EPERM
else:
    raise AssertionError('non-Unix socketpair allowed')
try:
    socket.socket()
except OSError as e:
    assert e.errno == errno.EPERM
else:
    raise AssertionError('renderer networking allowed')
print('SOCKET_DENIED')
"""
    child = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=5, check=True)
    assert child.stdout.strip() == b"SOCKET_DENIED"
    bad = subprocess.run([os.environ["REPORT_RENDERER_NODE"], "-e", "process.exit(0)"],
                         capture_output=True, timeout=5, check=False)
    assert bad.returncode != 0 and bad.stderr == b"EXPORT_UNAVAILABLE"


def main() -> None:
    from PIL import Image

    from trust_receipt.reporting import BusinessReportView, export_docx, export_pdf
    from trust_receipt.reporting.renderer import EChartsRenderer, ExportUnavailable

    parser = argparse.ArgumentParser()
    parser.add_argument("views", type=Path)
    parser.add_argument("--memory-mib", type=int, default=640)
    parser.add_argument("--pids", type=int, default=128)
    args = parser.parse_args()
    assert args.memory_mib > 0 and args.pids > 0
    assert not Path("/app/.env").exists()
    assert Path("/sys/fs/cgroup/memory.max").read_text().strip() == str(args.memory_mib * 1024**2)
    assert Path("/sys/fs/cgroup/memory.swap.max").read_text().strip() == "0"
    assert Path("/sys/fs/cgroup/pids.max").read_text().strip() == str(args.pids)
    source = Path("/app/src/trust_receipt/reporting/assets")
    installed = Path(importlib.metadata.distribution("trust-receipt").locate_file("trust_receipt/reporting/assets"))
    manifests = [{str(p.relative_to(root)): sha256(p.read_bytes()).hexdigest()
                  for p in root.rglob("*") if p.is_file() and p.name != ".gitignore"}
                 for root in (source, installed)]
    assert manifests[0] == manifests[1], "Reporting assets differ from wheel"
    assert (source / "ReportSans-Regular.ttf").read_bytes() == Path(
        "/usr/local/share/fonts/report/ReportSans-Regular.ttf").read_bytes()
    check_isolation()
    modules = Path(os.environ["REPORT_RENDERER_MODULES"])
    assert (modules / "sharp/LICENSE").is_file()
    native = modules / "@img/sharp-libvips-linux-x64"
    assert (native / "README.md").is_file()
    assert json.loads((native / "package.json").read_bytes())["license"] == "LGPL-3.0-or-later"
    assert Path("/usr/local/share/doc/node/LICENSE").is_file()
    renderer = EChartsRenderer(node_path=os.environ["REPORT_RENDERER_NODE"], modules_path=str(modules))
    cases = []
    for file in sorted(args.views.glob("*.view.json")):
        view = BusinessReportView.model_validate_json(file.read_bytes())
        rendered = renderer.render(view)
        assert rendered.view_hash == sha256(view.model_dump_json().encode()).hexdigest()
        with Image.open(io.BytesIO(rendered.png)) as image:
            assert image.format == "PNG" and image.width == 1440
        docx = export_docx(view, renderer=renderer)
        with ZipFile(io.BytesIO(docx)) as archive:
            assert "word/fonts/report.odttf" in archive.namelist()
            assert view.current.receipt_hash.encode() in archive.read("word/document.xml")
        pdf = export_pdf(view, renderer=renderer)
        assert pdf.startswith(b"%PDF-") and b"%%EOF" in pdf[-100:]
        cases.append({"case": file.stem, "png_bytes": len(rendered.png),
                      "docx_bytes": len(docx), "pdf_bytes": len(pdf)})
    assert len(cases) == 7
    try:
        EChartsRenderer(node_path="/missing-renderer").render(view)
    except ExportUnavailable:
        pass
    else:
        raise AssertionError("Missing renderer did not fail closed")
    print(json.dumps({"cases": cases, "assets_match_wheel": True, "renderer_socket_denied": True,
                      "parent_socket_available": True, "no_key_or_rpc": True,
                      "visual_approval": "not-asserted"}))


if __name__ == "__main__":
    main()
