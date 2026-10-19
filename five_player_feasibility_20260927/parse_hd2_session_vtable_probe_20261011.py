"""Parse the HD2Scanner runtime vtable/object probe into a read-only receipt.

The capture contains internal C++ virtual slots.  The generic public SDK names
are deliberately not copied into this receipt because the saved machine code
does not establish that correspondence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

import capstone
import pefile


BUILD = 25480438
EXPECTED_EXE_SHA256 = "f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06"
DEFAULT_LOG = Path(__file__).parents[1] / "output/native_dispatch_20261010/hd2_session_vtable_probe_20261011.log"
DEFAULT_PREVIOUS = Path(__file__).with_name("live_engine_session_vtable_20261003.json")
DEFAULT_EXE = Path(r"F:\Game\Steam\steamapps\common\Helldivers 2\bin\helldivers2.exe")
EXE_IMAGE_SIZE = 0x39E8000


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def disassemble(code: bytes, address: int) -> list[dict]:
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    return [
        {"rva": hex(ins.address - address), "bytes": ins.bytes.hex(), "asm": f"{ins.mnemonic} {ins.op_str}".strip()}
        for ins in decoder.disasm(code, address)
    ]


def parse_section(log_text: str) -> tuple[str, list[str]]:
    sections = re.split(r"(?=^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d START )", log_text, flags=re.MULTILINE)
    starts = [section for section in sections if re.search(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d START ", section, re.MULTILINE)]
    if not starts:
        raise SystemExit("probe_start_missing")
    # Never fall back to an older successful run.  A current incomplete run is
    # evidence of an incomplete capture and must fail closed.
    section = starts[-1]
    if "VTABLE_DONE" not in section or "OBJECT_DONE" not in section:
        raise SystemExit("latest_probe_section_incomplete")
    return section, [line for line in section.splitlines() if line]


def build_receipt(log_path: Path, previous_path: Path, exe_path: Path) -> dict:
    log_bytes = log_path.read_bytes()
    section, lines = parse_section(log_bytes.decode("utf-8"))
    request = re.search(r"REQUEST id=([^ ]+) game_base=0x([0-9A-Fa-f]+)", section)
    vtable = re.search(r"VTABLE base=0x([0-9A-Fa-f]+) slots=(\d+) game_base=0x([0-9A-Fa-f]+)", section)
    object_hits = list(re.finditer(r"OBJECT_HITS(?: run=(\d+))? count=(\d+) vtable=0x([0-9A-Fa-f]+)", section))
    object_rows = list(re.finditer(
        r"OBJECT occurrence=(\d+) pointer_at=0x([0-9A-Fa-f]+) object_candidate=0x([0-9A-Fa-f]+) context=([0-9A-Fa-f]+)",
        section,
    ))
    if not request or not vtable or not object_hits or not object_rows:
        raise SystemExit("probe_receipt_fields_missing")
    object_hit = object_hits[-1]
    object_row = object_rows[-1]
    game_base = int(request.group(2), 16)
    vtable_address = int(vtable.group(1), 16)
    slot_count = int(vtable.group(2))
    vtable_game_base = int(vtable.group(3), 16)
    if game_base != vtable_game_base:
        raise SystemExit("vtable_game_base_field_mismatch")
    if not game_base or not game_base <= vtable_address < game_base + EXE_IMAGE_SIZE:
        raise SystemExit("vtable_outside_exe_image")
    if slot_count != 42:
        raise SystemExit("unexpected_vtable_slot_count")

    previous = json.loads(previous_path.read_text(encoding="utf-8"))
    previous_rows = {int(row["slot"], 16): bytes.fromhex(row["bytes"]) for row in previous["rows"]}
    exe_bytes = exe_path.read_bytes()
    exe_sha = sha256(exe_bytes)
    if exe_sha != EXPECTED_EXE_SHA256:
        raise SystemExit(f"executable_sha256_mismatch:{exe_sha}")
    pe = pefile.PE(data=exe_bytes, fast_load=True)
    capture_rows = []
    code_pattern = re.compile(r"CODE slot=0x([0-9A-Fa-f]+) role=([^ ]+) target=0x([0-9A-Fa-f]+) rva=0x([0-9A-Fa-f]+) bytes=([0-9A-Fa-f]+)")
    for line in lines:
        match = code_pattern.search(line)
        if not match:
            continue
        slot = int(match.group(1), 16)
        target = int(match.group(3), 16)
        rva = int(match.group(4), 16)
        code = bytes.fromhex(match.group(5))
        if slot % 8 or slot >= slot_count * 8 or target != game_base + rva:
            raise SystemExit("invalid_runtime_code_identity")
        if len(code) != 128 or not code:
            raise SystemExit("runtime_code_window_not_128_bytes")
        disk_code = pe.get_data(rva, len(code))
        capture_rows.append(
            {
                "slot": hex(slot),
                "probe_label_unverified": match.group(2),
                "semantic_name": None,
                "target": hex(target),
                "rva": hex(rva),
                "code_bytes": len(code),
                "code_sha256": sha256(code),
                "instructions": disassemble(code, target),
                "matches_previous_live_capture": previous_rows.get(slot) == code if slot in previous_rows else None,
                "matches_on_disk_image": disk_code == code,
                "semantic_claim": False,
            }
        )

    if len(capture_rows) != 9 or len({row["slot"] for row in capture_rows}) != 9:
        raise SystemExit("runtime_code_slot_set_incomplete")

    context = bytes.fromhex(object_row.group(4))
    if len(context) < 40:
        raise SystemExit("object_context_too_short")
    object_address = int(object_row.group(3), 16)
    object_bytes = context[32:]
    first_qword = int.from_bytes(object_bytes[:8], "little")
    u32 = lambda offset: int.from_bytes(object_bytes[offset : offset + 4], "little")
    u64 = lambda offset: int.from_bytes(object_bytes[offset : offset + 8], "little")
    count_0x138 = u32(0x138)
    array_0x140 = u64(0x140)
    return {
        "schema": "hd2_live_session_vtable_and_object_probe_v2",
        "build": BUILD,
        "probe": {
            "log_path": str(log_path),
            "log_sha256": sha256(log_bytes),
            "request_id": request.group(1),
            "game_base": hex(game_base),
            "vtable": hex(vtable_address),
            "vtable_slots": slot_count,
            "object_pointer_hits": int(object_hit.group(2)),
            "object_scan_runs": len(object_hits),
            "candidate_filter": "only complete vtable matches inside helldivers2.exe image",
            "semantic_slot_names": "withheld_until_callsite_and_return_contract_are_proven",
            "read_only": True,
            "calls_made": False,
            "writes_made": False,
            "hooks_installed": False,
        },
        "session_object_candidate": {
            "address": hex(object_address),
            "pointer_occurrence_address": hex(int(object_row.group(2), 16)),
            "read_start": hex(object_address - 32),
            "context_bytes": len(context),
            "object_window_bytes": len(object_bytes),
            "first_qword": hex(first_qword),
            "first_qword_matches_vtable": first_qword == vtable_address,
            "stable_reread": False,
            "semantic_decode": False,
            "bytes_sha256": sha256(object_bytes),
            "structural_fields": {
                "dword_0x138": count_0x138,
                "dword_0x13c": u32(0x13C),
                "qword_0x140": hex(array_0x140),
                "qword_0x148": hex(u64(0x148)),
                "count_nonzero": count_0x138 != 0,
                "array_pointer_nonzero": array_0x140 != 0,
            },
        },
        "runtime_methods": capture_rows,
        "identity": {
            "executable_path": str(exe_path),
            "executable_sha256": exe_sha,
            "previous_vtable_capture_path": str(previous_path),
            "previous_vtable_capture_sha256": sha256(previous_path.read_bytes()),
            "live_code_windows_match_previous": all(
                row["matches_previous_live_capture"] is True for row in capture_rows if row["matches_previous_live_capture"] is not None
            ),
            "on_disk_code_windows_match_live": all(row["matches_on_disk_image"] for row in capture_rows),
        },
        "production": {
            "runtime_table_observed": True,
            "session_object_address_observed": True,
            "method_semantics_proven": False,
            "calling_convention_proven": False,
            "owner_lifetime_proven": False,
            "join_leave_migration_behavior_proven": False,
            "player_admission_proven": False,
            "installable": False,
            "runtime_verified": False,
            "multiplayer_verified": False,
        },
        "structural_crosscheck": {
            "captured_object_has_nonzero_count_field": count_0x138 != 0,
            "captured_object_has_nonzero_array_pointer": array_0x140 != 0,
            "object_contains_nonzero_count_and_array_pointer": count_0x138 != 0 and array_0x140 != 0,
            "semantic_meaning_proven": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--previous", type=Path, default=DEFAULT_PREVIOUS)
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = build_receipt(args.log, args.previous, args.exe)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "sha256": sha256(args.output.read_bytes()),
        "object": receipt["session_object_candidate"]["address"],
        "first_qword_matches_vtable": receipt["session_object_candidate"]["first_qword_matches_vtable"],
        "object_dword_0x138": receipt["session_object_candidate"]["structural_fields"]["dword_0x138"],
        "object_qword_0x140": receipt["session_object_candidate"]["structural_fields"]["qword_0x140"],
        "runtime_methods": len(receipt["runtime_methods"]),
        "live_windows_match_previous": receipt["identity"]["live_code_windows_match_previous"],
        "disk_windows_match_live": receipt["identity"]["on_disk_code_windows_match_live"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
