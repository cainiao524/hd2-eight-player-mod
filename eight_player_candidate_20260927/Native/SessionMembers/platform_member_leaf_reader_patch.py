"""Build a template-only sidecar reader detour for game.dll+0x10936e0."""
from __future__ import annotations

import json
import struct
from pathlib import Path

from platform_member_consumer_patch import (
    Assembler,
    SENTINELS,
    STUB_ADDRESS as CONSUMER_STUB,
    sha256,
    require,
)


ENTRY_RVA = 0x10936E0
ENTRY_END = 0x109375E
PATCH_SPAN = 14
STUB_ADDRESS = 0x7FFFDEAE0000
UNWIND_ADDRESS = 0x7FFFDEAE1000
RESULT_OFFSET = 0x44


def mov_rax_imm(a: Assembler, value: int) -> None:
    a.emit(b"\x48\xb8" + struct.pack("<Q", value))


def build_stub() -> bytes:
    a = Assembler(STUB_ADDRESS)
    # push rbx; sub rsp,20h: valid 5-byte Windows x64 prologue with shadow.
    a.emit(b"\x53\x48\x83\xec\x20")
    a.emit(b"\x48\x89\x4c\x24\x20")  # save owner above callback shadow
    mov_rax_imm(a, SENTINELS["resolver"])
    a.emit(b"\xff\xd0")                # resolver(owner) -> sidecar
    a.emit(b"\x48\x85\xc0")
    a.jcc(b"\x0f\x84", "fail")
    a.emit(b"\x48\x89\xc3")            # rbx = sidecar
    a.emit(b"\x8b\x43" + bytes([RESULT_OFFSET]))  # eax = sidecar signed result
    a.emit(b"\x85\xc0")
    a.jcc(b"\x0f\x88", "fallback")
    a.emit(b"\x0f\x95\xc0")            # bool result = result != 0
    a.emit(b"\x0f\xb6\xc0")            # zero extend AL
    a.jmp("finish")
    a.label("fallback")
    a.emit(b"\x48\x8b\x4c\x24\x20")  # restore owner in RCX
    mov_rax_imm(a, SENTINELS["mode"])
    a.emit(b"\xff\xd0")
    a.jmp("finish")
    a.label("fail")
    a.emit(b"\xb8\xff\xff\xff\xff")
    a.label("finish")
    a.emit(b"\x48\x83\xc4\x20\x5b\xc3")
    return a.finish()


def unwind_info() -> bytes:
    # Version 1, prologue length 5, two codes: alloc_small(0x20), push rbx.
    return bytes([0x01, 0x05, 0x02, 0x00, 0x05, 0x32, 0x01, 0x03])


def load_exact_site(evidence: Path) -> tuple[bytes, str]:
    doc = json.loads(evidence.read_text(encoding="utf-8"))
    rows = doc["instructions"]
    require(doc.get("source", {}).get("capture_sha256") == "5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8", "capture identity changed")
    raw_parts = []
    cursor = ENTRY_RVA
    for row in rows:
        data = bytes.fromhex(row["bytes"])
        require(int(row["rva"], 16) == cursor, "instruction coverage changed")
        require(sha256(data) == row["sha256"], "instruction fingerprint changed")
        raw_parts.append(data)
        cursor += len(data)
    raw = b"".join(raw_parts)
    require(len(raw) == ENTRY_END - ENTRY_RVA, "body span changed")
    require(sha256(raw) == "61b38874c67e6ea40b0c3fe3ca8ec80895d0f86fee14addf112d13b0a60eca65", "body hash changed")
    return raw, sha256(raw)


def build(evidence: Path) -> dict:
    original, body_hash = load_exact_site(evidence)
    stub = build_stub()
    patch = b"\xff\x25\x00\x00\x00\x00" + struct.pack("<Q", STUB_ADDRESS)
    return {
        "status": "template_sidecar_leaf_reader_patch_candidate",
        "steam_build": 25480438,
        "entry": {
            "rva": hex(ENTRY_RVA), "original_end_exclusive": hex(ENTRY_END),
            "captured_body_bytes": len(original), "captured_body_sha256": body_hash,
            "entry_patch_span": PATCH_SPAN,
            "expected_entry_bytes": original[:PATCH_SPAN].hex(),
            "expected_entry_bytes_sha256": sha256(original[:PATCH_SPAN]),
            "rollback_bytes": original[:PATCH_SPAN].hex(),
            "patch_bytes_template": patch.hex(),
        },
        "stub": {
            "address_template": hex(STUB_ADDRESS), "size_bytes": len(stub),
            "code_hex": stub.hex(), "code_sha256": sha256(stub),
            "abi": {
                "input": {"RCX": "owner/platform state"},
                "output": {"EAX": "0/1 for non-negative sidecar result; mode fallback or -1"},
                "resolver": "RCX=owner; RAX=sidecar or 0",
                "sidecar_result": f"signed int32 at sidecar+0x{RESULT_OFFSET:x}",
                "mode": "RCX=owner; EAX=0/1 fallback predicate",
            },
            "callbacks_template": {"resolver": hex(SENTINELS["resolver"]), "mode": hex(SENTINELS["mode"])},
        },
        "unwind": {
            "registration": "RtlAddFunctionTable for stub; RtlDeleteFunctionTable on rollback",
            "prologue_size": 5, "unwind_info_address_template": hex(UNWIND_ADDRESS),
            "unwind_info_hex": unwind_info().hex(),
            "runtime_function": {"begin": hex(STUB_ADDRESS), "end": hex(STUB_ADDRESS + len(stub)), "unwind": hex(UNWIND_ADDRESS)},
            "saved_nonvolatile": ["RBX"], "stack_allocation": 32,
        },
        "continuation": {
            "mode": "full_replacement", "forward_target": None,
            "reason": "the original leaf embeds the old owner result and mode path; sidecar result is explicit",
            "rollback_resume": hex(ENTRY_RVA),
            "caller_return": "stub restores RBX and returns to original caller",
        },
        "rollback": {
            "restore_rva": hex(ENTRY_RVA), "restore_bytes": original[:PATCH_SPAN].hex(),
            "verify_before_restore_sha256": sha256(original[:PATCH_SPAN]),
            "flush_instruction_cache": True, "remove_function_table": True,
            "restore_page_protection": True, "atomic_install_required": True,
        },
        "verification": {"runtime_verified": False, "installable": False, "game_execution": False, "multiplayer_verified": False},
        "limits": [
            "Resolver and mode callback addresses are template sentinels.",
            "sidecar+0x44 is a new signed result field; production owner/sidecar synchronization is unresolved.",
            "No process write, injection, or live callback call is performed.",
        ],
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "refusing overwrite")
    result = build(args.evidence)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "stub_bytes": result["stub"]["size_bytes"], "installable": False}))


if __name__ == "__main__":
    main()
