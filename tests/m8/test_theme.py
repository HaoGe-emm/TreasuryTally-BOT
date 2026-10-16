import re
import tomllib
from pathlib import Path

import pytest

from app.branding import LOGO_PATH, logo_data_url, logo_static_url
from app.styles import APP_CSS


def luminance(color):
    channels = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    channels = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
                for channel in channels]
    return sum(channel * weight for channel, weight in zip(channels, (0.2126, 0.7152, 0.0722), strict=True))


@pytest.mark.parametrize("foreground", ["primary", "secondary", "note"])
@pytest.mark.parametrize("background", ["page", "surface", "raised"])
def test_all_text_tokens_meet_high_contrast(foreground, background):
    tokens = dict(re.findall(r"(--tr-[a-z-]+):(#[0-9A-Fa-f]{6})", APP_CSS))
    first = luminance(tokens[f"--tr-text-{foreground}"])
    second = luminance(tokens[f"--tr-bg-{background}"])
    assert (first + 0.05) / (second + 0.05) >= 7


def test_native_widgets_use_dark_theme_and_accent_remains_dark_text():
    root = Path(__file__).parents[2]
    theme = tomllib.loads((root / ".streamlit" / "config.toml").read_text())["theme"]
    assert theme["base"] == "dark"
    assert theme["textColor"] == "#F3F1EA"
    assert theme["backgroundColor"] == "#0A0A0A"
    assert theme["secondaryBackgroundColor"] == "#242429"
    assert "COPY .streamlit ./.streamlit" in (root / "deploy" / "Dockerfile").read_text()
    assert "--tr-text-on-accent:#0A0A0A" in APP_CSS
    assert "opacity:1 !important" in APP_CSS
    assert ".finding-card,.badge,.flow-edge,.flow-legend { border:0; box-shadow:none; }" in APP_CSS


def test_state_decoration_is_neutral_and_emphasis_uses_structure():
    tokens = dict(re.findall(r"(--tr-state-[a-z-]+):(#[0-9A-Fa-f]{6})", APP_CSS))
    assert set(tokens.values()) == {"#C0BBAF"}
    assert "st-key-metric-actual-" in APP_CSS
    assert ".attempt-meaning" in APP_CSS
    assert "font-size:var(--tr-font-title); font-weight:800" in APP_CSS


def test_typography_has_exactly_five_sizes_and_uses_role_tokens():
    tokens = dict(re.findall(r"(--tr-font-[a-z-]+):(\d+px)", APP_CSS))
    assert tokens == {
        "--tr-font-title": "24px", "--tr-font-subtitle": "20px",
        "--tr-font-body": "16px", "--tr-font-helper": "14px",
        "--tr-font-note": "12px",
    }
    sizes = [size.replace(" !important", "").strip()
             for size in re.findall(r"font-size:([^;}]+)", APP_CSS)]
    assert all(size == "16px" or size in {f"var({token})" for token in tokens}
               for size in sizes)
    spec = (Path(__file__).parents[2] / "FRONTEND_SPEC.md").read_text(encoding="utf-8")
    for token, size in tokens.items():
        assert f"| `{token}` | `{size}` |" in spec


def test_graph_canvas_does_not_scale_node_typography_with_container():
    source = (Path(__file__).parents[2] / "app" / "fund_flow_graph.py").read_text(encoding="utf-8")
    assert 'font-size="12"' in source
    assert 'width="720" style="width:720px;max-width:none"' in source
    assert 'style="overflow-x:auto"' in source


def test_blockchain_texture_is_local_decorative_and_not_network_loaded():
    assert "data:image/svg+xml" in APP_CSS
    assert "__CHAIN_BACKGROUND__" not in APP_CSS
    assert "radial-gradient(ellipse" in APP_CSS
    assert "rgba(255,255,255,.035)" in APP_CSS
    assert "https://" not in APP_CSS


def test_reference_style_uses_layered_panels_and_short_gold_accents():
    assert "--tr-bg-surface:#1B1B20" in APP_CSS
    assert "--tr-bg-raised:#242429" in APP_CSS
    assert ".section-head h2::after" in APP_CSS
    assert 'width:64px; height:6px' in APP_CSS
    assert 'st-key-panel-' in APP_CSS
    assert ".hero-emblem { display:none; }" in APP_CSS


def test_brand_asset_is_a_real_png_and_sections_have_no_repeated_numbering():
    assert LOGO_PATH.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert logo_data_url().startswith("data:image/png;base64,")
    source = (Path(__file__).parents[2] / "app" / "streamlit_app.py").read_text(encoding="utf-8")
    assert 'class="section-kicker"' not in source
    assert 'class="brand-mark">TR' not in source


def test_logo_is_static_and_preserves_reverse_proxy_prefix():
    root = Path(__file__).parents[2]
    config = tomllib.loads((root / ".streamlit" / "config.toml").read_text())
    assert config["server"]["enableStaticServing"] is True
    assert logo_static_url() == "/app/static/logo.png"
    assert logo_static_url("/trust-receipt/") == "/trust-receipt/app/static/logo.png"
    source = (root / "app" / "streamlit_app.py").read_text(encoding="utf-8")
    assert "logo_data_url(" not in source


def test_mobile_fields_and_cards_keep_sixteen_pixel_spacing():
    assert '.signal-grid,.task-summary { grid-template-columns:1fr; gap:16px; }' in APP_CSS
    assert 'flex-direction:column !important; gap:16px !important;' in APP_CSS
    assert '.block-container { padding:12px 24px 64px; }' in APP_CSS
    assert '.attempt-card { padding:20px; margin:0 0 16px;' in APP_CSS
