from __future__ import annotations

import pytest

from trust_receipt.chain.rpc import EvmRpcProbe
from trust_receipt.integrations.config import M0Settings
from trust_receipt.reputation.erc8004 import (
    ChainWriteState,
    read_confirmed_neutral_feedback,
    verify_registries,
)

from .conftest import require_configuration

pytestmark = pytest.mark.external


def _registry_overrides(settings: M0Settings) -> dict[int, dict[str, str]]:
    return {
        settings.chain_id: {
            "IDENTITY": settings.identity_registry_address or "",
            "REPUTATION": settings.reputation_registry_address or "",
            "VALIDATION": settings.validation_registry_address or "",
        }
    }


def test_erc8004_registries_have_code_and_identity_is_readable(m0_settings: M0Settings) -> None:
    require_configuration(m0_settings.missing_for_erc8004_read(), "ERC-8004 read")
    rpc = EvmRpcProbe(
        m0_settings.rpc_url_value(),
        expected_chain_id=m0_settings.chain_id,
        timeout_seconds=m0_settings.rpc_timeout_seconds,
    )
    result = verify_registries(
        rpc,
        identity_registry=m0_settings.identity_registry_address or "",
        reputation_registry=m0_settings.reputation_registry_address or "",
        validation_registry=m0_settings.validation_registry_address or "",
        service_id=m0_settings.agent0_service_id or "",
    )
    assert result.owner
    assert result.agent_uri


def test_erc8004_neutral_feedback_is_confirmed_and_read_back(m0_settings: M0Settings) -> None:
    require_configuration(m0_settings.missing_for_erc8004_feedback_read(), "ERC-8004 feedback read")
    result = read_confirmed_neutral_feedback(
        chain_id=m0_settings.chain_id,
        rpc_url=m0_settings.rpc_url_value(),
        service_id=m0_settings.agent0_service_id or "",
        reviewer_address=m0_settings.reviewer_address or "",
        feedback_index=m0_settings.feedback_index or 0,
        transaction_hash=m0_settings.feedback_transaction_hash or "",
        registry_overrides=_registry_overrides(m0_settings),
    )
    assert result.state is ChainWriteState.CONFIRMED
    assert result.transaction_hash
    assert result.block_number is not None
    assert result.feedback_index is not None
