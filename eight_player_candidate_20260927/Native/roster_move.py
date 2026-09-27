"""Emit an offline x64 candidate for the complete four-array roster move.

This emits bytes only. It does not allocate storage, install a hook, register
Windows unwind data, inspect a process, or execute native game code. The
required reject continuation receives an unchanged entry stack frame.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

EVIDENCE_SHA256 = "115802c09eb15f840932667717731150aa347e7ae8a72245dd92e05a5e86a242"
SOURCE_SHA256 = "b977816b8863034f0c247d0ee58779ab0f7d87cdb54eaa49ebfcdd5cab95434b"
ENTRY_RVA, END_RVA = 0x60C410, 0x60C5BE
GUARD_OFFSET, GUARD_RESUME = 0x60C419 - ENTRY_RVA, 0x60C41E - ENTRY_RVA
MAP_OFFSET, MAP_RESUME = 0x60C54A - ENTRY_RVA, 0x60C551 - ENTRY_RVA
GUARD_BYTES = bytes.fromhex("48895c2420")          # mov [rsp+20h],rbx
MAP_BYTES = bytes.fromhex("448b9bd8000000")       # mov r11d,[rbx+D8h]
PTR_END = 1 << 47
STORAGE_SIZE = 0x680
LAYOUT = {
    "pointer": {"offset": 0x000, "size": 0x040, "stride": 0x08},
    "primary": {"offset": 0x040, "size": 0x380, "stride": 0x70},
    "aux": {"offset": 0x3C0, "size": 0x1C0, "stride": 0x38},
    "property": {"offset": 0x580, "size": 0x100, "stride": 0x20},
}
TARGET_PROFILE = {
    "build": 25480438,
    "exe_sha256": "f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06",
    "game_dll_sha256": "2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e",
}
# (instruction RVA, terminal displacement offset, original displacement).
# The full fixed body/evidence fingerprints and each old disp32 are checked.
PRIMARY = (
    (0x60C44B, 5, 0x108), (0x60C463, 4, 0x108),
    (0x60C46B, 5, 0x118), (0x60C474, 4, 0x118),
    (0x60C47C, 5, 0x128), (0x60C485, 4, 0x128),
    (0x60C48D, 5, 0x138), (0x60C496, 4, 0x138),
    (0x60C49E, 5, 0x148), (0x60C4A7, 4, 0x148),
    (0x60C4AF, 5, 0x158), (0x60C4B8, 4, 0x158),
    (0x60C4C0, 5, 0x168), (0x60C4C9, 4, 0x168),
)
AUX = (
    (0x60C4D9, 4, 0x2C8), (0x60C4E5, 4, 0x2C8),
    (0x60C4ED, 4, 0x2D8), (0x60C4F5, 4, 0x2D8),
    (0x60C4FD, 4, 0x2E8), (0x60C505, 4, 0x2E8),
    (0x60C50D, 5, 0x2F8), (0x60C516, 5, 0x2F8),
)
PROPERTY = (
    (0x60C51F, 5, 0x3A8), (0x60C528, 5, 0x3A8),
    (0x60C531, 5, 0x3B8), (0x60C53A, 5, 0x3B8),
)
PATCH_GROUPS = (("primary", PRIMARY, 0x20),
                ("aux", AUX, 0x1E0),
                ("property", PROPERTY, 0x2C0))


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def load_source(evidence_path: Path) -> bytes:
    """Reconstruct the complete fixed mover from its pinned instruction rows."""
    raw = Path(evidence_path).read_bytes()
    require(sha(raw) == EVIDENCE_SHA256, "mover evidence fingerprint mismatch")
    move = json.loads(raw)["move"]
    require(int(move["entry"], 16) == ENTRY_RVA and
            int(move["end_exclusive"], 16) == END_RVA,
            "mover extent changed")
    cursor, chunks = ENTRY_RVA, []
    for row in move["instructions"]:
        require(int(row["rva"], 16) == cursor, "mover rows not contiguous")
        blob = bytes.fromhex(row["bytes"])
        require(sha(blob) == row["sha256"], "mover instruction fingerprint mismatch")
        chunks.append(blob)
        cursor += len(blob)
    body = b"".join(chunks)
    require(cursor == END_RVA and sha(body) == SOURCE_SHA256,
            "mover body fingerprint mismatch")
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
          roster_address: int, storage_address: int,
          reject_address: int) -> dict:
    """Emit one bound 8-slot mover; all addresses are supplied inputs.

    Matching fixed bytes does not prove that sidecar records, pointers or the
    original map are valid, initialized, synchronized or still alive.
    """
    require(type(source) is bytes and len(source) == END_RVA - ENTRY_RVA and
            sha(source) == SOURCE_SHA256, "mover source fingerprint mismatch")
    pointer(game_base, END_RVA, 0x1000, "game_base")
    pointer(code_address, 1, 16, "code_address")
    pointer(roster_address, 0x428, 8, "roster_address")
    pointer(storage_address, STORAGE_SIZE, 16, "storage_address")
    require(storage_address >= 0xE8, "storage address cannot encode pointer-array bias")
    pointer(reject_address, 1, 1, "reject_address")
    require(source[GUARD_OFFSET:GUARD_RESUME] == GUARD_BYTES,
            "entry guard splice changed")
    require(source[MAP_OFFSET:MAP_RESUME] == MAP_BYTES,
            "map restore splice changed")

    body = bytearray(source)
    patch_rows = []
    for group, sites, delta in PATCH_GROUPS:
        for rva, disp_offset, old in sites:
            at = rva - ENTRY_RVA + disp_offset
            require(source[at:at + 4] == struct.pack("<i", old),
                    "array displacement changed at " + hex(rva))
            new = old + delta
            body[at:at + 4] = struct.pack("<i", new)
            patch_rows.append({"rva": rva, "group": group,
                               "displacement_offset": at,
                               "original_displacement": old,
                               "new_displacement": new})
    require(len(patch_rows) == 26, "incomplete parallel-array rewrite")

    # Preserve the original equal-ordinal branch straight to its RET. Only
    # unequal ordinals reach C419. Both splice sites are whole instructions;
    # the 430-byte clone retains every original instruction offset/branch.
    trampoline_offset = (len(body) + 15) & ~15
    trampoline_address = code_address + trampoline_offset
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

    labels["entry_guard"] = trampoline_address + len(tail)
    emit(b"\x83\xfa\x08")                       # cmp edx,8 (destination)
    branch(b"\x0f\x83", "reject_destination")   # jae, unsigned
    emit(b"\x41\x83\xf8\x08")                 # cmp r8d,8 (source)
    branch(b"\x0f\x83", "reject_source")
    emit(b"\x48\xb8" + struct.pack("<Q", roster_address))
    emit(b"\x48\x39\xc1")                       # cmp rcx,rax
    branch(b"\x0f\x85", "reject_binding")
    emit(b"\x48\xb9" + struct.pack("<Q", storage_address - 0xE8))
    emit(GUARD_BYTES)                              # save original RBX
    branch(b"\xe9", code_address + GUARD_RESUME)

    # The guard runs before the first prologue write and before any array or
    # map access. Its rejection continuation receives entry RSP unchanged.
    for label, reason in (("reject_destination", 1),
                          ("reject_source", 2),
                          ("reject_binding", 3)):
        labels[label] = trampoline_address + len(tail)
        emit(b"\x41\xba" + struct.pack("<I", reason))  # r10d=reason
        branch(b"\xe9", reject_address)

    # C543 has just read the moved entity pointer from the new pointer slot.
    # Recover original S before the first map read at C54A, then retain the
    # entire original lookup/update and epilogue, including its failure risk.
    labels["map_restore"] = trampoline_address + len(tail)
    emit(b"\x48\xbb" + struct.pack("<Q", roster_address))
    emit(MAP_BYTES)
    branch(b"\xe9", code_address + MAP_RESUME)

    for offset, target in fixups:
        destination = labels[target] if isinstance(target, str) else target
        tail[offset:offset + 4] = rel32(trampoline_address + offset + 4,
                                        destination)
    body[GUARD_OFFSET:GUARD_RESUME] = b"\xe9" + rel32(
        code_address + GUARD_OFFSET + 5, labels["entry_guard"])
    body[MAP_OFFSET:MAP_RESUME] = b"\xe9" + rel32(
        code_address + MAP_OFFSET + 5, labels["map_restore"]) + b"\x90\x90"
    body.extend(tail)
    pointer(code_address, len(body), 16, "complete code")

    regions = [
        ("candidate code", code_address, len(body)),
        ("roster", roster_address, 0x428),
        ("four-array sidecar", storage_address, STORAGE_SIZE),
        ("original mover", game_base + ENTRY_RVA, len(source)),
        ("rejection continuation", reject_address, 1),
    ]
    for i, (name, first, size) in enumerate(regions):
        for other, second, length in regions[i + 1:]:
            require(not overlaps(first, size, second, length),
                    "known region overlap: " + name + " / " + other)
    code = bytes(body)
    property_address = storage_address + LAYOUT["property"]["offset"]
    return {
        "status": "offline_native_candidate", "installable": False,
        "game_execution": False, "multiplayer_verified": False,
        "target_profile": dict(TARGET_PROFILE),
        "source_sha256": sha(source), "evidence_sha256": EVIDENCE_SHA256,
        "code_sha256": sha(code), "code_hex": code.hex(),
        "game_base": game_base, "code_address": code_address,
        "entry_address": code_address, "size_bytes": len(code),
        "roster_address": roster_address, "storage_address": storage_address,
        "storage_size_bytes": STORAGE_SIZE, "layout": LAYOUT,
        "property_address": property_address, "property_size_bytes": 0x100,
        "record_capacity": 8,
        "pointer_stride": 8, "primary_stride": 0x70,
        "aux_stride": 0x38, "property_stride": 0x20,
        "same_ordinal_fast_return_retained": True,
        "displacement_patches": patch_rows,
        "external_relocations": [],
        "trampoline_address": trampoline_address,
        "entry_guard_splice": {"offset": GUARD_OFFSET,
                               "expected_hex": GUARD_BYTES.hex(),
                               "replacement_hex": code[GUARD_OFFSET:GUARD_RESUME].hex()},
        "map_restore_splice": {"offset": MAP_OFFSET,
                               "expected_hex": MAP_BYTES.hex(),
                               "replacement_hex": code[MAP_OFFSET:MAP_RESUME].hex()},
        "resume_addresses": {"entry_guard": code_address + GUARD_RESUME,
                             "map_restore": code_address + MAP_RESUME},
        "reject_address": reject_address,
        "reject_reasons": {"1": "destination_ordinal_outside_0_to_7",
                           "2": "source_ordinal_outside_0_to_7",
                           "3": "roster_binding_mismatch"},
        "reject_state": {
            "rsp": "original entry RSP; no prologue stack writes or nonvolatile changes",
            "rcx": "original roster pointer; unchanged on every reject",
            "edx": "destination ordinal (low 32 bits)",
            "r8d": "source ordinal (low 32 bits)",
            "r10d": "rejection reason; original R10 is volatile",
            "rax": "reasons 1/2: original input RAX; reason 3: expected roster binding address",
            "memory": "no array/map access or writes by the mover before rejection",
        },
        "entry_or_callsite_patch": None,
        "required_integration": [
            "Validate actual image/source and allocate live executable code plus initialized 0x680-byte sidecar",
            "Migrate and preserve active pointer, 0x70, 0x38 and property records; never infer empty records from zero bytes",
            "Use storage_address+580h as the property base for producer/receiver and all other readers/writers",
            "Keep original roster S, counts and map; require valid entity pointer and map entry for the moved destination",
            "Provide rejection continuation for unchanged entry frame and abort enclosing operation",
            "Register correct Windows unwind metadata for all original fragments and both trampolines",
            "Install/remove hook with engine-safe synchronization and shared sidecar lifetime",
            "Validate all other insertion/removal/classification paths before enabling eight slots",
        ],
        "limits": [
            "Unequal ordinal guard only; equal low-32-bit ordinals follow original direct RET without checking S or bounds",
            "Original map miss can lead to write at address 4 after copies; valid map membership is a precondition, not proven by guard",
            "Only this mover is redirected; sidecar address validity, initialization, aliases and lifetime are unproven",
            "Known-range collision checks are finite, not a full image or allocation map",
            "No native hook, Windows unwind, game execution or multiplayer validation",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    for name in ("game-base", "code-address", "roster-address",
                 "storage-address", "reject-address"):
        parser.add_argument("--" + name, type=lambda s: int(s, 0), required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "refusing to overwrite output")
    result = build(load_source(args.evidence), game_base=args.game_base,
                   code_address=args.code_address,
                   roster_address=args.roster_address,
                   storage_address=args.storage_address,
                   reject_address=args.reject_address)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "status": result["status"],
                      "size_bytes": result["size_bytes"],
                      "code_sha256": result["code_sha256"]}))


if __name__ == "__main__":
    main()
