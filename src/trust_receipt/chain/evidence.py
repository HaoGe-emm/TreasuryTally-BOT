"""Product-facing live reference evidence adapters."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from time import monotonic

from pydantic import BaseModel, ConfigDict, Field

from trust_receipt.chain.blockscout import probe_blockscout
from trust_receipt.chain.rpc import EvmRpcProbe
from trust_receipt.integrations.errors import IntegrationError
from trust_receipt.models import EvidenceSource, SourceDescriptor, TaskSpec, TransferRecord
from trust_receipt.verification import ReferenceEvidence, ReferencePage, ReferenceStream


class EvidenceDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str
    role: str
    status: str
    detail: str
    pages: int = Field(default=0, ge=0)
    records: int = Field(default=0, ge=0)
    elapsed_ms: int = Field(default=0, ge=0)


class RpcReferenceEvidenceProvider:
    """Fetch a confirmed TaskSpec scope from live JSON-RPC, with optional Blockscout sampling."""

    def __init__(
        self,
        rpc_url: str,
        *,
        expected_chain_id: int,
        timeout_seconds: float = 30,
        confirmations: int = 2,
        page_size_blocks: int = 2_000,
        blockscout_mcp_url: str | None = None,
        enable_blockscout_cross_check: bool = False,
        rpc_probe: EvmRpcProbe | None = None,
        clock=lambda: datetime.now(UTC),
    ) -> None:
        self._rpc = rpc_probe or EvmRpcProbe(
            rpc_url,
            expected_chain_id=expected_chain_id,
            timeout_seconds=timeout_seconds,
        )
        self._confirmations = confirmations
        self._page_size_blocks = page_size_blocks
        self._blockscout_mcp_url = blockscout_mcp_url
        self._enable_blockscout = enable_blockscout_cross_check
        self._timeout_seconds = timeout_seconds
        self._clock = clock
        self._diagnostics: tuple[EvidenceDiagnostic, ...] = ()

    @property
    def diagnostics(self) -> tuple[EvidenceDiagnostic, ...]:
        return self._diagnostics

    def fetch(self, task: TaskSpec) -> ReferenceEvidence:
        started = monotonic()
        retrieved_at = self._clock()
        try:
            latest = self._rpc.latest_block()
            confirmed_tip = latest - self._confirmations
            if task.end_block > confirmed_tip:
                return self._inconclusive(
                    task,
                    retrieved_at,
                    code="UNCONFIRMED_RANGE",
                    detail=f"end_block={task.end_block} exceeds confirmed tip {confirmed_tip}",
                    elapsed_ms=self._elapsed(started),
                )
            record_pages = self._rpc.fetch_transfer_pages(
                token_address=task.token_address,
                from_block=task.start_block,
                to_block=task.end_block,
                page_size_blocks=self._page_size_blocks,
            )
        except IntegrationError as error:
            return self._inconclusive(
                task,
                retrieved_at,
                code=error.code.value,
                detail=str(error),
                elapsed_ms=self._elapsed(started),
            )
        except (OSError, ValueError) as error:
            return self._inconclusive(
                task,
                retrieved_at,
                code="INVALID_OR_UNAVAILABLE",
                detail=f"{type(error).__name__}: {error}",
                elapsed_ms=self._elapsed(started),
            )

        pages = self._reference_pages(record_pages)
        records = tuple(record for page in record_pages for record in page)
        elapsed = self._elapsed(started)
        rpc_diagnostic = EvidenceDiagnostic(
            source="rpc",
            role="authoritative-reference",
            status="COMPLETE",
            detail=f"Sepolia chain_id={task.chain_id}; confirmed through block {confirmed_tip}",
            pages=len(pages),
            records=len(records),
            elapsed_ms=elapsed,
        )
        blockscout_diagnostic = self._cross_check(records, task.chain_id)
        self._diagnostics = (rpc_diagnostic, blockscout_diagnostic)
        descriptor = SourceDescriptor(
            source=EvidenceSource.RPC,
            source_id=f"rpc:{task.chain_id}:{task.start_block}-{task.end_block}",
            retrieved_at=retrieved_at,
            complete=True,
            details={
                "start_block": task.start_block,
                "end_block": task.end_block,
                "latest_block": latest,
                "confirmations": self._confirmations,
                "pages": len(pages),
                "records": len(records),
            },
        )
        return ReferenceEvidence(
            streams=(ReferenceStream(source=descriptor, pages=pages),),
            evidence_sufficient=True,
            insufficiency_reason=None,
        )

    @staticmethod
    def _reference_pages(
        record_pages: tuple[tuple[TransferRecord, ...], ...],
    ) -> tuple[ReferencePage, ...]:
        pages: list[ReferencePage] = []
        for index, transfers in enumerate(record_pages):
            cursor = None if index == 0 else f"page:{index}"
            next_cursor = f"page:{index + 1}" if index + 1 < len(record_pages) else None
            pages.append(ReferencePage(cursor=cursor, next_cursor=next_cursor, transfers=transfers))
        return tuple(pages)

    def _cross_check(self, records: tuple[TransferRecord, ...], chain_id: int) -> EvidenceDiagnostic:
        if not self._enable_blockscout or self._blockscout_mcp_url is None:
            return EvidenceDiagnostic(
                source="blockscout",
                role="supplementary-sample",
                status="NOT_CONFIGURED",
                detail="RPC remains the sole reference source",
            )
        if not records:
            return EvidenceDiagnostic(
                source="blockscout",
                role="supplementary-sample",
                status="SKIPPED_EMPTY",
                detail="No RPC transfer was available to sample",
            )
        started = monotonic()
        try:
            result = asyncio.run(
                probe_blockscout(
                    self._blockscout_mcp_url,
                    chain_id=chain_id,
                    transaction_hash=records[0].transaction_hash,
                    timeout_seconds=self._timeout_seconds,
                )
            )
            return EvidenceDiagnostic(
                source="blockscout",
                role="supplementary-sample",
                status="SAMPLED",
                detail=f"Sampled transaction {records[0].transaction_hash}; not used as sole truth",
                records=1,
                elapsed_ms=result.elapsed_ms,
            )
        except (IntegrationError, RuntimeError) as error:
            return EvidenceDiagnostic(
                source="blockscout",
                role="supplementary-sample",
                status="DEGRADED",
                detail=f"{type(error).__name__}: {error}; RPC-only fallback retained",
                elapsed_ms=self._elapsed(started),
            )

    def _inconclusive(
        self,
        task: TaskSpec,
        retrieved_at: datetime,
        *,
        code: str,
        detail: str,
        elapsed_ms: int,
    ) -> ReferenceEvidence:
        self._diagnostics = (
            EvidenceDiagnostic(
                source="rpc",
                role="authoritative-reference",
                status="INCOMPLETE",
                detail=f"{code}: {detail}",
                elapsed_ms=elapsed_ms,
            ),
            EvidenceDiagnostic(
                source="blockscout",
                role="supplementary-sample",
                status="NOT_RUN",
                detail="Primary RPC evidence was incomplete",
            ),
        )
        descriptor = SourceDescriptor(
            source=EvidenceSource.RPC,
            source_id=f"rpc:{task.chain_id}:{task.start_block}-{task.end_block}",
            retrieved_at=retrieved_at,
            complete=False,
            details={"error_code": code, "error": detail},
        )
        return ReferenceEvidence(
            streams=(ReferenceStream(source=descriptor, pages=()),),
            evidence_sufficient=False,
            insufficiency_reason=f"RPC evidence unavailable or incomplete ({code})",
        )

    @staticmethod
    def _elapsed(started: float) -> int:
        return max(0, round((monotonic() - started) * 1_000))
