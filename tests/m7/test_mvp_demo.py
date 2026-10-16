from __future__ import annotations

from pathlib import Path

from trust_receipt.demo import run_offline_mvp_demo


def test_offline_mvp_demo_proves_fail_switch_pass_and_replay(tmp_path):
    result = run_offline_mvp_demo(Path(__file__).parents[2], tmp_path / "demo")

    assert result["valid"] is True
    assert result["calculation"] == "120000 - 30000 + 20000 = 110000; two eligible grants remain."
    assert result["attempts"] == [
        {"attempt": 1, "service_id": "service-a", "outcome": "FAIL"},
        {"attempt": 2, "service_id": "service-b", "outcome": "PASS"},
    ]
    assert result["receipt_replays"] == [True, True]
    assert result["restored_outcomes"] == ["FAIL", "PASS"]
    assert result["publication_mode"] == "not-executed"
