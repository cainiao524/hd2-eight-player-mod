"""Audit static four-member candidates in the saved game.dll code capture.

The capture is file-backed and was collected previously without calls or
writes.  This audit only decodes bounded instructions around known string
references; it does not assign a capacity meaning to a constant unless the
runtime owner, field semantics, and host/client behavior are also proven.
"""

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
LOBBY_XREFS = ROOT / "five_player_feasibility_20260927" / "lobby_string_xrefs.json"

IMAGE_BASE = 0x7FF814A30000
LOBBY_MEMBER_COUNT_RVA = 0x22C9B38
NUM_LOBBY_MEMBERS_RVA = 0x2260D90
WINDOW_BEFORE = 0x100
WINDOW_AFTER = 0x180


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reconstruct() -> tuple[bytearray, bytearray, dict]:
    report = json.loads(CAPTURE_REPORT.read_text(encoding="utf-8"))
    payload = CAPTURE_DATA.read_bytes()
    image = bytearray(report["image_size"])
    covered = bytearray(report["image_size"])
    for chunk in report["chunks"]:
        rva = chunk["rva"]
        size = chunk["size"]
        offset = chunk["file_offset"]
        image[rva:rva + size] = payload[offset:offset + size]
        covered[rva:rva + size] = b"\x01" * size
    return image, covered, report


def slice_bytes(image: bytearray, covered: bytearray, start: int, size: int) -> bytes:
    if start < 0 or start + size > len(image) or not all(covered[start:start + size]):
        raise ValueError(f"uncovered capture range: {start:#x}+{size:#x}")
    return bytes(image[start:start + size])


def target_from_rip(ins: capstone.CsInsn) -> int | None:
    if ins.mnemonic != "lea" or len(ins.operands) < 2:
        return None
    operand = ins.operands[1]
    if operand.type != capstone.x86.X86_OP_MEM or operand.mem.base != capstone.x86.X86_REG_RIP:
        return None
    return (ins.address - IMAGE_BASE) + ins.size + operand.mem.disp


def decode_site(image: bytearray, covered: bytearray, xref_rva: int,
                target_rva: int) -> dict:
    start = max(0, xref_rva - WINDOW_BEFORE)
    size = WINDOW_BEFORE + WINDOW_AFTER
    code = slice_bytes(image, covered, start, size)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    instructions = list(md.disasm(code, IMAGE_BASE + start))
    rows = []
    for ins in instructions:
        rva = ins.address - IMAGE_BASE
        if rva < xref_rva - 0x60 or rva > xref_rva + 0x100:
            continue
        rows.append({
            "rva": hex(rva),
            "bytes": ins.bytes.hex(),
            "asm": f"{ins.mnemonic} {ins.op_str}".strip(),
        })
    target_matches = [ins for ins in instructions if target_from_rip(ins) == target_rva]
    four_minus_field = []
    bounded_four = []
    for index, ins in enumerate(instructions):
        if ins.mnemonic == "mov" and ins.op_str == "r8d, 4":
            following = instructions[index + 1:index + 12]
            for next_ins in following:
                if next_ins.mnemonic == "sub" and next_ins.op_str == "r8d, dword ptr [rbx + 0x1c]":
                    four_minus_field.append({
                        "mov_rva": hex(ins.address - IMAGE_BASE),
                        "sub_rva": hex(next_ins.address - IMAGE_BASE),
                        "mov_bytes": ins.bytes.hex(),
                        "sub_bytes": next_ins.bytes.hex(),
                        "formula_candidate": "r8d = 4 - dword ptr [rbx+0x1c]",
                    })
        if ins.mnemonic == "cmp" and ins.op_str.endswith(", 4"):
            bounded_four.append({"rva": hex(ins.address - IMAGE_BASE), "bytes": ins.bytes.hex(), "asm": ins.op_str})
    return {
        "xref_rva": hex(xref_rva),
        "target_rva": hex(target_rva),
        "target_lea_matches": [{"rva": hex(ins.address - IMAGE_BASE), "bytes": ins.bytes.hex(), "asm": ins.op_str} for ins in target_matches],
        "four_minus_field_candidates": four_minus_field,
        "compare_four_candidates": bounded_four,
        "bounded_instructions": rows,
        "window_sha256": hashlib.sha256(code).hexdigest(),
    }


def main() -> int:
    image, covered, capture_report = reconstruct()
    xrefs = json.loads(LOBBY_XREFS.read_text(encoding="utf-8"))
    target_rows = xrefs["targets"]
    lobby_row = target_rows[hex(LOBBY_MEMBER_COUNT_RVA)]
    num_row = target_rows[hex(NUM_LOBBY_MEMBERS_RVA)]
    lobby_sites = [decode_site(image, covered, int(row["rva"], 16), LOBBY_MEMBER_COUNT_RVA)
                   for row in lobby_row["rip_references"]]
    num_sites = [decode_site(image, covered, int(row["rva"], 16), NUM_LOBBY_MEMBERS_RVA)
                 for row in num_row["rip_references"]]
    formula_sites = [row for row in lobby_sites if row["four_minus_field_candidates"]]
    compare_sites = [row for row in num_sites if row["compare_four_candidates"]]
    report = {
        "schema": "hd2_static_lobby_capacity_constant_audit_v1",
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
        "targets": {
            "lobby_member_count": {
                "rva": hex(LOBBY_MEMBER_COUNT_RVA),
                "known_text": "%s/lobby/memberCount",
                "xref_sites": lobby_sites,
            },
            "num_lobby_members": {
                "rva": hex(NUM_LOBBY_MEMBERS_RVA),
                "known_text": "numLobbyMembers",
                "xref_sites": num_sites,
            },
        },
        "findings": {
            "lobby_member_count_four_minus_field_observed": bool(formula_sites),
            "lobby_member_count_formula_site_count": len(formula_sites),
            "num_lobby_members_compare_four_observed": bool(compare_sites),
            "num_lobby_members_compare_four_site_count": len(compare_sites),
            "static_four_candidate_repeats_across_paths": bool(formula_sites and compare_sites),
            "capacity_gate_semantics_proven": False,
            "field_rbx_plus_1c_semantics_proven": False,
            "host_client_admission_proven": False,
            "safe_to_patch_constant": False,
            "eight_player_mod_proven": False,
        },
        "interpretation": [
            "The saved game.dll capture contains a lobby/memberCount path that computes a candidate value as 4 minus dword [rbx+0x1c].",
            "A separate numLobbyMembers path contains a compare-to-4 candidate.",
            "These are static serialization/parser candidates; they do not prove that either value is the authoritative Session capacity or that changing it admits peers.",
            "The owner object, field lifetime, return ABI, server acceptance, player creation, replication and cleanup remain unbound.",
        ],
        "required_runtime_evidence": [
            "capture the owning object and [rbx+0x1c] value in an actual host room and across a client join",
            "correlate the same field with GameSession peer_count and lobby/session identifiers",
            "observe whether the value changes on leave, migration and cleanup",
            "only after that, test a fail-closed candidate patch in host+client before 5-8 clients",
        ],
        "tool_path": str(Path(__file__).resolve()),
        "tool_sha256": sha256(Path(__file__)),
    }
    output = ROOT / "output" / "native_dispatch_20261010" / "static_lobby_capacity_constant_audit_20261111.json"
    if output.exists():
        raise SystemExit(f"refusing to overwrite: {output}")
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "formula_sites": len(formula_sites), "compare_sites": len(compare_sites), "safe_to_patch_constant": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
