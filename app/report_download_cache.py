"""Bounded private reading-copy bytes, never receipts or business history.

Streamlit keeps downloadable media beyond the rerun that removed its widget.
Only our exact registered IDs are retired here, including their framework refs.
The small framework adapter is tested against the pinned runtime.
"""

import threading
import weakref
from dataclasses import dataclass, field
from uuid import uuid4

from trust_receipt.reporting import ExportUnavailable

FORMATS = frozenset({"docx", "pdf", "html", "png", "svg"})


@dataclass
class _Entry:
    payload: bytes
    media: object | None = None
    file_ids: set[str] = field(default_factory=set)
    references: set[tuple[str, str]] = field(default_factory=set)


class DownloadLease:
    """Session owns this lease; cache never retains the session or lease."""

    def __init__(self, cache):
        self.owner = uuid4().hex
        self._finalizer = weakref.finalize(self, cache.drop_owner, self.owner)

    def close(self):
        self._finalizer()


class DownloadCache:
    def __init__(self, *, max_bytes: int, max_file_bytes: int):
        if not 0 < max_file_bytes <= max_bytes:
            raise ValueError("Invalid download budget")
        self.max_bytes = max_bytes
        self.max_file_bytes = max_file_bytes
        self._entries = {}
        self._views = {}
        self._bytes = 0
        self._retired = {}
        self._lock = threading.RLock()

    def lease(self):
        return DownloadLease(self)

    def activate(self, owner, view_hash):
        with self._lock:
            if self._views.get(owner) != view_hash:
                self.drop_owner(owner)
                self._views[owner] = view_hash

    def drop_owner(self, owner):
        with self._lock:
            for key in [key for key in self._entries if key[0] == owner]:
                entry = self._entries.pop(key)
                self._bytes -= len(entry.payload)
                self._retire_media(entry)
            self._views.pop(owner, None)

    def _retire_media(self, entry):
        manager = entry.media
        if manager is None:
            return
        retained = set().union(*(item.file_ids for item in self._entries.values()
                                 if item.media is manager))
        retained_refs = set().union(*(item.references for item in self._entries.values()
                                      if item.media is manager))
        with manager._lock:
            for session, coordinate in entry.references - retained_refs:
                refs = manager._files_by_session_and_coord.get(session, {})
                if refs.get(coordinate) in entry.file_ids:
                    del refs[coordinate]
            for file_id in entry.file_ids - retained:
                if file_id not in manager._file_metadata:
                    continue
                if any(file_id in refs.values() for refs in manager._files_by_session_and_coord.values()):
                    # A foreign/legacy widget still owns this deduplicated file.
                    # Keep it and continue charging the application budget.
                    size = manager._storage._files_by_id[file_id].content_size
                    key = (weakref.ref(manager), file_id)
                    if key not in self._retired:
                        self._retired[key] = size
                        self._bytes += size
                else:
                    manager._delete_file(file_id)

    def _sweep_retired(self):
        for key, size in list(self._retired.items()):
            manager_ref, file_id = key
            manager = manager_ref()
            if manager is not None:
                with manager._lock:
                    if any(file_id in refs.values() for refs in manager._files_by_session_and_coord.values()):
                        continue
                    if file_id in manager._file_metadata:
                        manager._delete_file(file_id)
            del self._retired[key]
            self._bytes -= size

    def get(self, owner, view_hash, suffix):
        with self._lock:
            entry = self._entries.get((owner, view_hash, suffix))
            return entry.payload if entry is not None else None

    def put(self, owner, view_hash, suffix, payload):
        if suffix not in FORMATS or not isinstance(payload, (bytes, str)):
            raise ExportUnavailable("EXPORT_UNAVAILABLE: invalid download")
        payload = payload.encode("utf-8") if isinstance(payload, str) else payload
        with self._lock:
            self._sweep_retired()
            if self._views.get(owner) != view_hash:
                raise ExportUnavailable("EXPORT_UNAVAILABLE: obsolete view")
            key = (owner, view_hash, suffix)
            previous = self._entries.get(key)
            # Published predecessors may remain owned by a foreign widget;
            # reserve their bytes conservatively before mutating anything.
            size = self._bytes - (len(previous.payload) if previous and previous.media is None else 0) + len(payload)
            if not payload or len(payload) > self.max_file_bytes or size > self.max_bytes:
                raise ExportUnavailable("EXPORT_UNAVAILABLE: download budget exceeded")
            if previous is not None:
                del self._entries[key]
                self._bytes -= len(previous.payload)
                self._retire_media(previous)
            self._entries[key] = _Entry(payload)
            self._bytes += len(payload)

    def publish(self, owner, view_hash, suffix, *, media, session_id, coordinate, filename, mime, download):
        """Atomic registration versus pruning; canonical bytes avoid hidden copies."""
        with self._lock:
            entry = self._entries.get((owner, view_hash, suffix))
            if entry is None:
                raise ExportUnavailable("EXPORT_UNAVAILABLE: download expired")
            if media is not None:
                self._check_media_adapter(media)
            try:
                download(entry.payload)
            finally:
                # Track an already-added file even if widget enqueue fails.
                if media is not None:
                    self._bind_registered(entry, media, session_id, coordinate, filename, mime)
            if media is None:
                return
            if not entry.file_ids:
                raise ExportUnavailable("EXPORT_UNAVAILABLE: download registration failed")

    def _bind_registered(self, entry, media, session_id, coordinate, filename, mime):
        with media._lock:
            file_id = media._files_by_session_and_coord.get(session_id, {}).get(coordinate)
            item = media._storage._files_by_id.get(file_id)
            if (item is None or item.filename != filename or item.mimetype != mime
                    or item.content != entry.payload):
                return
            entry.media = media
            entry.file_ids.add(file_id)
            self._bytes -= self._retired.pop((weakref.ref(media), file_id), 0)
            entry.references.add((session_id, coordinate))
            entry.payload = item.content

    @staticmethod
    def _check_media_adapter(media):
        if (not all(hasattr(media, name) for name in (
            "_lock", "_files_by_session_and_coord", "_file_metadata", "_delete_file", "_storage",
        )) or not hasattr(media._storage, "_files_by_id")):
            raise ExportUnavailable("EXPORT_UNAVAILABLE: unsupported media runtime")
        if (not all(isinstance(value, dict) for value in (
            media._files_by_session_and_coord, media._file_metadata, media._storage._files_by_id,
        )) or not callable(media._delete_file)):
            raise ExportUnavailable("EXPORT_UNAVAILABLE: unsupported media runtime")

    def stats(self):
        with self._lock:
            self._sweep_retired()
            return {"bytes": self._bytes, "files": len(self._entries), "owners": len(self._views)}
