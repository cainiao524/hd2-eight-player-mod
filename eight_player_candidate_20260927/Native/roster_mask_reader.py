"""Emit the offline 1277920 roster/mask reader candidate.

The source body is relocated from the pinned build.  The reader keeps the
original entity map, mask loop, ring operations and external calls, while the
two player-roster array reads are redirected to the shared four-array sidecar
used by the other offline candidates.  The guard runs before the original
input+10h timer write and does not reject an ordinary map miss.

This module only emits bytes.  It does not access a process, install a hook,
allocate native memory, or claim multiplayer compatibility.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


ENTRY, END = 0x1277920, 0x1277F7B
IMAGE_SIZE = 74727424
GLOBAL_RVA = 0x3326468
SOURCE_SHA256 = "aecf466c012f2e9ba64787a5108b1807753f55166b484d7a0c21c71a21e5d1ca"
EVIDENCE_SHA256 = ""  # filled from the pinned evidence file at load time
sha = lambda b: hashlib.sha256(b).hexdigest()


class EmitError(ValueError):
    pass


def require(ok: bool, message: str) -> None:
    if not ok:
        raise EmitError(message)


def pointer(address: int, size: int, alignment: int, name: str) -> None:
    require(isinstance(address, int) and address >= 0, f"invalid {name}")
    require(address % alignment == 0, f"{name} is not aligned")
    require(address + size < (1 << 64), f"{name} overflows")


def rel32(source_after: int, target: int) -> bytes:
    delta = target - source_after
    require(-(1 << 31) <= delta < (1 << 31), "rel32 target out of range")
    return struct.pack("<i", delta)


def overlaps(a: int, asize: int, b: int, bsize: int) -> bool:
    return a < b + bsize and b < a + asize


class Code:
    def __init__(self, base: int):
        self.base = base
        self.data = bytearray()
        self.labels: dict[str, int] = {}
        self.fixups: list[tuple[int, str | int]] = []

    def emit(self, blob: bytes) -> None:
        self.data.extend(blob)

    def label(self, name: str) -> None:
        require(name not in self.labels, f"duplicate label {name}")
        self.labels[name] = self.base + len(self.data)

    def branch(self, opcode: bytes, target: str | int) -> None:
        self.emit(opcode)
        self.fixups.append((len(self.data), target))
        self.emit(b"\0" * 4)

    def finish(self) -> bytes:
        for offset, target in self.fixups:
            destination = self.labels[target] if isinstance(target, str) else target
            self.data[offset:offset + 4] = rel32(self.base + offset + 4, destination)
        return bytes(self.data)


def load_source(path: Path) -> tuple[bytes, dict]:
    raw = path.read_bytes()
    global EVIDENCE_SHA256
    EVIDENCE_SHA256 = sha(raw)
    evidence = json.loads(raw)
    body = evidence["body"]
    blob = bytes.fromhex(body["bytes_hex"])
    require(body["entry"] == hex(ENTRY) and body["end_exclusive"] == hex(END),
            "reader evidence range changed")
    require(len(blob) == END - ENTRY and sha(blob) == SOURCE_SHA256,
            "reader body fingerprint mismatch")
    return blob, evidence


def _instruction_rows(evidence: dict) -> list[dict]:
    rows = evidence["body"]["instructions"]
    require(rows and int(rows[0]["rva"], 16) == ENTRY, "missing reader instructions")
    expected = ENTRY
    for row in rows:
        require(int(row["rva"], 16) == expected, "reader instruction boundary changed")
        expected += len(bytes.fromhex(row["bytes"]))
    require(expected == END, "reader instruction coverage changed")
    return rows


def _emit_guard(c: Code, *, game_base: int, roster_address: int,
                reject_address: int) -> None:
    """Guard immediately before the first input dereference.

    The body has already created its normal frame and stack-cookie slot.  The
    guard uses only R10/R11, leaving caller arguments, XMM values and the
    original cookie state untouched.  Ordinary entity-map misses are handled by
    the original body and never reach this rejection path.
    """
    # The body normally fills these slots later.  A guard can reject before
    # those stores, so seed the same slots first and let the reject epilogue
    # restore the caller's nonvolatile registers and RCX from them.
    c.emit(b"\x48\x89\x4c\x24\x30")                 # [RSP+30]=original RCX
    c.emit(b"\x4c\x89\xa4\x24\x70\x01\x00\x00")   # [RSP+170]=R12
    c.emit(b"\x4c\x89\xac\x24\x78\x01\x00\x00")   # [RSP+178]=R13
    c.emit(b"\x48\x89\x9c\x24\x80\x01\x00\x00")   # [RSP+180]=RBX
    c.emit(b"\x49\xba" + struct.pack("<Q", game_base + GLOBAL_RVA))  # R10=global S pointer
    c.emit(b"\x4d\x8b\x1a")                         # R11=[R10]
    c.emit(b"\x49\xba" + struct.pack("<Q", roster_address))
    c.emit(b"\x4d\x3b\xda")                         # R11 == expected S
    c.branch(b"\x0f\x85", "reject_binding")
    c.emit(b"\x48\x85\xd2")                         # input record must exist
    c.branch(b"\x0f\x84", "reject_input")


def _emit_reject(c: Code, reason: int, reject_address: int) -> None:
    """Restore the original frame and tail-jump to the explicit reject hook."""
    c.emit(b"\x41\xba" + struct.pack("<I", reason))  # R10D=reason
    c.emit(b"\xb8\xff\xff\xff\xff")                # RAX=-1 result marker
    # Run the captured cookie helper with the original cookie value.  The
    # helper's volatile clobbers are not part of the reject ABI, so reason and
    # return value are restored after it returns.
    c.emit(b"\x48\x8b\x8c\x24\x30\x01\x00\x00")     # RCX=[RSP+130]
    c.emit(b"\x48\x33\xcc")                         # RCX ^= RSP
    c.emit(b"\xe8\0\0\0\0")
    # The zero-displacement marker is replaced by build() with the captured
    # cookie helper address.
    c.emit(b"\x41\xba" + struct.pack("<I", reason))
    c.emit(b"\xb8\xff\xff\xff\xff")
    c.emit(b"\x48\x8b\x4c\x24\x30")                 # restore original RCX
    c.emit(b"\x4c\x8b\xa4\x24\x70\x01\x00\x00")   # R12
    c.emit(b"\x4c\x8b\xac\x24\x78\x01\x00\x00")   # R13
    c.emit(b"\x48\x8b\x9c\x24\x80\x01\x00\x00")   # RBX
    c.emit(b"\x48\x81\xc4\x40\x01\x00\x00")
    c.emit(b"\x41\x5f\x41\x5e\x5f\x5e\x5d")
    c.emit(b"\xe9" + rel32(c.base + len(c.data) + 5, reject_address))


def _relocate_rip(raw: bytes, old: int, emitted: int, target: int,
                  game_base: int, displacement_offset: int,
                  displacement_size: int) -> bytes:
    out = bytearray(raw)
    require(displacement_size == 4, "unsupported RIP displacement size")
    require(0 <= displacement_offset <= len(raw) - displacement_size,
            "invalid RIP displacement offset")
    original = struct.unpack_from("<i", raw, displacement_offset)[0]
    require(old + len(raw) + original == target,
            "source RIP relocation metadata mismatch")
    out[displacement_offset:displacement_offset + displacement_size] = rel32(
        emitted + len(raw), game_base + target)
    return bytes(out)


def build(source: bytes, evidence: dict, *, game_base: int, code_address: int,
          roster_address: int, storage_address: int, reject_address: int,
          cookie_helper_address: int = 0) -> dict:
    require(type(source) is bytes and len(source) == END - ENTRY and sha(source) == SOURCE_SHA256,
            "reader source fingerprint mismatch")
    pointer(game_base, IMAGE_SIZE, 0x1000, "game_base")
    pointer(code_address, 1, 16, "code_address")
    pointer(roster_address, 0x428, 8, "roster_address")
    pointer(storage_address, 0x680, 16, "storage_address")
    pointer(reject_address, 1, 1, "reject_address")
    require(storage_address >= 0x1D8, "storage cannot encode primary/property bias")
    rows = _instruction_rows(evidence)
    c = Code(code_address)
    mapping: dict[int, int] = {}
    relocations: list[dict] = []
    patches: list[dict] = []
    rip_by_rva = {int(item["rva"], 16): item
                  for item in evidence["body"].get("rip_relocations", [])}
    guard_at = 0x1277945
    # The original body calls this helper during its cookie epilogue.  A zero
    # address is accepted only for plans that intentionally route to a local
    # return stub; normal builds must provide the captured image address.
    if cookie_helper_address == 0:
        cookie_helper_address = game_base + 0x2088770

    for row in rows:
        old = int(row["rva"], 16)
        raw = bytes.fromhex(row["bytes"])
        mapping[old] = c.base + len(c.data)
        c.label(hex(old))
        if old == guard_at:
            _emit_guard(c, game_base=game_base, roster_address=roster_address,
                        reject_address=reject_address)
        # The two player-roster reads must use the shared B sidecar.  The bias
        # keeps the original instruction encoding and changes only R11's base.
        # The original operands are +0x12c and +0x3b4.  Their common-B
        # destinations are +0x64 and +0x58c respectively, so the second
        # replacement uses the positive 0x1d8 bias (0x3b4 + 0x1d8 = 0x58c).
        bias = {0x12779F5: -0xC8, 0x1277A06: 0x1D8}.get(old)
        if bias is not None:
            replacement = b"\x49\xbb" + struct.pack("<Q", storage_address + bias) + raw
            c.emit(replacement)
            patches.append({"original_rva": hex(old), "group": "primary" if old == 0x12779F5 else "property",
                            "original_hex": raw.hex(), "replacement_hex": replacement.hex(),
                            "storage_bias": bias, "destination": "B+0x64+ordinal*0x70" if old == 0x12779F5 else "B+0x58c+ordinal*0x20"})
            continue
        target = None
        # Relative branches/calls are relocated from the saved original RVA.
        if raw[0] in (0x70, 0x71, 0x72, 0x73, 0x74, 0x75, 0x76, 0x77,
                      0x78, 0x79, 0x7A, 0x7B, 0x7C, 0x7D, 0x7E, 0x7F):
            target = old + len(raw) + struct.unpack("<b", raw[1:2])[0]
            require(ENTRY <= target < END, "conditional branch leaves reader body")
            c.branch(bytes((0x0F, raw[0] + 0x10)), hex(target))
            relocations.append({"original_rva": hex(old), "kind": "local_conditional", "target_rva": hex(target)})
        elif len(raw) == 6 and raw[0] == 0x0F and 0x80 <= raw[1] <= 0x8F:
            target = old + len(raw) + struct.unpack("<i", raw[2:])[0]
            require(ENTRY <= target < END, "near conditional branch leaves reader body")
            c.branch(raw[:2], hex(target))
            relocations.append({"original_rva": hex(old), "kind": "local_conditional", "target_rva": hex(target)})
        elif raw[:1] == b"\xeb":
            target = old + len(raw) + struct.unpack("<b", raw[1:2])[0]
            require(ENTRY <= target < END, "short jump leaves reader body")
            c.branch(b"\xe9", hex(target))
            relocations.append({"original_rva": hex(old), "kind": "local_jump", "target_rva": hex(target)})
        elif raw[:1] in (b"\xe8", b"\xe9"):
            target = old + len(raw) + struct.unpack("<i", raw[1:])[0]
            if raw[0] == 0xE9:
                require(ENTRY <= target < END, "reader jump target leaves body")
                c.branch(b"\xe9", hex(target))
                relocations.append({"original_rva": hex(old), "kind": "local_jump", "target_rva": hex(target)})
            else:
                blob = bytearray(raw)
                blob[1:5] = rel32(c.base + len(c.data) + len(raw), game_base + target)
                c.emit(bytes(blob))
                relocations.append({"original_rva": hex(old), "kind": "call", "target_rva": hex(target), "target_address": hex(game_base + target)})
        else:
            # Relocate every RIP memory operand using evidence metadata.  The
            # source row may have more than one textual operand but at most one
            # RIP displacement in this body.
            rip_row = rip_by_rva.get(old)
            if rip_row is not None:
                target_rva = int(rip_row["target_rva"], 16)
                c.emit(_relocate_rip(raw, old, c.base + len(c.data), target_rva,
                                     game_base, int(rip_row["displacement_offset"]),
                                     int(rip_row["displacement_size"])))
                relocations.append({"original_rva": hex(old), "kind": "rip_memory", "target_rva": hex(target_rva),
                                    "displacement_offset": int(rip_row["displacement_offset"]),
                                    "displacement_size": int(rip_row["displacement_size"])})
            else:
                c.emit(raw)
    # The guard labels are appended after the full body so all normal local
    # branches continue to use the original body map.
    c.label("reject_binding")
    _emit_reject(c, 1, reject_address)
    c.label("reject_input")
    _emit_reject(c, 2, reject_address)
    # Replace the two cookie-call placeholders emitted by _emit_reject.
    code = bytearray(c.finish())
    # Locate exactly two fixed markers emitted by the two reject paths.
    needle = b"\xe8\0\0\0\0"
    positions = []
    start = 0
    while True:
        pos = code.find(needle, start)
        if pos < 0:
            break
        positions.append(pos)
        start = pos + 1
    require(len(positions) == 2, "reject cookie call placeholders missing")
    for pos in positions:
        code[pos:pos + 5] = b"\xe8" + rel32(c.base + pos + 5, cookie_helper_address)
    code = bytes(code)
    pointer(code_address, len(code), 16, "complete reader code")
    regions = [
        {"name": "reader code", "address": code_address, "size_bytes": len(code)},
        {"name": "reader reject", "address": reject_address, "size_bytes": 1},
        {"name": "original roster", "address": roster_address, "size_bytes": 0x428},
        {"name": "four-array sidecar", "address": storage_address, "size_bytes": 0x680},
        {"name": "game image", "address": game_base, "size_bytes": IMAGE_SIZE},
    ]
    for i, a in enumerate(regions):
        for b in regions[i + 1:]:
            require(not overlaps(a["address"], a["size_bytes"], b["address"], b["size_bytes"]),
                    f"known region overlap: {a['name']} / {b['name']}")
    return {
        "status": "offline_native_roster_mask_reader_candidate",
        "installable": False, "game_execution": False, "multiplayer_verified": False,
        "game_base": game_base, "code_address": code_address, "entry_address": code_address,
        "body_address": mapping[ENTRY], "size_bytes": len(code), "code_hex": code.hex(),
        "code_sha256": sha(code), "source_sha256": SOURCE_SHA256, "evidence_sha256": EVIDENCE_SHA256,
        "roster_address": roster_address, "storage_address": storage_address,
        "storage_size_bytes": 0x680, "reject_address": reject_address,
        "array_patches": patches, "relocations": relocations,
        "instruction_address_map": {hex(k): v for k, v in mapping.items()},
        "guard_addresses": {k: v for k, v in c.labels.items() if k.startswith("reject_")},
        "reject_reasons": {"1": "global_roster_binding_mismatch", "2": "null_input_record"},
        "reject_state": {"reason_register": "R10D", "result_register": "RAX=-1",
                         "ordinary_missing": "preserved by original map lookup and fallback stores",
                         "nonstack_writes": "none before rejection; cookie helper and external handler are contracts"},
        "known_regions": regions,
        "caller_contract": {"entry": "0x128495c", "rcx": "original context", "rdx": "input record",
                             "xmm2": "caller timestep input", "helper_927050": "captured full map/status helper",
                             "opaque_calls": ["0x127ba30", "0x836570", "0x127cad0", "0x1327f50", "0x2088770", "indirect virtual call"]},
        "limits": [
            "Fixed-build offline bytes only; no hook, allocator, installation or process access",
            "The two roster reads use common B; all other global/ring sources remain original",
            "Ordinary entity-map missing keeps the original input+4/input+8 fallback",
            "Empty keys and out-of-range ordinals are not newly rejected; B sidecar bounds remain an external precondition",
            "Reject handler, ring/resource callbacks, reentrancy, unwind integration and storage lifetime remain external contracts",
            "Mask producer and network-index population are not modified or validated",
            "No multiplayer or mission acceptance is claimed",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--addresses", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "refusing to overwrite output")
    source, evidence = load_source(args.evidence)
    addresses = json.loads(args.addresses.read_bytes())
    result = build(source, evidence, **addresses)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("status", "size_bytes", "code_sha256")}))


if __name__ == "__main__":
    main()
