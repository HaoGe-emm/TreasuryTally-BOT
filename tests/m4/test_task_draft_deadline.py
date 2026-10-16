from __future__ import annotations

import asyncio
import json
import time

import httpx
import pytest

from trust_receipt.agents import DeepSeekStructuredOutputAdapter, OpenAIStructuredOutputAdapter
from trust_receipt.agents.models import TaskSpecCandidate
from trust_receipt.agents.task_draft import TaskDraftError


@pytest.mark.parametrize("adapter_class", [OpenAIStructuredOutputAdapter, DeepSeekStructuredOutputAdapter])
@pytest.mark.parametrize("failure,kind", [
    ("timeout", "timeout"), ("connection", "connection"),
    (429, "rate_limit"), (500, "provider"), (401, "provider"),
])
def test_real_sdk_transport_failures_are_single_attempt_and_safe(monkeypatch, adapter_class, failure, kind):
    calls = []
    clients = []
    original_async_client = httpx.AsyncClient

    async def handle(request):
        calls.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("SECRET vendor response", request=request)
        if failure == "connection":
            raise httpx.ConnectError("SECRET vendor response", request=request)
        return httpx.Response(failure, json={"error": {"message": "SECRET vendor response"}})

    class MockClient(original_async_client):
        def __init__(self, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handle)
            super().__init__(**kwargs)
            clients.append(self)

    monkeypatch.setattr(httpx, "AsyncClient", MockClient)
    adapter = adapter_class(api_key="synthetic-not-a-key", model_name="fixed-test-model", max_retries=2)
    with pytest.raises(TaskDraftError) as captured:
        adapter.generate(schema=TaskSpecCandidate, system_prompt="Return JSON.", payload={"user_request": "scope"})
    assert captured.value.kind == kind
    assert "SECRET" not in str(captured.value)
    assert captured.value.__context__ is None
    assert captured.value.__cause__ is None
    assert len(calls) == 1
    assert clients[-1].is_closed
    assert clients[-1].timeout.read == 20
    body = json.loads(calls[0].content)
    assert body.get("max_output_tokens", body.get("max_completion_tokens")) == 2048
    assert "tools" not in body


def test_deadline_cancels_invocation_closes_clients_and_never_accepts_late_output(monkeypatch, ready_candidate):
    observed = {"calls": 0, "cancelled": 0, "returned": 0}
    original_client, original_async_client = httpx.Client, httpx.AsyncClient

    class MockClient(original_client):
        def __init__(self, **kwargs):
            super().__init__(**kwargs, transport=httpx.MockTransport(lambda _: httpx.Response(500)))

    class MockAsyncClient(original_async_client):
        def __init__(self, **kwargs):
            super().__init__(**kwargs, transport=httpx.MockTransport(lambda _: httpx.Response(500)))

    monkeypatch.setattr(httpx, "Client", MockClient)
    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)

    class Model:
        def __init__(self, **kwargs):
            observed["clients"] = (kwargs["http_client"], kwargs["http_async_client"])

        def with_structured_output(self, *args, **kwargs):
            return self

        async def ainvoke(self, messages):
            observed["calls"] += 1
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                observed["cancelled"] += 1
                raise
            observed["returned"] += 1
            return ready_candidate

    monkeypatch.setattr("trust_receipt.agents.openai.ChatOpenAI", Model)
    monkeypatch.setattr("trust_receipt.agents.task_draft.TASK_DRAFT_DEADLINE_SECONDS", 0.05)
    # The generic model does not use this test's fake client references.
    adapter = OpenAIStructuredOutputAdapter.__new__(OpenAIStructuredOutputAdapter)
    adapter._configuration = {"timeout": 30}
    started = time.monotonic()
    with pytest.raises(TaskDraftError, match="超时") as captured:
        adapter.generate(schema=TaskSpecCandidate, system_prompt="Return JSON.", payload={"user_request": "scope"})
    assert captured.value.kind == "timeout"
    assert time.monotonic() - started < 1.5
    assert observed["calls"] == observed["cancelled"] == 1
    assert observed["returned"] == 0
    assert all(client.is_closed for client in observed["clients"])


@pytest.mark.parametrize("invalid", [None, {"schema_version": "1.0"}])
def test_invalid_candidate_is_not_retried_or_used(monkeypatch, invalid):
    class Model:
        def __init__(self, **kwargs):
            pass

        def with_structured_output(self, *args, **kwargs):
            return self

        async def ainvoke(self, messages):
            return invalid

    monkeypatch.setattr("trust_receipt.agents.openai.ChatOpenAI", Model)
    adapter = OpenAIStructuredOutputAdapter(api_key="synthetic", model_name="fixed")
    with pytest.raises(TaskDraftError) as captured:
        adapter.generate(schema=TaskSpecCandidate, system_prompt="Return JSON.", payload={})
    assert captured.value.kind == "invalid_output"


def test_other_artifacts_keep_existing_sync_configuration(monkeypatch, claim_extraction):
    configurations = []

    class Model:
        def __init__(self, **kwargs):
            configurations.append(kwargs)

        def with_structured_output(self, *args, **kwargs):
            return self

        def invoke(self, messages):
            return claim_extraction

    monkeypatch.setattr("trust_receipt.agents.openai.ChatOpenAI", Model)
    adapter = OpenAIStructuredOutputAdapter(api_key="synthetic", model_name="fixed", timeout_seconds=75, max_retries=2)
    assert adapter.generate(schema=type(claim_extraction), system_prompt="Return JSON.", payload={}) == claim_extraction
    assert len(configurations) == 1
    assert configurations[0]["timeout"] == 75
    assert configurations[0]["max_retries"] == 2
    assert "max_completion_tokens" not in configurations[0]


@pytest.mark.parametrize("adapter_class", [OpenAIStructuredOutputAdapter, DeepSeekStructuredOutputAdapter])
def test_sdk_stalled_transport_is_cancelled_at_operation_deadline(monkeypatch, adapter_class):
    observed = {"calls": 0, "cancelled": 0, "clients": []}
    original_client, original_async_client = httpx.Client, httpx.AsyncClient

    async def handle(request):
        observed["calls"] += 1
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            observed["cancelled"] += 1
            raise
        raise AssertionError("late response must not be reached")

    class MockClient(original_client):
        def __init__(self, **kwargs):
            kwargs["transport"] = httpx.MockTransport(lambda _: httpx.Response(500))
            super().__init__(**kwargs)
            observed["clients"].append(self)

    class MockAsyncClient(original_async_client):
        def __init__(self, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handle)
            super().__init__(**kwargs)
            observed["clients"].append(self)

    monkeypatch.setattr(httpx, "Client", MockClient)
    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)
    adapter = adapter_class(api_key="synthetic", model_name="fixed", timeout_seconds=120, max_retries=2)
    monkeypatch.setattr("trust_receipt.agents.task_draft.TASK_DRAFT_DEADLINE_SECONDS", 0.1)
    started = time.monotonic()
    with pytest.raises(TaskDraftError) as captured:
        adapter.generate(schema=TaskSpecCandidate, system_prompt="Return JSON.", payload={})
    elapsed = time.monotonic() - started
    assert captured.value.kind == "timeout"
    assert 0.08 <= elapsed < 1.5
    assert observed["calls"] == observed["cancelled"] == 1
    # The last two clients belong to the candidate, not the generic adapter.
    assert all(client.is_closed for client in observed["clients"][-2:])
