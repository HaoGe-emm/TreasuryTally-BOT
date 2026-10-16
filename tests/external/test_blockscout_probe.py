from __future__ import annotations

import pytest

from trust_receipt.chain.blockscout import probe_blockscout
from trust_receipt.integrations.config import M0Settings

from .conftest import require_configuration

pytestmark = [pytest.mark.external, pytest.mark.asyncio]


async def test_blockscout_mcp_initializes_and_reads_same_transaction(m0_settings: M0Settings) -> None:
    missing = []
    if m0_settings.blockscout_pro_api_key is None:
        missing.append("BLOCKSCOUT_PRO_API_KEY")
    if m0_settings.test_transfer_tx_hash is None:
        missing.append("TEST_TRANSFER_TX_HASH")
    require_configuration(missing, "Blockscout MCP")
    result = await probe_blockscout(
        m0_settings.blockscout_mcp_url,
        chain_id=m0_settings.chain_id,
        transaction_hash=m0_settings.test_transfer_tx_hash or "",
        timeout_seconds=m0_settings.rpc_timeout_seconds,
    )
    assert "get_transaction_info" in result.tool_names
    assert result.structured_result
    assert isinstance(result.pagination_complete, bool)
    assert result.elapsed_ms <= 120_000
