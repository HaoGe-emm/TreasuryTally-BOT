from __future__ import annotations

from types import SimpleNamespace

import pytest
from web3.exceptions import Web3RPCError

from trust_receipt.chain import RpcReferenceEvidenceProvider
from trust_receipt.chain.rpc import EvmRpcProbe
from trust_receipt.integrations.errors import IntegrationError, IntegrationErrorCode
from trust_receipt.verification import verify_submission

SECRET = "https://private.invalid/?api_key=secret-sentinel"


def rpc_error(response=None):
    return Web3RPCError(SECRET, rpc_response=response)


def historical_error():
    return rpc_error({"error": {"code": 4444, "message": f"history pruned unavailable {SECRET}"}})


@pytest.fixture
def probe(monkeypatch):
    monkeypatch.setattr("trust_receipt.integrations.retry.time.sleep", lambda _seconds: None)
    return object.__new__(EvmRpcProbe)


def test_history_denial_once_and_no_vendor_context(probe):
    calls = 0

    def read():
        nonlocal calls
        calls += 1
        raise historical_error()

    with pytest.raises(IntegrationError) as caught:
        probe._read(read, method="eth_getLogs")
    assert calls == 1
    error = caught.value
    assert error.code is IntegrationErrorCode.HISTORICAL_DATA_UNAVAILABLE
    assert error.inconclusive
    assert error.__cause__ is None and error.__context__ is None
    assert SECRET not in str(error)


@pytest.mark.parametrize(
    "response",
    [
        None,
        [],
        {"error": None},
        {"error": []},
        {"error": "historical state unavailable"},
        {"error": {"code": "4444", "message": "historical state unavailable"}},
        {"error": {"code": 4444, "message": None}},
        {"error": {"code": 4444, "message": "unrelated failure"}},
        {"error": {"code": 4444, "message": "historical state query invalid"}},
        {"error": {"code": 4444, "message": "history pruned"}},
        {"error": {"code": 4444, "message": "history unavailable"}},
        {"error": {"code": 4444, "message": "pruned unavailable"}},
        {"error": {"code": 4444, "message": "prehistory unpruned unavailable"}},
        {"error": {"code": 1234, "message": "historical state unavailable"}},
    ],
)
def test_unknown_or_malformed_response_is_not_history(probe, response):
    calls = 0

    def read():
        nonlocal calls
        calls += 1
        raise rpc_error(response)

    with pytest.raises(IntegrationError) as caught:
        probe._read(read, method="eth_getLogs")
    assert calls == 3
    assert caught.value.code is IntegrationErrorCode.UNAVAILABLE
    assert SECRET not in str(caught.value)


@pytest.mark.parametrize("method", [None, "eth_call", "eth_getTransactionReceipt"])
def test_same_code_other_methods_do_not_gain_history_semantics(probe, method):
    calls = 0

    def read():
        nonlocal calls
        calls += 1
        raise historical_error()

    with pytest.raises(IntegrationError) as caught:
        probe._read(read, method=method)
    assert calls == 3
    assert caught.value.code is IntegrationErrorCode.UNAVAILABLE


@pytest.mark.parametrize(
    "error, code",
    [
        (TimeoutError(), IntegrationErrorCode.TIMEOUT),
        (OSError("offline"), IntegrationErrorCode.UNAVAILABLE),
    ],
)
def test_transient_retries_unchanged(probe, error, code):
    calls = 0

    def read():
        nonlocal calls
        calls += 1
        raise error

    with pytest.raises(IntegrationError) as caught:
        probe._read(read, method="eth_getLogs")
    assert calls == 3
    assert caught.value.code is code


def wire_probe(probe, task, logs):
    probe._expected_chain_id = task.chain_id
    probe._web3 = SimpleNamespace(
        eth=SimpleNamespace(
            chain_id=task.chain_id,
            block_number=task.end_block + 10,
            contract=lambda *_args, **_kwargs: SimpleNamespace(
                functions=SimpleNamespace(decimals=lambda: SimpleNamespace(call=lambda: 18))
            ),
            get_logs=logs,
        )
    )
    return RpcReferenceEvidenceProvider(
        "https://unused.invalid", expected_chain_id=task.chain_id, rpc_probe=probe, page_size_blocks=1
    )


def test_later_page_denial_cannot_become_complete(probe, vertical_case):
    calls = 0

    def logs(_query):
        nonlocal calls
        calls += 1
        if calls == 1:
            return []
        raise historical_error()

    task = vertical_case.task_spec
    assert task.end_block > task.start_block
    provider = wire_probe(probe, task, logs)
    evidence = provider.fetch(task)
    assert calls == 2
    assert not evidence.evidence_sufficient
    assert not evidence.streams[0].source.complete
    assert evidence.streams[0].pages == ()
    assert evidence.streams[0].source.details["error_code"] == "HISTORICAL_DATA_UNAVAILABLE"
    assert SECRET not in evidence.model_dump_json()
    assert SECRET not in str(provider.diagnostics)
    result = verify_submission(
        task,
        vertical_case.submission,
        evidence,
        run_id="history-denial",
        started_at=task.confirmed_at,
        finished_at=task.confirmed_at,
    )
    assert result.outcome.value == "INCONCLUSIVE"
    assert not result.reference_complete and not result.evidence_sufficient
    assert result.calculated_total_base_units is None and result.calculated_count is None


def test_successful_empty_pages_remain_complete(probe, vertical_case):
    provider = wire_probe(probe, vertical_case.task_spec, lambda _query: [])
    evidence = provider.fetch(vertical_case.task_spec)
    assert evidence.evidence_sufficient
    assert evidence.streams[0].source.complete
    assert all(not page.transfers for page in evidence.streams[0].pages)
