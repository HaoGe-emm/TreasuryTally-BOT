"""Human-operated approval command kept outside the MCP tool registry."""

from __future__ import annotations

import argparse
import json

from trust_receipt.headless.authorization import LocalApprovalController
from trust_receipt.headless.config import WorkspaceRegistry
from trust_receipt.headless.facade import safe_error_payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Operator-owned M16 workspace registry")
    subcommands = parser.add_subparsers(dest="command", required=True)
    for name in ("inspect", "approve"):
        command = subcommands.add_parser(name)
        command.add_argument("--workspace", required=True)
        command.add_argument("--challenge", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        approvals = LocalApprovalController(WorkspaceRegistry.load(args.config))
        challenge = approvals.inspect(args.workspace, args.challenge)
        preview = challenge.model_dump(mode="json")
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        if args.command == "inspect":
            return 0
        phrase = f"APPROVE {challenge.challenge_id}"
        entered = input(f"Type '{phrase}' to grant this one-time local authorization: ")
        if entered != phrase:
            print(json.dumps({"ok": False, "status": "CANCELLED"}))
            return 1
        approved = approvals.approve(args.workspace, args.challenge)
        print(json.dumps({"ok": True, "challenge": approved.model_dump(mode="json")}, ensure_ascii=False))
        return 0
    except Exception as error:
        print(json.dumps(safe_error_payload(error), ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
