from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from trust_receipt.chain.blockscout import _mcp_endpoint, _pagination_complete, _tool_error_code
from trust_receipt.chain.rpc import TRANSFER_TOPIC, EvmRpcProbe
from trust_receipt.integrations.config import M0Settings
from trust_receipt.integrations.errors import IntegrationError, IntegrationErrorCode
from trust_receipt.integrations.retry import read_with_retry
from trust_receipt.reputation.erc8004 import _write_error_code


def test_empty_configuration_reports_explicit_blockers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in M0Settings.ENV_TO_FIELD:
        monkeypatch.delenv(name, raising=False)
    settings = M0Settings.load(tmp_path / "missing.env")
    assert "ETH_RPC_URL" in settings.missing_for_rpc()
    assert "AGENT0_EXPECTED_OWNER" in settings.missing_for_agent0()
    assert "M0_ENABLE_WRITES=true" in settings.missing_for_erc8004_write()


def test_invalid_block_range_is_rejected(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_FROM_BLOCK=20\nTEST_TO_BLOCK=10\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="TEST_TO_BLOCK"):
        M0Settings.load(env_file)


def test_read_retry_allows_only_two_retries() -> None:
    attempts = 0

    def fail() -> None:
        nonlocal attempts
        attempts += 1
        raise OSError("offline")

    with pytest.raises(OSError, match="offline"):
        read_with_retry(fail, initial_backoff_seconds=0)
    assert attempts == 3
    with pytest.raises(ValueError, match="between 0 and 2"):
        read_with_retry(lambda: None, retries=3)


def test_blockscout_endpoint_and_pagination_detection() -> None:
    assert _mcp_endpoint("http://localhost:8000") == "http://localhost:8000/mcp"
    assert _mcp_endpoint("http://localhost:8000/mcp") == "http://localhost:8000/mcp"
    assert _pagination_complete({"data": [1], "next_page_params": None})
    assert not _pagination_complete({"next_page_params": {"page": 2}})


def test_write_failures_keep_unknown_distinct_from_known_failures() -> None:
    assert _write_error_code(RuntimeError("insufficient funds")) is IntegrationErrorCode.INSUFFICIENT_FUNDS
    assert _write_error_code(RuntimeError("execution reverted")) is IntegrationErrorCode.TRANSACTION_REVERTED
    assert _write_error_code(TimeoutError()) is IntegrationErrorCode.TRANSACTION_UNKNOWN


def test_rpc_timeout_and_wrong_network_remain_inconclusive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("trust_receipt.integrations.retry.time.sleep", lambda _seconds: None)
    probe = object.__new__(EvmRpcProbe)
    probe._expected_chain_id = 11_155_111
    probe._web3 = SimpleNamespace(eth=SimpleNamespace(chain_id=1))
    with pytest.raises(IntegrationError) as wrong_network:
        probe.chain_id()
    assert wrong_network.value.code is IntegrationErrorCode.WRONG_NETWORK
    assert wrong_network.value.inconclusive

    def timeout() -> None:
        raise TimeoutError

    with pytest.raises(IntegrationError) as timed_out:
        probe._read(timeout)
    assert timed_out.value.code is IntegrationErrorCode.TIMEOUT
    assert timed_out.value.inconclusive


def test_blockscout_auth_and_rate_limit_errors_are_distinct() -> None:
    unauthorized = SimpleNamespace(content=[SimpleNamespace(text="Unauthorized API key")])
    rate_limited = SimpleNamespace(content=[SimpleNamespace(text="429 Too Many Requests")])
    assert _tool_error_code(unauthorized) is IntegrationErrorCode.AUTHENTICATION
    assert _tool_error_code(rate_limited) is IntegrationErrorCode.RATE_LIMITED


def test_transfer_topic_is_rpc_hex() -> None:
    assert TRANSFER_TOPIC.startswith("0x")
    assert len(TRANSFER_TOPIC) == 66
