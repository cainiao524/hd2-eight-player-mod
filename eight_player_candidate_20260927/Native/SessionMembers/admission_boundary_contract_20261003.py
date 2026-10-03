"""Fail-closed static contract for the fixed-build host admission call sites.

This module replays the saved disassembly only.  It never opens a game process,
invokes a function, writes memory, installs a hook, or names either indirect
target as a public GameSession API.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "five_player_feasibility_20260927" / "host_expansion_disasm_108d9f0.json"
BUILD = 25480438
MODULE = "game.dll"
SITES = {
    "first_admission_call": {
        "rva": "0x108ddc7", "bytes": "41ff5008", "target_table_offset": "0x08",
        "asm": "call qword ptr [r8 + 8]",
    },
    "second_admission_call": {
        "rva": "0x108de09", "bytes": "41ff5050", "target_table_offset": "0x50",
        "asm": "call qword ptr [r8 + 0x50]",
    },
}
REQUIRED = {
    "peer_id_load": ("0x108ddaf", "498b1424", "mov rdx, qword ptr [r12]"),
    "table_load": ("0x108ddbc", "4c8b4040", "mov r8, qword ptr [rax + 0x40]"),
    "owner_load_1": ("0x108ddc0", "488b8990b30000", "mov rcx, qword ptr [rcx + 0xb390]"),
    "owner_load_2": ("0x108de02", "488b8990b30000", "mov rcx, qword ptr [rcx + 0xb390]"),
    "state_write": ("0x108ddf2", "41c744242007000000", "mov dword ptr [r12 + 0x20], 7"),
    "event_hash_1": ("0x108de17", "b9dda297a4", "mov ecx, 0xa497a2dd"),
    "event_hash_2": ("0x108de4e", "b99601e78f", "mov ecx, 0x8fe70196"),
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def instruction_map(doc: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for fragment in doc.get("fragments", []):
        for row in fragment.get("instructions", []):
            rva = str(row.get("rva", "")).lower()
            if rva:
                require(rva not in out, f"duplicate instruction {rva}")
                out[rva] = row
    return out


def recover() -> dict:
    raw = SOURCE.read_bytes()
    doc = json.loads(raw.decode("utf-8"))
    require(doc.get("root") == "0x108d9f0", "unexpected disassembly root")
    rows = instruction_map(doc)
    required_rows: dict[str, dict] = {}
    for name, (rva, expected_bytes, expected_asm) in REQUIRED.items():
        row = rows.get(rva)
        require(row is not None, f"missing {name} at {rva}")
        require(str(row.get("bytes", "")).lower() == expected_bytes, f"bytes drift at {rva}")
        require(str(row.get("asm", "")).lower() == expected_asm.lower(), f"asm drift at {rva}")
        required_rows[name] = row

    calls = []
    for name, spec in SITES.items():
        row = rows.get(spec["rva"])
        require(row is not None, f"missing {name}")
        require(str(row.get("bytes", "")).lower() == spec["bytes"], f"bytes drift at {spec['rva']}")
        require(str(row.get("asm", "")).lower() == spec["asm"].lower(), f"call shape drift at {spec['rva']}")
        calls.append({
            "name": name,
            "rva": spec["rva"],
            "bytes": spec["bytes"],
            "asm": row["asm"],
            "table_base": "R8",
            "table_source": "[game.dll+0x3326308+0x40]",
            "target_table_offset": spec["target_table_offset"],
            "RCX": "[network_context+0xB390]",
            "RDX": "[r12] peer/player opaque id",
            "return_semantics": "unresolved",
        })

    return {
        "schema": "hd2_host_admission_boundary_contract_v1",
        "status": "static_call_shape_only",
        "build": BUILD,
        "module": MODULE,
        "source": str(SOURCE.relative_to(ROOT)),
        "source_sha256": sha256(raw),
        "source_root": doc["root"],
        "call_sites": calls,
        "supporting_sites": {
            name: {"rva": row["rva"], "bytes": row["bytes"], "asm": row["asm"]}
            for name, row in required_rows.items()
        },
        "observed_chain": [
            "load peer/player opaque id from [r12]",
            "load interface table from [game.dll+0x3326308]+0x40",
            "load session/network owner from [network_context+0xB390]",
            "indirect call table+0x08",
            "write slot+0x20 = 7",
            "indirect call table+0x50",
            "dispatch hashes 0xA497A2DD and 0x8FE70196",
        ],
        "semantics": {
            "peer_admission_proven": False,
            "player_index_4_to_7_proven": False,
            "return_values_decoded": False,
            "cleanup_abi_proven": False,
            "player_creation_proven": False,
            "client_replication_proven": False,
            "target_functions_named": False,
        },
        "safety": {
            "process_started": False,
            "process_accessed": False,
            "function_calls_made": False,
            "memory_writes": False,
            "hooks_installed": False,
            "injection": False,
            "production_executable": False,
            "installable": False,
            "runtime_verified": False,
            "multiplayer_verified": False,
        },
        "blockers": [
            "indirect target return and state-consumer ABI are unresolved",
            "the call shape supplies an opaque id and owner but does not prove PeerId or player index semantics",
            "the following cleanup, rejection, migration and client receiver paths are not bound",
            "the saved source is static evidence and cannot produce a production hook",
        ],
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "refusing overwrite")
    result = recover()
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "calls": len(result["call_sites"]), "installable": False}))


if __name__ == "__main__":
    main()
