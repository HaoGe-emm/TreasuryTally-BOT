"""Fail-closed readiness evidence: unexecuted checks stay BLOCKED."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

CHECK_IDS = tuple(f"UR-{number:02d}" for number in range(1, 15))
STATUSES = {"PASS", "FAIL", "BLOCKED"}


def build_matrix(observations: list[dict], build: str, input_hash: str) -> dict:
    indexed: dict[str, dict] = {}
    for item in observations:
        check_id = item["id"]
        if check_id not in CHECK_IDS or check_id in indexed:
            raise ValueError("unknown or duplicate readiness check")
        if item["status"] not in STATUSES:
            raise ValueError("invalid readiness status")
        if item["status"] == "PASS" and not item.get("evidence"):
            raise ValueError("PASS requires actual evidence")
        indexed[check_id] = item
    checks = [indexed.get(key, {
        "id": key, "status": "BLOCKED", "reason": "not executed by this run", "evidence": {},
    }) for key in CHECK_IDS]
    return {
        "schema_version": "1.0", "created_at": datetime.now(UTC).isoformat(),
        "build": build, "input_sha256": input_hash,
        "real_user_testing": False,
        "limitation": "Browser automation does not establish real-user validation.",
        "ready": all(item["status"] == "PASS" for item in checks), "checks": checks,
    }


def save_matrix(destination: Path, matrix: dict) -> None:
    # Refuse to overwrite earlier failures with a later successful run.
    with destination.open("x", encoding="utf-8") as handle:
        json.dump(matrix, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
