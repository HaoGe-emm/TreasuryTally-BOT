"""Shared automatic first and repair upload input; no JSON adoption step."""

from pathlib import Path

from app.automatic_report_ui import render_automatic_report
from app.report_identification_state import reset_report_input
from trust_receipt.services.report_recognition import persist_recognized_report, recognize_report


def render_report_intake(
    st, uploaded, *, directory: Path, namespace: str, recognizer=None, provider: str = "unconfigured",
) -> bytes | None:
    def clear_old_service():
        st.session_state.pop("uploaded_service", None)
        st.session_state.pop("uploaded_report_hash", None)
        if namespace.endswith(":first"):
            st.session_state.pop("candidate", None)
            st.session_state.pop("candidate_source", None)

    if uploaded is None:
        reset_report_input(st.session_state, namespace)
        if namespace.endswith(":first"):
            clear_old_service()
        return None
    return render_automatic_report(
        st, uploaded, directory=directory, namespace=namespace, recognizer=recognizer,
        provider=provider, recognize=recognize_report, retain=persist_recognized_report,
        on_change=clear_old_service,
    )
