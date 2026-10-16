"""Launch only a loopback app with an explicitly labelled M14 test fault."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from fault_provider import ConflictRpcProvider, UnavailableRpcProvider  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8535)
    parser.add_argument("--fault", choices=("unavailable", "conflict"), required=True)
    args = parser.parse_args()
    import app.runtime

    app.runtime.RpcReferenceEvidenceProvider = (
        ConflictRpcProvider if args.fault == "conflict" else UnavailableRpcProvider
    )
    spec = importlib.util.spec_from_file_location("m13_isolated_launcher", ROOT / "scripts/m13/start_local.py")
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    sys.argv = [str(spec.origin), "--env-file", str(args.env_file), "--port", str(args.port)]
    print(f"M14 LOCAL TEST FAULT={args.fault}; only loopback; no publishing or chain writes", flush=True)
    launcher.main()


if __name__ == "__main__":
    main()
