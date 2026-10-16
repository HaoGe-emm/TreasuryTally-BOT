"""Evidence must not turn omissions or partial automation into readiness."""

import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[2] / "scripts" / "m14" / "evidence.py"
SPEC = importlib.util.spec_from_file_location("m14_evidence", MODULE_PATH)
evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence)


def test_unexecuted_checks_are_blocked_and_not_ready():
    matrix = evidence.build_matrix([], "build", "hash")
    assert len(matrix["checks"]) == 14
    assert not matrix["ready"]
    assert not matrix["real_user_testing"]
    assert all(item["status"] == "BLOCKED" for item in matrix["checks"])


@pytest.mark.parametrize("observations", [
    [{"id": "UR-01", "status": "PASS", "evidence": {}}],
    [{"id": "UR-99", "status": "PASS", "evidence": {"actual": True}}],
    [{"id": "UR-01", "status": "SUCCESS", "evidence": {"actual": True}}],
    [{"id": "UR-01", "status": "FAIL"}, {"id": "UR-01", "status": "PASS"}],
])
def test_unsubstantiated_and_conflicting_evidence_rejected(observations):
    with pytest.raises(ValueError):
        evidence.build_matrix(observations, "build", "hash")


def test_evidence_does_not_overwrite_previous_failure(tmp_path):
    target = tmp_path / "matrix.json"
    matrix = evidence.build_matrix([], "build", "hash")
    evidence.save_matrix(target, matrix)
    with pytest.raises(FileExistsError):
        evidence.save_matrix(target, {"ready": True})
    assert json.loads(target.read_text())["ready"] is False
