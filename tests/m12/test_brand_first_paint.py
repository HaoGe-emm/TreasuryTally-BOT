from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[2]


def test_brand_shell_is_direct_html_and_logo_is_eager(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_REQUIRE_LIVE", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    monkeypatch.setenv("DEEPSEEK_MODEL", "")
    monkeypatch.chdir(tmp_path)
    page = AppTest.from_file(str(ROOT / "app/streamlit_app.py"), default_timeout=30).run()
    assert not page.exception
    bodies = [item.proto.body for item in page.get("html")]
    assert any("--tr-bg-page" in body for body in bodies)
    brand = next(body for body in bodies if 'class="product-bar"' in body)
    assert "核对服务商报表与链上资金流" in brand
    assert "<span>TreasuryTally</span>" in brand
    assert 'alt="TreasuryTally Logo"' in brand
    assert 'loading="eager" decoding="async"' in brand
    assert 'class="brand-logo"' in brand
    assert 'class="hero-emblem"' in brand
    assert not any('class="product-bar"' in item.value for item in page.markdown)
    assert 'unsafe_allow_javascript=True' not in (ROOT / "app/streamlit_app.py").read_text(encoding="utf-8")


def test_display_media_preserves_original_and_reverse_proxy_prefix(monkeypatch):
    from streamlit.elements.lib import image_utils

    from app.branding import LOGO_PATH, logo_display_url

    original = LOGO_PATH.read_bytes()
    calls = []

    def fake_media(image, layout, **kwargs):
        calls.append((image, layout.width, kwargs))
        return "/media/content-hash.png"

    monkeypatch.setattr(image_utils, "image_to_url", fake_media)
    assert logo_display_url("/trust-receipt/") == "/trust-receipt/media/content-hash.png"
    assert calls[0][0] == str(LOGO_PATH)
    assert calls[0][1] == 288
    assert calls[0][2]["output_format"] == "PNG"
    assert LOGO_PATH.read_bytes() == original
