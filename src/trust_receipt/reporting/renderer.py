"""Fixed offline worker adapter. Application composition owns concurrency scope."""

import base64
import hashlib
import json
import os
import shutil
import subprocess
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from trust_receipt.reporting.echarts_flow import echarts_flow_option
from trust_receipt.reporting.models import BusinessReportView


class ExportUnavailable(RuntimeError):
    """No format substitution or silent non-ECharts drawing fallback."""


@dataclass(frozen=True)
class RenderedDiagram:
    view_hash: str
    option_hash: str
    png: bytes
    svg: str


class EChartsRenderer:
    """Reuse one application-owned instance: one complete export at a time.

    Paths are trusted deployment configuration, never report/request fields.
    Runtime script has no networking calls; production must deny worker egress.
    Native-process memory containment belongs to deployment cgroup/Job limits.
    """

    def __init__(self, *, node_path: str | None = None, modules_path: str | None = None):
        self._node = node_path or shutil.which("node")
        self._modules = modules_path
        self._export_lock = threading.RLock()
        self._slots = threading.BoundedSemaphore(1)

    @contextmanager
    def export_slot(self) -> Iterator[None]:
        """Nonblocking complete-export budget, reentrant only on its thread.

        Hold through font/layout/ZIP construction and final output bytes, not
        just Node execution. Callers must share the application-owned instance.
        Contention does not queue or affect the independent original JSON.
        """
        if not self._export_lock.acquire(blocking=False):
            raise ExportUnavailable("EXPORT_UNAVAILABLE: export busy")
        try:
            yield
        finally:
            self._export_lock.release()

    def render(self, view: BusinessReportView) -> RenderedDiagram:
        with self.export_slot():
            return self._render(view)

    def _render(self, view: BusinessReportView) -> RenderedDiagram:
        from trust_receipt.reporting.layout import validate_export_view

        validate_export_view(view)
        if not self._node or not Path(self._node).is_file():
            raise ExportUnavailable("EXPORT_UNAVAILABLE: local renderer not installed")
        pairs = [(r.sender.full.lower(), r.recipient.full.lower()) for r in view.current.flow_rows[:4]]
        limit = 1 if len(pairs) != len(set(pairs)) else 4
        try:
            option = echarts_flow_option(view, limit=limit, theme="print")
        except ValueError as error:
            raise ExportUnavailable("EXPORT_UNAVAILABLE: diagram record limits exceeded") from error
        option_json = json.dumps(option, ensure_ascii=True, separators=(",", ":"))
        view_hash = hashlib.sha256(view.model_dump_json().encode()).hexdigest()
        option_hash = hashlib.sha256(option_json.encode()).hexdigest()
        binding = hashlib.sha256((view_hash + option_hash).encode()).hexdigest()
        data = json.dumps({"binding": binding, "option": option}, ensure_ascii=True).encode()
        if len(data) > 256000:
            raise ExportUnavailable("EXPORT_UNAVAILABLE: diagram exceeds input limit")
        if not self._slots.acquire(blocking=False):
            raise ExportUnavailable("EXPORT_UNAVAILABLE: renderer busy")
        try:
            return self._run(data, binding, view_hash, option_hash)
        finally:
            self._slots.release()

    def _run(self, data: bytes, binding: str, view_hash: str, option_hash: str) -> RenderedDiagram:
        script = files("trust_receipt.reporting").joinpath("assets/renderer/render.cjs")
        # Credentials, NODE_OPTIONS and inherited module overrides are not passed.
        env = {key: os.environ[key] for key in ("PATH", "SystemRoot", "WINDIR", "TEMP", "TMP", "LANG")
               if key in os.environ}
        if self._modules:
            env["NODE_PATH"] = str(Path(self._modules).resolve())
        try:
            result = subprocess.run(
                [self._node, "--max-old-space-size=128", "--disable-proto=throw", str(script)],
                input=data, capture_output=True, timeout=20, check=False, env=env, shell=False,
            )
            if result.returncode or len(result.stdout) > 6000000 or len(result.stderr) > 4096:
                raise ExportUnavailable("EXPORT_UNAVAILABLE: rendering failed")
            output = json.loads(result.stdout)
            if output["binding"] != binding:
                raise ExportUnavailable("EXPORT_UNAVAILABLE: report binding mismatch")
            png = base64.b64decode(output["png"], validate=True)
            svg = output["svg"]
            if not png.startswith(b"\x89PNG\r\n\x1a\n") or len(png) > 4000000 or len(svg.encode()) > 512000:
                raise ExportUnavailable("EXPORT_UNAVAILABLE: invalid diagram")
            from io import BytesIO

            from PIL import Image

            with Image.open(BytesIO(png)) as image:
                if image.format != "PNG" or image.width != 1440 or image.width * image.height > 2600000:
                    raise ExportUnavailable("EXPORT_UNAVAILABLE: invalid image dimensions")
                image.verify()
            return RenderedDiagram(view_hash, option_hash, png, svg)
        except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, TypeError, ImportError) as error:
            raise ExportUnavailable("EXPORT_UNAVAILABLE: local renderer failed") from error
