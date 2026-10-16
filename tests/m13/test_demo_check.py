from __future__ import annotations

import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

from trust_receipt.demo import run_offline_mvp_demo
from trust_receipt.hashing import canonical_json_bytes, content_hash
from trust_receipt.publishing import authorize_public_receipt
from trust_receipt.receipts import load_receipt

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "scripts" / "m13" / "check_demo.py"


def _public_pass_receipt(tmp_path: Path) -> tuple[Path, str, bytes]:
    output = tmp_path / "demo"
    run_offline_mvp_demo(PROJECT_ROOT, output)
    private_receipt = next(output.glob("receipts/*/attempt-2.json"))
    public_receipt = authorize_public_receipt(load_receipt(private_receipt))
    payload = canonical_json_bytes(public_receipt) + b"\n"
    path = tmp_path / "public-pass.json"
    path.write_bytes(payload)
    return path, content_hash(payload), payload


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        cwd=PROJECT_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def _uploaded_report(path: Path, *, total: str, count: int) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "claimed_total_base_units": total,
                "claimed_count": count,
                "transfers": [],
            }
        ),
        encoding="utf-8",
    )


def test_receipt_command_replays_in_a_fresh_process(tmp_path):
    receipt, expected_hash, _ = _public_pass_receipt(tmp_path)

    completed = _run(
        "receipt",
        "--receipt-file",
        str(receipt),
        "--expected-content-hash",
        expected_hash,
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["overall_status"] == "READY"
    assert result["checks"][0]["evidence"]["outcome"] == "PASS"
    assert result["checks"][0]["evidence"]["content_hash"] == expected_hash


def test_receipt_command_rejects_a_content_hash_mismatch(tmp_path):
    receipt, _, _ = _public_pass_receipt(tmp_path)

    completed = _run(
        "receipt",
        "--receipt-file",
        str(receipt),
        "--expected-content-hash",
        "0x" + "00" * 32,
    )

    assert completed.returncode == 1
    result = json.loads(completed.stdout)
    assert result["overall_status"] == "FAILED"
    assert "content hash" in result["checks"][0]["detail"]


def test_network_failure_is_inconclusive_and_not_negative_reputation():
    completed = _run(
        "receipt",
        "--receipt-uri",
        "https://127.0.0.1:9/unavailable.json",
        "--expected-content-hash",
        "0x" + "00" * 32,
        "--timeout-seconds",
        "0.2",
    )

    assert completed.returncode == 2
    result = json.loads(completed.stdout)
    assert result["overall_status"] == "INCONCLUSIVE"
    assert result["checks"][0]["evidence"]["service_reputation_effect"] == "none"


def test_preflight_checks_reports_app_and_public_receipt(tmp_path):
    _, expected_hash, receipt_payload = _public_pass_receipt(tmp_path)
    faulty = tmp_path / "faulty.json"
    corrected = tmp_path / "corrected.json"
    _uploaded_report(faulty, total="100", count=1)
    _uploaded_report(corrected, total="120", count=2)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            payload = receipt_payload if self.path == "/receipt.json" else b"<html>M13 rehearsal</html>"
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{server.server_port}"
        completed = _run(
            "preflight",
            "--app-url",
            base_url,
            "--faulty-report",
            str(faulty),
            "--corrected-report",
            str(corrected),
            "--receipt-uri",
            f"{base_url}/receipt.json",
            "--expected-content-hash",
            expected_hash,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["overall_status"] == "READY"
    assert [check["status"] for check in result["checks"]] == ["READY"] * 5


@pytest.mark.parametrize("scheme", ["file", "ftp"])
def test_remote_receipt_rejects_non_https_schemes(scheme):
    completed = _run(
        "receipt",
        "--receipt-uri",
        f"{scheme}://example.test/receipt.json",
        "--expected-content-hash",
        "0x" + "00" * 32,
    )

    assert completed.returncode == 1
    assert json.loads(completed.stdout)["overall_status"] == "FAILED"
