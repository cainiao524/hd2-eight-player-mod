"""Emit and statically verify exact-build mid-function bridge stubs.

This module only builds byte templates and verifies saved disassembly.  It does
not open a process, allocate executable memory, patch a game module, or install
an exception table.  Runtime helper addresses are explicit inputs and remain
unbound until a separately reviewed owner/lifetime ABI exists.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import struct
from typing import Iterable

STEAM_BUILD = 25480438
MODULE = "game.dll"
GAME_SHA256 = "2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e"
DISASM_PATH = Path(__file__).resolve().parents[3] / "five_player_feasibility_20260927" / "join_handler_disasm.json"

CAPACITY_SITE = 0x108C18F
CAPACITY_SPAN_END = 0x108C1B5  # immediately before the original mov ecx,4
CAPACITY_CONTINUATION = 0x108C1BA  # original sub ecx,eax
ALLOCATOR_SITE = 0x108C3D8
ALLOCATOR_SPAN_END = 0x108C3E7  # immediately before original failure jmp
ALLOCATOR_CONTINUATION = 0x108C3F7  # original outer-loop continuation

# These addresses are deliberately recognizable templates.  They must be
# replaced by a runtime allocator and callback binder after owner/lifetime and
# dispatcher ABI review.  A template is never accepted by an installer.
TEMPLATE_CAPACITY_STUB = 0x1111111122222222
TEMPLATE_ALLOCATOR_STUB = 0x3333333344444444
TEMPLATE_HELPER = 0x5555555566666666
TEMPLATE_CAPACITY_CONT = 0x7777777788888888
TEMPLATE_ALLOCATOR_CONT = 0x99999999AAAABBBB


@dataclass(frozen=True)
class PatchSite:
    name: str
    rva: int
    end_rva: int
    continuation: int
    expected: bytes
    patch: bytes
    stub: bytes
    helper: int
    stub_address: int
    unwind: bytes
    prolog_size: int
    preserved_registers: tuple[str, ...]

    @property
    def span_length(self) -> int:
        return self.end_rva - self.rva

    @property
    def expected_sha256(self) -> str:
        return hashlib.sha256(self.expected).hexdigest()

    @property
    def patch_sha256(self) -> str:
        return hashlib.sha256(self.patch).hexdigest()

    @property
    def stub_sha256(self) -> str:
        return hashlib.sha256(self.stub).hexdigest()


def _load_instructions() -> list[dict]:
    with DISASM_PATH.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    rows = payload.get("instructions")
    if not isinstance(rows, list):
        raise ValueError("join_disasm_instructions_missing")
    return rows


def _span(rows: Iterable[dict], start: int, end: int) -> bytes:
    selected: list[bytes] = []
    cursor = start
    for row in rows:
        rva = int(str(row["rva"]), 16)
        raw = bytes.fromhex(row["bytes"])
        if rva < start or rva >= end:
            continue
        if rva != cursor:
            raise ValueError(f"instruction_gap_or_overlap:{cursor:#x}:{rva:#x}")
        selected.append(raw)
        cursor += len(raw)
    if cursor != end:
        raise ValueError(f"span_not_instruction_aligned:{cursor:#x}:{end:#x}")
    return b"".join(selected)


def _push(reg_opcode: bytes) -> bytes:
    return reg_opcode


def _mov_abs(reg: str, address: int) -> bytes:
    if reg == "rax":
        return b"\x48\xB8" + struct.pack("<Q", address)
    if reg == "r11":
        return b"\x49\xBB" + struct.pack("<Q", address)
    raise ValueError(reg)


def _absolute_jump(address: int) -> bytes:
    # FF 25 00 00 00 00 followed by an absolute qword target.
    return b"\xFF\x25\x00\x00\x00\x00" + struct.pack("<Q", address)


def _register_unwind(prolog_size: int, operations: list[tuple[int, int]]) -> bytes:
    """Build a version-1 UNWIND_INFO, using descending prologue offsets."""
    ordered = sorted(operations, key=lambda item: item[0], reverse=True)
    count = len(ordered)
    encoded = bytearray([0x01, prolog_size, count, 0x00])
    for offset, op_info in ordered:
        encoded.extend((offset, op_info))
    if count & 1:
        encoded.extend((0, 0))
    return bytes(encoded)


def _capacity_stub(helper: int, continuation: int, stub_address: int) -> tuple[bytes, bytes, int, tuple[str, ...]]:
    # At this site RSP is the already allocated game frame.  Six pushes (48)
    # plus shadow space (32) keep RSP 16-byte aligned before CALL.  The helper
    # returns an occupied-count in EAX.  Invalid values are clamped to 8 so the
    # original SUB produces a fail-closed zero/negative capacity.
    code = bytearray()
    code += _push(b"\x41\x51")  # push r9 (host owner)
    code += _push(b"\x41\x54")  # push r12 (context)
    code += _push(b"\x41\x55")  # push r13 (request count)
    code += _push(b"\x41\x56")  # push r14 (base/index)
    code += _push(b"\x41\x57")  # push r15 (request list)
    code += _push(b"\x55")      # push rbp (game frame)
    code += b"\x48\x83\xEC\x20"  # sub rsp,32-byte shadow space
    # R9 carries the native host owner at this mid-function site.  The
    # helper ABI receives it in RCX; 49 8B C9 is mov rcx,r9.  4C 8B C9
    # would move the unrelated RCX value into R9 and silently lose owner.
    code += b"\x49\x8B\xC9"       # mov rcx,r9 (owner)
    code += b"\x41\x8B\xD6"       # mov edx,r14d (native base/index)
    code += _mov_abs("rax", helper)
    code += b"\xFF\xD0"           # call rax
    code += b"\x48\x83\xC4\x20"  # add rsp,32
    code += b"\x5D"               # pop rbp
    code += b"\x41\x5F"           # pop r15
    code += b"\x41\x5E"           # pop r14
    code += b"\x41\x5D"           # pop r13
    code += b"\x41\x5C"           # pop r12
    code += b"\x41\x59"           # pop r9
    # Reject helper results outside [0,8] by treating them as fully occupied.
    # The original mov ecx,4 lies inside the overwritten span.  Set the
    # replacement capacity before both branches so the continuation's
    # original sub ecx,eax always has a defined eight-slot capacity.
    code += b"\xB9\x08\x00\x00\x00"  # mov ecx,8
    code += b"\x83\xF8\x08"       # cmp eax,8
    code += b"\x76\x05"           # jbe valid
    code += b"\xB8\x08\x00\x00\x00"  # mov eax,8
    code += _absolute_jump(continuation)
    unwind = _register_unwind(15, [
        (15, 0x32),  # UWOP_ALLOC_SMALL, 32 bytes
        (11, 0x50),  # UWOP_PUSH_NONVOL RBP
        (10, 0xF0),  # UWOP_PUSH_NONVOL R15
        (8, 0xE0),   # UWOP_PUSH_NONVOL R14
        (6, 0xD0),   # UWOP_PUSH_NONVOL R13
        (4, 0xC0),   # UWOP_PUSH_NONVOL R12
        (2, 0x90),   # UWOP_PUSH_NONVOL R9
    ])
    return bytes(code), unwind, 15, ("r9", "r12", "r13", "r14", "r15", "rbp")


def _allocator_stub(helper: int, continuation: int, stub_address: int) -> tuple[bytes, bytes, int, tuple[str, ...]]:
    # The native loop carries host in R9 and the record destination in RDX.
    # Preserve both volatile values across the sidecar allocator call.
    code = bytearray()
    code += b"\x41\x51"           # push r9
    code += b"\x52"               # push rdx
    code += b"\x48\x83\xEC\x20"  # shadow space
    # R9 carries the native host owner; pass it through the Windows x64 first
    # argument register RCX before calling the sidecar helper.
    code += b"\x49\x8B\xC9"       # mov rcx,r9 (owner)
    code += b"\x41\x8B\xD6"       # mov edx,r14d (start index)
    code += _mov_abs("rax", helper)
    code += b"\xFF\xD0"           # call rax
    code += b"\x48\x83\xC4\x20"  # release shadow space
    code += b"\x5A"               # pop rdx
    code += b"\x41\x59"           # pop r9
    # Valid return values are 0..7 or the native failure sentinel -1.
    code += b"\x83\xF8\x08"       # cmp eax,8
    code += b"\x72\x0A"           # jb valid
    code += b"\x83\xF8\xFF"       # cmp eax,-1
    code += b"\x74\x05"           # je valid
    code += b"\xB8\xFF\xFF\xFF\xFF"  # mov eax,-1
    code += b"\x44\x8B\xC0"       # mov r8d,eax
    code += _mov_abs("r11", continuation)
    code += b"\x41\xFF\xE3"       # jmp r11
    unwind = _register_unwind(7, [
        (7, 0x32),  # UWOP_ALLOC_SMALL, 32 bytes
        (3, 0x20),  # UWOP_PUSH_NONVOL RDX
        (2, 0x90),  # UWOP_PUSH_NONVOL R9
    ])
    return bytes(code), unwind, 7, ("r9", "rdx")


def _patch(stub_address: int, span_length: int) -> bytes:
    jump = _absolute_jump(stub_address)
    if len(jump) > span_length:
        raise ValueError("patch_span_too_short")
    return jump + b"\x90" * (span_length - len(jump))


def _make_sites(rows: list[dict]) -> tuple[PatchSite, PatchSite]:
    capacity_expected = _span(rows, CAPACITY_SITE, CAPACITY_SPAN_END)
    allocator_expected = _span(rows, ALLOCATOR_SITE, ALLOCATOR_SPAN_END)
    capacity_stub, capacity_unwind, capacity_prolog, capacity_preserved = _capacity_stub(
        TEMPLATE_HELPER, TEMPLATE_CAPACITY_CONT, TEMPLATE_CAPACITY_STUB)
    allocator_stub, allocator_unwind, allocator_prolog, allocator_preserved = _allocator_stub(
        TEMPLATE_HELPER, TEMPLATE_ALLOCATOR_CONT, TEMPLATE_ALLOCATOR_STUB)
    return (
        PatchSite(
            "host_capacity_midgate", CAPACITY_SITE, CAPACITY_SPAN_END,
            CAPACITY_CONTINUATION, capacity_expected,
            _patch(TEMPLATE_CAPACITY_STUB, CAPACITY_SPAN_END - CAPACITY_SITE),
            capacity_stub, TEMPLATE_HELPER, TEMPLATE_CAPACITY_STUB,
            capacity_unwind, capacity_prolog, capacity_preserved,
        ),
        PatchSite(
            "host_index_allocator_midloop", ALLOCATOR_SITE, ALLOCATOR_SPAN_END,
            ALLOCATOR_CONTINUATION, allocator_expected,
            _patch(TEMPLATE_ALLOCATOR_STUB, ALLOCATOR_SPAN_END - ALLOCATOR_SITE),
            allocator_stub, TEMPLATE_HELPER, TEMPLATE_ALLOCATOR_STUB,
            allocator_unwind, allocator_prolog, allocator_preserved,
        ),
    )


def _branch_targets(rows: list[dict]) -> list[tuple[int, int, str]]:
    results: list[tuple[int, int, str]] = []
    for row in rows:
        asm = str(row.get("asm", ""))
        mnemonic = asm.split(" ", 1)[0].lower() if asm else ""
        if not (mnemonic.startswith("j") or mnemonic == "call"):
            continue
        matches = re.findall(r"0x[0-9a-fA-F]+", asm)
        if not matches:
            continue
        results.append((int(str(row["rva"]), 16), int(matches[-1], 16), mnemonic))
    return results


def _check_no_external_targets(rows: list[dict], site: PatchSite) -> None:
    for source, target, mnemonic in _branch_targets(rows):
        if site.rva <= source < site.end_rva:
            continue
        # A pre-existing edge to the first byte remains valid because the
        # absolute jump at the site is the new entry.  Edges to bytes after
        # that first instruction would bypass the replacement and are unsafe.
        if site.rva < target < site.end_rva:
            raise ValueError(f"external_branch_into_patch:{site.name}:{source:#x}:{target:#x}:{mnemonic}")


def _check_stub(site: PatchSite) -> None:
    if len(site.patch) != site.span_length:
        raise ValueError(f"patch_length:{site.name}")
    if site.patch[:6] != b"\xFF\x25\x00\x00\x00\x00":
        raise ValueError(f"patch_not_absolute_jump:{site.name}")
    if any(byte != 0x90 for byte in site.patch[14:]):
        raise ValueError(f"patch_fill_not_nop:{site.name}")
    # All machine-code templates use absolute helper/continuation calls.  No
    # relative CALL/JMP is allowed because the runtime allocation address is
    # not known until activation.
    if b"\xE8" in site.stub or b"\xE9" in site.stub:
        raise ValueError(f"relative_call_or_jump_in_stub:{site.name}")
    if site.prolog_size <= 0 or len(site.unwind) < 4:
        raise ValueError(f"unwind_missing:{site.name}")
    if site.unwind[0] & 7 != 1:
        raise ValueError(f"unwind_version:{site.name}")
    if site.unwind[1] != site.prolog_size:
        raise ValueError(f"unwind_prolog_size:{site.name}")
    count = site.unwind[2]
    if count == 0 or 4 + ((count + 1) & ~1) * 2 != len(site.unwind):
        raise ValueError(f"unwind_slots:{site.name}")
    if site.prolog_size % 16 != 0 and site.name == "host_capacity_midgate":
        # 15-byte prologue is legal; this branch documents that alignment is a
        # call-site invariant, not an UNWIND_INFO alignment requirement.
        pass


def verify() -> dict:
    rows = _load_instructions()
    sites = _make_sites(rows)
    for site in sites:
        _check_no_external_targets(rows, site)
        _check_stub(site)
    capacity, allocator = sites
    if capacity.span_length != 38 or allocator.span_length != 15:
        raise ValueError("unexpected_patch_span")
    if capacity.continuation != 0x108C1BA or allocator.continuation != 0x108C3F7:
        raise ValueError("unexpected_continuation")
    # The two generated stubs use stack adjustments that keep the pre-CALL RSP
    # alignment unchanged: 6*8+32 and 2*8+32 are both divisible by 16.
    alignment = {"capacity": (6 * 8 + 32) % 16, "allocator": (2 * 8 + 32) % 16}
    if alignment != {"capacity": 0, "allocator": 0}:
        raise ValueError("call_stack_alignment")
    return {
        "schema": "hd2_midgate_machine_stub_candidate_v1",
        "steam_build": STEAM_BUILD,
        "module": MODULE,
        "game_sha256": GAME_SHA256,
        "disassembly_source": str(DISASM_PATH),
        "disassembly_sha256": hashlib.sha256(DISASM_PATH.read_bytes()).hexdigest(),
        "status": {
            "machine_code_emitted": True,
            "patch_record_reversible": True,
            "windows_unwind_layout_emitted": True,
            "process_accessed": False,
            "game_module_modified": False,
            "install_game_rva": False,
            "executable": False,
            "multiplayer_verified": False,
        },
        "sites": [
            {
                "name": site.name,
                "rva": hex(site.rva),
                "span_end_exclusive": hex(site.end_rva),
                "span_length": site.span_length,
                "continuation": hex(site.continuation),
                "expected_bytes": site.expected.hex(),
                "expected_sha256": site.expected_sha256,
                "patch_template_bytes": site.patch.hex(),
                "patch_sha256": site.patch_sha256,
                "stub_template_address": hex(site.stub_address),
                "helper_template_address": hex(site.helper),
                "stub_bytes": site.stub.hex(),
                "stub_sha256": site.stub_sha256,
                "unwind_info_bytes": site.unwind.hex(),
                "unwind_sha256": hashlib.sha256(site.unwind).hexdigest(),
                "unwind_prolog_size": site.prolog_size,
                "preserved_registers": list(site.preserved_registers),
                "runtime_function": {
                    "begin_address": 0,
                    "end_address": len(site.stub),
                    "unwind_data": (len(site.stub) + 3) & ~3,
                    "alignment": "runtime allocation must be DWORD aligned",
                },
            }
            for site in sites
        ],
        "rollback": {
            "method": "restore_exact_expected_bytes_then_flush_instruction_cache",
            "capacity_original_sha256": capacity.expected_sha256,
            "allocator_original_sha256": allocator.expected_sha256,
            "quiescence_required": True,
            "unwind_delete_before_stub_free": True,
        },
        "abi_status": {
            "capacity_helper_signature": "uint32_t helper(void* host_owner, uint32_t native_base_index)",
            "allocator_helper_signature": "int32_t helper(void* host_owner, uint32_t start_index)",
            "owner_lifetime_closed": False,
            "confirmed_peer_dispatch_closed": False,
            "player_creation_closed": False,
            "midfunction_live_execution_verified": False,
            "reason_blocked": [
                "helper addresses are template values and have no production owner binding",
                "host/client sidecar lifetime and reentrancy are not proven",
                "confirmed-peer receiver and player-creation callbacks remain unresolved",
                "only saved bytes and synthetic template checks exist; no live patch was installed",
            ],
        },
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify()
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

