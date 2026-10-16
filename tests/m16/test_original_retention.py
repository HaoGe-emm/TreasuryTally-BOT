"""Original bytes must become visible whole, without overwriting existing evidence."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from multiprocessing import get_context
from pathlib import Path
from threading import Event, current_thread
from unittest.mock import patch

import pytest

from trust_receipt.hashing import content_hash
from trust_receipt.services import upload
from trust_receipt.services.upload import retain_original


class PausedStream:
    def __init__(self, stream, ready, release):
        self.stream = stream
        self.ready = ready
        self.release = release

    def __enter__(self):
        self.stream.__enter__()
        return self

    def __exit__(self, *args):
        return self.stream.__exit__(*args)

    def write(self, data):
        split = len(data) // 2
        self.stream.write(data[:split])
        self.stream.flush()
        self.ready.set()
        assert self.release.wait(20), "paused writer was not released"
        return split + self.stream.write(data[split:])

    def __getattr__(self, name):
        return getattr(self.stream, name)


def _retain_in_paused_process(payload, directory, ready, release):
    original_fdopen = upload.os.fdopen

    def paused_fdopen(*args, **kwargs):
        return PausedStream(original_fdopen(*args, **kwargs), ready, release)

    with patch.object(upload.os, "fdopen", paused_fdopen):
        retain_original(payload, directory)


def test_partial_writer_does_not_expose_hash_target(tmp_path, monkeypatch):
    payload = b'{"private":"original report"}'
    target = tmp_path / f"{content_hash(payload)[2:]}.json"
    ready, release = Event(), Event()
    original_open = Path.open
    original_fdopen = upload.os.fdopen

    def paused_open(path, mode="r", *args, **kwargs):
        stream = original_open(path, mode, *args, **kwargs)
        if mode == "xb" and current_thread().name.startswith("paused-retention"):
            return PausedStream(stream, ready, release)
        return stream

    def paused_fdopen(*args, **kwargs):
        stream = original_fdopen(*args, **kwargs)
        if current_thread().name.startswith("paused-retention"):
            return PausedStream(stream, ready, release)
        return stream

    monkeypatch.setattr(Path, "open", paused_open)
    monkeypatch.setattr(upload.os, "fdopen", paused_fdopen)
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="paused-retention") as pool:
        first = pool.submit(retain_original, payload, tmp_path)
        try:
            assert ready.wait(10), "writer did not reach partial write"
            assert not target.exists(), "hash target exposed incomplete original bytes"
            assert retain_original(payload, tmp_path) == content_hash(payload)
        finally:
            release.set()
        assert first.result(timeout=10) == content_hash(payload)
    assert target.read_bytes() == payload
    assert list(tmp_path.iterdir()) == [target]


def test_process_partial_writer_and_other_process_publish_identical_original(tmp_path):
    payload = b"same private original across independent processes"
    target = tmp_path / f"{content_hash(payload)[2:]}.json"
    context = get_context("spawn")
    ready, release = context.Event(), context.Event()
    first = context.Process(target=_retain_in_paused_process, args=(payload, tmp_path, ready, release))
    first.start()
    try:
        assert ready.wait(20), "child did not reach partial write"
        assert not target.exists()
        assert retain_original(payload, tmp_path) == content_hash(payload)
        assert target.read_bytes() == payload
    finally:
        release.set()
        first.join(20)
        if first.is_alive():
            first.terminate()
            first.join(5)
    assert first.exitcode == 0
    assert list(tmp_path.iterdir()) == [target]


def test_same_payload_is_idempotent_without_replacing_original(tmp_path):
    payload = b"immutable original"
    digest = retain_original(payload, tmp_path)
    target = tmp_path / f"{digest[2:]}.json"
    original_stat = target.stat()
    assert retain_original(payload, tmp_path) == digest
    assert target.stat().st_ino == original_stat.st_ino
    assert target.stat().st_mtime_ns == original_stat.st_mtime_ns
    assert target.read_bytes() == payload
    if upload.os.name == "posix":
        assert target.stat().st_mode & 0o777 == 0o600
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize("corrupt", [b"", b"incomplete", b"wrong existing content"])
def test_corrupt_original_is_rejected_and_preserved(tmp_path, corrupt):
    payload = b"intended original"
    target = tmp_path / f"{content_hash(payload)[2:]}.json"
    target.write_bytes(corrupt)
    with pytest.raises(ValueError, match="collision or corrupt"):
        retain_original(payload, tmp_path)
    assert target.read_bytes() == corrupt
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize("operation", ["write", "fsync", "link"])
def test_failed_retention_removes_only_its_temporary(tmp_path, monkeypatch, operation):
    unrelated = tmp_path / ".original-other-writer.tmp"
    unrelated.write_bytes(b"other writer's private bytes")
    original_fdopen = upload.os.fdopen

    def fail(*args, **kwargs):
        raise OSError("injected storage failure")

    class FailedWriteStream(PausedStream):
        def write(self, data):
            self.stream.write(data[:2])
            raise OSError("injected storage failure")

    if operation == "write":
        monkeypatch.setattr(
            upload.os, "fdopen",
            lambda *args, **kwargs: FailedWriteStream(original_fdopen(*args, **kwargs), None, None),
        )
    else:
        monkeypatch.setattr(upload.os, operation, fail)
    with pytest.raises(OSError, match="injected storage failure"):
        retain_original(b"private original", tmp_path)
    assert list(tmp_path.iterdir()) == [unrelated]
    assert unrelated.read_bytes() == b"other writer's private bytes"
