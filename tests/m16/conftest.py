from __future__ import annotations

import json
from pathlib import Path

import pytest

from trust_receipt.headless.authorization import LocalApprovalController
from trust_receipt.headless.config import WorkspaceRegistry
from trust_receipt.headless.facade import HeadlessTrustReceiptFacade
from trust_receipt.models import EvidenceSource
from trust_receipt.orchestration.m5 import eligible_records, load_vertical_demo_fixture

WORKSPACE_HANDLE = "ws_0123456789abcdef"
SECOND_WORKSPACE_HANDLE = "ws_fedcba9876543210"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def write_registry(tmp_path: Path, *, include_second: bool = False) -> Path:
    workspaces = {
        WORKSPACE_HANDLE: {
            "directory": str(tmp_path / "workspace-a"),
            "project_root": str(PROJECT_ROOT),
            "profile": "FIXTURE_TEST_ONLY",
            "ai_provider": "fixture",
            "evidence_provider": "fixture",
        }
    }
    if include_second:
        workspaces[SECOND_WORKSPACE_HANDLE] = {
            "directory": str(tmp_path / "workspace-b"),
            "project_root": str(PROJECT_ROOT),
            "profile": "FIXTURE_TEST_ONLY",
            "ai_provider": "fixture",
            "evidence_provider": "fixture",
        }
    path = tmp_path / "m16-workspaces.json"
    path.write_text(json.dumps({"config_version": "1.0", "workspaces": workspaces}), encoding="utf-8")
    return path


@pytest.fixture
def registry_path(tmp_path):
    return write_registry(tmp_path, include_second=True)


@pytest.fixture
def facade(registry_path):
    return HeadlessTrustReceiptFacade(WorkspaceRegistry.load(registry_path))


@pytest.fixture
def approvals(registry_path):
    return LocalApprovalController(WorkspaceRegistry.load(registry_path))


@pytest.fixture
def fixture_case():
    return load_vertical_demo_fixture(PROJECT_ROOT)


def report_json(fixture_case, *, corrected: bool) -> str:
    transfers = (
        tuple(record.model_copy(update={"source": EvidenceSource.SERVICE}) for record in eligible_records(fixture_case))
        if corrected
        else fixture_case.submission.transfers
    )
    total = sum(int(record.amount_base_units) for record in transfers)
    return json.dumps(
        {
            "schema_version": "1.0",
            "claimed_total_base_units": str(total),
            "claimed_count": len(transfers),
            "transfers": [record.model_dump(mode="json") for record in transfers],
        },
        separators=(",", ":"),
    )
