"""Bounded, cancellable candidate requests and secret-safe failure categories."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Mapping
from typing import Any

from pydantic import ValidationError

TASK_DRAFT_DEADLINE_SECONDS = 20
TASK_DRAFT_MAX_OUTPUT_TOKENS = 2048

_MESSAGES = {
    "timeout": "整理范围请求超时。可以重试或直接填写范围。",
    "connection": "无法连接模型服务。可以重试或直接填写范围。",
    "rate_limit": "模型服务暂时限流。请稍后重试或直接填写范围。",
    "provider": "模型服务暂时不可用。可以重试或直接填写范围。",
    "invalid_output": "模型返回的范围未通过校验。请修改说明或直接填写范围。",
    "unavailable": "暂时无法整理范围。可以直接填写范围。",
}


class TaskDraftError(RuntimeError):
    """Only a fixed public category/message; never preserve a vendor response."""

    def __init__(self, kind: str) -> None:
        self.kind = kind if kind in _MESSAGES else "unavailable"
        super().__init__(_MESSAGES[self.kind])


def generate_task_draft(
    factory: Callable[..., Any],
    configuration: Mapping[str, Any],
    schema: type,
    messages: list[tuple[str, str]],
) -> Any:
    """Use an async transport, not an uncancellable background sync thread.

    Clients belong to this invocation/loop and are closed on success or cancellation.
    Closing local sockets cannot guarantee that an already received server request
    stops generating or charging; no retry is issued by this application.
    """
    from langchain_core.exceptions import OutputParserException
    from openai import (
        APIConnectionError,
        APIStatusError,
        APITimeoutError,
        ContentFilterFinishReasonError,
        LengthFinishReasonError,
        RateLimitError,
    )

    async def invoke():
        import httpx

        deadline = TASK_DRAFT_DEADLINE_SECONDS
        ends_at = asyncio.get_running_loop().time() + deadline
        options = dict(configuration)
        options.update(
            timeout=min(float(options["timeout"]), deadline),
            max_retries=0,
            max_completion_tokens=TASK_DRAFT_MAX_OUTPUT_TOKENS,
        )
        # Explicit per-invocation transports avoid reusing an async pool across
        # asyncio.run loops, and keep both SDK-created client wrappers bounded.
        with httpx.Client(timeout=options["timeout"]) as sync_client:
            async with httpx.AsyncClient(timeout=options["timeout"]) as async_client:
                model = factory(
                    **options, http_client=sync_client, http_async_client=async_client,
                )
                structured = model.with_structured_output(schema, method="json_schema", strict=True)
                # Setup consumes the same budget. Never start a late request
                # if synchronous SDK/schema setup has already used it up.
                remaining = ends_at - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise TimeoutError
                response = await asyncio.wait_for(structured.ainvoke(messages), timeout=remaining)
                # Validation also happens before this invocation's deadline.
                if hasattr(response, "model_dump"):
                    response = response.model_dump(mode="json")
                return schema.model_validate(response)

    async def bounded():
        return await asyncio.wait_for(invoke(), timeout=TASK_DRAFT_DEADLINE_SECONDS)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        # This sync port must not leak a coroutine or start another worker when
        # called from an async loop. Async callers need an explicit async port.
        raise TaskDraftError("unavailable")
    try:
        return asyncio.run(bounded())
    except (TimeoutError, APITimeoutError):
        kind = "timeout"
    except RateLimitError:
        kind = "rate_limit"
    except APIConnectionError:
        kind = "connection"
    except APIStatusError:
        kind = "provider"
    except (
        ValidationError, OutputParserException, json.JSONDecodeError,
        LengthFinishReasonError, ContentFilterFinishReasonError,
    ):
        kind = "invalid_output"
    except Exception:
        kind = "unavailable"
    # Raise after leaving the SDK exception handler: even __context__ must not
    # retain a response object/body if the caller stores this public error.
    raise TaskDraftError(kind)
