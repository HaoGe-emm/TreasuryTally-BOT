"""Command-line entry point for receipt verification in a fresh process."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from trust_receipt.receipts.local import load_receipt
from trust_receipt.receipts.replay import replay_receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and replay a local TreasuryTally receipt")
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    replay = replay_receipt(load_receipt(args.receipt))
    payload = asdict(replay)
    payload["recorded_outcome"] = replay.recorded_outcome.value
    payload["recomputed_outcome"] = replay.recomputed_outcome.value
    payload["valid"] = replay.valid
    print(json.dumps(payload, sort_keys=True))
    return 0 if replay.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
