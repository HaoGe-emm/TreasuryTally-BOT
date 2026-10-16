"""Stable ports for structured model output."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

StructuredArtifact = TypeVar("StructuredArtifact", bound=BaseModel)


class StructuredOutputPort(Protocol):
    """A model may return one schema and receives no executable tools."""

    def generate(
        self,
        *,
        schema: type[StructuredArtifact],
        system_prompt: str,
        payload: Mapping[str, Any],
    ) -> StructuredArtifact: ...
