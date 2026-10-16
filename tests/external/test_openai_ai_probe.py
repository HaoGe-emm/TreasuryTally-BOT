from __future__ import annotations

import pytest

from trust_receipt.agents import M4AISettings, OpenAIStructuredOutputAdapter, RestrictedAIService

pytestmark = pytest.mark.external


def test_openai_returns_a_schema_validated_task_candidate() -> None:
    settings = M4AISettings.load()
    missing = settings.missing_for_openai()
    if missing:
        pytest.skip(f"M4 OpenAI blocked by missing configuration: {', '.join(missing)}")

    adapter = OpenAIStructuredOutputAdapter(
        api_key=settings.api_key_value(),
        model_name=settings.model_name or "",
        timeout_seconds=settings.timeout_seconds,
        max_retries=settings.max_retries,
    )
    service = RestrictedAIService(adapter)
    candidate = service.draft_task(
        "On Sepolia (chain 11155111), verify token 0x1111111111111111111111111111111111111111 "
        "from treasury 0x2222222222222222222222222222222222222222 to recipient "
        "0x3333333333333333333333333333333333333333 for inclusive blocks 100 through 200. "
        "Exclude transfers between confirmed treasury accounts."
    )

    assert candidate.chain_id == 11_155_111
    assert candidate.max_records == 200
