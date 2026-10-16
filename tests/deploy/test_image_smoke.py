from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = spec_from_file_location("image_smoke", ROOT / "scripts/deploy/check_image.py")
assert SPEC is not None and SPEC.loader is not None
SMOKE = module_from_spec(SPEC)
SPEC.loader.exec_module(SMOKE)


def test_identical_source_and_wheel_pass(tmp_path):
    source = tmp_path / "source"
    installed = tmp_path / "installed"
    for directory in (source, installed):
        directory.mkdir()
        (directory / "__init__.py").write_text("# package\n")
    assert SMOKE.assert_source_matches_installed(source, installed) == 1


def test_git_checkout_line_endings_are_not_source_drift(tmp_path):
    source = tmp_path / "source"
    installed = tmp_path / "installed"
    source.mkdir()
    installed.mkdir()
    (source / "__init__.py").write_bytes(b"# package\r\n")
    (installed / "__init__.py").write_bytes(b"# package\n")
    assert SMOKE.assert_source_matches_installed(source, installed) == 1


@pytest.mark.parametrize("failure", ["missing", "changed", "stale_extra", "empty"])
def test_stale_source_or_wheel_fails(tmp_path, failure):
    source = tmp_path / "source"
    installed = tmp_path / "installed"
    source.mkdir()
    installed.mkdir()
    if failure != "empty":
        (installed / "__init__.py").write_text("# current\n")
    if failure in {"changed", "stale_extra"}:
        (source / "__init__.py").write_text("# old\n" if failure == "changed" else "# current\n")
    if failure == "stale_extra":
        (source / "old.py").write_text("# removed module\n")
    with pytest.raises(RuntimeError, match="Source/wheel mismatch"):
        SMOKE.assert_source_matches_installed(source, installed)


def test_release_dockerfile_checks_real_entrypoint_after_source_copy():
    dockerfile = (ROOT / "deploy/Dockerfile.release").read_text()
    assert "COPY --chown=app:app src /app/src" in dockerfile
    assert dockerfile.index("COPY --chown=app:app src") < dockerfile.index("RUN python -c")
    assert "WORKDIR /app" in dockerfile
    assert "runpy.run_path('/opt/trust-receipt-smoke/check_image.py', run_name='__main__')" in dockerfile
    assert "RUN python /opt/" not in dockerfile
    assert "PYTHONPATH=" not in dockerfile
