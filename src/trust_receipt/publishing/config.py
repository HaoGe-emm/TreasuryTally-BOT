"""M6 publishing configuration loaded without exposing credentials."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, SecretStr


class M6Settings(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    pinata_jwt: SecretStr | None = None
    pinata_api_url: str = "https://uploads.pinata.cloud/v3/files"
    pinata_gateway_url: str = "https://gateway.pinata.cloud/ipfs"
    public_receipt_directory: Path | None = None
    public_receipt_base_url: str | None = None
    enable_writes: bool = False

    @classmethod
    def load(cls, env_file: Path | str = ".env") -> M6Settings:
        file_values = dotenv_values(env_file) if Path(env_file).is_file() else {}
        merged = {**file_values, **os.environ}
        values = {
            "pinata_jwt": merged.get("PINATA_JWT") or None,
            "pinata_api_url": merged.get("PINATA_API_URL") or cls.model_fields["pinata_api_url"].default,
            "pinata_gateway_url": (
                merged.get("PINATA_GATEWAY_URL") or cls.model_fields["pinata_gateway_url"].default
            ),
            "public_receipt_directory": merged.get("PUBLIC_RECEIPT_DIRECTORY") or None,
            "public_receipt_base_url": merged.get("PUBLIC_RECEIPT_BASE_URL") or None,
            "enable_writes": merged.get("M6_ENABLE_WRITES", "false"),
        }
        return cls.model_validate(values)
