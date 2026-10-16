"""Stable error vocabulary for untrusted external systems."""

from __future__ import annotations

from enum import StrEnum


class IntegrationErrorCode(StrEnum):
    CONFIGURATION = "CONFIGURATION"
    AUTHENTICATION = "AUTHENTICATION"
    TIMEOUT = "TIMEOUT"
    UNAVAILABLE = "UNAVAILABLE"
    HISTORICAL_DATA_UNAVAILABLE = "HISTORICAL_DATA_UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    WRONG_NETWORK = "WRONG_NETWORK"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    EMPTY_RESULT = "EMPTY_RESULT"
    INCOMPLETE_RESULT = "INCOMPLETE_RESULT"
    CONTRACT_MISMATCH = "CONTRACT_MISMATCH"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    TRANSACTION_REVERTED = "TRANSACTION_REVERTED"
    TRANSACTION_UNKNOWN = "TRANSACTION_UNKNOWN"


class IntegrationError(RuntimeError):
    """An external failure that must map to insufficient evidence, not blame."""

    def __init__(self, code: IntegrationErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.inconclusive = True
