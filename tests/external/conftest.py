from __future__ import annotations

from collections.abc import Sequence

import pytest

from trust_receipt.integrations.config import M0Settings


@pytest.fixture(scope="session")
def m0_settings() -> M0Settings:
    return M0Settings.load()


def require_configuration(missing: Sequence[str], probe: str) -> None:
    if missing:
        pytest.skip(f"M0 {probe} blocked by missing configuration: {', '.join(missing)}")
