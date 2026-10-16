"""Blockscout MCP client probe using the official MCP transport."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from time import monotonic
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from pydantic import BaseModel, ConfigDict

from trust_receipt.integrations.errors import IntegrationError, IntegrationErrorCode


class BlockscoutProbeResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    protocol_version: str
    tool_names: tuple[str, ...]
    query_tool: str
    elapsed_ms: int
    pagination_complete: bool
    structured_result: dict[str, Any]


def _mcp_endpoint(base_url: str) -> str:
    return base_url.rstrip("/") if base_url.rstrip("/").endswith("/mcp") else f"{base_url.rstrip('/')}/mcp"


def _pagination_complete(value: Any) -> bool:
    if isinstance(value, dict):
        if value.get("next_page_params"):
            return False
        return all(_pagination_complete(item) for item in value.values())
    if isinstance(value, list):
        return all(_pagination_complete(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        return "is truncated" not in lowered and "to paginate" not in lowered
    return True


def _tool_error_code(response: Any) -> IntegrationErrorCode:
    text = " ".join(str(getattr(item, "text", "")) for item in getattr(response, "content", ())).lower()
    if any(marker in text for marker in ("unauthorized", "forbidden", "authentication", "api key")):
        return IntegrationErrorCode.AUTHENTICATION
    if any(marker in text for marker in ("rate limit", "too many requests", "429")):
        return IntegrationErrorCode.RATE_LIMITED
    return IntegrationErrorCode.UNAVAILABLE


async def _probe_once(
    base_url: str,
    *,
    chain_id: int,
    transaction_hash: str,
    timeout_seconds: float = 30,
) -> BlockscoutProbeResult:
    started = monotonic()
    timeout = httpx.Timeout(timeout_seconds)
    session_timeout = timedelta(seconds=timeout_seconds)
    try:
        async with (
            httpx.AsyncClient(timeout=timeout, trust_env=False) as http_client,
            streamable_http_client(
                _mcp_endpoint(base_url),
                http_client=http_client,
            ) as streams,
            ClientSession(
                streams[0],
                streams[1],
                read_timeout_seconds=session_timeout,
            ) as session,
        ):
            initialized = await session.initialize()
            listed = await session.list_tools()
            names = tuple(sorted(tool.name for tool in listed.tools))
            tool_name = "get_transaction_info"
            if tool_name not in names:
                raise IntegrationError(
                    IntegrationErrorCode.INVALID_RESPONSE,
                    f"Blockscout MCP did not advertise required tool {tool_name}",
                )
            response = await session.call_tool(
                tool_name,
                {"chain_id": str(chain_id), "transaction_hash": transaction_hash},
                read_timeout_seconds=session_timeout,
            )
            if response.isError:
                raise IntegrationError(
                    _tool_error_code(response),
                    "Blockscout MCP tool returned an error",
                )
            structured = response.structuredContent
            if not isinstance(structured, dict):
                raise IntegrationError(
                    IntegrationErrorCode.INVALID_RESPONSE,
                    "Blockscout MCP response did not contain structured content",
                )
            return BlockscoutProbeResult(
                protocol_version=initialized.protocolVersion,
                tool_names=names,
                query_tool=tool_name,
                elapsed_ms=round((monotonic() - started) * 1000),
                pagination_complete=_pagination_complete(structured),
                structured_result=structured,
            )
    except IntegrationError:
        raise
    except httpx.TimeoutException as exc:
        raise IntegrationError(IntegrationErrorCode.TIMEOUT, "Blockscout MCP request timed out") from exc
    except (httpx.HTTPError, OSError) as exc:
        raise IntegrationError(
            IntegrationErrorCode.UNAVAILABLE,
            f"Blockscout MCP unavailable: {type(exc).__name__}",
        ) from exc
    except Exception as exc:
        raise IntegrationError(
            IntegrationErrorCode.UNAVAILABLE,
            f"Blockscout MCP session failed: {type(exc).__name__}",
        ) from exc


async def probe_blockscout(
    base_url: str,
    *,
    chain_id: int,
    transaction_hash: str,
    timeout_seconds: float = 30,
) -> BlockscoutProbeResult:
    """Probe the MCP server, retrying only the entire idempotent read session."""
    last_error: IntegrationError | None = None
    for attempt in range(3):
        try:
            return await _probe_once(
                base_url,
                chain_id=chain_id,
                transaction_hash=transaction_hash,
                timeout_seconds=timeout_seconds,
            )
        except IntegrationError as exc:
            last_error = exc
            if attempt == 2 or exc.code in {
                IntegrationErrorCode.AUTHENTICATION,
                IntegrationErrorCode.INVALID_RESPONSE,
            }:
                raise
            await asyncio.sleep(0.25 * (2**attempt))
    raise last_error or AssertionError("Blockscout retry loop exhausted")
