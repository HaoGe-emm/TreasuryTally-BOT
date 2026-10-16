"""Fail closed on stale source overlays or real Streamlit entrypoint exceptions.

Run only inside an isolated image without production mounts, env files or network.
This checks initial rendering, not external evidence or a full business workflow.
"""

from __future__ import annotations

import importlib.metadata
import json
import os
import sys
from hashlib import sha256
from pathlib import Path


def source_manifest(directory: Path) -> dict[str, str]:
    return {
        str(path.relative_to(directory)): sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        for path in sorted(directory.rglob("*.py"))
    }


def assert_source_matches_installed(source: Path, installed: Path) -> int:
    source_files = source_manifest(source)
    installed_files = source_manifest(installed)
    if not source_files or source_files != installed_files:
        different = sorted(
            name for name in source_files.keys() | installed_files.keys()
            if source_files.get(name) != installed_files.get(name)
        )
        raise RuntimeError(f"Source/wheel mismatch: {different}")
    return len(source_files)


def main() -> None:
    root = Path("/app")
    if Path.cwd() != root or os.environ.get("PYTHONPATH") or (root / ".env").exists():
        raise RuntimeError("Image smoke requires /app cwd, no PYTHONPATH override and no .env")
    source = root / "src" / "trust_receipt"
    installed = Path(importlib.metadata.distribution("trust-receipt").locate_file("trust_receipt"))
    count = assert_source_matches_installed(source, installed)
    os.environ.update(APP_REQUIRE_LIVE="true", M0_ENABLE_WRITES="false", M6_ENABLE_WRITES="false")

    from streamlit.testing.v1 import AppTest

    page = AppTest.from_file(str(root / "app" / "streamlit_app.py"), default_timeout=30).run()
    if len(page.exception):
        raise RuntimeError(f"Real app entrypoint raised {len(page.exception)} exception(s)")
    html_bodies = [item.proto.body for item in page.get("html")]
    header = any(
        "核对服务商报表与链上资金流" in body and "TreasuryTally" in body for body in html_bodies
    )
    if not header:
        raise RuntimeError("Real app entrypoint did not render its product header")
    origin = Path(sys.modules["trust_receipt"].__file__).resolve()
    if origin != source / "__init__.py":
        raise RuntimeError(f"Unexpected real entrypoint package origin: {origin}")
    print(json.dumps({
        "status": "PASS", "source_files": count, "source_matches_wheel": True,
        "package_origin": str(origin), "app_exceptions": 0, "product_header": header,
        "scope": "isolated initial rendering only; no external verification",
    }))


if __name__ == "__main__":
    main()
