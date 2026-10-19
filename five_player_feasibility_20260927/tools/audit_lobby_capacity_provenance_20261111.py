"""Record callers and argument setup for the static lobby/memberCount helper."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct

import capstone


BUILD = 25480438
ROOT = Path(__file__).resolve().parents[2]
CAPTURE_DIR = ROOT / "evidence" / "existing-code-evidence-25480438"
CAPTURE_REPORT = CAPTURE_DIR / "capture-report.json"
CAPTURE_DATA = CAPTURE_DIR / "captured-data.bin"
IMAGE_BASE = 0x7FF814A30000
CODE_RVA = 0x1000
CODE_SIZE = 34667155
HELPER_RVA = 0x133AC30
WINDOW_BEFORE = 0x80
WINDOW_AFTER = 0x30


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_capture() -> tuple[bytearray, bytearray, dict]:
    report = json.loads(CAPTURE_REPORT.read_text(encoding="utf-8"))
    payload = CAPTURE_DATA.read_bytes()
    image = bytearray(report["image_size"])
    covered = bytearray(report["image_size"])
    for chunk in report["chunks"]:
        rva, size, offset = chunk["rva"], chunk["size"], chunk["file_offset"]
        image[rva:rva + size] = payload[offset:offset + size]
        covered[rva:rva + size] = b"\x01" * size
    return image, covered, report


def decode(image: bytearray, covered: bytearray, start: int, size: int) -> list[dict]:
    if not all(covered[start:start + size]):
        raise ValueError(f"uncovered range {start:#x}+{size:#x}")
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    return [
        {"rva": hex(ins.address - IMAGE_BASE), "bytes": ins.bytes.hex(),
         "asm": f"{ins.mnemonic} {ins.op_str}".strip()}
        for ins in md.disasm(bytes(image[start:start + size]), IMAGE_BASE + start)
    ]


def main() -> int:
    image, covered, capture_report = load_capture()
    callers = []
    for rva in range(CODE_RVA, CODE_RVA + CODE_SIZE - 5):
        if image[rva] != 0xE8 or not all(covered[rva:rva + 5]):
            continue
        target = rva + 5 + struct.unpack_from("<i", image, rva + 1)[0]
        if target != HELPER_RVA:
            continue
        start = max(CODE_RVA, rva - WINDOW_BEFORE)
        size = WINDOW_BEFORE + WINDOW_AFTER
        instructions = decode(image, covered, start, size)
        before = [row for row in instructions if int(row["rva"], 16) < rva]
        callers.append({
            "call_rva": hex(rva),
            "call_bytes": bytes(image[rva:rva + 5]).hex(),
            "window_sha256": hashlib.sha256(bytes(image[start:start + size])).hexdigest(),
            "preceding_instructions": before[-16:],
        })
    helper = bytes(image[HELPER_RVA:HELPER_RVA + 0x500])
    report = {
        "schema": "hd2_static_lobby_capacity_provenance_audit_v1",
        "build": BUILD,
        "audited_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_capture": {
            "capture_report": str(CAPTURE_REPORT),
            "capture_report_sha256": sha256(CAPTURE_REPORT),
            "capture_data": str(CAPTURE_DATA),
            "capture_data_sha256": sha256(CAPTURE_DATA),
            "capture_complete": capture_report["capture_complete"],
            "readable_complete": capture_report["readable_complete"],
            "runtime_verified": capture_report["runtime_verified"],
        },
        "read_only": True,
        "calls_made": False,
        "writes_made": False,
        "hooks_installed": False,
        "helper": {
            "rva": hex(HELPER_RVA),
            "code_window_size": 0x500,
            "code_sha256": hashlib.sha256(helper).hexdigest(),
            "direct_callers": callers,
        },
        "findings": {
            "direct_caller_count": len(callers),
            "multiple_state_update_callers_observed": len(callers) > 1,
            "capacity_helper_direct_game_session_binding_proven": False,
            "capacity_helper_party_or_steam_binding_proven": False,
            "argument_field_semantics_proven": False,
            "runtime_owner_lifetime_proven": False,
            "safe_to_patch": False,
        },
        "interpretation": [
            "The four-minus-field candidate is reached from several state-update callsites, so the helper has broader state/serialization provenance than a single UI constant.",
            "The saved code alone does not identify the object passed in RDX, the meaning of RBX+0x1c, or the indirect callee used to serialize lobby/memberCount.",
            "No caller is assigned Session create/join/leave/capacity semantics without runtime owner and return/state evidence.",
        ],
        "required_runtime_evidence": [
            "capture one caller's live state object and the value at [rbx+0x1c] during host creation and client join",
            "correlate the indirect serializer target with the GameSession and lobby/session identifiers",
            "observe changes through leave, migration and cleanup",
        ],
        "tool_path": str(Path(__file__).resolve()),
        "tool_sha256": sha256(Path(__file__)),
    }
    output = ROOT / "output" / "native_dispatch_20261010" / "static_lobby_capacity_provenance_audit_20261111.json"
    if output.exists():
        raise SystemExit(f"refusing to overwrite: {output}")
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "direct_callers": len(callers), "safe_to_patch": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
