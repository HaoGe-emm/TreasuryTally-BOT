from __future__ import annotations

from pathlib import Path

from jsonschema import Draft202012Validator

from scripts.export_schemas import (
    SCHEMA_DIALECT,
    SCHEMA_MODELS,
    SCHEMA_VERSION,
    generate_schemas,
    render_schema,
    write_schemas,
)


def test_all_frozen_schemas_have_stable_identity_and_valid_dialect() -> None:
    schemas = generate_schemas()

    assert tuple(schemas) == tuple(filename for filename, _, _ in SCHEMA_MODELS)
    for filename, kebab_name, model in SCHEMA_MODELS:
        schema = schemas[filename]
        assert schema["$schema"] == SCHEMA_DIALECT
        assert schema["$id"] == f"urn:xinjv:schema:{SCHEMA_VERSION}:{kebab_name}"
        assert schema["title"] == model.__name__
        assert schema["additionalProperties"] is False
        Draft202012Validator.check_schema(schema)


def test_generation_is_byte_stable_and_check_detects_drift(tmp_path: Path) -> None:
    write_schemas(tmp_path)
    first = {path.name: path.read_bytes() for path in tmp_path.iterdir()}

    write_schemas(tmp_path)
    second = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    assert second == first
    assert all(content.endswith(b"\n") and not content.startswith(b"\xef\xbb\xbf") for content in second.values())

    write_schemas(tmp_path, check=True)
    drifted = tmp_path / "task_spec.schema.json"
    drifted.write_text("{}\n", encoding="utf-8")

    try:
        write_schemas(tmp_path, check=True)
    except RuntimeError as exc:
        assert "task_spec.schema.json" in str(exc)
    else:
        raise AssertionError("schema check did not detect a changed file")


def test_rendering_sorts_keys_and_has_one_trailing_newline() -> None:
    rendered = render_schema({"z": 1, "a": 2})
    assert rendered == '{\n  "a": 2,\n  "z": 1\n}\n'
