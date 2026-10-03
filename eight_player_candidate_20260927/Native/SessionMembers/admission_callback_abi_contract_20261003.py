"""Replay the fixed-build admission callback ABI boundary.

This module consumes only saved disassembly and read-only capture artifacts.  It
does not start or attach to a game process, resolve writable function tables,
call a native target, install a hook, or emit a patch.  A direct address or an
instruction shape is recorded as evidence only; an ABI field is marked proven
only when the saved evidence actually supports it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
BUILD = 25480438
MODULE = "game.dll"

SOURCE_FILES = {
    "host_admission": ROOT / "five_player_feasibility_20260927" / "host_expansion_disasm_108d9f0.json",
    "host_dispatch": ROOT / "five_player_feasibility_20260927" / "protocol_host_to_client_dispatch.json",
    "confirmed_sender": ROOT / "five_player_feasibility_20260927" / "protocol_confirmed_peer_sender.json",
    "join_handler": ROOT / "five_player_feasibility_20260927" / "join_handler_disasm.json",
    "admission_sites_capture": ROOT / "five_player_feasibility_20260927" / "native_admission_sites_live_20261002_r2.json",
    "confirmed_peer_capture": ROOT / "five_player_feasibility_20260927" / "native_admission_confirmed_peer_live_20261002_r3.json",
    "client_insert_disasm": ROOT / "five_player_feasibility_20260927" / "protocol_b90b20_disasm.json",
}

EXPECTED_SOURCE_SHA256 = {
    "host_admission": "5e065ebbac9e6274ab59f486155e06fed146d1ba5e42bc3bebf22e5f5803e888",
    "host_dispatch": "a485b4b0559181a85fa43b7fbc288edce9a278469e876218166c888c78e1c565",
    "confirmed_sender": "1bf9a21b46bf125d2f6565ee944047b6c4af49d61e0ab88c72faf44dc4210dda",
    "join_handler": "f0e2c853fb731fecffd27ed2bbab97f9d8ed2868b076c60ee51bcdfe472e505c",
    "admission_sites_capture": "31a75196a5afd3b8d102a160225bb0a7066a42af3d47b614ed4eac7be67b304e",
    "confirmed_peer_capture": "50cc6fcb8fa4224791a7d40cdd37dafa719664d92a01b7a6d3505655b5f30f7e",
    "client_insert_disasm": "2c3aca7050821bc93c26653faa7815f21074b95a9139c2407d4003f704b2c85f",
}

EXPECTED_ROWS = {
    "host_admission": {
        "0x108ddaf": ("498b1424", "mov rdx, qword ptr [r12]"),
        "0x108ddc7": ("41ff5008", "call qword ptr [r8 + 8]"),
        "0x108ddf2": ("41c744242007000000", "mov dword ptr [r12 + 0x20], 7"),
        "0x108de02": ("488b8990b30000", "mov rcx, qword ptr [rcx + 0xb390]"),
        "0x108de09": ("41ff5050", "call qword ptr [r8 + 0x50]"),
        "0x108de17": ("b9dda297a4", "mov ecx, 0xa497a2dd"),
        "0x108de4e": ("b99601e78f", "mov ecx, 0x8fe70196"),
    },
    "host_dispatch": {
        "0x108c8cb": ("e8601bb5ff", "call 0xbde430"),
        "0x108c8de": ("e84d1bb5ff", "call 0xbde430"),
        "0x108c8e3": ("498d7e40", "lea rdi, [r14 + 0x40]"),
        "0x108c8e7": ("41bc04000000", "mov r12d, 4"),
        "0x108c8f0": ("488b77e0", "mov rsi, qword ptr [rdi - 0x20]"),
        "0x108c8fd": ("8b07", "mov eax, dword ptr [rdi]"),
        "0x108c8ff": ("83f805", "cmp eax, 5"),
        "0x108c902": ("727c", "jb 0x108c980"),
        "0x108c904": ("448b4ff0", "mov r9d, dword ptr [rdi - 0x10]"),
        "0x108c908": ("83f807", "cmp eax, 7"),
        "0x108c90b": ("4c8b47e8", "mov r8, qword ptr [rdi - 0x18]"),
        "0x108c90f": ("488bd6", "mov rdx, rsi"),
        "0x108c912": ("0f93c0", "setae al"),
        "0x108c915": ("488bcb", "mov rcx, rbx"),
        "0x108c918": ("88442428", "mov byte ptr [rsp + 0x28], al"),
        "0x108c91c": ("8b47f4", "mov eax, dword ptr [rdi - 0xc]"),
        "0x108c91f": ("89442420", "mov dword ptr [rsp + 0x20], eax"),
        "0x108c923": ("e8e87fb5ff", "call 0xbe4910"),
        "0x108c94f": ("488bce", "mov rcx, rsi"),
        "0x108c95d": ("488bd3", "mov rdx, rbx"),
        "0x108c960": ("e8bb41b0ff", "call 0xb90b20"),
        "0x108c980": ("4883c738", "add rdi, 0x38"),
        "0x108c984": ("4983ec01", "sub r12, 1"),
    },
    "join_handler": {
        "0x108bfb9": ("498b4050", "mov rax, qword ptr [r8 + 0x50]"),
        "0x108bfbd": ("4c8b4028", "mov r8, qword ptr [rax + 0x28]"),
        "0x108bfc1": ("41ffd0", "call r8"),
        "0x108bfc4": ("8d48ff", "lea ecx, [rax - 1]"),
        "0x108bfc7": ("f7c1faffffff", "test ecx, 0xfffffffa"),
        "0x108bfcd": ("7505", "jne 0x108bfd4"),
        "0x108bfcf": ("83f802", "cmp eax, 2"),
        "0x108bfd2": ("756f", "jne 0x108c043"),
        "0x108bfd4": ("488bd3", "mov rdx, rbx"),
        "0x108bfd7": ("e8543f3600", "call 0x13eff30"),
        "0x108bfdc": ("84c0", "test al, al"),
        "0x108bfde": ("7563", "jne 0x108c043"),
    },
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _rows(value: object) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}

    def visit(item: object) -> None:
        if isinstance(item, dict):
            if "rva" in item and ("bytes" in item or "asm" in item):
                rva = str(item.get("rva", "")).lower()
                if rva:
                    require(rva not in result, f"duplicate RVA {rva}")
                    result[rva] = item
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return result


def _read_sources() -> tuple[dict[str, Any], dict[str, str]]:
    docs: dict[str, Any] = {}
    hashes: dict[str, str] = {}
    for name, path in SOURCE_FILES.items():
        raw = path.read_bytes()
        digest = sha256(raw)
        require(digest == EXPECTED_SOURCE_SHA256[name], f"source hash drift: {name}")
        docs[name] = json.loads(raw.decode("utf-8"))
        hashes[str(path.relative_to(ROOT)).replace("\\", "/")] = digest
    return docs, hashes


def _expect(table: dict[str, dict[str, Any]], rva: str, expected_bytes: str, expected_asm: str) -> dict[str, str]:
    row = table.get(rva.lower())
    require(row is not None, f"missing instruction {rva}")
    actual_bytes = str(row.get("bytes", "")).lower()
    actual_asm = str(row.get("asm", "")).lower()
    require(actual_bytes == expected_bytes.lower(), f"bytes drift at {rva}")
    require(actual_asm == expected_asm.lower(), f"asm drift at {rva}")
    return {"rva": rva, "bytes": expected_bytes, "asm": expected_asm}


def recover() -> dict[str, Any]:
    docs, source_hashes = _read_sources()
    host = _rows(docs["host_admission"])
    dispatch = _rows(docs["host_dispatch"])
    join = _rows(docs["join_handler"])

    host_rows = {rva: _expect(host, rva, *spec) for rva, spec in EXPECTED_ROWS["host_admission"].items()}
    dispatch_rows = {rva: _expect(dispatch, rva, *spec) for rva, spec in EXPECTED_ROWS["host_dispatch"].items()}
    join_rows = {rva: _expect(join, rva, *spec) for rva, spec in EXPECTED_ROWS["join_handler"].items()}

    capture = docs["confirmed_peer_capture"]
    require(capture.get("build") == BUILD, "confirmed peer capture build drift")
    require(capture.get("read_only") is True, "confirmed peer capture must be read-only")
    require(capture.get("calls_made") is False and capture.get("writes_made") is False, "capture contains active operations")
    game_image = capture.get("pinned_images", {}).get(MODULE, {})
    require(game_image.get("sha256") == "2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e", "game image identity drift")

    return {
        "schema": "hd2_admission_callback_abi_contract_v1",
        "status": "static_abi_contract_fail_closed",
        "build": BUILD,
        "module": MODULE,
        "version_lock": {
            "game_image_sha256": game_image["sha256"],
            "source_sha256": source_hashes,
            "calling_convention": "Windows x64 register ABI (RCX, RDX, R8, R9); indirect target ownership is unresolved",
        },
        "callbacks": [
            {
                "id": "host_admission_table_0x08",
                "kind": "indirect_vtable_target",
                "call_site": host_rows["0x108ddc7"],
                "target": {"table_base": "R8", "table_offset": "0x08", "resolved": False, "address": None},
                "inputs": {"RCX": "[network_context+0xB390] opaque owner", "RDX": "[r12] opaque peer/player id", "R8": "interface table pointer"},
                "return": {"value": "unknown", "semantics_proven": False, "caller_dependency": "unknown"},
                "state_effect": {"linked_site": host_rows["0x108ddf2"], "location": "[r12+0x20]", "value": 7, "meaning_proven": False},
                "cleanup": {"callback": None, "abi_proven": False, "required": ["reject unwind", "departure", "host migration", "owner release"]},
                "proven": False,
            },
            {
                "id": "host_admission_table_0x50",
                "kind": "indirect_vtable_target",
                "call_site": host_rows["0x108de09"],
                "target": {"table_base": "R8", "table_offset": "0x50", "resolved": False, "address": None},
                "inputs": {"RCX": "[network_context+0xB390] opaque owner", "RDX": "[r12] opaque peer/player id", "R8": "interface table pointer"},
                "return": {"value": "unknown", "semantics_proven": False, "caller_dependency": "unknown"},
                "state_effect": {"linked_site": host_rows["0x108de17"], "event_hash": "0xa497a2dd", "meaning_proven": False},
                "cleanup": {"callback": None, "abi_proven": False, "required": ["reject unwind", "departure", "host migration", "owner release"]},
                "proven": False,
            },
            {
                "id": "host_to_client_confirmed_peer_sender",
                "kind": "direct_call_target",
                "call_site": dispatch_rows["0x108c923"],
                "target": {"address_rva": "0xbe4910", "resolved": True, "semantic_name": "confirmed-peer sender candidate"},
                "inputs": {"RCX": "RBX opaque recipient", "RDX": "[RDI-0x20] record opaque id", "R8": "[RDI-0x18] opaque qword", "R9D": "[RDI-0x10] opaque dword", "caller_rsp+0x20": "[RDI-0x0c] opaque dword", "caller_rsp+0x28": "unsigned([RDI]) >= 7 byte flag"},
                "return": {"value": "unconsumed along saved caller continuation", "semantics_proven": False, "evidence": "0x108c928 overwrites RAX after the call; no void ABI is inferred"},
                "state_effect": {"slot_loop_count": 4, "record_stride": "0x38", "state_field": "record+0x20 (RDI)", "dispatch_condition": "opaque id nonzero and unsigned state >=5", "meaning_proven": False},
                "cleanup": {"callback": None, "abi_proven": False, "required": ["record release", "departure", "migration", "serializer unwind"]},
                "proven": False,
            },
            {
                "id": "client_confirmed_peer_insert",
                "kind": "direct_call_target",
                "call_site": dispatch_rows["0x108c960"],
                "target": {"address_rva": "0xb90b20", "resolved": True, "semantic_name": "client confirmed-peer insert candidate"},
                "inputs": {"RCX": "RSI opaque id", "RDX": "RBX opaque recipient", "R8": "[R15+R14+0x28] opaque qword", "R9D": "[R15+R14+0x30] opaque dword", "caller_rsp+0x20": "[R15+R14+0x34] opaque dword", "caller_rsp+0x28": "unsigned([R15+R14+0x40]) >=7 byte flag", "receiver_owner": "unresolved"},
                "return": {"value": "unknown", "semantics_proven": False},
                "state_effect": {"sender_loop_count": 4, "sender_record_stride": "0x38", "client_storage_capacity": "unresolved", "meaning_proven": False},
                "cleanup": {"callback": None, "abi_proven": False, "required": ["duplicate rejection", "remove", "reset", "reconnect"]},
                "proven": False,
            },
            {
                "id": "join_nested_status_probe",
                "kind": "nested_indirect_target",
                "call_site": join_rows["0x108bfc1"],
                "target": {"load_chain": "[object+0x50] -> [returned+0x28] -> call r8", "resolved": False, "address": None},
                "inputs": {"registers": "unresolved", "object_owner": "unresolved"},
                "return": {"value": "EAX low32 opaque status", "semantics_proven": False, "checks": ["ECX=EAX-1 modulo 2^32", "test ecx, 0xfffffffa", "cmp eax, 2"], "mask_pass_values": [1, 2, 5, 6], "branch_0x108c043_without_cleanup_candidate": [1, 5, 6], "other_values": "fall through to 0x108bfd4; includes value 2"},
                "state_effect": {"meaning": "join state or result candidate", "meaning_proven": False},
                "cleanup": {"callback": "0x13eff30 candidate", "abi_proven": False, "required": ["reject cleanup", "partial admission rollback"]},
                "proven": False,
            },
            {
                "id": "join_reject_cleanup_candidate",
                "kind": "direct_call_candidate",
                "call_site": join_rows["0x108bfd7"],
                "target": {"address_rva": "0x13eff30", "resolved": True, "semantic_name": "reject/cleanup candidate only"},
                "inputs": {"RDX": "RBX opaque candidate", "other_registers": "unresolved or volatile after nested probe"},
                "return": {"value": "AL predicate", "semantics_proven": False, "consumer": join_rows["0x108bfdc"]},
                "state_effect": {"meaning": "reject or cleanup predicate", "meaning_proven": False},
                "cleanup": {"callback": None, "abi_proven": False, "required": ["owner release", "pending removal", "partial resource rollback"]},
                "proven": False,
            },
        ],
        "state_contract": {
            "state_write_7": {"site": host_rows["0x108ddf2"], "field": "r12+0x20", "value": 7, "enum_meaning": "unresolved"},
            "event_hashes": ["0xa497a2dd", "0x8fe70196", "0x4bfb3315", "0x1ab72826", "0x9bf86d8c"],
            "player_index_4_to_7_proven": False,
            "state_transition_abi_proven": False,
            "dispatch_state_tests": {"field": "record+0x20", "lower_bound_inclusive": 5, "bool_flag_lower_bound_inclusive": 7, "upper_bound": None, "network_index_gate": False},
        },
        "cleanup_contract": {
            "required_paths": ["reject", "departure", "reconnect", "host migration", "reset/unload"],
            "bound_callbacks": [],
            "target_and_return_abi_proven": False,
            "cleanup_abi_proven": False,
            "fail_closed_reason": "no saved evidence binds a complete inverse path with owner lifetime and resource release",
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
            "indirect table+0x08 and table+0x50 target addresses and return ABIs are unresolved",
            "state value 7 has no decoded enum meaning and is not a player index",
            "dispatcher and client insert call targets do not prove receiver storage, index, or player creation semantics",
            "reject/cleanup candidate has no resolved input, return, owner lifetime, or inverse path ABI",
            "static and read-only evidence cannot produce an installable callback patch",
        ],
    }


def verify(artifact: dict[str, Any]) -> dict[str, Any]:
    current = recover()
    require(artifact == current, "callback artifact differs from replay or promotes unproven ABI")
    return {"status": "passed_static_callback_abi_replay", "callbacks": len(current["callbacks"]), "installable": False, "multiplayer_verified": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "refusing overwrite")
    result = recover()
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "callbacks": len(result["callbacks"]), "installable": False, "multiplayer_verified": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
