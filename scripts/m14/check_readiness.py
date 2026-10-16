"""Drive a separate local Playwright CLI session and preserve matrix evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from contextlib import suppress
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from evidence import build_matrix, save_matrix

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from trust_receipt.services.upload import parse_report  # noqa: E402


def local_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise argparse.ArgumentTypeError("readiness automation only accepts isolated loopback HTTP")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise argparse.ArgumentTypeError("URL cannot contain credentials, query or fragment")
    return value


def run_cli(npx: str, session: str, args: list[str], cwd: Path, timeout: int = 90) -> str:
    result = subprocess.run(
        [npx, "--yes", "--package", "@playwright/cli", "playwright-cli", f"-s={session}", *args],
        cwd=cwd, capture_output=True, text=True, encoding="utf-8", timeout=timeout, check=False,
    )
    if result.returncode:
        raise RuntimeError(f"Playwright CLI {args[0]} failed with exit {result.returncode}")
    return result.stdout


def parse_observations(output: str) -> list[dict]:
    observations = json.loads(output)
    if not isinstance(observations, list):
        raise ValueError("browser did not emit a structured evidence list")
    return observations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", type=local_url, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--task-spec", type=Path, required=True)
    parser.add_argument("--expected-total", required=True, help="integer frozen by independent RPC precheck")
    parser.add_argument("--restore-task-hash", help="run only fresh-context restoration after an app restart")
    parser.add_argument(
        "--fault", choices=("unavailable", "conflict"), help="connect only to matching local fault launcher",
    )
    parser.add_argument("--build", required=True)
    parser.add_argument("--workspace-id", default=f"m14-{uuid4().hex[:12]}")
    parser.add_argument("--public-test-input-confirmed", action="store_true", required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    payload = args.report.read_bytes()
    report = parse_report(payload)
    if not report.transfers or any(record.chain_id != 11155111 for record in report.transfers):
        parser.error("provide a nonempty public Sepolia test report")
    output = args.evidence_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    session = f"m14-{uuid4().hex}"
    npx = shutil.which("npx.cmd") or shutil.which("npx")
    observations: list[dict] = []
    if npx:
        config = {
            "url": args.base_url, "report": str(args.report.resolve()), "scope": args.scope,
            "workspace": args.workspace_id, "output": str(output),
            "task": json.loads(args.task_spec.read_text(encoding="utf-8")),
            "expectedTotal": args.expected_total,
            "reportData": json.loads(payload),
            "restoreTaskHash": args.restore_task_hash,
            "fault": args.fault,
        }
        source = "restore_checks.js" if args.restore_task_hash else "browser_checks.js"
        if args.fault:
            source = "fault_checks.js"
        code = (Path(__file__).with_name(source).read_text(encoding="utf-8")
                .replace("__M14_CONFIG__", json.dumps(config, ensure_ascii=False))
                .replace("__M14_FLOW__", Path(__file__).with_name("flow_checks.js").read_text(encoding="utf-8")))
        executable = output / "browser-checks.js"
        executable.write_text(code, encoding="utf-8")
        try:
            run_cli(npx, session, ["open", args.base_url], output)
            # Snapshot establishes live UI before role/label-based automation.
            run_cli(npx, session, ["snapshot"], output)
            stdout = run_cli(npx, session, ["--raw", "run-code", "--filename", str(executable)], output, 360)
            observations = parse_observations(stdout)
        except (RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
            observations = [{"id": "UR-03", "status": "BLOCKED", "reason": str(error), "evidence": {}}]
        finally:
            with suppress(RuntimeError, subprocess.TimeoutExpired):
                run_cli(npx, session, ["close"], output)
    else:
        observations = [{"id": "UR-03", "status": "BLOCKED", "reason": "npx unavailable", "evidence": {}}]
    matrix = build_matrix(observations, args.build, hashlib.sha256(payload).hexdigest())
    save_matrix(output / "matrix.json", matrix)
    print(json.dumps({"evidence": str(output / "matrix.json"), "ready": matrix["ready"]}))
    return 0 if matrix["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
