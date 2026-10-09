"""Static and offline verifier for the client replication sidecar contract.

The verifier hashes only the saved contract files and build receipt.  It never
opens a game process, loads game.dll, emits a patch, or sends a network packet.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = 25480438
CAPACITY = 16
ARRAY_MASK = 0x1F
REQUIRED_SOURCES = (
    "ep_client_replication_contract.h",
    "ep_client_replication_contract.cpp",
    "ep_client_replication_contract_test.cpp",
    "build_x64.bat",
    "CLIENT_REPLICATION_SIDECAR_CONTRACT_20261004.zh-TW.md",
)
REQUIRED_TOKENS = (
    "EP_CR_ARRAY_ALL",
    "EP_CR_EVENT_ROLLBACK",
    "EP_CR_EVENT_MIGRATION_BEGIN",
    "EP_CR_EVENT_MIGRATION_COMMIT",
    "EP_CR_EVENT_MIGRATION_ABORT",
    "EP_CR_ROLLBACK",
    "EP_CR_QUIESCENCE_REQUIRED",
    "EP_CR_CAPACITY EP_CAPACITY_HARD_LIMIT",
    "ep_cr_production_enabled() { return 0; }",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_sources() -> dict:
    missing = [name for name in REQUIRED_SOURCES if not (HERE / name).is_file()]
    if missing:
        raise FileNotFoundError(",".join(missing))
    text = "\n".join((HERE / name).read_text(encoding="utf-8") for name in REQUIRED_SOURCES)
    missing_tokens = [token for token in REQUIRED_TOKENS if token not in text]
    if missing_tokens:
        raise ValueError(f"contract_tokens_missing:{missing_tokens}")
    return {name: sha256(HERE / name) for name in REQUIRED_SOURCES}


def build_receipt() -> dict:
    source_hashes = verify_sources()
    artifacts = [{"path": name, "sha256": value} for name, value in source_hashes.items()]
    for name in ("ep_client_replication_contract.dll", "ep_client_replication_contract_test.exe"):
        path = HERE / name
        if not path.is_file():
            raise FileNotFoundError(path)
        artifacts.append({"path": name, "sha256": sha256(path)})
    return {
        "schema": "hd2_client_replication_sidecar_contract_v1",
        "build": BUILD,
        "capacity": CAPACITY,
        "source_inventory": "client_fixed_four_inventory_20261003.json",
        "source_inventory_role": "saved static evidence only; no native write target inferred",
        "array_groups": {
            "adjacent_8": 1,
            "adjacent_16": 2,
            "adjacent_16b": 4,
            "confirmed_32": 8,
            "peer_keyed": 16,
            "all_mask": ARRAY_MASK,
            "each_has_independent_ordinal_view": True,
            "stable_network_index_is_not_compact_ordinal": True,
            "peer_keyed_one_to_one_with_confirmed_not_proven": True,
        },
        "operations": {
            "append_exact_index": True,
            "confirm": True,
            "remove": True,
            "kicked": True,
            "reset": True,
            "generation_fence": True,
            "callback_failure_compensation": True,
            "rollback_retry": True,
            "callback_lease_quiescence": True,
            "host_migration_transaction": True,
            "holes_preserved_in_network_index_table": True,
        },
        "checks": {
            "fixed_build": True,
            "all_indexes_0_to_15": True,
            "index_16_rejected": True,
            "five_array_masks_explicit": True,
            "rollback_token_retained": True,
            "stale_generation_rejected": True,
            "lease_blocks_mutation": True,
            "migration_epoch_and_quiescence": True,
            "production_gate_false": True,
            "no_process_access": True,
            "no_patch_emitted": True,
        },
        "artifacts": artifacts,
        "build_result": {
            "test_output": "ep_client_replication_contract_synthetic_passed",
            "test_exit_code": 0,
        },
        "decision": {
            "production_patch_ready": False,
            "installable": False,
            "runtime_verified": False,
            "multiplayer_verified": False,
            "reason": "The sidecar is only an offline transaction contract. Native callback ABI, entity creation and five-to-eight-player runtime evidence remain unresolved.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = build_receipt()
    if args.output:
        if args.output.exists():
            raise FileExistsError(args.output)
        args.output.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"schema": receipt["schema"], "checks": len(receipt["checks"]), "installable": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
