"""Operator-owned workspace registry; MCP callers never supply filesystem paths."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trust_receipt.headless.contracts import HeadlessProfile, WorkspaceHandle


class WorkspaceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    directory: Path
    project_root: Path
    profile: HeadlessProfile = HeadlessProfile.LIVE_READ_ONLY
    ai_provider: Literal["openai", "deepseek", "fixture"] = "deepseek"
    evidence_provider: Literal["rpc", "fixture"] = "rpc"

    @model_validator(mode="after")
    def enforce_profile(self) -> WorkspaceConfig:
        fixture_selected = self.ai_provider == "fixture" or self.evidence_provider == "fixture"
        if self.profile is HeadlessProfile.LIVE_READ_ONLY and fixture_selected:
            raise ValueError("LIVE_READ_ONLY workspaces cannot use fixture providers")
        if self.profile is HeadlessProfile.FIXTURE_TEST_ONLY and not (
            self.ai_provider == "fixture" and self.evidence_provider == "fixture"
        ):
            raise ValueError("FIXTURE_TEST_ONLY requires fixture AI and evidence providers")
        return self


class RegistryDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    config_version: Literal["1.0"]
    workspaces: dict[WorkspaceHandle, WorkspaceConfig] = Field(min_length=1)


class WorkspaceRegistry:
    def __init__(self, workspaces: dict[str, WorkspaceConfig]) -> None:
        self._workspaces = workspaces

    @classmethod
    def load(cls, path: str | Path) -> WorkspaceRegistry:
        config_path = Path(path).resolve(strict=True)
        document = RegistryDocument.model_validate_json(config_path.read_text(encoding="utf-8"))
        resolved: dict[str, WorkspaceConfig] = {}
        directories: list[Path] = []
        for handle, item in document.workspaces.items():
            directory = cls._resolve_from(config_path.parent, item.directory)
            project_root = cls._resolve_from(config_path.parent, item.project_root)
            if not (project_root / "fixtures" / "m1").is_dir():
                raise ValueError("workspace project_root is not a TreasuryTally checkout")
            if any(directory == existing or directory.is_relative_to(existing) or existing.is_relative_to(directory)
                   for existing in directories):
                raise ValueError("workspace directories must be distinct and non-nested")
            directories.append(directory)
            resolved[handle] = item.model_copy(update={"directory": directory, "project_root": project_root})
        return cls(resolved)

    @staticmethod
    def _resolve_from(base: Path, value: Path) -> Path:
        target = value if value.is_absolute() else base / value
        return target.resolve()

    def get(self, handle: str) -> WorkspaceConfig:
        try:
            return self._workspaces[handle]
        except KeyError:
            raise KeyError("unknown workspace handle") from None

    def handles(self) -> tuple[str, ...]:
        return tuple(sorted(self._workspaces))
