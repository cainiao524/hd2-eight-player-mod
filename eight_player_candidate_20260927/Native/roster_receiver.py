"""Build an offline x64 candidate for the fixed roster property receiver.

This module emits bytes. It neither allocates executable storage nor installs
hooks, queries processes, registers unwind data, or executes native code.
The explicit rejection continuation has an interior-frame ABI, not a normal
function ABI. A usable game integration must supply and verify that handler.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

EVIDENCE_SHA256 = "bad5661771df280dd5e982b765d2f4ab1c73de9ae7e86e974751af6c3c383c10"
SOURCE_SHA256 = "23d53b4f2f46ec26d23d79b958ee31d469910217ea843fb92bd98cf24c017411"
ENTRY_RVA, END_RVA = 0x60C890, 0x60C9BF
SENTINEL_RVA = 0x3483C20
SPLICE_OFFSET, RESUME_OFFSET = 0x60C932 - ENTRY_RVA, 0x60C938 - ENTRY_RVA
SPLICE_BYTES = bytes.fromhex("8b04298d5104")
PTR_END = 1 << 47
TARGET_PROFILE = {
    "build": 25480438,
    "exe_sha256": "f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06",
    "game_dll_sha256": "2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def load_source(evidence_path: Path) -> bytes:
    """Reconstruct the exact body from pinned, contiguous saved instructions."""
    raw = Path(evidence_path).read_bytes()
    require(sha(raw) == EVIDENCE_SHA256, "receiver evidence fingerprint mismatch")
    receiver = json.loads(raw)["receiver"]
    cursor, chunks = ENTRY_RVA, []
    for row in receiver["instructions"]:
        require(int(row["rva"], 16) == cursor, "receiver rows not contiguous")
        blob = bytes.fromhex(row["bytes"])
        require(sha(blob) == row["sha256"], "receiver instruction fingerprint mismatch")
        chunks.append(blob)
        cursor += len(blob)
    body = b"".join(chunks)
    require(cursor == END_RVA and sha(body) == SOURCE_SHA256, "receiver body mismatch")
    return body


def pointer(value: int, size: int, alignment: int, label: str) -> int:
    require(type(value) is int and value > 0 and value % alignment == 0,
            label + " must be a positive aligned integer")
    require(value + size <= PTR_END, label + " outside supported low canonical range")
    return value


def rel32(next_ip: int, target: int) -> bytes:
    delta = target - next_ip
    require(-(1 << 31) <= delta < (1 << 31), "relative displacement outside signed 32 bits")
    return struct.pack("<i", delta)


def overlaps(a: int, size: int, b: int, other_size: int) -> bool:
    return a < b + other_size and b < a + size


def build(source: bytes, *, game_base: int, code_address: int,
          roster_address: int, property_address: int, reject_address: int) -> dict:
    """Emit a bound eight-record receiver; all addresses are supplied inputs.

    Matching source bytes establish a fixed code profile only. Supplied bases
    do not prove that memory is allocated, writable/executable, current, or
    synchronized. No call-site or entry patch is emitted by this component.
    """
    require(type(source) is bytes and len(source) == END_RVA - ENTRY_RVA and
            sha(source) == SOURCE_SHA256, "receiver source fingerprint mismatch")
    pointer(game_base, SENTINEL_RVA + 4, 0x1000, "game_base")
    pointer(code_address, 1, 16, "code_address")
    pointer(roster_address, 0x428, 8, "roster_address")
    pointer(property_address, 8 * 0x20, 8, "property_address")
    require(property_address >= 0x3A8, "property address cannot encode biased base")
    pointer(reject_address, 1, 1, "reject_address")
    require(source[SPLICE_OFFSET:RESUME_OFFSET] == SPLICE_BYTES, "splice bytes changed")

    body = bytearray(source)
    # The original body has exactly one RIP-relative memory operand. Its
    # external sentinel remains in game.dll; retaining its old displacement
    # after cloning would read a different address.
    require(source[7:13] == bytes.fromhex("3b158373e702"), "RIP operand changed")
    body[9:13] = rel32(code_address + 13, game_base + SENTINEL_RVA)

    # The clone keeps all original instruction offsets, including internal
    # branch targets. Only the six-byte, instruction-aligned splice is replaced.
    trampoline_offset = (len(body) + 15) & ~15
    trampoline_address = code_address + trampoline_offset
    body[SPLICE_OFFSET:RESUME_OFFSET] = b"\xe9" + rel32(
        code_address + SPLICE_OFFSET + 5, trampoline_address) + b"\x90"
    body.extend(b"\xcc" * (trampoline_offset - len(body)))

    tail = bytearray()
    labels, fixups = {}, []

    def emit(blob: bytes) -> None:
        tail.extend(blob)

    def branch(opcode: bytes, target: str | int) -> None:
        tail.extend(opcode)
        fixups.append((len(tail), target))
        tail.extend(b"\0" * 4)

    # EAX is still the map ordinal at C932; R8 already holds ordinal*32.
    # The unsigned check rejects -1/missing and every ordinal outside 0..7.
    emit(b"\x83\xf8\x08")                         # cmp eax,8
    branch(b"\x0f\x83", "reject_ordinal")         # jae
    # RAX is dead after the ordinal check and is overwritten by the replayed
    # first DWORD load. Use it instead of changing another success-path GPR.
    emit(b"\x48\xb8" + struct.pack("<Q", roster_address))
    emit(b"\x49\x39\xc3")                       # cmp r11,rax
    branch(b"\x0f\x85", "reject_binding")         # jne
    emit(b"\x49\xbb" + struct.pack("<Q", property_address - 0x3A8))
    emit(SPLICE_BYTES)                             # original load; cursor+4
    branch(b"\xe9", code_address + RESUME_OFFSET)

    # A rejection transfers control before payload access or record/cursor
    # writes. Do not synthesize a successful return/skip: downstream property
    # parsing shares the cursor and requires an integration-specific abort.
    labels["reject_ordinal"] = trampoline_address + len(tail)
    emit(b"\x41\xba\x01\0\0\0")              # r10d = 1
    branch(b"\xe9", reject_address)
    labels["reject_binding"] = trampoline_address + len(tail)
    emit(b"\x41\xba\x02\0\0\0")              # r10d = 2
    branch(b"\xe9", reject_address)
    for offset, target in fixups:
        destination = labels[target] if isinstance(target, str) else target
        tail[offset:offset + 4] = rel32(trampoline_address + offset + 4, destination)
    body.extend(tail)
    pointer(code_address, len(body), 16, "complete code")

    regions = [
        ("candidate code", code_address, len(body)),
        ("roster", roster_address, 0x428),
        ("property sidecar", property_address, 0x100),
        ("sentinel", game_base + SENTINEL_RVA, 4),
        ("original receiver", game_base + ENTRY_RVA, len(source)),
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
        "rip_relocation": {"displacement_offset": 9, "target": game_base + SENTINEL_RVA},
        "reject_address": reject_address,
        "reject_reasons": {"1": "ordinal_outside_0_to_7", "2": "roster_binding_mismatch"},
        "reject_state": {
            "rsp": "entry_rsp-8; [rsp] saved R14; [rsp+28h] saved RBP",
            "r14": "cursor pointer", "rbp": "payload base", "r11": "input roster",
            "r8": "zero-extended uint32 ordinal * 32", "rcx": "uint32 entry cursor",
            "rax": "reason 1: uint32 ordinal; reason 2: expected roster binding address",
            "r10d": "rejection reason; original RBX/RSI/RDI already restored",
            "memory": "no payload read or record/cursor write by this receiver before rejection",
        },
        "entry_or_callsite_patch": None,
        "required_integration": [
            "Actual image fingerprint and source validation; allocate live code and sidecar storage",
            "Bind the current roster incarnation and redirect all other parallel-array consumers",
            "Valid map/header/payload/cursor and non-overlapping source/storage; shared lifetime and synchronization",
            "Provide rejection continuation that restores the interior frame and aborts this whole property dispatch",
            "Register valid Windows unwind metadata for clone and trampoline; original chained entries cannot be reused blindly",
            "Install/remove entry or callsite redirection under engine-safe execution control",
            "Verify original four-player behavior and fifth-through-eighth-player mission lifecycle",
        ],
        "limits": [
            "Fixed supplied bytes and supplied addresses only; no runtime origin/allocation/lifetime proof",
            "Only this receiver is redirected; it must not be enabled while producers and other consumers use old storage",
            "No safe continuation or return is supplied for rejection; caller cursor recovery is an unresolved integration requirement",
            "Emulator execution does not verify Windows unwinding, concurrent callbacks, native ABI callers or gameplay",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    for name in ("game-base", "code-address", "roster-address", "property-address", "reject-address"):
        parser.add_argument("--" + name, type=lambda s: int(s, 0), required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "refusing to overwrite output")
    result = build(load_source(args.evidence), game_base=args.game_base,
                   code_address=args.code_address, roster_address=args.roster_address,
                   property_address=args.property_address, reject_address=args.reject_address)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "status": result["status"],
                      "size_bytes": result["size_bytes"], "code_sha256": result["code_sha256"]}))


if __name__ == "__main__":
    main()
