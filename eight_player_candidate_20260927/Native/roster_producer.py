"""Emit an offline x64 candidate for the fixed roster property producer.

This module only emits bytes. It does not allocate executable memory, install
hooks, inspect processes, register unwind metadata, or run native game code.
Its required rejection continuation starts inside the producer's saved frame.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

EVIDENCE_SHA256 = "f73ec903d06f2304f4f944c25e011a7ef86d78737cb1b197101a1c96daaabacb"
SOURCE_SHA256 = "8b9a20e5207ae395e99e45f153cba1994ff50c10cb258101fd16a74285824c34"
ENTRY_RVA, END_RVA = 0x60C640, 0x60C882
SPLICE_OFFSET, RESUME_OFFSET = 0x60C6C9 - ENTRY_RVA, 0x60C6CE - ENTRY_RVA
SPLICE_BYTES = bytes.fromhex("488b4c2468")  # mov rcx,[rsp+68h]: allocator pointer
SENTINEL_RVA, ROSTER_GLOBAL_RVA = 0x3483C20, 0x3326468
ALLOCATOR_RVA, INDEX_HELPER_RVA = 0x173B8D0, 0x134F190
PTR_END = 1 << 47
TARGET_PROFILE = {
    "build": 25480438,
    "exe_sha256": "f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06",
    "game_dll_sha256": "2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e",
}
# Whole instructions, each with one external rel32 operand. The complete
# 130-instruction pinned evidence proves there are no other external refs.
RELOCATIONS = (
    (0x60C65E, "3b05bc75e702", 2, SENTINEL_RVA, "rip_memory"),
    (0x60C667, "488b2dfa9dd102", 3, ROSTER_GLOBAL_RVA, "rip_memory"),
    (0x60C6DA, "e8f1f11201", 1, ALLOCATOR_RVA, "call_rel32"),
    (0x60C778, "e8132ad400", 1, INDEX_HELPER_RVA, "call_rel32"),
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def load_source(evidence_path: Path) -> bytes:
    """Reconstruct the complete function from pinned contiguous instructions."""
    raw = Path(evidence_path).read_bytes()
    require(sha(raw) == EVIDENCE_SHA256, "producer evidence fingerprint mismatch")
    producer = json.loads(raw)["producer"]
    require(int(producer["entry"], 16) == ENTRY_RVA and
            int(producer["end_exclusive"], 16) == END_RVA,
            "producer extent changed")
    cursor, chunks = ENTRY_RVA, []
    for row in producer["instructions"]:
        require(int(row["rva"], 16) == cursor, "producer rows not contiguous")
        blob = bytes.fromhex(row["bytes"])
        require(sha(blob) == row["sha256"], "producer instruction fingerprint mismatch")
        chunks.append(blob)
        cursor += len(blob)
    body = b"".join(chunks)
    require(cursor == END_RVA and sha(body) == SOURCE_SHA256,
            "producer body fingerprint mismatch")
    return body


def pointer(value: int, size: int, alignment: int, label: str) -> int:
    require(type(value) is int and value > 0 and value % alignment == 0,
            label + " must be a positive aligned integer")
    require(value + size <= PTR_END, label + " outside supported low canonical range")
    return value


def rel32(next_ip: int, target: int) -> bytes:
    delta = target - next_ip
    require(-(1 << 31) <= delta < (1 << 31),
            "relative displacement outside signed 32 bits")
    return struct.pack("<i", delta)


def overlaps(a: int, size: int, b: int, other_size: int) -> bool:
    return a < b + other_size and b < a + size


def build(source: bytes, *, game_base: int, code_address: int,
          roster_address: int, property_address: int, reject_address: int) -> dict:
    """Emit a bound eight-record producer using supplied, unproven addresses.

    A matching byte profile does not prove that the supplied pointers are
    live or that the original global contains the expected roster instance.
    The emitted guard checks that global-loaded RBP after the map lookup.
    """
    require(type(source) is bytes and len(source) == END_RVA - ENTRY_RVA and
            sha(source) == SOURCE_SHA256, "producer source fingerprint mismatch")
    pointer(game_base, SENTINEL_RVA + 4, 0x1000, "game_base")
    pointer(code_address, 1, 16, "code_address")
    pointer(roster_address, 0x428, 8, "roster_address")
    pointer(property_address, 8 * 0x20, 8, "property_address")
    require(property_address >= 0x3A8, "property address cannot encode biased base")
    pointer(reject_address, 1, 1, "reject_address")
    require(source[SPLICE_OFFSET:RESUME_OFFSET] == SPLICE_BYTES,
            "five-byte splice changed")

    body = bytearray(source)
    for rva, expected_hex, disp_offset, target_rva, _kind in RELOCATIONS:
        instruction = bytes.fromhex(expected_hex)
        offset = rva - ENTRY_RVA
        require(source[offset:offset + len(instruction)] == instruction,
                "external relocation instruction changed")
        body[offset + disp_offset:offset + disp_offset + 4] = rel32(
            code_address + offset + len(instruction), game_base + target_rva)

    # All original internal branches keep their relative offsets because the
    # entire body stays at identical local offsets. C6C9 is one full 5-byte
    # instruction and dominates the allocator and eight roster property stores.
    trampoline_offset = (len(body) + 15) & ~15
    trampoline_address = code_address + trampoline_offset
    body[SPLICE_OFFSET:RESUME_OFFSET] = b"\xe9" + rel32(
        code_address + SPLICE_OFFSET + 5, trampoline_address)
    body.extend(b"\xcc" * (trampoline_offset - len(body)))

    tail = bytearray()
    labels: dict[str, int] = {}
    fixups: list[tuple[int, str | int]] = []

    def emit(blob: bytes) -> None:
        tail.extend(blob)

    def branch(opcode: bytes, target: str | int) -> None:
        tail.extend(opcode)
        fixups.append((len(tail), target))
        tail.extend(b"\0" * 4)

    # RBX is the zero-extended map ordinal at C6C9. RBP is the original
    # roster pointer loaded from global 3326468, not caller RCX. RAX's old
    # entity ID is dead here and the allocator will replace it with a buffer.
    emit(b"\x83\xfb\x08")                       # cmp ebx,8
    branch(b"\x0f\x83", "reject_ordinal")       # jae (unsigned)
    emit(b"\x48\xb8" + struct.pack("<Q", roster_address))
    emit(b"\x48\x39\xc5")                       # cmp rbp,rax
    branch(b"\x0f\x85", "reject_binding")       # jne
    emit(b"\x48\xbd" + struct.pack("<Q", property_address - 0x3A8))
    emit(SPLICE_BYTES)                             # original stack arg6 load
    branch(b"\xe9", code_address + RESUME_OFFSET)

    # Both failures occur before the allocator call and before output buffer,
    # descriptor, count or property writes. No return/skip path is invented.
    labels["reject_ordinal"] = trampoline_address + len(tail)
    emit(b"\x41\xba\x01\0\0\0")             # r10d = 1
    branch(b"\xe9", reject_address)
    labels["reject_binding"] = trampoline_address + len(tail)
    emit(b"\x41\xba\x02\0\0\0")             # r10d = 2
    branch(b"\xe9", reject_address)
    for offset, target in fixups:
        destination = labels[target] if isinstance(target, str) else target
        tail[offset:offset + 4] = rel32(trampoline_address + offset + 4,
                                        destination)
    body.extend(tail)
    pointer(code_address, len(body), 16, "complete code")

    regions = [
        ("candidate code", code_address, len(body)),
        ("roster", roster_address, 0x428),
        ("property sidecar", property_address, 0x100),
        ("sentinel", game_base + SENTINEL_RVA, 4),
        ("roster global pointer", game_base + ROSTER_GLOBAL_RVA, 8),
        ("original producer", game_base + ENTRY_RVA, len(source)),
        ("allocator entry", game_base + ALLOCATOR_RVA, 1),
        ("index helper", game_base + INDEX_HELPER_RVA, 0x5C),
        ("rejection continuation", reject_address, 1),
    ]
    for i, (name, first, size) in enumerate(regions):
        for other, second, length in regions[i + 1:]:
            require(not overlaps(first, size, second, length),
                    "known region overlap: " + name + " / " + other)

    code = bytes(body)
    return {
        "status": "offline_native_candidate", "installable": False,
        "game_execution": False, "multiplayer_verified": False,
        "target_profile": dict(TARGET_PROFILE),
        "source_sha256": sha(source), "evidence_sha256": EVIDENCE_SHA256,
        "code_sha256": sha(code), "code_hex": code.hex(),
        "code_address": code_address, "entry_address": code_address,
        "size_bytes": len(code), "game_base": game_base,
        "roster_address": roster_address, "property_address": property_address,
        "property_size_bytes": 0x100, "record_capacity": 8, "record_stride": 0x20,
        "trampoline_address": trampoline_address,
        "resume_address": code_address + RESUME_OFFSET,
        "splice": {"offset": SPLICE_OFFSET, "expected_hex": SPLICE_BYTES.hex(),
                   "replacement_hex": code[SPLICE_OFFSET:RESUME_OFFSET].hex()},
        "external_relocations": [
            {"rva": rva, "kind": kind, "displacement_offset":
             rva - ENTRY_RVA + disp_offset, "target": game_base + target_rva}
            for rva, _hex, disp_offset, target_rva, kind in RELOCATIONS
        ],
        "reject_address": reject_address,
        "reject_reasons": {"1": "ordinal_outside_0_to_7",
                           "2": "roster_global_binding_mismatch"},
        "reject_state": {
            "rsp": "entry_rsp-38h; [rsp+20h] R15, +28h R14, +30h RDI, +40h RBX, +48h RBP, +50h RSI",
            "rbx": "zero-extended uint32 roster ordinal, or FFFFFFFF on map miss",
            "rbp": "original roster loaded from game_base+3326468; not yet sidecar-biased",
            "r14": "descriptor output array", "r15d": "zero",
            "rax": "reason 1: entity ID; reason 2: expected roster binding address",
            "r10d": "rejection reason",
            "memory": "prologue stack writes and entity/global/map reads only; no allocator, descriptor, count, output buffer or property write",
        },
        "entry_or_callsite_patch": None,
        "required_integration": [
            "Validate actual image and source bytes; allocate executable clone and sidecar storage",
            "Bind the current global-loaded roster incarnation to the same property sidecar as the receiver",
            "Validate entity/map pointers and capacity before this late guard, plus allocator and index-helper contracts",
            "Redirect every other producer, move/remove path and property consumer to the same sidecar",
            "Supply rejection continuation to restore this interior frame and abort the whole property stage",
            "Register valid Windows unwind metadata for the clone and trampoline",
            "Install/remove entry or callsite redirection under engine-safe execution control",
            "Verify original four-player and fifth-through-eighth-player mission lifecycle",
        ],
        "limits": [
            "Fixed saved bytes and supplied addresses only; no current allocation or lifetime proof",
            "Guard occurs after entity ID and map reads; invalid pointers may fault before rejection",
            "No default reject return or caller recovery is supplied",
            "Only this producer is redirected; it cannot be enabled separately from receiver and other consumers",
            "Offline instruction execution cannot prove Windows unwind, concurrent callbacks or gameplay",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    for name in ("game-base", "code-address", "roster-address",
                 "property-address", "reject-address"):
        parser.add_argument("--" + name, type=lambda s: int(s, 0), required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "refusing to overwrite output")
    result = build(load_source(args.evidence), game_base=args.game_base,
                   code_address=args.code_address,
                   roster_address=args.roster_address,
                   property_address=args.property_address,
                   reject_address=args.reject_address)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "status": result["status"],
                      "size_bytes": result["size_bytes"],
                      "code_sha256": result["code_sha256"]}))


if __name__ == "__main__":
    main()
