"""M0 probe result composed from the provider-neutral transfer model."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from trust_receipt.models import TransferRecord


class RpcProbeResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    chain_id: int
    latest_block: int
    historical_block: int
    transfer: TransferRecord


__all__ = ["RpcProbeResult", "TransferRecord"]
