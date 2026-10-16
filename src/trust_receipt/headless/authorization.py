"""Persistent one-time approvals that are deliberately not exposed through MCP."""

from __future__ import annotations

import json
import secrets
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from trust_receipt.headless.config import WorkspaceRegistry
from trust_receipt.headless.contracts import AuthorizationAction, AuthorizationChallenge, AuthorizationState
from trust_receipt.headless.errors import authorization_required, rejected


@dataclass(frozen=True)
class StoredChallenge:
    challenge: AuthorizationChallenge
    payload: dict
    result: dict | None
    approved_at: datetime | None


class AuthorizationStore:
    def __init__(self, database: Path, workspace_handle: str) -> None:
        database.parent.mkdir(parents=True, exist_ok=True)
        self._database = str(database)
        self._workspace_handle = workspace_handle
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS authorization_challenges (
                    challenge_id TEXT PRIMARY KEY,
                    action TEXT NOT NULL,
                    payload_digest TEXT NOT NULL,
                    task_id TEXT,
                    task_spec_hash TEXT,
                    attempt INTEGER,
                    summary TEXT NOT NULL,
                    state TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    result_json TEXT,
                    approved_at TEXT
                )"""
            )
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(authorization_challenges)").fetchall()
            }
            if "task_spec_hash" not in columns:
                connection.execute("ALTER TABLE authorization_challenges ADD COLUMN task_spec_hash TEXT")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database)
        connection.row_factory = sqlite3.Row
        return connection

    def create(
        self,
        *,
        action: AuthorizationAction,
        payload_digest: str,
        payload: dict,
        summary: str,
        task_id: str | None = None,
        task_spec_hash: str | None = None,
        attempt: int | None = None,
        ttl: timedelta = timedelta(minutes=15),
    ) -> AuthorizationChallenge:
        challenge = AuthorizationChallenge(
            challenge_id="ch_" + secrets.token_hex(16),
            workspace_handle=self._workspace_handle,
            action=action,
            payload_digest=payload_digest,
            task_id=task_id,
            task_spec_hash=task_spec_hash,
            attempt=attempt,
            summary=summary,
            authorization_state=AuthorizationState.PENDING,
            expires_at=datetime.now(UTC) + ttl,
        )
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """INSERT INTO authorization_challenges(
                    challenge_id, action, payload_digest, task_id, task_spec_hash, attempt, summary, state,
                    expires_at, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    challenge.challenge_id,
                    challenge.action.value,
                    challenge.payload_digest,
                    challenge.task_id,
                    challenge.task_spec_hash,
                    challenge.attempt,
                    challenge.summary,
                    challenge.authorization_state.value,
                    challenge.expires_at.isoformat(),
                    json.dumps(payload, sort_keys=True, separators=(",", ":")),
                ),
            )
        return challenge

    def get(self, challenge_id: str) -> StoredChallenge:
        with closing(self._connect()) as connection, connection:
            row = connection.execute(
                "SELECT * FROM authorization_challenges WHERE challenge_id = ?", (challenge_id,)
            ).fetchone()
            if row is None:
                raise rejected("UNKNOWN_CHALLENGE", "Unknown authorization challenge.")
            state = AuthorizationState(row["state"])
            expires_at = datetime.fromisoformat(row["expires_at"])
            if state in {AuthorizationState.PENDING, AuthorizationState.APPROVED} and expires_at <= datetime.now(UTC):
                state = AuthorizationState.EXPIRED
                connection.execute(
                    "UPDATE authorization_challenges SET state = ? WHERE challenge_id = ?",
                    (state.value, challenge_id),
                )
        challenge = AuthorizationChallenge(
            challenge_id=row["challenge_id"],
            workspace_handle=self._workspace_handle,
            action=AuthorizationAction(row["action"]),
            payload_digest=row["payload_digest"],
            task_id=row["task_id"],
            task_spec_hash=row["task_spec_hash"],
            attempt=row["attempt"],
            summary=row["summary"],
            authorization_state=state,
            expires_at=expires_at,
        )
        return StoredChallenge(
            challenge=challenge,
            payload=json.loads(row["payload_json"]),
            result=json.loads(row["result_json"]) if row["result_json"] else None,
            approved_at=datetime.fromisoformat(row["approved_at"]) if row["approved_at"] else None,
        )

    def approve(self, challenge_id: str) -> AuthorizationChallenge:
        stored = self.get(challenge_id)
        if stored.challenge.authorization_state is AuthorizationState.EXPIRED:
            raise rejected("EXPIRED_CHALLENGE", "Authorization challenge has expired.")
        if stored.challenge.authorization_state is AuthorizationState.CONSUMED:
            return stored.challenge
        approved_at = datetime.now(UTC)
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """UPDATE authorization_challenges SET state = ?, approved_at = ?
                   WHERE challenge_id = ? AND state IN (?, ?)""",
                (
                    AuthorizationState.APPROVED.value,
                    approved_at.isoformat(),
                    challenge_id,
                    AuthorizationState.PENDING.value,
                    AuthorizationState.APPROVED.value,
                ),
            )
        return self.get(challenge_id).challenge

    def require_approved(self, challenge_id: str, action: AuthorizationAction) -> StoredChallenge:
        stored = self.get(challenge_id)
        if stored.challenge.action is not action:
            raise rejected("CHALLENGE_ACTION_MISMATCH", "Authorization challenge is for another action.")
        if stored.challenge.authorization_state is AuthorizationState.PENDING:
            raise authorization_required()
        if stored.challenge.authorization_state is AuthorizationState.EXPIRED:
            raise rejected("EXPIRED_CHALLENGE", "Authorization challenge has expired.")
        return stored

    def consume(self, challenge_id: str, result: dict) -> None:
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """UPDATE authorization_challenges SET state = ?, result_json = ?
                   WHERE challenge_id = ? AND state = ?""",
                (
                    AuthorizationState.CONSUMED.value,
                    json.dumps(result, sort_keys=True, separators=(",", ":")),
                    challenge_id,
                    AuthorizationState.APPROVED.value,
                ),
            )
            if cursor.rowcount != 1:
                raise rejected("CHALLENGE_STATE_CHANGED", "Authorization challenge is no longer consumable.")


class LocalApprovalController:
    """Operator-only boundary; intentionally absent from HeadlessTrustReceiptPort and MCP."""

    def __init__(self, registry: WorkspaceRegistry) -> None:
        self._registry = registry

    def _store(self, workspace_handle: str) -> AuthorizationStore:
        try:
            config = self._registry.get(workspace_handle)
        except KeyError:
            raise rejected("UNKNOWN_WORKSPACE", "Unknown workspace handle.") from None
        return AuthorizationStore(config.directory / "authorization.db", workspace_handle)

    def inspect(self, workspace_handle: str, challenge_id: str) -> AuthorizationChallenge:
        return self._store(workspace_handle).get(challenge_id).challenge

    def approve(self, workspace_handle: str, challenge_id: str) -> AuthorizationChallenge:
        return self._store(workspace_handle).approve(challenge_id)
