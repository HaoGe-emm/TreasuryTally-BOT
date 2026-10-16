"""Export a confirmed TaskSpec without changing its scope or inventing its hash."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from trust_receipt.hashing import canonical_json_bytes, task_spec_hash  # noqa: E402
from trust_receipt.models import TaskSpec  # noqa: E402


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def export_task(input_path: Path, output_path: Path, *, expected_chain_id: int, demo: bool) -> dict:
    raw = json.loads(input_path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    task = TaskSpec.model_validate(raw)
    if task.chain_id != expected_chain_id:
        raise ValueError(
            f"TaskSpec chain {task.chain_id} differs from expected {expected_chain_id}; scope is never rewritten"
        )
    digest = task_spec_hash(task)
    if digest != task.spec_hash:
        raise ValueError("TaskSpec spec_hash differs from its normalized model content")
    canonical_body = task.model_dump(mode="json", exclude={"spec_hash"})
    proof = {
        "model": "trust_receipt.models.TaskSpec",
        "upstream_sha": "f5efc9cf9b1a5860bc824d176d3a92407e96b495",
        "chain_id": task.chain_id,
        "demo_data": demo,
        "algorithm": "SHA-256",
        "canonicalization": (
            "Pydantic model_dump(mode=json), omit spec_hash; UTF-8, ensure_ascii=False, "
            "sort_keys=True, separators=(comma,colon); floats forbidden"
        ),
        "spec_hash": digest,
        "canonical_file": "task-spec.canonical.json",
        "limitation": (
            "Export and hash agreement do not establish report truth, "
            "source-chain evidence completeness, or a financial verification result."
        ),
    }
    output_path.mkdir(parents=True, exist_ok=True)
    (output_path / "task-spec.json").write_bytes(canonical_json_bytes(task))
    (output_path / "task-spec.canonical.json").write_bytes(canonical_json_bytes(canonical_body))
    (output_path / "hash-proof.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8")
    return proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expected-chain-id", type=int, default=677)
    parser.add_argument("--demo", action="store_true", help="Label public sample data explicitly")
    args = parser.parse_args()
    proof = export_task(args.task, args.out, expected_chain_id=args.expected_chain_id, demo=args.demo)
    print(json.dumps(proof, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
