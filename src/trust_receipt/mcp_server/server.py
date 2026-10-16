"""Official MCP SDK adapter; business decisions remain in the headless facade."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from trust_receipt.agents import TaskSpecCandidate
from trust_receipt.headless.facade import HeadlessTrustReceiptFacade, safe_error_payload


def _call(operation):
    try:
        value = operation()
        return {"ok": True, "data": value.model_dump(mode="json")}
    except Exception as error:
        return safe_error_payload(error)


def create_server(facade: HeadlessTrustReceiptFacade) -> FastMCP:
    server = FastMCP(
        "TreasuryTally",
        instructions=(
            "TreasuryTally local, workspace-scoped deterministic treasury report verification. "
            "Task confirmation and report verification require a separate local approval command. "
            "No publication, chain writes, arbitrary paths, URLs, code, SQL, or secrets are available."
        ),
        log_level="WARNING",
    )
    read_only = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
    prepare = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
    authorized_write = ToolAnnotations(
        readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False
    )

    @server.tool(name="draft_task_candidate", annotations=read_only, structured_output=True)
    def draft_task_candidate(workspace_handle: str, user_request: str) -> dict[str, object]:
        """Draft a TreasuryTally UNCONFIRMED task candidate; this never confirms a task."""
        return _call(lambda: facade.draft_task(workspace_handle, user_request))

    @server.tool(name="prepare_task_confirmation", annotations=prepare, structured_output=True)
    def prepare_task_confirmation(
        workspace_handle: str, candidate: TaskSpecCandidate
    ) -> dict[str, object]:
        """Create a TreasuryTally digest-bound challenge; approval must happen outside MCP."""
        return _call(lambda: facade.prepare_task_confirmation(workspace_handle, candidate))

    @server.tool(name="confirm_task", annotations=authorized_write, structured_output=True)
    def confirm_task(workspace_handle: str, challenge_id: str) -> dict[str, object]:
        """Confirm a TreasuryTally task only from a separately approved challenge."""
        return _call(lambda: facade.confirm_task(workspace_handle, challenge_id))

    @server.tool(name="prepare_report_verification", annotations=prepare, structured_output=True)
    def prepare_report_verification(
        workspace_handle: str, task_id: str, report_json: str
    ) -> dict[str, object]:
        """Validate inline TreasuryTally report JSON and prepare an attempt-bound challenge."""
        return _call(lambda: facade.prepare_report_verification(workspace_handle, task_id, report_json))

    @server.tool(name="verify_report", annotations=authorized_write, structured_output=True)
    def verify_report(workspace_handle: str, challenge_id: str) -> dict[str, object]:
        """Verify a TreasuryTally report through the deterministic workflow after local approval."""
        return _call(lambda: facade.verify_report(workspace_handle, challenge_id))

    @server.tool(name="get_verification_result", annotations=read_only, structured_output=True)
    def get_verification_result(
        workspace_handle: str, task_id: str, attempt: int
    ) -> dict[str, object]:
        """Read a stored TreasuryTally three-state result without rerunning external work."""
        return _call(lambda: facade.get_result(workspace_handle, task_id, attempt))

    @server.tool(name="get_receipt", annotations=read_only, structured_output=True)
    def get_receipt(workspace_handle: str, task_id: str, attempt: int) -> dict[str, object]:
        """Read a TreasuryTally receipt; no report body, private path, or secret is returned."""
        return _call(lambda: facade.get_receipt(workspace_handle, task_id, attempt))

    @server.tool(name="replay_receipt", annotations=read_only, structured_output=True)
    def replay_saved_receipt(
        workspace_handle: str, task_id: str, attempt: int
    ) -> dict[str, object]:
        """Replay a TreasuryTally receipt's hashes, links, and outcome without fetching the chain."""
        return _call(lambda: facade.replay_receipt(workspace_handle, task_id, attempt))

    return server
