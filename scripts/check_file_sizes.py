"""Enforce the repository's 1000-physical-line source file limit."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCOPED_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".jsx",
    ".ps1",
    ".py",
    ".sh",
    ".sol",
    ".toml",
    ".ts",
    ".tsx",
    ".yaml",
    ".yml",
}
EXCLUDED_PARTS = {
    ".code-review-graph",
    ".git",
    ".playwright-cli",
    ".pytest_cache",
    ".ruff_cache",
    ".tmp",
    ".venv",
    ".venv-blockscout",
    "data",
    "references",
}


def main() -> int:
    oversized: list[tuple[Path, int]] = []
    for path in PROJECT_ROOT.rglob("*"):
        relative = path.relative_to(PROJECT_ROOT)
        if not path.is_file() or path.suffix.lower() not in SCOPED_SUFFIXES:
            continue
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if relative.parts[:2] == ("receipts", "private"):
            continue
        with path.open(encoding="utf-8") as handle:
            line_count = sum(1 for _ in handle)
        if line_count > 1000:
            oversized.append((relative, line_count))
    if oversized:
        for path, line_count in oversized:
            print(f"{line_count}\t{path}")
        return 1
    print("All scoped files are <= 1000 physical lines.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
