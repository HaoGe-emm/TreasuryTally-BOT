"""Minimal Sepolia JSON-RPC probe and ERC-20 Transfer parser."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from web3 import HTTPProvider, Web3
from web3.exceptions import Web3Exception, Web3RPCError

from trust_receipt.chain.models import RpcProbeResult, TransferRecord
from trust_receipt.integrations.errors import IntegrationError, IntegrationErrorCode
from trust_receipt.integrations.retry import read_with_retry


def _hex_with_prefix(value: Any) -> str:
    encoded = value.hex()
    return encoded if encoded.startswith("0x") else f"0x{encoded}"


TRANSFER_TOPIC = _hex_with_prefix(Web3.keccak(text="Transfer(address,address,uint256)"))
DECIMALS_ABI = [
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function",
    }
]


def _historical_logs_unavailable(error: Exception, *, method: str | None) -> bool:
    """Recognize only the observed structured historical-log denial, never persist its body."""
    if method != "eth_getLogs" or not isinstance(error, Web3RPCError):
        return False
    response = error.rpc_response
    if not isinstance(response, dict):
        return False
    detail = response.get("error")
    if not isinstance(detail, dict) or type(detail.get("code")) is not int or detail["code"] != 4444:
        return False
    message = detail.get("message")
    if not isinstance(message, str):
        return False
    message = message.lower()
    return all(re.search(rf"\b{word}\b", message) for word in ("history", "pruned", "unavailable"))


class EvmRpcProbe:
    def __init__(self, rpc_url: str, *, expected_chain_id: int, timeout_seconds: float = 30) -> None:
        provider = HTTPProvider(rpc_url, request_kwargs={"timeout": timeout_seconds})
        self._web3 = Web3(provider)
        self._expected_chain_id = expected_chain_id

    def _read(self, operation: Callable[[], Any], *, method: str | None = None) -> Any:
        historical_denial = False
        try:
            return read_with_retry(
                operation,
                retryable=lambda exc: not isinstance(exc, ValueError)
                and not _historical_logs_unavailable(exc, method=method),
            )
        except TimeoutError as exc:
            raise IntegrationError(IntegrationErrorCode.TIMEOUT, "RPC read timed out") from exc
        except (OSError, Web3Exception) as exc:
            historical_denial = _historical_logs_unavailable(exc, method=method)
            if not historical_denial:
                raise IntegrationError(
                    IntegrationErrorCode.UNAVAILABLE, f"RPC read failed: {type(exc).__name__}"
                ) from exc
        # Raise outside the handler: no vendor body retained in cause/context.
        if historical_denial:
            raise IntegrationError(
                IntegrationErrorCode.HISTORICAL_DATA_UNAVAILABLE,
                "RPC cannot provide the requested historical Transfer logs",
            )
        raise AssertionError("RPC read ended without a result or failure")

    def chain_id(self) -> int:
        chain_id = int(self._read(lambda: self._web3.eth.chain_id))
        if chain_id != self._expected_chain_id:
            raise IntegrationError(
                IntegrationErrorCode.WRONG_NETWORK,
                f"RPC returned chain_id={chain_id}, expected {self._expected_chain_id}",
            )
        return chain_id

    def latest_block(self) -> int:
        return int(self._read(lambda: self._web3.eth.block_number))

    def fetch_transfer_pages(
        self,
        *,
        token_address: str,
        from_block: int,
        to_block: int,
        page_size_blocks: int = 2_000,
    ) -> tuple[tuple[TransferRecord, ...], ...]:
        """Read every Transfer log in contiguous block pages for one token."""
        if from_block < 0 or to_block < from_block:
            raise ValueError("invalid inclusive block range")
        if page_size_blocks <= 0:
            raise ValueError("page_size_blocks must be positive")
        chain_id = self.chain_id()
        token = Web3.to_checksum_address(token_address)
        decimals = int(self._read(lambda: self._web3.eth.contract(token, abi=DECIMALS_ABI).functions.decimals().call()))
        pages: list[tuple[TransferRecord, ...]] = []
        page_start = from_block
        while page_start <= to_block:
            page_end = min(page_start + page_size_blocks - 1, to_block)
            logs = self._read(
                lambda start=page_start, end=page_end: self._web3.eth.get_logs(
                    {
                        "address": token,
                        "fromBlock": start,
                        "toBlock": end,
                        "topics": [TRANSFER_TOPIC],
                    }
                ),
                method="eth_getLogs",
            )
            pages.append(
                tuple(
                    self._parse_transfer(log, chain_id=chain_id, token_address=token, decimals=decimals)
                    for log in logs
                )
            )
            page_start = page_end + 1
        return tuple(pages)

    def contract_code(self, address: str) -> bytes:
        checksum = Web3.to_checksum_address(address)
        code = bytes(self._read(lambda: self._web3.eth.get_code(checksum)))
        if not code:
            raise IntegrationError(IntegrationErrorCode.CONTRACT_MISMATCH, f"No bytecode at {checksum}")
        return code

    def contract(self, address: str, abi: list[dict[str, Any]]) -> Any:
        return self._web3.eth.contract(Web3.to_checksum_address(address), abi=abi)

    def probe_transfer(
        self,
        *,
        token_address: str,
        from_block: int,
        to_block: int,
        expected_transaction_hash: str,
    ) -> RpcProbeResult:
        chain_id = self.chain_id()
        latest = int(self._read(lambda: self._web3.eth.block_number))
        historical = int(self._read(lambda: self._web3.eth.get_block(from_block)["number"]))
        token = Web3.to_checksum_address(token_address)
        logs = self._read(
            lambda: self._web3.eth.get_logs(
                {"address": token, "fromBlock": from_block, "toBlock": to_block, "topics": [TRANSFER_TOPIC]}
            ),
            method="eth_getLogs",
        )
        if not logs:
            raise IntegrationError(
                IntegrationErrorCode.EMPTY_RESULT,
                "RPC returned no Transfer logs in the fixed range",
            )
        expected_hash = expected_transaction_hash.lower()
        matching = [log for log in logs if _hex_with_prefix(log["transactionHash"]).lower() == expected_hash]
        if not matching:
            raise IntegrationError(
                IntegrationErrorCode.EMPTY_RESULT,
                "The configured known transaction was absent from the returned Transfer logs",
            )
        decimals = int(self._read(lambda: self._web3.eth.contract(token, abi=DECIMALS_ABI).functions.decimals().call()))
        transfer = self._parse_transfer(matching[0], chain_id=chain_id, token_address=token, decimals=decimals)
        return RpcProbeResult(
            chain_id=chain_id,
            latest_block=latest,
            historical_block=historical,
            transfer=transfer,
        )

    @staticmethod
    def _parse_transfer(log: Any, *, chain_id: int, token_address: str, decimals: int) -> TransferRecord:
        topics = log.get("topics", [])
        if len(topics) != 3 or _hex_with_prefix(topics[0]).lower() != TRANSFER_TOPIC.lower():
            raise IntegrationError(IntegrationErrorCode.INVALID_RESPONSE, "Malformed ERC-20 Transfer log topics")
        from_address = Web3.to_checksum_address("0x" + topics[1].hex()[-40:])
        to_address = Web3.to_checksum_address("0x" + topics[2].hex()[-40:])
        amount = int.from_bytes(bytes(log["data"]), byteorder="big", signed=False)
        return TransferRecord(
            chain_id=chain_id,
            token_address=token_address,
            transaction_hash=_hex_with_prefix(log["transactionHash"]),
            log_index=int(log["logIndex"]),
            block_number=int(log["blockNumber"]),
            block_hash=_hex_with_prefix(log["blockHash"]) if log.get("blockHash") else None,
            from_address=from_address,
            to_address=to_address,
            amount_base_units=str(amount),
            token_decimals=decimals,
            source="rpc",
        )
