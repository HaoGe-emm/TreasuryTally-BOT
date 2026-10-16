from __future__ import annotations

import re
import urllib.parse
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]
METADATA_FIELDS = ("doc-id", "title", "status", "authority-for", "last-reviewed")
LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def _root_documents() -> tuple[Path, ...]:
    return tuple(sorted(PROJECT_ROOT.glob("*.md")))


def _front_matter(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path.name} is missing YAML front matter"
    end = text.find("\n---\n", 4)
    assert end > 4, f"{path.name} has incomplete YAML front matter"
    return text[4:end]


def _metadata_value(front_matter: str, field: str) -> str:
    match = re.search(rf"(?m)^{re.escape(field)}:\s*(.*)$", front_matter)
    assert match is not None, f"missing metadata field: {field}"
    return match.group(1).strip()


def test_root_document_metadata_is_complete_and_doc_ids_are_unique():
    documents = _root_documents()
    doc_ids: list[str] = []
    for document in documents:
        front_matter = _front_matter(document)
        for field in METADATA_FIELDS:
            _metadata_value(front_matter, field)
        doc_id = _metadata_value(front_matter, "doc-id")
        assert doc_id, f"{document.name} has an empty doc-id"
        assert re.fullmatch(r"[a-z0-9-]+", doc_id), f"{document.name} has an invalid doc-id"
        assert re.fullmatch(
            r"\d{4}-\d{2}-\d{2}", _metadata_value(front_matter, "last-reviewed")
        ), f"{document.name} has an invalid last-reviewed date"
        assert "\n  - " in front_matter, f"{document.name} has no authority-for entries"
        doc_ids.append(doc_id)
    assert len(doc_ids) == len(set(doc_ids)), "root document doc-id values must be unique"


def test_local_markdown_links_resolve_inside_the_project():
    missing: list[str] = []
    for document in _root_documents():
        text = document.read_text(encoding="utf-8")
        for target in LINK_PATTERN.findall(text):
            if target.startswith("#") or urllib.parse.urlparse(target).scheme:
                continue
            relative = urllib.parse.unquote(target.split("#", 1)[0])
            resolved = (document.parent / relative).resolve()
            if not resolved.is_relative_to(PROJECT_ROOT.resolve()) or not resolved.exists():
                missing.append(f"{document.name} -> {target}")
    assert missing == [], "broken local Markdown links:\n" + "\n".join(missing)
