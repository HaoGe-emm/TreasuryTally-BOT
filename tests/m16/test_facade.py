from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from trust_receipt.headless.authorization import LocalApprovalController
from trust_receipt.headless.config import WorkspaceRegistry
from trust_receipt.headless.contracts import AuthorizationState
from trust_receipt.headless.errors import HeadlessError
from trust_receipt.headless.facade import HeadlessTrustReceiptFacade
from trust_receipt.models import VerificationOutcome
from trust_receipt.storage.sqlite import SQLiteRepository

from .conftest import SECOND_WORKSPACE_HANDLE, WORKSPACE_HANDLE, report_json


def _confirm(facade, approvals, fixture_case):
    candidate = facade.draft_task(WORKSPACE_HANDLE, "核验固定测试报表")
    challenge = facade.prepare_task_confirmation(WORKSPACE_HANDLE, candidate.candidate)
    with pytest.raises(HeadlessError, match="approval") as error:
        facade.confirm_task(WORKSPACE_HANDLE, challenge.challenge_id)
    assert error.value.status == "AUTHORIZATION_REQUIRED"
    approvals.approve(WORKSPACE_HANDLE, challenge.challenge_id)
    confirmed = facade.confirm_task(WORKSPACE_HANDLE, challenge.challenge_id)
    repeated = facade.confirm_task(WORKSPACE_HANDLE, challenge.challenge_id)
    assert confirmed.idempotent_replay is False
    assert repeated.idempotent_replay is True
    assert confirmed.task_id == repeated.task_id
    return confirmed


def _verify(facade, approvals, fixture_case, task_id, *, corrected):
    challenge = facade.prepare_report_verification(
        WORKSPACE_HANDLE, task_id, report_json(fixture_case, corrected=corrected)
    )
    assert challenge.task_spec_hash is not None
    approvals.approve(WORKSPACE_HANDLE, challenge.challenge_id)
    result = facade.verify_report(WORKSPACE_HANDLE, challenge.challenge_id)
    repeated = facade.verify_report(WORKSPACE_HANDLE, challenge.challenge_id)
    assert result.idempotent_replay is False
    assert repeated.idempotent_replay is True
    assert result.receipt_hash == repeated.receipt_hash
    return result


def test_full_facade_is_authorized_idempotent_and_attempt_limited(facade, approvals, fixture_case):
    confirmed = _confirm(facade, approvals, fixture_case)
    first = _verify(facade, approvals, fixture_case, confirmed.task_id, corrected=False)
    second = _verify(facade, approvals, fixture_case, confirmed.task_id, corrected=True)
    assert first.outcome is VerificationOutcome.FAIL
    assert second.outcome is VerificationOutcome.PASS
    assert first.spec_hash == second.spec_hash == confirmed.spec_hash
    assert second.attempt == 2
    assert facade.get_result(WORKSPACE_HANDLE, confirmed.task_id, 1).receipt_hash == first.receipt_hash
    assert facade.get_receipt(WORKSPACE_HANDLE, confirmed.task_id, 2).receipt.receipt_hash == second.receipt_hash
    assert facade.replay_receipt(WORKSPACE_HANDLE, confirmed.task_id, 2).valid is True

    with pytest.raises(HeadlessError) as error:
        facade.prepare_report_verification(
            WORKSPACE_HANDLE, confirmed.task_id, report_json(fixture_case, corrected=True)
        )
    assert error.value.code == "ATTEMPT_NOT_ALLOWED"


def test_workspace_handles_cannot_cross_read(facade, approvals, fixture_case):
    confirmed = _confirm(facade, approvals, fixture_case)
    _verify(facade, approvals, fixture_case, confirmed.task_id, corrected=False)
    with pytest.raises(HeadlessError) as error:
        facade.get_receipt(SECOND_WORKSPACE_HANDLE, confirmed.task_id, 1)
    assert error.value.code == "UNKNOWN_ATTEMPT"


def test_challenge_digest_binds_workspace_task_scope_and_attempt(facade, approvals, fixture_case):
    first_candidate = facade.draft_task(WORKSPACE_HANDLE, "核验固定测试报表")
    second_candidate = facade.draft_task(SECOND_WORKSPACE_HANDLE, "核验固定测试报表")
    first_confirmation = facade.prepare_task_confirmation(WORKSPACE_HANDLE, first_candidate.candidate)
    second_confirmation = facade.prepare_task_confirmation(
        SECOND_WORKSPACE_HANDLE, second_candidate.candidate
    )
    assert first_confirmation.payload_digest != second_confirmation.payload_digest

    approvals.approve(WORKSPACE_HANDLE, first_confirmation.challenge_id)
    confirmed = facade.confirm_task(WORKSPACE_HANDLE, first_confirmation.challenge_id)
    report_challenge = facade.prepare_report_verification(
        WORKSPACE_HANDLE,
        confirmed.task_id,
        report_json(fixture_case, corrected=False),
    )
    assert report_challenge.task_spec_hash == confirmed.spec_hash
    with pytest.raises(HeadlessError) as error:
        facade.verify_report(SECOND_WORKSPACE_HANDLE, report_challenge.challenge_id)
    assert error.value.code == "UNKNOWN_CHALLENGE"


def test_requests_reject_paths_instead_of_interpreting_them(facade):
    with pytest.raises(HeadlessError) as error:
        facade.get_receipt("../../private", "task-1", 1)
    assert error.value.code == "UNKNOWN_WORKSPACE"


def test_challenge_state_survives_new_facade_instance(registry_path, fixture_case):
    first = HeadlessTrustReceiptFacade(WorkspaceRegistry.load(registry_path))
    candidate = first.draft_task(WORKSPACE_HANDLE, "核验测试")
    challenge = first.prepare_task_confirmation(WORKSPACE_HANDLE, candidate.candidate)
    approvals = LocalApprovalController(WorkspaceRegistry.load(registry_path))
    approvals.approve(WORKSPACE_HANDLE, challenge.challenge_id)

    restarted = HeadlessTrustReceiptFacade(WorkspaceRegistry.load(registry_path))
    confirmed = restarted.confirm_task(WORKSPACE_HANDLE, challenge.challenge_id)
    assert confirmed.state == "CONFIRMED"
    assert approvals.inspect(
        WORKSPACE_HANDLE, challenge.challenge_id
    ).authorization_state is AuthorizationState.CONSUMED


def test_live_workspace_without_model_configuration_is_blocked(tmp_path, monkeypatch):
    for name in ("OPENAI_API_KEY", "OPENAI_MODEL", "DEEPSEEK_API_KEY", "DEEPSEEK_MODEL"):
        monkeypatch.delenv(name, raising=False)
    project = tmp_path / "project"
    (project / "fixtures" / "m1").mkdir(parents=True)
    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps(
            {
                "config_version": "1.0",
                "workspaces": {
                    WORKSPACE_HANDLE: {
                        "directory": str(tmp_path / "live"),
                        "project_root": str(project),
                        "profile": "LIVE_READ_ONLY",
                        "ai_provider": "deepseek",
                        "evidence_provider": "rpc",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    live = HeadlessTrustReceiptFacade(WorkspaceRegistry.load(path))
    with pytest.raises(HeadlessError) as error:
        live.draft_task(WORKSPACE_HANDLE, "live task")
    assert error.value.status == "BLOCKED"
    assert "DEEPSEEK" not in error.value.safe_message


def test_live_verification_without_rpc_is_blocked_without_consuming_attempt(
    tmp_path, monkeypatch, fixture_case
):
    monkeypatch.delenv("ETH_RPC_URL", raising=False)
    project = tmp_path / "project"
    (project / "fixtures" / "m1").mkdir(parents=True)
    workspace = tmp_path / "live"
    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps(
            {
                "config_version": "1.0",
                "workspaces": {
                    WORKSPACE_HANDLE: {
                        "directory": str(workspace),
                        "project_root": str(project),
                        "profile": "LIVE_READ_ONLY",
                        "ai_provider": "deepseek",
                        "evidence_provider": "rpc",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    repository = SQLiteRepository(workspace / "workspace.db")
    repository.add_task(fixture_case.task_spec)
    live = HeadlessTrustReceiptFacade(WorkspaceRegistry.load(path))
    challenge = live.prepare_report_verification(
        WORKSPACE_HANDLE,
        fixture_case.task_spec.task_id,
        report_json(fixture_case, corrected=True),
    )
    LocalApprovalController(WorkspaceRegistry.load(path)).approve(WORKSPACE_HANDLE, challenge.challenge_id)
    with pytest.raises(HeadlessError) as error:
        live.verify_report(WORKSPACE_HANDLE, challenge.challenge_id)
    assert error.value.code == "RPC_CONFIGURATION_MISSING"
    assert repository.list_attempts(fixture_case.task_spec.task_id) == ()


def test_persisted_in_flight_attempt_blocks_new_challenge(facade, approvals, fixture_case, registry_path):
    confirmed = _confirm(facade, approvals, fixture_case)
    registry = WorkspaceRegistry.load(registry_path)
    repository = SQLiteRepository(registry.get(WORKSPACE_HANDLE).directory / "workspace.db")
    assert repository.request_attempt(confirmed.task_id) == 1

    with pytest.raises(HeadlessError) as error:
        facade.prepare_report_verification(
            WORKSPACE_HANDLE, confirmed.task_id, report_json(fixture_case, corrected=False)
        )
    assert error.value.code == "ATTEMPT_NOT_ALLOWED"
    assert "IN_FLIGHT" in error.value.safe_message
    assert repository.list_attempts(confirmed.task_id) == ()


def test_concurrent_authorized_challenges_reserve_only_one_attempt(
    facade, approvals, fixture_case, registry_path
):
    confirmed = _confirm(facade, approvals, fixture_case)
    report = report_json(fixture_case, corrected=False)
    challenges = [
        facade.prepare_report_verification(WORKSPACE_HANDLE, confirmed.task_id, report)
        for _ in range(2)
    ]
    for challenge in challenges:
        approvals.approve(WORKSPACE_HANDLE, challenge.challenge_id)

    def verify(challenge):
        try:
            return facade.verify_report(WORKSPACE_HANDLE, challenge.challenge_id)
        except HeadlessError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(verify, challenges))
    successes = [item for item in results if not isinstance(item, HeadlessError)]
    failures = [item for item in results if isinstance(item, HeadlessError)]
    assert len(successes) == len(failures) == 1
    assert failures[0].code == "ATTEMPT_STATE_CHANGED"

    registry = WorkspaceRegistry.load(registry_path)
    repository = SQLiteRepository(registry.get(WORKSPACE_HANDLE).directory / "workspace.db")
    attempts = repository.list_attempts(confirmed.task_id)
    assert len(attempts) == 1
    assert attempts[0].submission.attempt == 1


def test_missing_receipt_blocks_second_attempt(facade, approvals, fixture_case, registry_path):
    confirmed = _confirm(facade, approvals, fixture_case)
    _verify(facade, approvals, fixture_case, confirmed.task_id, corrected=False)
    registry = WorkspaceRegistry.load(registry_path)
    receipt = registry.get(WORKSPACE_HANDLE).directory / "receipts" / confirmed.task_id / "attempt-1.json"
    receipt.unlink()

    with pytest.raises(HeadlessError) as error:
        facade.prepare_report_verification(
            WORKSPACE_HANDLE, confirmed.task_id, report_json(fixture_case, corrected=True)
        )
    assert error.value.code == "ATTEMPT_NOT_ALLOWED"
    assert "MISSING_RECEIPT" in error.value.safe_message
