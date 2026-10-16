"""Validated M0 configuration loaded without exposing secret values."""

from __future__ import annotations

import os
from pathlib import Path
from typing import ClassVar

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

SEPOLIA_CHAIN_ID = 11_155_111


class M0Settings(BaseModel):
    """Configuration needed by real M0 probes."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    rpc_url: SecretStr | None = None
    chain_id: int = SEPOLIA_CHAIN_ID
    rpc_timeout_seconds: float = Field(default=30, gt=0, le=120)
    rpc_confirmations: int = Field(default=2, ge=0, le=128)
    test_token_address: str | None = None
    test_transfer_tx_hash: str | None = None
    test_from_block: int | None = Field(default=None, ge=0)
    test_to_block: int | None = Field(default=None, ge=0)
    blockscout_mcp_url: str = "http://127.0.0.1:8000"
    blockscout_pro_api_key: SecretStr | None = None
    agent0_service_id: str | None = None
    agent0_expected_owner: str | None = None
    identity_registry_address: str | None = None
    reputation_registry_address: str | None = None
    validation_registry_address: str | None = None
    feedback_transaction_hash: str | None = None
    reviewer_address: str | None = None
    feedback_index: int | None = Field(default=None, ge=1)
    reviewer_private_key: SecretStr | None = None
    enable_writes: bool = False

    ENV_TO_FIELD: ClassVar[dict[str, str]] = {
        "ETH_RPC_URL": "rpc_url",
        "CHAIN_ID": "chain_id",
        "RPC_TIMEOUT_SECONDS": "rpc_timeout_seconds",
        "RPC_CONFIRMATIONS": "rpc_confirmations",
        "TEST_TOKEN_ADDRESS": "test_token_address",
        "TEST_TRANSFER_TX_HASH": "test_transfer_tx_hash",
        "TEST_FROM_BLOCK": "test_from_block",
        "TEST_TO_BLOCK": "test_to_block",
        "BLOCKSCOUT_MCP_URL": "blockscout_mcp_url",
        "BLOCKSCOUT_PRO_API_KEY": "blockscout_pro_api_key",
        "AGENT0_SERVICE_ID": "agent0_service_id",
        "AGENT0_EXPECTED_OWNER": "agent0_expected_owner",
        "ERC8004_IDENTITY_REGISTRY_ADDRESS": "identity_registry_address",
        "ERC8004_REPUTATION_REGISTRY_ADDRESS": "reputation_registry_address",
        "ERC8004_VALIDATION_REGISTRY_ADDRESS": "validation_registry_address",
        "ERC8004_FEEDBACK_TX_HASH": "feedback_transaction_hash",
        "ERC8004_REVIEWER_ADDRESS": "reviewer_address",
        "ERC8004_FEEDBACK_INDEX": "feedback_index",
        "REVIEWER_PRIVATE_KEY": "reviewer_private_key",
        "M0_ENABLE_WRITES": "enable_writes",
    }

    @field_validator("test_to_block")
    @classmethod
    def validate_block_range(cls, value: int | None, info: object) -> int | None:
        data = getattr(info, "data", {})
        start = data.get("test_from_block")
        if value is not None and start is not None and value < start:
            raise ValueError("TEST_TO_BLOCK must be greater than or equal to TEST_FROM_BLOCK")
        return value

    @classmethod
    def load(cls, env_file: Path | str = ".env") -> M0Settings:
        file_values = dotenv_values(env_file) if Path(env_file).is_file() else {}
        merged = {**file_values, **os.environ}
        values = {field: merged[name] for name, field in cls.ENV_TO_FIELD.items() if merged.get(name) not in (None, "")}
        return cls.model_validate(values)

    def missing_for_rpc(self) -> list[str]:
        required = {
            "ETH_RPC_URL": self.rpc_url,
            "TEST_TOKEN_ADDRESS": self.test_token_address,
            "TEST_TRANSFER_TX_HASH": self.test_transfer_tx_hash,
            "TEST_FROM_BLOCK": self.test_from_block,
            "TEST_TO_BLOCK": self.test_to_block,
        }
        return [name for name, value in required.items() if value is None]

    def missing_for_agent0(self) -> list[str]:
        required = {
            "ETH_RPC_URL": self.rpc_url,
            "AGENT0_SERVICE_ID": self.agent0_service_id,
            "AGENT0_EXPECTED_OWNER": self.agent0_expected_owner,
        }
        return [name for name, value in required.items() if value is None]

    def missing_for_erc8004_read(self) -> list[str]:
        required = {
            "ETH_RPC_URL": self.rpc_url,
            "ERC8004_IDENTITY_REGISTRY_ADDRESS": self.identity_registry_address,
            "ERC8004_REPUTATION_REGISTRY_ADDRESS": self.reputation_registry_address,
            "ERC8004_VALIDATION_REGISTRY_ADDRESS": self.validation_registry_address,
            "AGENT0_SERVICE_ID": self.agent0_service_id,
        }
        return [name for name, value in required.items() if value is None]

    def missing_for_erc8004_write(self) -> list[str]:
        missing = self.missing_for_erc8004_read()
        if self.reviewer_private_key is None:
            missing.append("REVIEWER_PRIVATE_KEY")
        if not self.enable_writes:
            missing.append("M0_ENABLE_WRITES=true")
        return missing

    def missing_for_erc8004_feedback_read(self) -> list[str]:
        required = {
            "ETH_RPC_URL": self.rpc_url,
            "ERC8004_IDENTITY_REGISTRY_ADDRESS": self.identity_registry_address,
            "ERC8004_REPUTATION_REGISTRY_ADDRESS": self.reputation_registry_address,
            "AGENT0_SERVICE_ID": self.agent0_service_id,
            "ERC8004_FEEDBACK_TX_HASH": self.feedback_transaction_hash,
            "ERC8004_REVIEWER_ADDRESS": self.reviewer_address,
            "ERC8004_FEEDBACK_INDEX": self.feedback_index,
        }
        return [name for name, value in required.items() if value is None]

    def rpc_url_value(self) -> str:
        if self.rpc_url is None:
            raise ValueError("ETH_RPC_URL is not configured")
        return self.rpc_url.get_secret_value()
