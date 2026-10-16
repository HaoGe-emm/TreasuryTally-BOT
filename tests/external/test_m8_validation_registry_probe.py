from __future__ import annotations

import pytest

from trust_receipt.chain.rpc import EvmRpcProbe
from trust_receipt.commitments import ValidationRegistryReadProbe
from trust_receipt.integrations.config import M0Settings

from .conftest import require_configuration

pytestmark = pytest.mark.external


def test_m8_validation_registry_read_interface_on_sepolia(m0_settings: M0Settings) -> None:
    require_configuration(m0_settings.missing_for_erc8004_read(), "M8 Validation Registry read")
    rpc = EvmRpcProbe(
        m0_settings.rpc_url_value(),
        expected_chain_id=m0_settings.chain_id,
        timeout_seconds=m0_settings.rpc_timeout_seconds,
    )
    result = ValidationRegistryReadProbe(
        rpc,
        validation_registry=m0_settings.validation_registry_address or "",
        expected_identity_registry=m0_settings.identity_registry_address or "",
    ).probe(m0_settings.agent0_service_id or "")

    assert result.chain_id == 11_155_111
    assert result.existing_request_count >= 0
    assert result.supports_task_commitment_anchor is False
