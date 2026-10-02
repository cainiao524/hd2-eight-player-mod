"""Replay the fixed-build player creation ABI and enumerate the safe gaps.

This is a bounded offline evidence join.  It reads saved disassembly/evidence
only; it never opens a process, calls a game function, writes memory, patches
or installs a mod.  The output is deliberately a gap audit rather than a
production patch recipe.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
BUILD = 25480438
CAPTURE_SHA = "5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8"


def load(name: str):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def walk_rows(value):
    if isinstance(value, dict):
        if isinstance(value.get("rva"), str) and "asm" in value:
            yield value
        for child in value.values():
            yield from walk_rows(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_rows(child)


def index_rows(*docs):
    out = {}
    for doc in docs:
        for row in walk_rows(doc):
            out.setdefault(row["rva"].lower(), []).append(row)
    return out


def require(rows, rva: str, *parts: str):
    candidates = rows.get(rva.lower(), [])
    if not candidates:
        raise AssertionError(f"missing pinned instruction {rva}")
    for row in candidates:
        asm = row.get("asm", "")
        if all(part in asm for part in parts):
            return {
                "rva": rva,
                "bytes": row.get("bytes"),
                "sha256": row.get("sha256"),
                "asm": asm,
                "root": row.get("root"),
            }
    got = [row.get("asm") for row in candidates]
    raise AssertionError(f"{rva}: no row contains {parts!r}; got {got!r}")


def build_audit() -> dict:
    identity = load("spawn_resource_identity_evidence.json")
    property_dispatch = load("property_dispatch_evidence.json")
    gate = load("local_player_creation_gate_evidence.json")
    binding = load("roster_component_binding_evidence_v3.json")
    lifecycle = load("component238_lifecycle_evidence_v2.json")
    resource_581320 = load("spawn_resource_581320_disasm.json")
    resource_581780 = load("spawn_resource_581780_disasm.json")
    rows = index_rows(identity, property_dispatch, gate, binding)
    rows_581320 = index_rows(resource_581320)
    rows_581780 = index_rows(resource_581780)

    for name, doc in (("identity", identity), ("property_dispatch", property_dispatch), ("gate", gate), ("binding", binding)):
        observed = doc.get("capture_identity_sha256") or doc.get("capture_sha256")
        if observed and observed != CAPTURE_SHA:
            raise AssertionError(f"{name} capture identity changed: {observed}")

    pins = {
        "gate_call": require(rows, "0x10868d7", "call 0xfdc140"),
        "gate_arg_rcx": require(rows, "0x10868ce", "lea rcx, [rsi + 0xe49f0]"),
        "gate_arg_rdx": require(rows, "0x10868cc", "mov edx, eax"),
        "gate_arg_r8": require(rows, "0x10868c9", "mov r8, rdi"),
        "gate_arg_r9": require(rows, "0x10868c2", "lea r9, [rbp + 0x2b0]"),
        "fdc_owner_save": require(rows, "0xfdc165", "mov rsi, rcx"),
        "fdc_metadata_save": require(rows, "0xfdc172", "mov rbp, r9"),
        "fdc_hash_save": require(rows, "0xfdc175", "mov rdi, r8"),
        "fdc_handle_save": require(rows, "0xfdc178", "mov ebx, edx"),
        "fdc_owner_counter": require(rows, "0xfdc191", "[rsi + 0xf32f14]"),
        "fdc_record_address": require(rows, "0xfdc1af", "lea r14, [rsi + r14*8]"),
        "fdc_record_handle": require(rows, "0xfdc1bb", "[r14 + 8], ebx"),
        "fdc_record_hash": require(rows, "0xfdc1c3", "[r14], rdi"),
        "fdc_record_metadata": require(rows, "0xfdc1c9", "[r14 + 0x10], eax"),
        "fdc_record_flag": require(rows, "0xfdc1d7", "[r14 + 0x14], 1"),
        "fdc_callback_owner": require(rows, "0xfdc250", "lea rcx, [rsi + 0x40]"),
        "fdc_callback_metadata": require(rows, "0xfdc254", "mov r8, rbp"),
        "fdc_callback_record": require(rows, "0xfdc257", "mov rdx, r14"),
        "fdc_first_dispatch": require(rows, "0xfdc25a", "call 0x581320"),
        "fdc_second_dispatch": require(rows, "0xfdc2b1", "call 0x581780"),
        "dispatch_first_owner": require(rows_581320, "0x581353", "mov r12, rcx"),
        "dispatch_first_record": require(rows_581320, "0x581366", "mov r15, rdx"),
        "dispatch_first_metadata": require(rows_581320, "0x581348", "mov rsi, r8"),
        "dispatch_first_table": require(rows_581320, "0x58140e", "+ 0xf0c110"),
        "dispatch_first_call": require(rows_581320, "0x581421", "call rax"),
        "dispatch_second_table": require(rows_581320, "0x581509", "+ 0xf0cb30"),
        "dispatch_second_call": require(rows_581320, "0x58152f", "call rax"),
        "dispatch_second_owner": require(rows_581780, "0x5817b0", "mov rdi, rcx"),
        "dispatch_second_record": require(rows_581780, "0x5817ad", "mov r12, rdx"),
        "dispatch_second_metadata": require(rows_581780, "0x58180d", "movups xmm0, xmmword ptr [r8]"),
        "dispatch_third_table": require(rows_581780, "0x581a3b", "+ 0xf0d550"),
        "dispatch_third_call": require(rows_581780, "0x581a4e", "call rax"),
        "roster_four_guard": require(rows, "0x54093c", "cmp eax, 4"),
        "roster_params_flag": require(rows, "0x54094c", "[rdx], 0"),
        "roster_count_read": require(rows, "0x540957", "[rbx + 0x88]"),
        "roster_count_write": require(rows, "0x54097b", "[rbx + 0x88], eax"),
        "roster_record_write": require(rows, "0x540a24", "[rbx + rdx*8 + 0xe8], rdi"),
    }

    # 0x581320 establishes the owner+8 metadata side effects and failure
    # sentinel.  These fields must move together with a sidecar.
    for key, rva, fragment in (
        ("ordinal_sentinel", "0x58159b", "[r15 + 0x10], 0x7fff"),
        ("owner_ordinal_map", "0x58175a", "[r13 + r14*4 + 0x1c]"),
        ("owner_flag_a", "0x58175f", "[r14 + r13 + 0x201c]"),
        ("owner_flag_b", "0x581768", "[r14 + r13 + 0x281c]"),
        ("owner_count_increment", "0x581771", "[r13 + 0x18]"),
        ("record_ordinal_write", "0x581775", "[r15 + 0x10], r9d"),
    ):
        pins[key] = require(rows_581320, rva, fragment)

    # 0x540920 is the actual roster first-stage leaf: it still rejects a
    # roster count >=4, increments count/active counters and writes an inline
    # pointer array.  This is the concrete component-side blocker.
    component238 = lifecycle["lifecycle"]
    cleanup_pins = lifecycle["pins"]["destroy_owner_and_unregister_component"]
    cleanup_targets = [
        {"rva": row["rva"], "asm": row["asm"], "root": row.get("root"), "sha256": row.get("sha256")}
        for row in cleanup_pins
        if row["rva"].lower() in {"0x56534c", "0x565353", "0x565358", "0x56535f", "0x565364", "0x56536b"}
    ]
    if len(cleanup_targets) != 6:
        raise AssertionError("component 238 cleanup pins changed")

    checks = {
        "gate_rejects_index_4_to_7": True,
        "resource_record_has_dynamic_search_counter": True,
        "resource_record_has_handle_hash_metadata_and_flag": True,
        "three_callback_tables_have_explicit_owner_base": True,
        "first_stage_roster_has_fixed_four_guard": True,
        "roster_inline_record_write_is_not_sidecar": True,
        "component238_cleanup_is_owner_scoped": True,
        "player_resource_reverse_cleanup_proven": False,
        "partial_resource_rollback_proven": False,
        "owner_migration_and_thread_quiescence_proven": False,
        "index_4_to_7_player_creation_proven": False,
        "runtime_verified": False,
        "multiplayer_verified": False,
        "installable": False,
    }

    return {
        "schema": "hd2_player_creation_abi_gap_audit_v1",
        "build": BUILD,
        "capture_sha256": CAPTURE_SHA,
        "abi": {
            "gate": "0x1086460 compares the owner+0x163ac network index with 4 before 0x10868d7",
            "caller_contract": {
                "rcx": "rsi + 0xe49f0 (resource/creation context)",
                "rdx": "returned resource handle in eax",
                "r8": "player entity resource hash in rdi",
                "r9": "stack metadata at rbp + 0x2b0",
            },
            "fdc140_contract": {
                "owner": "entry rcx saved as rsi",
                "metadata": "entry r9 saved as rbp",
                "resource_hash": "entry r8 saved as rdi",
                "resource_handle": "entry edx saved as ebx",
                "record": "r14 = owner + (counter-derived record index)*8",
                "record_fields": {"+0": "resource hash", "+8": "handle", "+0x10": "component ordinal/sentinel", "+0x14": "creation flag"},
                "dispatch": [
                    "0x581320(rcx=owner+0x40, rdx=record, r8=metadata, r9=owner+8)",
                    "0x581780(rcx=owner+0x40, rdx=record, r8=metadata)",
                ],
            },
            "callback_tables": {
                "first": "owner+0x40 + component_index*8 + 0xf0c110",
                "second": "owner+0x40 + component_index*8 + 0xf0cb30",
                "third": "owner+0x40 + component_index*8 + 0xf0d550",
                "roster_component": 239,
            },
            "roster_leaf_540920": {
                "guard": "global roster field +0x80 cmp 4",
                "params": "RDX points to creation parameter byte; zero skips insertion",
                "writes": "global +0x88 count and inline pointer table at +0xe8 + ordinal*8",
            },
            "owner8_side_effects": {
                "ordinal_map": "owner+8 + ordinal*4 + 0x1c",
                "flag_a": "owner+8 + ordinal + 0x201c",
                "flag_b": "owner+8 + ordinal + 0x281c",
                "count": "owner+8 + 0x18",
                "failure_sentinel": "record+0x10 = 0x7fff",
            },
        },
        "cleanup_evidence": {
            "component238": component238,
            "pins": cleanup_targets,
            "player_resource_reverse_cleanup": None,
            "partial_failure_rollback": None,
            "interpretation": "The saved cleanup proof removes component-238 owner state through 0x873a70/0xb2fc70. It does not prove that the 0xfdc140 resource record, callback tables, owner+8 maps, and roster pointer are reversed exactly once for index 4..7.",
        },
        "required_sidecar_contract": [
            "Keep network index, roster ordinal, resource record ordinal and component-map ordinal distinct.",
            "Allocate owner-keyed records for indices 4..7 without changing the 0x800 hash-search wrap semantics.",
            "Provide an idempotent failure unwind after each of: resource record write, 0x581320 callbacks, 0x581780 callbacks, 0x540920 roster insertion.",
            "Reverse owner+8 ordinal/flags/count, record+0x10/+0x14, callback registration and roster inline pointer in the same generation.",
            "Prove owner migration, reconnect and thread quiescence before exposing a native hook.",
        ],
        "checks": checks,
        "pins": pins,
        "limits": [
            "Fixed saved capture only; no process query/read, game execution, patch, installation or multiplayer test.",
            "No safe production patch is emitted. A literal cmp-4 change would leave resource, roster, callback and cleanup contracts unresolved.",
            "The 0x800 counter/search bound is an internal resource-record wrap, not player capacity.",
            "Component 238 cleanup evidence is owner-scoped and cannot be promoted to complete player-resource rollback.",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True, type=Path)
    ns = ap.parse_args()
    if ns.output.exists():
        raise FileExistsError(ns.output)
    result = build_audit()
    ns.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"schema": result["schema"], "pin_count": len(result["pins"]), "installable": result["checks"]["installable"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
