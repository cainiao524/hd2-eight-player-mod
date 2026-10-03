"""Replay the AI source audit and compare its complete saved receipt."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ai_scaling_contract_20261003 import audit_source, self_test


def verify(receipt_path: Path, source: Path) -> dict:
    saved = json.loads(receipt_path.read_text(encoding="utf-8"))
    replay = audit_source(source)
    replay["synthetic_verification"] = self_test()
    # A file can be moved without changing any of the audited bytes.  All
    # semantic fields, metadata, paths within JSON, and hashes must match.
    saved_source = saved.get("source")
    if not isinstance(saved_source, dict):
        raise ValueError("receipt source is missing")
    replay["source"]["path"] = saved_source.get("path")
    return {
        "schema": "hd2_ai_scaling_contract_verification_v1",
        "receipt_matches_replay": saved == replay,
        "pinned_source_matches": replay["source"]["sha256_matches_pinned_snapshot"],
        "all_247_arrays_four_entries": replay["player_count_multiplier_arrays"]["count"] == 247
            and replay["player_count_multiplier_arrays"]["all_exactly_four"],
        "synthetic_contract_passed": replay["synthetic_verification"]["passed"],
        "runtime_activation_allowed": False,
        "installable": False,
        "multiplayer_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, default=Path(__file__).with_name("ai_scaling_contract_receipt_20261003.json"))
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.receipt, args.source)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if all(result[key] for key in ("receipt_matches_replay", "pinned_source_matches", "all_247_arrays_four_entries", "synthetic_contract_passed")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
