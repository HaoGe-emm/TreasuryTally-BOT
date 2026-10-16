"""Adapter failure boundaries and strict receipt/view binding, without external services."""

import builtins
import json
import subprocess
from types import SimpleNamespace

import pytest

from trust_receipt.reporting import build_business_report, export_docx, export_pdf
from trust_receipt.reporting.renderer import EChartsRenderer, ExportUnavailable


def view_for(item):
    return build_business_report(item.receipt, item.submission, fund_flow=item.fund_flow, source_mode="fixture")


def test_missing_renderer_does_not_fall_back(failing_input):
    with pytest.raises(ExportUnavailable, match="EXPORT_UNAVAILABLE"):
        EChartsRenderer(node_path="no-such-node").render(view_for(failing_input))


def test_worker_binding_cannot_be_reused_for_another_report(failing_input, monkeypatch):
    monkeypatch.setattr("trust_receipt.reporting.renderer.Path.is_file", lambda _: True)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: SimpleNamespace(
        returncode=0, stdout=json.dumps({"binding": "0" * 64}).encode(), stderr=b""))
    with pytest.raises(ExportUnavailable, match="binding mismatch"):
        EChartsRenderer(node_path="node").render(view_for(failing_input))


def test_fixed_argv_no_shell_and_no_credential_environment(failing_input, monkeypatch):
    monkeypatch.setattr("trust_receipt.reporting.renderer.Path.is_file", lambda _: True)
    monkeypatch.setenv("NODE_OPTIONS", "--require=unsafe")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-forwarded")

    def run(args, **kwargs):
        assert args[0] == "node"
        assert args[-1].endswith("render.cjs")
        assert kwargs["shell"] is False and kwargs["timeout"] == 20
        assert "NODE_OPTIONS" not in kwargs["env"] and "OPENAI_API_KEY" not in kwargs["env"]
        value = json.loads(kwargs["input"])
        assert set(value) == {"binding", "option"}
        assert value["option"]["series"][0]["links"][0]["amount_base_units"].isdigit()
        raise subprocess.TimeoutExpired(args, 20, stderr=b"secret must not be exposed")

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(ExportUnavailable, match="EXPORT_UNAVAILABLE") as error:
        EChartsRenderer(node_path="node").render(view_for(failing_input))
    assert "secret" not in str(error.value)


def test_renderer_instance_limits_concurrency(failing_input):
    renderer = EChartsRenderer(node_path=__file__)
    assert renderer._slots.acquire(blocking=False)
    try:
        with pytest.raises(ExportUnavailable, match="busy"):
            renderer.render(view_for(failing_input))
    finally:
        renderer._slots.release()


@pytest.mark.parametrize(("builder", "package"), [(export_docx, "docx"), (export_pdf, "reportlab")])
def test_missing_document_dependency_is_explicit(failing_input, monkeypatch, builder, package):
    original = builtins.__import__

    def restricted_import(name, *args, **kwargs):
        if name == package or name.startswith(package + "."):
            raise ImportError("not installed")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", restricted_import)
    with pytest.raises(ExportUnavailable, match="dependency missing"):
        builder(view_for(failing_input), renderer=EChartsRenderer(node_path="no-such-node"))


def test_graph_record_limit_is_export_unavailable(failing_input):
    view = view_for(failing_input)
    current = view.current.model_copy(update={"flow_rows": view.current.flow_rows[:1] * 201})
    with pytest.raises(ExportUnavailable, match="record limits"):
        EChartsRenderer(node_path=__file__).render(view.model_copy(update={"current": current}))
