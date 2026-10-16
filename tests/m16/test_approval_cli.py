from __future__ import annotations

from trust_receipt.headless.cli import main
from trust_receipt.headless.config import WorkspaceRegistry
from trust_receipt.headless.facade import HeadlessTrustReceiptFacade

from .conftest import WORKSPACE_HANDLE


def test_approval_cli_requires_exact_interactive_phrase(registry_path, monkeypatch, capsys):
    facade = HeadlessTrustReceiptFacade(WorkspaceRegistry.load(registry_path))
    candidate = facade.draft_task(WORKSPACE_HANDLE, "核验测试")
    challenge = facade.prepare_task_confirmation(WORKSPACE_HANDLE, candidate.candidate)
    arguments = [
        "--config",
        str(registry_path),
        "approve",
        "--workspace",
        WORKSPACE_HANDLE,
        "--challenge",
        challenge.challenge_id,
    ]
    monkeypatch.setattr("builtins.input", lambda _prompt: "APPROVE something-else")
    assert main(arguments) == 1
    assert "CANCELLED" in capsys.readouterr().out

    monkeypatch.setattr("builtins.input", lambda _prompt: f"APPROVE {challenge.challenge_id}")
    assert main(arguments) == 0
    assert "APPROVED" in capsys.readouterr().out
