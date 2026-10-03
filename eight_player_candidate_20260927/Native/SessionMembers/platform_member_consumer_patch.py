"""Build a template-only x64 detour for the recovered 0x1093590 consumer.

The output is deliberately non-installable.  It contains a fourteen-byte
entry detour, a sidecar-aware Windows x64 stub, unwind metadata, and an exact
rollback record.  Callback addresses are sentinels and must never be resolved
or called against a live process by this script.
"""
from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path


ENTRY_RVA = 0x1093590
ENTRY_END = 0x10936DF
PATCH_SPAN = 14
STUB_ADDRESS = 0x7FFFDEAD0000
UNWIND_ADDRESS = 0x7FFFDEAD1000
SENTINELS = {
    "resolver": 0x7FFFDEAD2001,
    "mode": 0x7FFFDEAD2002,
    "identity": 0x7FFFDEAD2003,
    "lookup": 0x7FFFDEAD2004,
    "status": 0x7FFFDEAD2005,
}

sha256 = lambda b: hashlib.sha256(b).hexdigest()


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


class Assembler:
    def __init__(self, base: int):
        self.base = base
        self.data = bytearray()
        self.labels: dict[str, int] = {}
        self.fixups: list[tuple[int, str]] = []

    def emit(self, data: bytes) -> None:
        self.data.extend(data)

    def label(self, name: str) -> None:
        require(name not in self.labels, f"duplicate label: {name}")
        self.labels[name] = self.base + len(self.data)

    def jcc(self, opcode: bytes, label: str) -> None:
        self.emit(opcode)
        at = len(self.data)
        self.emit(b"\0" * 4)
        self.fixups.append((at, label))

    def jmp(self, label: str) -> None:
        self.emit(b"\xe9")
        at = len(self.data)
        self.emit(b"\0" * 4)
        self.fixups.append((at, label))

    def finish(self) -> bytes:
        out = bytearray(self.data)
        for at, label in self.fixups:
            require(label in self.labels, f"missing label: {label}")
            delta = self.labels[label] - (self.base + at + 4)
            require(-(1 << 31) <= delta < (1 << 31), "rel32 overflow")
            out[at:at + 4] = struct.pack("<i", delta)
        return bytes(out)


def mov_rax_imm(a: Assembler, value: int) -> None:
    a.emit(b"\x48\xb8" + struct.pack("<Q", value))


def build_stub(address: int = STUB_ADDRESS, callbacks: dict[str, int] | None = None) -> bytes:
    callbacks = SENTINELS if callbacks is None else callbacks
    require(set(callbacks) == set(SENTINELS), "callback set mismatch")
    a = Assembler(address)

    # Eight nonvolatile pushes leave RSP at +8 mod 16; 0x28 bytes make it
    # aligned for every callback and provide the mandatory 0x20 shadow area.
    a.emit(b"\x53\x55\x56\x57\x41\x54\x41\x55\x41\x56\x41\x57")
    a.emit(b"\x48\x83\xec\x28")
    a.emit(b"\x48\x85\xc9")
    a.jcc(b"\x0f\x84", "fail")
    a.emit(b"\x48\x89\xcb")  # rbx = owner

    mov_rax_imm(a, callbacks["resolver"])
    a.emit(b"\xff\xd0")       # resolver(owner) -> rax=sidecar
    a.emit(b"\x48\x85\xc0")
    a.jcc(b"\x0f\x84", "fail")
    a.emit(b"\x49\x89\xc4")  # r12 = sidecar
    a.emit(b"\x45\x8b\x6c\x24\x40")  # r13d = sidecar->count
    a.emit(b"\x41\x83\xfd\x08")
    a.jcc(b"\x0f\x87", "fail")

    mov_rax_imm(a, callbacks["mode"])
    a.emit(b"\x48\x89\xd9\xff\xd0")  # mode(owner) -> eax 0/1
    a.emit(b"\x44\x0f\xb6\xf8")        # r15d = zero-extended AL

    a.emit(b"\x48\x8b\x3b")             # rdi = owner->platform object
    a.emit(b"\x48\x85\xff")
    a.jcc(b"\x0f\x84", "return_mode")
    a.emit(b"\x80\xbb\xa6\x1b\x00\x00\x00")
    a.jcc(b"\x0f\x84", "fail")
    a.emit(b"\x45\x85\xed")
    a.jcc(b"\x0f\x84", "fail")
    mov_rax_imm(a, callbacks["identity"])
    a.emit(b"\x48\x89\xd9\xff\xd0")  # identity(owner) -> rax=local ID
    a.emit(b"\x48\x89\xc6")             # rsi = local ID
    a.emit(b"\xbd\x01\x00\x00\x00")     # ebp = 1
    a.emit(b"\x45\x33\xf6")               # r14d = 0

    a.label("loop")
    a.emit(b"\x45\x3b\xf5")               # cmp r14d,r13d
    a.jcc(b"\x0f\x83", "compare")
    a.emit(b"\x4b\x8b\x14\xf4")           # rdx=sidecar->ids[r14]
    a.emit(b"\x48\x39\xf2")               # cmp rdx,rsi
    a.jcc(b"\x0f\x84", "next")
    mov_rax_imm(a, callbacks["lookup"])
    a.emit(b"\x48\x89\xf9")               # rcx=platform object
    a.emit(b"\x49\x89\xd8")               # r8=owner context
    a.emit(b"\xff\xd0")                    # lookup(platform,id,owner)
    a.emit(b"\x48\x85\xc0")
    a.jcc(b"\x0f\x84", "next")
    a.emit(b"\x48\x89\xc1")               # rcx=token
    mov_rax_imm(a, callbacks["status"])
    a.emit(b"\xff\xd0")                    # status(token)
    a.emit(b"\x85\xc0\x0f\x94\xc0")       # al = status == 0
    a.emit(b"\x0f\xb6\xc0")                # eax = al
    a.emit(b"\x41\x21\xc7")                # r15d &= eax
    a.emit(b"\xff\xc5")                     # inc ebp
    a.label("next")
    a.emit(b"\x41\xff\xc6")                # inc r14d
    a.jmp("loop")

    a.label("compare")
    a.emit(b"\x41\x3b\xed")                # cmp ebp,r13d
    a.jcc(b"\x0f\x85", "fail")
    a.label("return_mode")
    a.emit(b"\x44\x89\xf8")                # eax = r15d
    a.jmp("epilogue")

    a.label("fail")
    a.emit(b"\xb8\xff\xff\xff\xff")        # eax = -1
    a.label("epilogue")
    a.emit(b"\x48\x83\xc4\x28")
    a.emit(b"\x41\x5f\x41\x5e\x41\x5d\x41\x5c\x5f\x5e\x5d\x5b\xc3")
    return a.finish()


def unwind_info() -> bytes:
    # Version 1, no flags, 16-byte prologue, 9 unwind codes.
    # Codes are stored in reverse prologue order by Windows x64 convention.
    codes = bytes([
        0x10, 0x42,  # sub rsp, 0x28 (UWOP_ALLOC_SMALL, size/8 - 1 = 4)
        0x0C, 0xF0,  # push r15 (UWOP_PUSH_NONVOL, OpInfo=15)
        0x0A, 0xE0,  # push r14
        0x08, 0xD0,  # push r13
        0x06, 0xC0,  # push r12
        0x04, 0x70,  # push rdi
        0x03, 0x60,  # push rsi
        0x02, 0x50,  # push rbp
        0x01, 0x30,  # push rbx
        0x00, 0x00,  # alignment padding
    ])
    return bytes([0x01, 0x10, 0x09, 0x00]) + codes


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
    require(rows and int(rows[0]["rva"], 16) == ENTRY_RVA, "entry changed")
    require(len(raw) == ENTRY_END - ENTRY_RVA, "body span changed")
    require(sha256(raw) == "940aa51124b7e6cab994cd4916165e4197ea2baf1df9427c642e7e67a1693c88", "body hash changed")
    return raw, sha256(raw)


def build(evidence: Path) -> dict:
    original, body_hash = load_exact_site(evidence)
    stub = build_stub()
    info = unwind_info()
    patch = b"\xff\x25\x00\x00\x00\x00" + struct.pack("<Q", STUB_ADDRESS)
    return {
        "status": "template_sidecar_consumer_patch_candidate",
        "steam_build": 25480438,
        "entry": {
            "rva": hex(ENTRY_RVA),
            "original_end_exclusive": hex(ENTRY_END),
            "captured_body_sha256": body_hash,
            "captured_body_bytes": len(original),
            "entry_patch_span": PATCH_SPAN,
            "expected_entry_bytes": original[:PATCH_SPAN].hex(),
            "expected_entry_bytes_sha256": sha256(original[:PATCH_SPAN]),
            "rollback_bytes": original[:PATCH_SPAN].hex(),
            "patch_bytes_template": patch.hex(),
            "patch_encoding": "FF 25 00 00 00 00 + absolute uint64 stub address",
        },
        "stub": {
            "address_template": hex(STUB_ADDRESS),
            "size_bytes": len(stub),
            "code_hex": stub.hex(),
            "code_sha256": sha256(stub),
            "abi": {
                "input": {"RCX": "owner/platform state"},
                "output": {"EAX": "-1 or 0/1 signed status"},
                "resolver": "RCX=owner; RAX=sidecar or 0",
                "mode": "RCX=owner; EAX=0/1",
                "identity": "RCX=owner; RAX=local platform ID",
                "lookup": "RCX=platform object; RDX=member ID; R8=owner context; RAX=token or 0",
                "status": "RCX=token; EAX=0 means valid",
            },
            "callbacks_template": {name: hex(value) for name, value in SENTINELS.items()},
            "sidecar": {"ids_offset": "0x00", "count_offset": "0x40", "max_count": 8},
        },
        "unwind": {
            "registration": "RtlAddFunctionTable for stub; RtlDeleteFunctionTable on rollback",
            "prologue_size": 16,
            "unwind_info_address_template": hex(UNWIND_ADDRESS),
            "unwind_info_hex": info.hex(),
            "runtime_function": {"begin": hex(STUB_ADDRESS), "end": hex(STUB_ADDRESS + len(stub)), "unwind": hex(UNWIND_ADDRESS)},
            "saved_nonvolatile": ["RBX", "RBP", "RSI", "RDI", "R12", "R13", "R14", "R15"],
            "stack_allocation": 40,
        },
        "continuation": {
            "mode": "full_replacement",
            "forward_target": None,
            "reason": "continuing into 0x109359e would execute the original four-slot reader",
            "rollback_resume": hex(ENTRY_RVA),
            "caller_return": "stub restores nonvolatiles and returns to the original caller",
        },
        "rollback": {
            "restore_rva": hex(ENTRY_RVA),
            "restore_bytes": original[:PATCH_SPAN].hex(),
            "verify_before_restore_sha256": sha256(original[:PATCH_SPAN]),
            "flush_instruction_cache": True,
            "remove_function_table": True,
            "restore_page_protection": True,
            "atomic_install_required": True,
        },
        "verification": {
            "source_evidence": str(evidence),
            "runtime_verified": False,
            "installable": False,
            "game_execution": False,
            "multiplayer_verified": False,
        },
        "limits": [
            "All callback and code addresses are template sentinels; none identifies a live game symbol.",
            "The patch intentionally bypasses the original body and has no forward continuation.",
            "An owner-lifetime-safe resolver, callback ABI binding, and production hook registration remain unresolved.",
            "This artifact does not write, inject, or call the game process.",
        ],
    }


def bind_candidate(evidence: Path, *, game_base: int, code_address: int,
                   unwind_address: int, callbacks: dict[str, int]) -> dict:
    """Emit relocatable bytes for an offline executor supplied by the caller.

    Addresses do not establish code provenance, lifetime, or permission to
    install. The caller must keep the resolver's storage stable across all
    nested callbacks; this generator never allocates or installs anything.
    """
    require(set(callbacks) == set(SENTINELS), "callback set mismatch")
    addresses = [game_base, code_address, unwind_address, *callbacks.values()]
    require(all(type(v) is int and 0x10000 <= v < (1 << 47) for v in addresses),
            "invalid user address")
    require(game_base % 0x1000 == 0, "unaligned game base")
    require(code_address % 16 == 0 and unwind_address % 4 == 0, "unaligned code/unwind")
    require(not any(v in SENTINELS.values() for v in callbacks.values()), "unresolved sentinel")
    require(len(set(callbacks.values())) == len(callbacks), "aliased callbacks")
    stub = build_stub(code_address, callbacks)
    info = unwind_info()
    ranges = [(game_base, game_base + 74727424),
              (code_address, code_address + len(stub)),
              (unwind_address, unwind_address + len(info))]
    require(all(end <= (1 << 47) for _, end in ranges), "range overflow")
    for i, (start, end) in enumerate(ranges):
        for other_start, other_end in ranges[i + 1:]:
            require(end <= other_start or other_end <= start, "overlapping image/code/unwind")
    for value in callbacks.values():
        require(all(not (start <= value < end) for start, end in ranges),
                "callback overlaps image/code/unwind; supply an explicit adapter")
    require(0 <= unwind_address - code_address <= 0xffffffff - len(info),
            "unwind RVA out of range")
    original, body_hash = load_exact_site(evidence)
    return {
        "schema": "platform_member_consumer_bound_candidate_v1",
        "steam_build": 25480438,
        "entry_address": game_base + ENTRY_RVA,
        "expected_entry_hex": original[:PATCH_SPAN].hex(),
        "body_sha256": body_hash,
        "detour_hex": (b"\xff\x25\0\0\0\0" + struct.pack("<Q", code_address)).hex(),
        "code_address": code_address, "code_hex": stub.hex(),
        "unwind_address": unwind_address, "unwind_hex": info.hex(),
        "function_table_base": code_address,
        "runtime_function_hex": struct.pack("<III", 0, len(stub), unwind_address - code_address).hex(),
        "callbacks": dict(callbacks),
        "resolver_contract": "storage and owner held stable through return, including nested callbacks",
        "installable": False, "runtime_verified": False, "multiplayer_verified": False,
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
