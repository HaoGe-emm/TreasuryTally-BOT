"""Bounded retry helpers for read-only, idempotent operations."""

from __future__ import annotations

import time
from collections.abc import Callable


def read_with_retry[T](
    operation: Callable[[], T],
    *,
    retries: int = 2,
    initial_backoff_seconds: float = 0.25,
    retryable: Callable[[Exception], bool] | None = None,
) -> T:
    """Run a read at most once plus ``retries`` additional attempts."""
    if retries < 0 or retries > 2:
        raise ValueError("read retries must be between 0 and 2")
    predicate = retryable or (lambda _exc: True)
    for attempt in range(retries + 1):
        try:
            return operation()
        except Exception as exc:
            if attempt == retries or not predicate(exc):
                raise
            time.sleep(initial_backoff_seconds * (2**attempt))
    raise AssertionError("retry loop exhausted without returning or raising")
