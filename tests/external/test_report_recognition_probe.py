"""Opt-in live header-only probes: two requests, one configured fixed provider."""

from __future__ import annotations

import csv
import io
import json
import os
import time

import pytest

from trust_receipt.agents.config import M4AISettings
from trust_receipt.services.report_recognition import build_header_recognizer, recognize_report

pytestmark = pytest.mark.external


@pytest.fixture(scope="module")
def live_recognizer():
    settings = M4AISettings.load(os.environ.get("M14_PROBE_ENV_FILE", ".env"))
    if not settings.missing_for_deepseek():
        provider = "DeepSeek"
    elif not settings.missing_for_openai():
        provider = "OpenAI"
    else:
        pytest.skip("No existing configured DeepSeek/OpenAI key and fixed model; no fallback")
    try:
        return build_header_recognizer(provider, settings)
    except Exception:
        pytest.fail("Existing model configuration cannot construct the recognizer", pytrace=False)


def synthetic_csv(unit_unspecified: bool) -> bytes:
    headers = [
        "chain_id", "token_address", "transaction_hash", "log_index", "block_number",
        "from_address", "to_address", "amount" if unit_unspecified else "amount_base_units",
        "token_decimals", "claimed_total_base_units", "claimed_count",
    ]
    # Local synthetic values are never included in the model request.
    values = ["11155111", "0x" + "1" * 40, "0x" + "2" * 64, "0", "100",
              "0x" + "3" * 40, "0x" + "4" * 40, "123", "18", "123", "1"]
    buffer = io.StringIO(newline="")
    csv.writer(buffer).writerows([headers, values])
    return buffer.getvalue().encode()


@pytest.mark.parametrize("unit_unspecified", [False, True], ids=["normal-csv", "local-unit-question"])
def test_live_header_recognition(live_recognizer, unit_unspecified):
    started = time.monotonic()
    result = recognize_report(synthetic_csv(unit_unspecified), "synthetic.csv", live_recognizer)
    evidence = {
        "case": "local-unit-question" if unit_unspecified else "normal-csv",
        "mode": result.recognition_mode,
        "model_id": result.model_id,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "api_and_schema_success": result.recognition is not None,
        "ready": result.ready,
        "issues": result.issues,
        "clarifications": result.clarifications,
        "missing_fields": result.missing_fields,
        "roles": result.recognition.model_dump(mode="json") if result.recognition else None,
        "rpc_or_business_verification": "not-tested",
    }
    print("HEADER_PROBE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True))
    if result.recognition is None:
        pytest.fail("Live recognition did not return a valid role binding; see redacted evidence", pytrace=False)
    if unit_unspecified:
        assert result.clarifications == ("amount_unit",)
        assert not result.ready
        resolved = recognize_report(
            synthetic_csv(True), "synthetic.csv", live_recognizer, amount_unit="base", previous=result,
        )
        assert resolved.ready  # Cache reuse: no third model request.
    else:
        assert result.ready
        assert result.report.claimed_total_base_units == "123"
