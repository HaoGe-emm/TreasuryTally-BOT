from __future__ import annotations

from app.service_history import render_service_history
from trust_receipt.history import ReceiptHistoryInput, compare_services, project_service_histories


class Context:
    def __init__(self, owner):
        self._owner = owner

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def metric(self, label, value):
        self._owner.metric(label, value)


class FakeStreamlit:
    def __init__(self):
        self.metrics = []
        self.captions = []
        self._selected = "b"

    def header(self, _value): pass
    def subheader(self, _value): pass
    def markdown(self, _value): pass
    def text(self, _value): pass
    def code(self, _value, **_kwargs): pass
    def link_button(self, _label, _uri): pass
    def caption(self, value): self.captions.append(value)
    def columns(self, count): return tuple(Context(self) for _ in range(count))
    def metric(self, label, value): self.metrics.append((label, value))
    def expander(self, _label): return Context(self)
    def radio(self, _label, **_kwargs): return self._selected
    def button(self, _label, **_kwargs): return True


def test_component_renders_both_services_and_returns_only_explicit_choice(make_receipt) -> None:
    receipts = (
        make_receipt(
            receipt_id="a", task_id="task-a", service_id="a", outcome="PASS", created_at="2026-10-01T00:00:00Z"
        ),
        make_receipt(
            receipt_id="b", task_id="task-b", service_id="b", outcome="INCONCLUSIVE", created_at="2026-10-02T00:00:00Z"
        ),
    )
    histories = project_service_histories(
        ReceiptHistoryInput(receipt=receipt, task_type="grant-report") for receipt in receipts
    )
    comparison = compare_services(histories, task_type="grant-report", service_ids=("a", "b"))
    fake = FakeStreamlit()

    assert render_service_history(comparison, streamlit_api=fake) == "b"
    assert ("无法判断", 1) in fake.metrics
    assert any("不计为未通过" in caption for caption in fake.captions)
