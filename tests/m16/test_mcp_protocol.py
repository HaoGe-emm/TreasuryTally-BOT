from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from trust_receipt.headless.authorization import LocalApprovalController
from trust_receipt.headless.config import WorkspaceRegistry

from .conftest import PROJECT_ROOT, WORKSPACE_HANDLE, report_json


def _server_parameters(registry_path: Path) -> StdioServerParameters:
    environment = {"PYTHONPATH": str(PROJECT_ROOT / "src")}
    if os.name == "nt" and "SYSTEMROOT" in os.environ:
        environment["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "trust_receipt.mcp_server.cli", "--config", str(registry_path)],
        env=environment,
        cwd=PROJECT_ROOT,
    )


async def _first_session(registry_path, fixture_case):
    async with stdio_client(_server_parameters(registry_path)) as streams, ClientSession(*streams) as session:
        initialized = await session.initialize()
        assert initialized.serverInfo.name == "TreasuryTally"
        assert "TreasuryTally" in initialized.instructions
        assert "Agent" not in initialized.serverInfo.name
        listed = await session.list_tools()
        names = {tool.name for tool in listed.tools}
        assert names == {
            "draft_task_candidate",
            "prepare_task_confirmation",
            "confirm_task",
            "prepare_report_verification",
            "verify_report",
            "get_verification_result",
            "get_receipt",
            "replay_receipt",
        }
        assert all("TreasuryTally" in (tool.description or "") for tool in listed.tools)
        assert all("TreasuryTally Agent" not in (tool.description or "") for tool in listed.tools)
        assert "path" not in str([tool.inputSchema for tool in listed.tools]).lower()

        drafted = await session.call_tool(
            "draft_task_candidate",
            {"workspace_handle": WORKSPACE_HANDLE, "user_request": "核验测试报表"},
        )
        assert drafted.isError is False
        draft_data = drafted.structuredContent["data"]
        assert draft_data["fixture_test_only"] is True
        prepared = await session.call_tool(
            "prepare_task_confirmation",
            {"workspace_handle": WORKSPACE_HANDLE, "candidate": draft_data["candidate"]},
        )
        task_challenge = prepared.structuredContent["data"]["challenge_id"]

        denied = await session.call_tool(
            "confirm_task", {"workspace_handle": WORKSPACE_HANDLE, "challenge_id": task_challenge}
        )
        assert denied.structuredContent["status"] == "AUTHORIZATION_REQUIRED"
        approvals = LocalApprovalController(WorkspaceRegistry.load(registry_path))
        approvals.approve(WORKSPACE_HANDLE, task_challenge)
        confirmed = await session.call_tool(
            "confirm_task", {"workspace_handle": WORKSPACE_HANDLE, "challenge_id": task_challenge}
        )
        task_id = confirmed.structuredContent["data"]["task_id"]

        prepared_report = await session.call_tool(
            "prepare_report_verification",
            {
                "workspace_handle": WORKSPACE_HANDLE,
                "task_id": task_id,
                "report_json": report_json(fixture_case, corrected=False),
            },
        )
        report_challenge = prepared_report.structuredContent["data"]["challenge_id"]
        approvals.approve(WORKSPACE_HANDLE, report_challenge)
        verified = await session.call_tool(
            "verify_report", {"workspace_handle": WORKSPACE_HANDLE, "challenge_id": report_challenge}
        )
        assert verified.structuredContent["data"]["outcome"] == "FAIL"
        assert verified.structuredContent["data"]["spec_hash"] == confirmed.structuredContent["data"]["spec_hash"]
        repeated = await session.call_tool(
            "verify_report", {"workspace_handle": WORKSPACE_HANDLE, "challenge_id": report_challenge}
        )
        assert repeated.structuredContent["data"]["idempotent_replay"] is True
        return task_id, report_challenge


async def _restart_session(registry_path, task_id, report_challenge):
    async with stdio_client(_server_parameters(registry_path)) as streams, ClientSession(*streams) as session:
        await session.initialize()
        repeated = await session.call_tool(
            "verify_report", {"workspace_handle": WORKSPACE_HANDLE, "challenge_id": report_challenge}
        )
        assert repeated.structuredContent["data"]["idempotent_replay"] is True
        result = await session.call_tool(
            "get_verification_result",
            {"workspace_handle": WORKSPACE_HANDLE, "task_id": task_id, "attempt": 1},
        )
        assert result.structuredContent["data"]["outcome"] == "FAIL"
        replay = await session.call_tool(
            "replay_receipt",
            {"workspace_handle": WORKSPACE_HANDLE, "task_id": task_id, "attempt": 1},
        )
        assert replay.structuredContent["data"]["valid"] is True

        injected = await session.call_tool(
            "get_receipt",
            {"workspace_handle": "../../private", "task_id": task_id, "attempt": 1},
        )
        assert injected.structuredContent["code"] == "UNKNOWN_WORKSPACE"

        malicious = await session.call_tool(
            "prepare_report_verification",
            {
                "workspace_handle": WORKSPACE_HANDLE,
                "task_id": task_id,
                "report_json": '{"path":"../../private","sql":"DROP TABLE tasks","secret":"never-echo"}',
            },
        )
        assert malicious.structuredContent["code"] == "INVALID_INPUT"
        assert "never-echo" not in str(malicious.structuredContent)


def test_real_stdio_initialize_list_call_restart_and_injection(registry_path, fixture_case):
    task_id, challenge = asyncio.run(_first_session(registry_path, fixture_case))
    asyncio.run(_restart_session(registry_path, task_id, challenge))
