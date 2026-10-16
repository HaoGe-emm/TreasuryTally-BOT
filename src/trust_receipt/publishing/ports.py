"""Public content storage contract."""

from typing import Protocol


class ContentPublisher(Protocol):
    def publish(self, payload: bytes, *, name: str) -> str: ...

    def fetch(self, uri: str) -> bytes: ...
