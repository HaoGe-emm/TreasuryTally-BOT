from pathlib import Path

from trust_receipt.models import FixtureCase, FixtureManifest

from .fixture_gate import assert_expected, run_case


def test_m1_manifest_and_all_cases_match_engine(m1_fixture_root: Path) -> None:
    manifest = FixtureManifest.model_validate_json((m1_fixture_root / "manifest.json").read_text(encoding="utf-8"))
    assert {path.name for path in (m1_fixture_root / "cases").glob("*.json")} == {
        f"{entry.fixture_id}.json" for entry in manifest.fixtures
    }
    for entry in manifest.fixtures:
        case = FixtureCase.model_validate_json((m1_fixture_root / entry.file).read_text(encoding="utf-8"))
        assert case.fixture_id == entry.fixture_id
        assert case.title == entry.title
        assert case.tags == entry.tags
        assert case.expected.outcome == entry.expected_outcome
        assert_expected(case, run_case(case))
