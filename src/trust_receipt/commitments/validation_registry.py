"""Read-only capability probe for the deployed ERC-8004 Validation Registry."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from web3 import Web3

from trust_receipt.chain.rpc import EvmRpcProbe
from trust_receipt.integrations.errors import IntegrationError, IntegrationErrorCode

VALIDATION_READ_ABI = [
    {
        "inputs": [],
        "name": "getIdentityRegistry",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "agentId", "type": "uint256"}],
        "name": "getAgentValidations",
        "outputs": [{"name": "", "type": "bytes32[]"}],
        "stateMutability": "view",
        "type": "function",
    },
]


class ValidationRegistryCapability(BaseModel):
    model_config = ConfigDict(frozen=True)

    chain_id: int
    validation_registry: str
    identity_registry: str
    service_id: str
    existing_request_count: int
    supports_task_commitment_anchor: bool
    limitation: str


class ValidationRegistryReadProbe:
    def __init__(
        self,
        rpc: EvmRpcProbe,
        *,
        validation_registry: str,
        expected_identity_registry: str,
    ) -> None:
        self._rpc = rpc
        self._validation_registry = validation_registry
        self._expected_identity_registry = expected_identity_registry

    def probe(self, service_id: str) -> ValidationRegistryCapability:
        chain_id = self._rpc.chain_id()
        self._rpc.contract_code(self._validation_registry)
        contract = self._rpc.contract(self._validation_registry, VALIDATION_READ_ABI)
        try:
            identity = contract.functions.getIdentityRegistry().call()
            requests = contract.functions.getAgentValidations(_numeric_service_id(service_id)).call()
        except Exception as exc:
            raise IntegrationError(
                IntegrationErrorCode.CONTRACT_MISMATCH,
                f"Validation Registry read interface failed: {type(exc).__name__}",
            ) from exc
        expected = Web3.to_checksum_address(self._expected_identity_registry)
        if Web3.to_checksum_address(identity) != expected:
            raise IntegrationError(
                IntegrationErrorCode.CONTRACT_MISMATCH,
                "Validation Registry points to an unexpected Identity Registry",
            )
        return ValidationRegistryCapability(
            chain_id=chain_id,
            validation_registry=Web3.to_checksum_address(self._validation_registry),
            identity_registry=expected,
            service_id=service_id,
            existing_request_count=len(requests),
            supports_task_commitment_anchor=False,
            limitation=(
                "validationRequest is an owner/operator initiated request to a validator; "
                "it is not a requester-owned generic task commitment anchor"
            ),
        )


def _numeric_service_id(service_id: str) -> int:
    try:
        return int(service_id.rsplit(":", maxsplit=1)[-1])
    except ValueError as exc:
        raise ValueError("service_id must end with a numeric ERC-8004 agent ID") from exc
