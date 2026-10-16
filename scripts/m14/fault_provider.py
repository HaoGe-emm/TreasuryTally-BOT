"""Explicit test-only faults over real RPC evidence; never a production adapter."""

from trust_receipt.chain.evidence import EvidenceDiagnostic, RpcReferenceEvidenceProvider
from trust_receipt.chain.rpc import EvmRpcProbe
from trust_receipt.models import EvidenceSource, SourceDescriptor
from trust_receipt.verification import ReferenceEvidence, ReferencePage, ReferenceStream
from trust_receipt.verification.scope import scope_violation


class UnavailableRpcProvider(RpcReferenceEvidenceProvider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rpc = EvmRpcProbe("http://127.0.0.1:9", expected_chain_id=11155111, timeout_seconds=1)


class ConflictRpcProvider(RpcReferenceEvidenceProvider):
    def fetch(self, task):
        live = super().fetch(task)
        if not live.evidence_sufficient:
            return live
        rpc = live.streams[0]
        records = tuple(record for page in rpc.pages for record in page.transfers)
        target = next((record for record in records if scope_violation(task, record) is None), None)
        if target is None:
            return live
        injected = tuple(record.model_copy(update={
            "source": EvidenceSource.BLOCKSCOUT,
            "amount_base_units": (
                str(int(record.amount_base_units) + 1) if record.event_key == target.event_key
                else record.amount_base_units
            ),
        }) for record in records)
        source = SourceDescriptor(
            source=EvidenceSource.BLOCKSCOUT, source_id="m14-injected-conflict",
            retrieved_at=rpc.source.retrieved_at, complete=True,
            details={"injected": True, "simulation": "m14-conflict", "records": len(injected)},
        )
        stream = ReferenceStream(source=source, pages=(ReferencePage(
            cursor=None, next_cursor=None, transfers=injected,
        ),))
        self._diagnostics = (*self._diagnostics, EvidenceDiagnostic(
            source="m14-injected-conflict", role="SIMULATED-TEST-CONFLICT", status="SIMULATED",
            detail="M14 local fault: full RPC set copied, selected amount +1; not a real Blockscout response",
            records=len(injected),
        ))
        return ReferenceEvidence(streams=(*live.streams, stream), evidence_sufficient=True, insufficiency_reason=None)
