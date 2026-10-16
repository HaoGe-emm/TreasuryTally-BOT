"""Secret-safe configuration for the real M4 model adapter."""

from __future__ import annotations

import os
from pathlib import Path
from typing import ClassVar

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, SecretStr


class M4AISettings(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    api_key: SecretStr | None = None
    model_name: str | None = Field(default=None, min_length=1)
    deepseek_api_key: SecretStr | None = None
    deepseek_model_name: str | None = Field(default=None, min_length=1)
    timeout_seconds: float = Field(default=30, gt=0, le=120)
    max_retries: int = Field(default=2, ge=0, le=2)

    ENV_TO_FIELD: ClassVar[dict[str, str]] = {
        "OPENAI_API_KEY": "api_key",
        "OPENAI_MODEL": "model_name",
        "DEEPSEEK_API_KEY": "deepseek_api_key",
        "DEEPSEEK_MODEL": "deepseek_model_name",
        "AI_TIMEOUT_SECONDS": "timeout_seconds",
        "AI_MAX_RETRIES": "max_retries",
    }

    @classmethod
    def load(cls, env_file: Path | str = ".env") -> M4AISettings:
        file_values = dotenv_values(env_file) if Path(env_file).is_file() else {}
        merged = {**file_values, **os.environ}
        values = {field: merged[name] for name, field in cls.ENV_TO_FIELD.items() if merged.get(name) not in (None, "")}
        return cls.model_validate(values)

    def missing_for_openai(self) -> list[str]:
        required = {"OPENAI_API_KEY": self.api_key, "OPENAI_MODEL": self.model_name}
        return [name for name, value in required.items() if value is None]

    def api_key_value(self) -> str:
        if self.api_key is None:
            raise ValueError("OPENAI_API_KEY is not configured")
        return self.api_key.get_secret_value()

    def missing_for_deepseek(self) -> list[str]:
        required = {
            "DEEPSEEK_API_KEY": self.deepseek_api_key,
            "DEEPSEEK_MODEL": self.deepseek_model_name,
        }
        return [name for name, value in required.items() if value is None]

    def deepseek_api_key_value(self) -> str:
        if self.deepseek_api_key is None:
            raise ValueError("DEEPSEEK_API_KEY is not configured")
        return self.deepseek_api_key.get_secret_value()
