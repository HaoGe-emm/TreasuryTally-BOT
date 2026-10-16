"""Start an isolated live-only app without publication or transaction credentials."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALLOWED_CONFIGURATION = (
    "ETH_RPC_URL", "CHAIN_ID", "RPC_TIMEOUT_SECONDS", "RPC_CONFIRMATIONS",
    "DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "AI_TIMEOUT_SECONDS", "AI_MAX_RETRIES",
)
DISABLED_CONFIGURATION = (
    "PINATA_JWT", "PUBLIC_RECEIPT_DIRECTORY", "PUBLIC_RECEIPT_BASE_URL",
    "REVIEWER_PRIVATE_KEY", "SERVICE_A_PRIVATE_KEY", "SERVICE_B_PRIVATE_KEY",
    "BLOCKSCOUT_PRO_API_KEY",
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8533)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    if (PROJECT_ROOT / ".env").exists():
        parser.error("isolated checkout must not contain .env; use --env-file outside it")
    values = dotenv_values(args.env_file)
    for name in ALLOWED_CONFIGURATION:
        if values.get(name):
            os.environ[name] = values[name]
    for name in DISABLED_CONFIGURATION:
        os.environ.pop(name, None)
    os.environ.update(APP_REQUIRE_LIVE="true", M0_ENABLE_WRITES="false", M6_ENABLE_WRITES="false")
    os.chdir(PROJECT_ROOT)
    sys.path.insert(0, str(PROJECT_ROOT))
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
    sys.argv = [
        "streamlit", "run", str(PROJECT_ROOT / "app" / "streamlit_app.py"),
        "--server.address", "127.0.0.1", "--server.port", str(args.port),
        "--server.headless", "true", "--browser.gatherUsageStats", "false",
    ]
    from streamlit.web import cli

    cli.main()


if __name__ == "__main__":
    main()
