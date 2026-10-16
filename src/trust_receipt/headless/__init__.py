"""Versioned, UI-independent boundary for trusted local clients."""

from trust_receipt.headless.contracts import (
    AttemptFindingView,
    AttemptResultView,
    AuthorizationAction,
    AuthorizationChallenge,
    AuthorizationState,
    ConfirmedTaskView,
    HeadlessProfile,
    ReceiptReplayView,
    ReceiptView,
    TaskCandidateView,
)
from trust_receipt.headless.ports import HeadlessTrustReceiptPort

__all__ = [
    "AttemptFindingView",
    "AttemptResultView",
    "AuthorizationAction",
    "AuthorizationChallenge",
    "AuthorizationState",
    "ConfirmedTaskView",
    "HeadlessProfile",
    "HeadlessTrustReceiptPort",
    "ReceiptReplayView",
    "ReceiptView",
    "TaskCandidateView",
]
