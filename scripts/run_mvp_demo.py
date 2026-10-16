"""Run the credential-free MVP demonstration and print its acceptance summary."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from trust_receipt.demo import run_offline_mvp_demo  # noqa: E402


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-directory",
        type=Path,
        help="Empty directory in which to retain the demo database and private receipts.",
    )
    return parser.parse_args()


def main() -> int:
    arguments = _arguments()
    if arguments.output_directory is not None:
        result = run_offline_mvp_demo(PROJECT_ROOT, arguments.output_directory)
    else:
        with tempfile.TemporaryDirectory(prefix="trust-receipt-demo-") as directory:
            result = run_offline_mvp_demo(PROJECT_ROOT, Path(directory))
            result["output_directory"] = "temporary (removed after successful replay)"
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
