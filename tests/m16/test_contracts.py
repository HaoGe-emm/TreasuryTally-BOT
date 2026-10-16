import sqlite3
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from trust_receipt.headless import AuthorizationAction, AuthorizationChallenge, AuthorizationState
from trust_receipt.headless.authorization import AuthorizationStore


def test_authorization_challenge_accepts_only_opaque_workspace_handle():
    challenge = AuthorizationChallenge(
        challenge_id="ch_" + "a" * 32,
        workspace_handle="ws_0123456789abcdef",
        action=AuthorizationAction.CONFIRM_TASK,
        payload_digest="0x" + "b" * 64,
        summary="Confirm the immutable task candidate.",
        authorization_state=AuthorizationState.PENDING,
        expires_at=datetime.now(UTC),
    )
    assert challenge.interface_version == "1.0"

    with pytest.raises(ValidationError):
        AuthorizationChallenge.model_validate(
            {**challenge.model_dump(), "workspace_handle": "../../private"}
        )


def test_challenge_attempt_cannot_exceed_repository_limit():
    with pytest.raises(ValidationError):
        AuthorizationChallenge(
            challenge_id="ch_" + "a" * 32,
            workspace_handle="ws_0123456789abcdef",
            action=AuthorizationAction.VERIFY_REPORT,
            payload_digest="0x" + "b" * 64,
            task_id="task-1",
            attempt=3,
            summary="Reject a third attempt.",
            authorization_state=AuthorizationState.PENDING,
            expires_at=datetime.now(UTC),
        )


def test_authorization_store_migrates_pre_scope_binding_database(tmp_path):
    database = tmp_path / "authorization.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """CREATE TABLE authorization_challenges (
                challenge_id TEXT PRIMARY KEY, action TEXT NOT NULL, payload_digest TEXT NOT NULL,
                task_id TEXT, attempt INTEGER, summary TEXT NOT NULL, state TEXT NOT NULL,
                expires_at TEXT NOT NULL, payload_json TEXT NOT NULL, result_json TEXT, approved_at TEXT
            )"""
        )
    AuthorizationStore(database, "ws_0123456789abcdef")
    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(authorization_challenges)")}
    assert "task_spec_hash" in columns
