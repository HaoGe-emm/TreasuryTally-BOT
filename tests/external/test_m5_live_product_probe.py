from __future__ import annotations

import pytest
from eth_account import Account

from trust_receipt.agents import DeepSeekStructuredOutputAdapter, M4AISettings, RestrictedAIService
from trust_receipt.chain import RpcReferenceEvidenceProvider
from trust_receipt.chain.rpc import EvmRpcProbe
from trust_receipt.models import VerificationOutcome
from trust_receipt.orchestration import M5Workflow
from trust_receipt.services import FaultMode, TeamControlledReportService
from trust_receipt.storage.sqlite import SQLiteRepository
from trust_receipt.verification.scope import scope_violation

from .conftest import require_configuration

pytestmark = pytest.mark.external


def test_real_deepseek_rpc_blockscout_use_case_runs_fail_then_switches_to_pass(
    m0_settings, tmp_path
) -> None:
    ai_settings = M4AISettings.load()
    missing = [*m0_settings.missing_for_rpc(), *ai_settings.missing_for_deepseek()]
    if m0_settings.blockscout_pro_api_key is None:
        missing.append("BLOCKSCOUT_PRO_API_KEY")
    require_configuration(missing, "M5 DeepSeek + RPC + Blockscout product flow")

    probe = EvmRpcProbe(
        m0_settings.rpc_url_value(),
        expected_chain_id=m0_settings.chain_id,
        timeout_seconds=m0_settings.rpc_timeout_seconds,
    )
    known = probe.probe_transfer(
        token_address=m0_settings.test_token_address or "",
        from_block=m0_settings.test_from_block or 0,
        to_block=m0_settings.test_to_block or 0,
        expected_transaction_hash=m0_settings.test_transfer_tx_hash or "",
    ).transfer
    ai = RestrictedAIService(
        DeepSeekStructuredOutputAdapter(
            api_key=ai_settings.deepseek_api_key_value(),
            model_name=ai_settings.deepseek_model_name or "",
            timeout_seconds=ai_settings.timeout_seconds,
            max_retries=ai_settings.max_retries,
        )
    )
    candidate = ai.draft_task(
        f"On Sepolia chain {m0_settings.chain_id}, verify ERC-20 token {known.token_address} "
        f"from the sole confirmed treasury {known.from_address} to the sole confirmed recipient "
        f"{known.to_address} for the inclusive "
        f"block range {m0_settings.test_from_block} through {m0_settings.test_to_block}. "
        "There are no other treasury or recipient accounts. Apply no exclusion rules; "
        "the confirmed exclusion_rules list is empty."
    )
    evidence_provider = RpcReferenceEvidenceProvider(
        m0_settings.rpc_url_value(),
        expected_chain_id=m0_settings.chain_id,
        timeout_seconds=m0_settings.rpc_timeout_seconds,
        confirmations=m0_settings.rpc_confirmations,
        blockscout_mcp_url=m0_settings.blockscout_mcp_url,
        enable_blockscout_cross_check=True,
    )

    def live_records(task):
        evidence = evidence_provider.fetch(task)
        assert evidence.evidence_sufficient
        return tuple(
            record
            for stream in evidence.streams
            for page in stream.pages
            for record in page.transfers
            if scope_violation(task, record) is None
        )

    service_a = TeamControlledReportService(
        service_id="service-a",
        private_key=Account.create().key.to_0x_hex(),
        records_provider=live_records,
        fault_by_attempt={1: FaultMode.OMIT_LAST_TRANSFER},
    )
    service_b = TeamControlledReportService(
        service_id="service-b",
        private_key=Account.create().key.to_0x_hex(),
        records_provider=live_records,
    )
    workflow = M5Workflow(
        repository=SQLiteRepository(tmp_path / "live-product.db"),
        evidence_provider=evidence_provider,
        ai_service=ai,
        receipt_directory=tmp_path / "receipts",
    )
    task = workflow.confirm_task(candidate)

    first = workflow.run_attempt(task.task_id, service_a)
    second = workflow.run_attempt(task.task_id, service_b)

    assert first.result.outcome is VerificationOutcome.FAIL
    assert second.result.outcome is VerificationOutcome.PASS
    assert first.ai_errors == ()
    assert second.ai_errors == ()
    assert first.follow_up is not None
    assert second.follow_up is not None
    assert first.evidence_diagnostics[0].status == "COMPLETE"
    assert first.evidence_diagnostics[1].status == "SAMPLED"
    assert second.evidence_diagnostics[0].records >= 1
    assert second.evidence_diagnostics[1].status == "SAMPLED"
    assert first.receipt_path is not None and first.receipt_path.is_file()
    assert second.receipt_path is not None and second.receipt_path.is_file()
