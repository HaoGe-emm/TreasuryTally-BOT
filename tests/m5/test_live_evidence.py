from __future__ import annotations

from trust_receipt.chain import RpcReferenceEvidenceProvider
from trust_receipt.integrations.errors import IntegrationError, IntegrationErrorCode


class FakeRpc:
    def __init__(self, *, pages=(), latest=2_000, error=None) -> None:
        self.pages = pages
        self.latest = latest
        self.error = error

    def latest_block(self):
        if self.error:
            raise self.error
        return self.latest

    def fetch_transfer_pages(self, **kwargs):
        del kwargs
        if self.error:
            raise self.error
        return self.pages


def test_live_rpc_provider_builds_complete_contiguous_pages(vertical_case) -> None:
    pages = ((vertical_case.reference.transfers[0],), (), (vertical_case.reference.transfers[2],))
    provider = RpcReferenceEvidenceProvider(
        "https://unused.invalid",
        expected_chain_id=vertical_case.task_spec.chain_id,
        rpc_probe=FakeRpc(pages=pages),
    )

    evidence = provider.fetch(vertical_case.task_spec)

    assert evidence.evidence_sufficient
    assert evidence.streams[0].source.complete
    assert [page.cursor for page in evidence.streams[0].pages] == [None, "page:1", "page:2"]
    assert [page.next_cursor for page in evidence.streams[0].pages] == ["page:1", "page:2", None]
    assert provider.diagnostics[0].status == "COMPLETE"
    assert provider.diagnostics[0].records == 2
    assert provider.diagnostics[1].status == "NOT_CONFIGURED"


def test_live_rpc_failure_becomes_incomplete_evidence(vertical_case) -> None:
    provider = RpcReferenceEvidenceProvider(
        "https://unused.invalid",
        expected_chain_id=vertical_case.task_spec.chain_id,
        rpc_probe=FakeRpc(error=IntegrationError(IntegrationErrorCode.TIMEOUT, "timed out")),
    )

    evidence = provider.fetch(vertical_case.task_spec)

    assert not evidence.evidence_sufficient
    assert not evidence.streams[0].source.complete
    assert evidence.streams[0].pages == ()
    assert provider.diagnostics[0].status == "INCOMPLETE"
    assert "TIMEOUT" in provider.diagnostics[0].detail


def test_unconfirmed_end_block_is_not_treated_as_complete(vertical_case) -> None:
    provider = RpcReferenceEvidenceProvider(
        "https://unused.invalid",
        expected_chain_id=vertical_case.task_spec.chain_id,
        confirmations=2,
        rpc_probe=FakeRpc(latest=vertical_case.task_spec.end_block + 1),
    )

    evidence = provider.fetch(vertical_case.task_spec)

    assert not evidence.evidence_sufficient
    assert evidence.streams[0].source.details["error_code"] == "UNCONFIRMED_RANGE"
