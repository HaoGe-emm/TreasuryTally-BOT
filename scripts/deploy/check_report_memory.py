"""Offline SDK warmup and actual multiview, multisession export pressure."""

import json
import runpy
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest


def main():
    from app.report_exports import application_download_cache
    from trust_receipt.agents import DeepSeekStructuredOutputAdapter, OpenAIStructuredOutputAdapter
    from trust_receipt.chain.rpc import EvmRpcProbe
    from trust_receipt.reporting import BusinessReportView

    assert not Path("/app/.env").exists()
    # Construction/import only. No client method is called and network is disabled.
    clients = [
        DeepSeekStructuredOutputAdapter(api_key="offline-construction-only", model_name="offline-test",
                                       timeout_seconds=1, max_retries=0),
        OpenAIStructuredOutputAdapter(api_key="offline-construction-only", model_name="offline-test",
                                     timeout_seconds=1, max_retries=0),
        EvmRpcProbe("http://127.0.0.1:9", expected_chain_id=11155111, timeout_seconds=1),
    ]
    assert len(clients) == 3
    harness = runpy.run_path("/opt/trust-receipt-smoke/check_report_downloads.py")["harness"]
    directory = Path(sys.argv[1])
    views = [BusinessReportView.model_validate_json(path.read_bytes())
             for path in sorted(directory.glob("*.view.json"))]
    assert len(views) == 7
    original = (directory / "fail.receipt.json").read_bytes()
    cache = application_download_cache()
    pages = [AppTest.from_function(harness, default_timeout=30) for _ in range(4)]
    accepted = rejected = 0
    max_cached = 0
    for cycle in range(2):
        for index, view in enumerate(views):
            page = pages[index % len(pages)]
            page.session_state["report"] = view.model_copy(update={"notice": f"pressure-{cycle}-{index}"})
            page.session_state["receipt"] = original
            page.session_state["executions"] = ["unchanged-history"]
            page.run()
            assert not page.exception
            next(button for button in page.button if button.label == "生成Word 报告").click().run()
            assert not page.exception
            if page.error:
                assert "原 JSON 回执仍可下载" in page.error[0].value
                rejected += 1
            else:
                accepted += 1
            stats = cache.stats()
            assert stats["bytes"] <= cache.max_bytes and stats["owners"] <= 4
            max_cached = max(max_cached, stats["bytes"])
            assert page.session_state["receipt"] == original
            assert page.session_state["executions"] == ["unchanged-history"]
            assert page.session_state["report"].current == view.current
            assert not any(key.startswith("report-export:") and isinstance(value, (bytes, str))
                           for key, value in page.session_state._state.filtered_state.items())
    for page in pages:
        page.session_state["report-download-lease"].close()
    assert cache.stats()["bytes"] == 0
    assert accepted > 0 and rejected > 0
    # Keep the real SDK clients alive while the actual page generates all formats.
    previous_args = sys.argv
    try:
        sys.argv = ["check", str(directory / "fail.view.json"), str(directory / "fail.receipt.json")]
        runpy.run_path("/opt/trust-receipt-smoke/check_report_downloads.py", run_name="__main__")
    finally:
        sys.argv = previous_args
    events = dict(line.split() for line in Path("/sys/fs/cgroup/memory.events").read_text().splitlines())
    assert events["max"] == events["oom"] == events["oom_kill"] == "0"
    memory_stats = dict(line.split() for line in Path("/sys/fs/cgroup/memory.stat").read_text().splitlines())
    print(json.dumps({"sdk_construction_only": True, "sessions": 4, "view_requests": 14,
                      "warm_sdk_five_actual_formats": True,
                      "accepted": accepted, "budget_rejections": rejected, "max_cached": max_cached,
                      "memory_peak": int(Path("/sys/fs/cgroup/memory.peak").read_text()),
                      "memory_current": int(Path("/sys/fs/cgroup/memory.current").read_text()),
                      "memory_stat": {key: int(memory_stats[key]) for key in ("anon", "file", "kernel")},
                      "memory_events": events, "json_history_unchanged": True,
                      "scope": "offline synthetic data, no network/client calls/browser/production"}))


if __name__ == "__main__":
    main()
