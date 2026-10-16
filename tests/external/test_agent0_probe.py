from __future__ import annotations

import pytest

from trust_receipt.integrations.config import M0Settings
from trust_receipt.reputation.agent0 import probe_agent_identity

from .conftest import require_configuration

pytestmark = pytest.mark.external


def test_agent0_reads_team_controlled_service_identity(m0_settings: M0Settings) -> None:
    require_configuration(m0_settings.missing_for_agent0(), "Agent0")
    result = probe_agent_identity(
        chain_id=m0_settings.chain_id,
        rpc_url=m0_settings.rpc_url_value(),
        service_id=m0_settings.agent0_service_id or "",
        timeout_seconds=m0_settings.rpc_timeout_seconds,
        expected_owner=m0_settings.agent0_expected_owner,
    )
    assert result.service_id == m0_settings.agent0_service_id
    assert result.owner.lower() == (m0_settings.agent0_expected_owner or "").lower()
