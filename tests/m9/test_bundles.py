import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

import pytest

from trust_receipt.hashing import canonical_json_bytes, content_hash, hash_model
from trust_receipt.m9 import (
    PublicBundleResolver,
    PublicReceiptReference,
    PublicReferenceKind,
    build_public_bundle,
    verify_public_reference,
)
from trust_receipt.m9.publication import PublicBundleStore
from trust_receipt.publishing.local import LocalDirectoryPublisher


def _bundle(two_attempts):
    return build_public_bundle(
        (two_attempts.first_receipt, two_attempts.second_receipt), authorized=True,
    )


@pytest.mark.parametrize("kind", [
    PublicReferenceKind.URI, PublicReferenceKind.RECEIPT_HASH, PublicReferenceKind.TASK_HASH,
])
def test_complete_public_history_replays_repair_without_private_workspace(two_attempts, kind):
    bundle = _bundle(two_attempts)
    payload = canonical_json_bytes(bundle) + b"\n"
    value = {
        PublicReferenceKind.URI: "https://example.test/history.json",
        PublicReferenceKind.RECEIPT_HASH: bundle.receipts[1].receipt_hash,
        PublicReferenceKind.TASK_HASH: bundle.receipts[1].task_spec.spec_hash,
    }[kind]
    result = verify_public_reference(
        PublicReceiptReference(kind, value),
        PublicBundleResolver(
            payload, location="https://example.test/history.json", expected_content_hash=content_hash(payload),
        ),
    )
    assert result.status.value == "VERIFIED"
    assert result.outcome.value == "PASS"
    assert result.resolution.value == "FIXED"
    assert result.attempt == 2
    assert result.commitment_status.value == "UNVERIFIED"
    assert bundle.revisions[1].parent_receipt_hash == bundle.receipts[0].receipt_hash
    assert bundle.receipts[0].receipt_hash != two_attempts.first_receipt.receipt_hash
    assert b'"report_text"' not in payload
    assert b'"signature"' not in payload


def test_bundle_requires_authorization_and_rejects_tampering(two_attempts):
    with pytest.raises(ValueError, match="authorization"):
        build_public_bundle((two_attempts.first_receipt,), authorized=False)
    bundle = _bundle(two_attempts)
    altered = bundle.model_copy(update={"receipts": (bundle.receipts[1], bundle.receipts[0])})
    altered = altered.model_copy(update={"bundle_hash": hash_model(altered, exclude=frozenset({"bundle_hash"}))})
    result = verify_public_reference(
        PublicReceiptReference(PublicReferenceKind.URI, "https://example.test/history.json"),
        PublicBundleResolver(canonical_json_bytes(altered), location="https://example.test/history.json"),
    )
    assert result.status.value == "INVALID"


def test_bundle_missing_parent_is_invalid_and_unknown_hash_is_inconclusive(two_attempts):
    bundle = _bundle(two_attempts)
    altered = bundle.model_copy(update={"revisions": (bundle.revisions[1],)})
    altered = altered.model_copy(update={"bundle_hash": hash_model(altered, exclude=frozenset({"bundle_hash"}))})
    result = verify_public_reference(
        PublicReceiptReference(PublicReferenceKind.URI, "public-file"),
        PublicBundleResolver(canonical_json_bytes(altered), location="public-file"),
    )
    assert result.status.value == "INVALID"
    unknown = verify_public_reference(
        PublicReceiptReference(PublicReferenceKind.RECEIPT_HASH, "0x" + "0" * 64),
        PublicBundleResolver(canonical_json_bytes(bundle), location="public-file"),
    )
    assert unknown.status.value == "INCONCLUSIVE"


def test_bundle_does_not_invent_feedback_transaction_binding(two_attempts):
    bundle = _bundle(two_attempts)
    result = verify_public_reference(
        PublicReceiptReference(PublicReferenceKind.FEEDBACK_TRANSACTION, "0x" + "ab" * 32),
        PublicBundleResolver(canonical_json_bytes(bundle), location="public-file"),
    )
    assert result.status.value == "INCONCLUSIVE"


@pytest.mark.parametrize("payload", [b'{"bundle_version":"1.0","bundle_version":"1.0"}', b'{"value":NaN}'])
def test_ambiguous_or_nonfinite_public_json_is_invalid(payload):
    result = verify_public_reference(
        PublicReceiptReference(PublicReferenceKind.URI, "public-file"),
        PublicBundleResolver(payload, location="public-file"),
    )
    assert result.status.value == "INVALID"


def test_bundle_publisher_verifies_download_and_restores_without_duplicate_upload(tmp_path, two_attempts):
    bundle = _bundle(two_attempts)
    store = PublicBundleStore(tmp_path / "metadata")
    publisher = LocalDirectoryPublisher(tmp_path / "public")
    with pytest.raises(ValueError, match="authorization"):
        store.publish(bundle, publisher, authorized=False)
    artifact = store.publish(bundle, publisher, authorized=True)
    assert PublicBundleStore(tmp_path / "metadata").get(bundle) == artifact
    assert store.publish(bundle, publisher, authorized=True) == artifact
    downloaded = publisher.fetch(artifact.uri)
    assert content_hash(downloaded) == artifact.content_hash

    class BrokenPublisher:
        def publish(self, payload, *, name):
            return "https://example.test/history.json"

        def fetch(self, uri):
            return b"{}"

    broken_store = PublicBundleStore(tmp_path / "broken-metadata")
    with pytest.raises(ValueError, match="do not match"):
        broken_store.publish(bundle, BrokenPublisher(), authorized=True)
    assert broken_store.get(bundle) is None


def test_new_process_verifies_complete_public_bundle(tmp_path, two_attempts):
    bundle = _bundle(two_attempts)
    payload = canonical_json_bytes(bundle) + b"\n"
    publisher = LocalDirectoryPublisher(tmp_path / "public")
    uri = publisher.publish(payload, name="history.json")
    path = Path(url2pathname(unquote(urlparse(uri).path)))
    environment = os.environ.copy()
    project_root = Path(__file__).parents[2]
    environment["PYTHONPATH"] = str(project_root / "src")
    result = subprocess.run(
        [sys.executable, "-m", "trust_receipt.m9.cli", str(path), "--bundle",
         "--kind", "TASK_HASH", "--value", bundle.receipts[1].task_spec.spec_hash,
         "--expected-content-hash", content_hash(payload)],
        cwd=tmp_path, env=environment, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    verified = json.loads(result.stdout)
    assert verified["status"] == "VERIFIED"
    assert verified["resolution"] == "FIXED"
