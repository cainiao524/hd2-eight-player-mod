"""Fail-closed static cross-reference for host admission and roster dispatch.

This verifier only replays saved disassembly.  It never opens a process, calls a
function, writes memory, or infers a public ABI from an indirect call.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "five_player_feasibility_20260927"
SOURCES = {
    "host_expansion": BASE / "host_expansion_disasm_108d9f0.json",
    "host_dispatch": BASE / "protocol_host_to_client_dispatch.json",
    "confirmed_sender": BASE / "protocol_confirmed_peer_sender.json",
    "join_handler": BASE / "join_handler_disasm.json",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def rows(doc: dict) -> dict[str, dict]:
    result: dict[str, dict] = {}
    def visit(value: object) -> None:
        if isinstance(value, dict):
            if "rva" in value and ("bytes" in value or "asm" in value):
                rva = str(value.get("rva", "")).lower()
                if rva:
                    require(rva not in result, f"duplicate RVA {rva}")
                    result[rva] = value
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(doc)
    return result


def expect(table: dict[str, dict], rva: str, bytecode: str, asm: str) -> dict:
    row = table.get(rva.lower())
    require(row is not None, f"missing instruction {rva}")
    require(str(row.get("bytes", "")).lower() == bytecode.lower(), f"bytes drift at {rva}")
    require(str(row.get("asm", "")).lower() == asm.lower(), f"asm drift at {rva}")
    return {"rva": rva, "bytes": bytecode, "asm": asm}


def load() -> tuple[dict[str, dict], dict[str, str]]:
    loaded: dict[str, dict] = {}
    hashes: dict[str, str] = {}
    for name, path in SOURCES.items():
        raw = path.read_bytes()
        loaded[name] = json.loads(raw.decode("utf-8"))
        hashes[str(path.relative_to(ROOT))] = sha256(raw)
    return loaded, hashes


def recover() -> dict:
    docs, source_hashes = load()
    host = rows(docs["host_expansion"])
    dispatch = rows(docs["host_dispatch"])
    sender = rows(docs["confirmed_sender"])
    join = rows(docs["join_handler"])

    host_rows = {
        "admission_call_08": expect(host, "0x108ddc7", "41ff5008", "call qword ptr [r8 + 8]"),
        "admission_call_50": expect(host, "0x108de09", "41ff5050", "call qword ptr [r8 + 0x50]"),
        "state_write": expect(host, "0x108ddf2", "41c744242007000000", "mov dword ptr [r12 + 0x20], 7"),
        "event_hash_1": expect(host, "0x108de17", "b9dda297a4", "mov ecx, 0xa497a2dd"),
        "event_hash_2": expect(host, "0x108de4e", "b99601e78f", "mov ecx, 0x8fe70196"),
    }

    dispatch_rows = {
        "event_hash_roster": expect(dispatch, "0x108c8af", "b91533fb4b", "mov ecx, 0x4bfb3315"),
        "event_call_roster": expect(dispatch, "0x108c8cb", "e8601bb5ff", "call 0xbde430"),
        "event_hash_peer": expect(dispatch, "0x108c8d9", "b92628b71a", "mov ecx, 0x1ab72826"),
        "event_call_peer": expect(dispatch, "0x108c8de", "e84d1bb5ff", "call 0xbde430"),
        "loop_count": expect(dispatch, "0x108c8e7", "41bc04000000", "mov r12d, 4"),
        "record_state_pointer": expect(dispatch, "0x108c8e3", "498d7e40", "lea rdi, [r14 + 0x40]"),
        "record_id_load": expect(dispatch, "0x108c8f0", "488b77e0", "mov rsi, qword ptr [rdi - 0x20]"),
        "record_state_load": expect(dispatch, "0x108c8fd", "8b07", "mov eax, dword ptr [rdi]"),
        "state_lower_bound": expect(dispatch, "0x108c8ff", "83f805", "cmp eax, 5"),
        "state_below_5_skip": expect(dispatch, "0x108c902", "727c", "jb 0x108c980"),
        "state_flag_lower_bound": expect(dispatch, "0x108c908", "83f807", "cmp eax, 7"),
        "state_ge_7_flag": expect(dispatch, "0x108c912", "0f93c0", "setae al"),
        "state_flag_stack_argument": expect(dispatch, "0x108c918", "88442428", "mov byte ptr [rsp + 0x28], al"),
        "sender_call": expect(dispatch, "0x108c923", "e8e87fb5ff", "call 0xbe4910"),
        "client_insert_call": expect(dispatch, "0x108c960", "e8bb41b0ff", "call 0xb90b20"),
        "slot_stride": expect(dispatch, "0x108c980", "4883c738", "add rdi, 0x38"),
        "loop_decrement": expect(dispatch, "0x108c984", "4983ec01", "sub r12, 1"),
        "loop_backedge": expect(dispatch, "0x108c988", "0f8562ffffff", "jne 0x108c8f0"),
        "post_loop_predicate": expect(dispatch, "0x108c991", "e87a202d00", "call 0x135ea10"),
        "post_loop_event_hash": expect(dispatch, "0x108c99e", "b98c6df89b", "mov ecx, 0x9bf86d8c"),
        "post_loop_event_call": expect(dispatch, "0x108c9ad", "e87e1ab5ff", "call 0xbde430"),
    }

    sender_rows = {
        "sender_event_hash": expect(sender, "0xbe4981", "b9f4fc0448", "mov ecx, 0x4804fcf4"),
        "sender_event_call": expect(sender, "0xbe49b8", "e8739affff", "call 0xbde430"),
        "sender_arg_r9": expect(sender, "0xbe496c", "41b905000000", "mov r9d, 5"),
        "sender_len_9": expect(sender, "0xbe493c", "c745a009000000", "mov dword ptr [rbp - 0x60], 9"),
        "sender_len_8": expect(sender, "0xbe494f", "c745a408000000", "mov dword ptr [rbp - 0x5c], 8"),
    }

    join_rows = {
        "nested_table_load": expect(join, "0x108bfb9", "498b4050", "mov rax, qword ptr [r8 + 0x50]"),
        "nested_target_load": expect(join, "0x108bfbd", "4c8b4028", "mov r8, qword ptr [rax + 0x28]"),
        "nested_call": expect(join, "0x108bfc1", "41ffd0", "call r8"),
        "nested_return_test": expect(join, "0x108bfc7", "f7c1faffffff", "test ecx, 0xfffffffa"),
        "nested_status_compare": expect(join, "0x108bfcf", "83f802", "cmp eax, 2"),
        "reject_or_cleanup_predicate": expect(join, "0x108bfd7", "e8543f3600", "call 0x13eff30"),
        "reject_or_cleanup_test": expect(join, "0x108bfdc", "84c0", "test al, al"),
    }

    return {
        "schema": "hd2_admission_dispatch_cleanup_contract_v1",
        "status": "static_cross_reference_only",
        "build": 25480438,
        "module": "game.dll",
        "source_sha256": source_hashes,
        "host_admission": {
            "fixed_rows": host_rows,
            "table_offsets": ["0x08", "0x50"],
            "owner_register": "RCX loaded from [network_context+0xB390]",
            "id_register": "RDX loaded from [r12]",
            "target_functions_named": False,
            "return_abi_decoded": False,
        },
        "host_to_client_dispatch": {
            "fixed_rows": dispatch_rows,
            "slot_loop_count": 4,
            "slot_stride": "0x38",
            "observed_state_gate": {"field": "record+0x20 (RDI)", "low_inclusive": 5, "upper_bound": None, "state_ge_7_stack_flag": True, "network_index_gate": False},
            "confirmed_peer_sender": "0xbe4910",
            "client_confirmed_peer_insert": "0xb90b20",
            "post_loop_predicate": "0x135ea10",
            "post_loop_event_hash": "0x9bf86d8c",
            "meaning": "roster/peer propagation candidate; loop shape is not a player-capacity proof",
        },
        "join_status_and_cleanup": {
            "fixed_rows": join_rows,
            "nested_probe_shape": "[object+0x50] -> [returned+0x28] -> call",
            "nested_return_observation": "EAX is checked against a small status set; semantics unresolved",
            "reject_or_cleanup_candidate": "0x13eff30 followed by test AL and branch to 0x108c043",
            "same_as_host_table_0x50": False,
            "cleanup_abi_proven": False,
        },
        "target_resolution": {
            "host_table_0x08_target_resolved": False,
            "host_table_0x50_target_resolved": False,
            "dispatcher_target_semantics_resolved": False,
            "player_index_4_to_7_proven": False,
            "client_replication_proven": False,
            "multiplayer_verified": False,
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
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "refusing overwrite")
    result = recover()
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "installable": False, "multiplayer_verified": False}))


if __name__ == "__main__":
    main()
