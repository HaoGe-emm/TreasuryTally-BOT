"""Consumer-facing protocol frozen for M15 and MCP adapters."""

from typing import Protocol

from trust_receipt.agents import TaskSpecCandidate
from trust_receipt.headless.contracts import (
    AttemptResultView,
    AuthorizationChallenge,
    ConfirmedTaskView,
    ReceiptReplayView,
    ReceiptView,
    TaskCandidateView,
)


class HeadlessTrustReceiptPort(Protocol):
    def draft_task(self, workspace_handle: str, user_request: str) -> TaskCandidateView: ...

    def prepare_task_confirmation(
        self, workspace_handle: str, candidate: TaskSpecCandidate
    ) -> AuthorizationChallenge: ...

    def confirm_task(self, workspace_handle: str, challenge_id: str) -> ConfirmedTaskView: ...

    def prepare_report_verification(
        self, workspace_handle: str, task_id: str, report_json: str
    ) -> AuthorizationChallenge: ...

    def verify_report(self, workspace_handle: str, challenge_id: str) -> AttemptResultView: ...

    def get_result(self, workspace_handle: str, task_id: str, attempt: int) -> AttemptResultView: ...

    def get_receipt(self, workspace_handle: str, task_id: str, attempt: int) -> ReceiptView: ...

    def replay_receipt(self, workspace_handle: str, task_id: str, attempt: int) -> ReceiptReplayView: ...
