"""Read-only newcomer guide; state belongs to the current browser document."""

from pathlib import Path
from typing import Any


def onboarding_html() -> str:
    """Only trusted, bundled markup/scripts; never interpolate uploaded data."""
    return Path(__file__).with_name("onboarding.html").read_text(encoding="utf-8")


def render_onboarding(st: Any) -> None:
    """A full reload resets the guide; Streamlit session reruns must not."""
    if st.query_params.get("verify") != "1":
        st.html(onboarding_html(), unsafe_allow_javascript=True)
