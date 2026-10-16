"""Guide integration is read-only; browser-document state is tested separately."""

import shutil
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.onboarding import onboarding_html, render_onboarding


def test_workspace_uses_only_trusted_bundled_html():
    st = Mock(query_params={})
    render_onboarding(st)
    st.html.assert_called_once_with(onboarding_html(), unsafe_allow_javascript=True)
    assert len(st.method_calls) == 1


def test_public_verifier_does_not_show_workspace_guide():
    st = Mock(query_params={"verify": "1"})
    render_onboarding(st)
    st.html.assert_not_called()


def test_guide_has_accessible_native_dialog_and_no_persistent_storage():
    html = onboarding_html()
    assert '<dialog id="tr-onboarding" aria-labelledby=' in html
    assert 'aria-live="polite"' in html
    assert 'dialog.showModal()' in html
    assert 'dialog.addEventListener("cancel"' in html
    assert "localStorage" not in html
    assert "sessionStorage" not in html
    assert "fetch(" not in html
    assert "不会自动确认范围、执行验收、发布回执或写链" in html


def test_document_lifecycle_state():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the pure JavaScript lifecycle test")
    result = subprocess.run(
        [node, str(Path(__file__).with_name("onboarding_lifecycle.cjs"))],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert "onboarding lifecycle: PASS" in result.stdout
