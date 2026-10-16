from pathlib import Path

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--m1-fixtures", help="Require and verify an M1 fixture directory, including manifest.json")


@pytest.fixture
def m1_fixture_root(request: pytest.FixtureRequest) -> Path:
    explicit = request.config.getoption("--m1-fixtures")
    root = Path(explicit) if explicit else Path(request.config.rootpath) / "fixtures" / "m1"
    if not (root / "manifest.json").is_file():
        if explicit:
            pytest.fail(f"Required M1 fixture manifest is missing: {root / 'manifest.json'}")
        pytest.skip("M1 fixtures are not integrated yet; use --m1-fixtures PATH to require the integration gate")
    return root
