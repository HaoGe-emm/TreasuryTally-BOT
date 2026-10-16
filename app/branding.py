"""The user-provided transparent brand asset, used unchanged."""

from base64 import b64encode
from functools import lru_cache
from pathlib import Path

LOGO_PATH = Path(__file__).resolve().parent / "static" / "logo.png"
LOGO_DISPLAY_WIDTH = 288  # Two pixels per CSS pixel for the 144px decorative logo.


def logo_static_url(base_path: str = "") -> str:
    prefix = base_path.strip("/")
    return f"/{prefix + '/' if prefix else ''}app/static/logo.png"


def logo_display_url(base_path: str = "") -> str:
    """Use Streamlit's image/media pipeline for a cached display-size PNG.

    The original file is untouched; both placements share one content-addressed
    media resource. Keep vendor-specific image handling within this UI adapter.
    """
    from streamlit.elements.lib.image_utils import image_to_url
    from streamlit.elements.lib.layout_utils import LayoutConfig

    url = image_to_url(
        str(LOGO_PATH), LayoutConfig(width=LOGO_DISPLAY_WIDTH),
        clamp=False, channels="RGB", output_format="PNG", image_id="treasurytally-brand-logo",
    )
    if not url:
        return logo_static_url(base_path)  # Bare Python, with no media-serving runtime.
    prefix = base_path.strip("/")
    return f"/{prefix}{url}" if prefix and url.startswith("/media/") else url


@lru_cache(maxsize=1)
def logo_data_url() -> str:
    return "data:image/png;base64," + b64encode(LOGO_PATH.read_bytes()).decode("ascii")
