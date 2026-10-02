"""Audit the fixed-build receive registration boundary.

This static replay records bounded registration shapes and the callback vector
for selector 168. It does not infer a runtime hash-to-selector mapping.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "research_handoff_20260927" / "indirect"))
from inspect_capture import EXPECTED, Image  # type: ignore

CAPTURE_DIR = HERE / "evidence" / "existing-code-evidence-25480438"
CAPTURE_SHA = "5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8"
TARGET_HASH = 0x4804FCF4
TARGET_RECEIVER = 0xBABA80
TARGET_TABLE = 0x214C2E0
TARGET_DISPATCH = 0xBC2D10
REG_CALL = bytes.fromhex("ff92b0000000")
STATIC_REGISTRATIONS = [
    (0x134D69E, 0xBDE53653),
    (0x134D6B4, 0x3E3F525A),
    (0x134D6CA, 0x5DCD723A),
    (0x134D6E0, 0x19339CD6),
    (0x134D6F6, 0x36334D22),
    (0x134D70C, 0x520227A4),
]
OTHER_STATIC_REGISTRATION = (0x14EE278, 0x068601A2)
DYNAMIC_REGISTRATION = 0x10946A4


def target_hits(im: Image, needle: bytes) -> list[dict]:
    hits: list[dict] = []
    for area in im.report["ranges"]:
        data = im.read(area["rva"], area["size"])
        start = 0
        while True:
            pos = data.find(needle, start)
            if pos < 0:
                break
            hits.append({"rva": hex(area["rva"] + pos), "range": area["label"], "bytes": needle.hex()})
            start = pos + 1
    return hits


def body_summary(im: Image, start: int, end: int, name: str) -> dict:
    raw = im.read(start, end - start)
    ins = list(im.md.disasm(raw, start))
    if sum(i.size for i in ins) != len(raw) or not ins or ins[-1].mnemonic != "ret":
        raise ValueError(f"{name} decode coverage mismatch")
    return {
        "name": name,
        "start_rva": hex(start),
        "end_rva_exclusive": hex(end),
        "size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "instructions": [{"rva": hex(i.address), "bytes": bytes(i.bytes).hex(), "asm": f"{i.mnemonic} {i.op_str}".rstrip()} for i in ins],
    }


def audit(evidence: Path) -> dict:
    im = Image(evidence)
    if im.report["capture_sha256"] != CAPTURE_SHA:
        raise ValueError("capture identity mismatch")
    static_rows: list[dict] = []
    for call_rva, value in STATIC_REGISTRATIONS:
        if im.read(call_rva, len(REG_CALL)) != REG_CALL:
            raise ValueError(f"registration call mismatch at {call_rva:#x}")
        hash_rva = call_rva - 9
        mov = im.read(hash_rva, 5)
        expected = b"\xb9" + struct.pack("<I", value)
        if mov != expected:
            raise ValueError(f"registration immediate mismatch at {hash_rva:#x}")
        static_rows.append({"call_rva": hex(call_rva), "call_bytes": REG_CALL.hex(), "hash_immediate_rva": hex(hash_rva), "hash": hex(value), "hash_little_endian": struct.pack("<I", value).hex(), "hash_instruction_bytes": mov.hex()})
    call_rva, value = OTHER_STATIC_REGISTRATION
    if im.read(call_rva, len(REG_CALL)) != REG_CALL:
        raise ValueError("secondary registration call mismatch")
    hash_rva = 0x14EE25B
    mov = im.read(hash_rva, 5)
    expected = b"\xb9" + struct.pack("<I", value)
    if mov != expected:
        raise ValueError("secondary registration immediate mismatch")
    static_rows.append({"call_rva": hex(call_rva), "call_bytes": REG_CALL.hex(), "hash_immediate_rva": hex(hash_rva), "hash": hex(value), "hash_little_endian": struct.pack("<I", value).hex(), "hash_instruction_bytes": mov.hex()})
    dynamic_call = im.read(DYNAMIC_REGISTRATION, len(REG_CALL))
    if dynamic_call != REG_CALL:
        raise ValueError("dynamic registration call mismatch")
    if b"\x89Q\x08" not in im.read(DYNAMIC_REGISTRATION - 0x14, 0x14 + len(REG_CALL)):
        raise ValueError("dynamic EDX storage shape missing")
    dispatch = im.read(TARGET_DISPATCH, 0x11)
    expected_dispatch = bytes.fromhex("418bc0498bd14c8d05c395580149ff24c0")
    if dispatch != expected_dispatch:
        raise ValueError("receive dispatch leaf mismatch")
    table = TARGET_DISPATCH + 13 + struct.unpack_from("<i", dispatch, 9)[0]
    if table != TARGET_TABLE:
        raise ValueError("callback table target mismatch")
    ptr = struct.unpack("<Q", im.read(TARGET_TABLE + 168 * 8, 8))[0]
    if ptr - im.base != TARGET_RECEIVER:
        raise ValueError("selector 168 receiver mismatch")
    hash_hits = target_hits(im, struct.pack("<I", TARGET_HASH))
    registration_body = body_summary(im, 0x1094680, 0x10946F4, "runtime_registration")
    destroy_body = body_summary(im, 0x1094710, 0x109477D, "runtime_unregistration")
    checks = [
        {"name": "static_registration_calls", "passed": True, "count": len(static_rows)},
        {"name": "dynamic_registration_shape", "passed": True, "call_rva": hex(DYNAMIC_REGISTRATION), "hash_source": "EDX argument stored at [RCX+8]"},
        {"name": "selector_168_callback_vector", "passed": True, "dispatch_rva": hex(TARGET_DISPATCH), "table_rva": hex(TARGET_TABLE), "entry": 168, "receiver_rva": hex(TARGET_RECEIVER)},
        {"name": "target_hash_occurrences", "passed": len(hash_hits) == 1, "hits": hash_hits, "expected_sender_only_rva": "0xbe4981"},
        {"name": "target_hash_in_static_registration_burst", "passed": hex(TARGET_HASH) not in [r["hash"] for r in static_rows], "registered_hashes": [r["hash"] for r in static_rows]},
    ]
    return {
        "schema": "hd2_receive_selector_registry_recovery_v1", "build": 25480438, "capture_sha256": CAPTURE_SHA, "source_sha256": EXPECTED,
        "read_only": True, "process_accessed": False, "game_memory_written": False, "hooks_installed": False,
        "target_event_hash": hex(TARGET_HASH), "selector": 168, "receiver_rva": hex(TARGET_RECEIVER),
        "static_registration_sites": static_rows,
        "dynamic_registration_site": {"rva": hex(DYNAMIC_REGISTRATION), "call_bytes": dynamic_call.hex(), "hash_source": "caller-supplied EDX stored at [RCX+8]"},
        "dynamic_registration_body": registration_body,
        "dynamic_unregistration_body": destroy_body,
        "target_hash_hits": hash_hits, "checks": checks,
        "hash_to_selector_proven": False, "service_registry_captured": False, "production_hook_ready": False,
        "installable": False, "multiplayer_verified": False,
        "limits": ["The capture has no writable service heap or network callback registry.", "Static [RDX+0xB0] sites prove a registration ABI shape, not ownership or runtime key contents.", "The dynamic registration site can receive a runtime hash/selector through EDX; no value is observed.", "The target event hash occurs only in the confirmed-peer sender in this bounded capture."],
        "next_required": "Capture the service-side registration/dispatch state or a runtime callback trace that supplies 0x4804FCF4 with selector 168.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, default=CAPTURE_DIR)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = audit(args.evidence)
    if args.write:
        if args.output.exists():
            raise SystemExit(f"refusing to overwrite output: {args.output}")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"schema": result["schema"], "static_sites": len(result["static_registration_sites"]), "target_hash_hits": len(result["target_hash_hits"]), "hash_to_selector_proven": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
