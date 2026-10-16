"""Read-only Agent0 identity probe."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Any

from agent0_sdk import SDK
from pydantic import BaseModel, ConfigDict

from trust_receipt.integrations.errors import IntegrationError, IntegrationErrorCode
from trust_receipt.integrations.retry import read_with_retry


class AgentIdentityResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    service_id: str
    owner: str
    name: str | None = None
    description: str | None = None


def _with_timeout(operation: Any, timeout_seconds: float) -> Any:
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="agent0-probe")
    future = executor.submit(operation)
    try:
        return future.result(timeout=timeout_seconds)
    except FutureTimeout as exc:
        future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
        raise IntegrationError(IntegrationErrorCode.TIMEOUT, "Agent0 SDK read timed out") from exc
    finally:
        if future.done():
            executor.shutdown(wait=True)


def probe_agent_identity(
    *,
    chain_id: int,
    rpc_url: str,
    service_id: str,
    timeout_seconds: float = 30,
    expected_owner: str | None = None,
    registry_overrides: dict[int, dict[str, str]] | None = None,
) -> AgentIdentityResult:
    def read() -> AgentIdentityResult:
        sdk = SDK(
            chainId=chain_id,
            rpcUrl=rpc_url,
            registryOverrides=registry_overrides,
        )
        summary = sdk.loadAgent(service_id)
        owner = sdk.getAgentOwner(service_id)
        if expected_owner and owner.lower() != expected_owner.lower():
            raise IntegrationError(
                IntegrationErrorCode.CONTRACT_MISMATCH,
                "Agent0 service owner does not match AGENT0_EXPECTED_OWNER",
            )
        return AgentIdentityResult(
            service_id=service_id,
            owner=owner,
            name=getattr(summary, "name", None),
            description=getattr(summary, "description", None),
        )

    try:
        return read_with_retry(lambda: _with_timeout(read, timeout_seconds))
    except IntegrationError:
        raise
    except Exception as exc:
        raise IntegrationError(
            IntegrationErrorCode.UNAVAILABLE,
            f"Agent0 identity read failed: {type(exc).__name__}",
        ) from exc
