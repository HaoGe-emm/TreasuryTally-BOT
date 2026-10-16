"""Read committed case inputs without importing expected verification outcomes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from trust_receipt.agents import TaskSpecCandidate
from trust_receipt.models import TaskSpec
from trust_receipt.services.upload import parse_report


@dataclass(frozen=True)
class CaseInputs:
    candidate: TaskSpecCandidate
    error_report: bytes
    corrected_report: bytes


def load_real_case(project_root: Path) -> CaseInputs:
    directory = project_root / "fixtures" / "m11"
    manifest = json.loads((directory / "case.json").read_text(encoding="utf-8"))

    def read_relative(relative: str) -> bytes:
        target = (directory / relative).resolve()
        if not target.is_relative_to(directory.resolve()):
            raise ValueError("case input must remain inside the committed case directory")
        return target.read_bytes()

    task = TaskSpec.model_validate_json(read_relative(manifest["task_spec"]))
    candidate = TaskSpecCandidate.model_validate({
        **task.model_dump(mode="json", exclude={"task_id", "confirmed_at", "spec_hash"}),
        "candidate_id": "m12-real-case-candidate",
        "ambiguities": [],
        "missing_fields": [],
        "clarification_questions": [],
    })
    error = read_relative(manifest["reports"]["error"])
    corrected = read_relative(manifest["reports"]["corrected"])
    parse_report(error)
    parse_report(corrected)
    return CaseInputs(candidate, error, corrected)
