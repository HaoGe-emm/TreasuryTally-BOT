"""Run the TreasuryTally MCP adapter over local stdio only."""

from __future__ import annotations

import argparse

from trust_receipt.headless.config import WorkspaceRegistry
from trust_receipt.headless.facade import HeadlessTrustReceiptFacade
from trust_receipt.mcp_server.server import create_server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Operator-owned M16 workspace registry")
    args = parser.parse_args(argv)
    facade = HeadlessTrustReceiptFacade(WorkspaceRegistry.load(args.config))
    create_server(facade).run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
