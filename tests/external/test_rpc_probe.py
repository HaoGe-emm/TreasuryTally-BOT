from __future__ import annotations

import pytest

from trust_receipt.chain.rpc import EvmRpcProbe
from trust_receipt.integrations.config import M0Settings

from .conftest import require_configuration

pytestmark = pytest.mark.external


def test_sepolia_rpc_returns_known_erc20_transfer(m0_settings: M0Settings) -> None:
    require_configuration(m0_settings.missing_for_rpc(), "RPC")
    probe = EvmRpcProbe(
        m0_settings.rpc_url_value(),
        expected_chain_id=m0_settings.chain_id,
        timeout_seconds=m0_settings.rpc_timeout_seconds,
    )
    result = probe.probe_transfer(
        token_address=m0_settings.test_token_address or "",
        from_block=m0_settings.test_from_block or 0,
        to_block=m0_settings.test_to_block or 0,
        expected_transaction_hash=m0_settings.test_transfer_tx_hash or "",
    )
    assert result.chain_id == 11_155_111
    assert result.transfer.event_key == (
        result.chain_id,
        result.transfer.transaction_hash,
        result.transfer.log_index,
    )
    assert int(result.transfer.amount_base_units) >= 0
    assert result.transfer.source == "rpc"
