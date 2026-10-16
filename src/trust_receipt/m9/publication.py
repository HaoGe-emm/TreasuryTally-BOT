"""Explicit publication and immutable recovery of complete public histories."""

from __future__ import annotations

import os
from pathlib import Path

from trust_receipt.hashing import canonical_json_bytes, content_hash
from trust_receipt.m9.bundles import PublicVerificationBundle, validate_public_bundle
from trust_receipt.publishing.models import PublishedArtifact
from trust_receipt.publishing.ports import ContentPublisher


class PublicBundleStore:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def _path(self, bundle: PublicVerificationBundle) -> Path:
        validate_public_bundle(bundle)
        return self._directory / f"{bundle.bundle_hash[2:]}.json"

    def get(self, bundle: PublicVerificationBundle) -> PublishedArtifact | None:
        path = self._path(bundle)
        if not path.is_file():
            return None
        artifact = PublishedArtifact.model_validate_json(path.read_bytes())
        payload = canonical_json_bytes(bundle) + b"\n"
        if artifact.content_hash != content_hash(payload) or artifact.byte_length != len(payload):
            raise ValueError("stored public bundle artifact does not match its bytes")
        return artifact

    def publish(
        self, bundle: PublicVerificationBundle, publisher: ContentPublisher, *, authorized: bool,
    ) -> PublishedArtifact:
        if not authorized:
            raise ValueError("explicit public-history publication authorization is required")
        existing = self.get(bundle)
        if existing is not None:
            return existing
        payload = canonical_json_bytes(bundle) + b"\n"
        expected_hash = content_hash(payload)
        uri = publisher.publish(payload, name=f"history-{bundle.bundle_hash[2:]}.json")
        downloaded = publisher.fetch(uri)
        if content_hash(downloaded) != expected_hash:
            raise ValueError("published public history bytes do not match the prepared bundle")
        artifact = PublishedArtifact(uri=uri, content_hash=expected_hash, byte_length=len(payload))
        path = self._path(bundle)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("xb") as handle:
                handle.write(canonical_json_bytes(artifact) + b"\n")
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError:
            saved = self.get(bundle)
            if saved is None:
                raise ValueError("public history artifact could not be recovered") from None
            return saved
        return artifact
