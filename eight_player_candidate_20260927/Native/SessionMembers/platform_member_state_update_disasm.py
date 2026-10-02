"""Recover the exact 0x10937a0 member-state routine from the read-only capture.

This module only reads the captured image.  It deliberately emits an ABI and
control-flow inventory instead of a patch: the routine mutates a large owner
state object and is not a bounded four-slot leaf.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import capstone  # type: ignore


ROOT = Path(__file__).resolve().parents[3]
CAPTURE_DIR = ROOT / "evidence" / "existing-code-evidence-25480438"
ENTRY_RVA = 0x10937A0
END_RVA = 0x10945D8
BODY_SIZE = END_RVA - ENTRY_RVA
BODY_SHA256 = "929b6b1a3163e7b405d92d90d44c19dd4b2dc3d592115d2bb3e0383a1e719a69"
CAPTURE_ID = "5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def load_capture() -> tuple[bytes, dict]:
    report = json.loads((CAPTURE_DIR / "capture-report.json").read_text(encoding="utf-8"))
    require(report.get("capture_sha256") == CAPTURE_ID, "capture identity changed")
    data = (CAPTURE_DIR / "captured-data.bin").read_bytes()
    out = bytearray()
    end = ENTRY_RVA + BODY_SIZE
    for chunk in report["chunks"]:
        begin = int(chunk["rva"])
        finish = begin + int(chunk["size"])
        lo = max(ENTRY_RVA, begin)
        hi = min(end, finish)
        if hi > lo:
            off = int(chunk["file_offset"]) + (lo - begin)
            out.extend(data[off : off + hi - lo])
    raw = bytes(out)
    require(len(raw) == BODY_SIZE, "capture does not cover the complete body")
    require(sha256(raw) == BODY_SHA256, "captured body fingerprint changed")
    return raw, report


def _target(insn: capstone.CsInsn) -> int | None:
    if insn.mnemonic not in {
        "call", "jmp", "ja", "jae", "jb", "jbe", "jc", "je", "jg", "jge", "jl", "jle",
        "jna", "jnae", "jnb", "jnbe", "jnc", "jne", "jng", "jnge", "jnl", "jnle", "jno",
        "jnp", "jns", "jnz", "jo", "jp", "jpe", "jpo", "js", "jz",
    }:
        return None
    text = insn.op_str.strip()
    if not text.startswith("0x"):
        return None
    try:
        return int(text, 16)
    except ValueError:
        return None


def _field_hits(insn: capstone.CsInsn) -> list[str]:
    hits = []
    for match in re.finditer(r"0x([0-9a-fA-F]+)", insn.op_str):
        off = int(match.group(1), 16)
        if off in {0x1B58, 0x1B78, 0x1B7C, 0x1B80, 0x1B84, 0x1B90, 0x1B98, 0x1B9C, 0x1BA0, 0x1BA4, 0x1BA5, 0x1BA6, 0x1BA7, 0x1BA8, 0x1BA9, 0x1BAC, 0x1BB0}:
            hits.append(f"owner+0x{off:x}")
    return sorted(set(hits))


def recover() -> dict:
    raw, report = load_capture()
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    decoder.detail = True
    instructions = list(decoder.disasm(raw, ENTRY_RVA))
    require(sum(i.size for i in instructions) == BODY_SIZE, "instruction coverage changed")
    require(instructions[0].address == ENTRY_RVA, "entry changed")
    require(instructions[-1].address + instructions[-1].size == END_RVA, "end changed")

    rows = []
    branches = []
    direct_calls = []
    indirect_calls = []
    field_sites = []
    four_sites = []
    returns = []
    for insn in instructions:
        data = bytes(insn.bytes)
        target = _target(insn)
        fields = _field_hits(insn)
        row = {
            "rva": hex(insn.address),
            "bytes": data.hex(),
            "sha256": sha256(data),
            "asm": f"{insn.mnemonic} {insn.op_str}".rstrip(),
        }
        if target is not None:
            row["target"] = hex(target)
            branches.append({"rva": hex(insn.address), "mnemonic": insn.mnemonic, "target": hex(target), "back_edge": target < insn.address})
        if insn.mnemonic == "call":
            if target is None:
                indirect_calls.append(hex(insn.address))
            else:
                direct_calls.append({"rva": hex(insn.address), "target": hex(target)})
        if insn.mnemonic == "ret":
            returns.append(hex(insn.address))
        if fields:
            row["owner_fields"] = fields
            field_sites.append({"rva": hex(insn.address), "asm": row["asm"], "fields": fields})
        if re.search(r"(?:,|\s)4(?:\s|$)", insn.op_str):
            row["immediate_four"] = True
            four_sites.append({"rva": hex(insn.address), "asm": row["asm"]})
        rows.append(row)

    caller_specs = {
        0x108F078: (0x108F040, 0x108F0A6),
        0x134E44A: (0x134E400, 0x134E596),
        0x13F788A: (0x13F76E0, 0x13F7B91),
        0x10944FC: (0x1094390, 0x1094587),
    }
    callers = []
    for call_rva, (start, finish) in caller_specs.items():
        chunk = bytearray()
        end = call_rva + 5
        for c in report["chunks"]:
            begin = int(c["rva"]); stop = begin + int(c["size"])
            lo = max(start, begin); hi = min(end, stop)
            if hi > lo:
                src = (CAPTURE_DIR / "captured-data.bin").read_bytes()
                off = int(c["file_offset"]) + lo - begin
                chunk.extend(src[off : off + hi - lo])
        ctx = list(decoder.disasm(bytes(chunk), start))
        callers.append({
            "call_rva": hex(call_rva),
            "context_range": [hex(start), hex(end)],
            "context_sha256": sha256(bytes(chunk)),
            "instructions": [{"rva": hex(i.address), "bytes": bytes(i.bytes).hex(), "asm": f"{i.mnemonic} {i.op_str}".rstrip()} for i in ctx],
            "owner_argument": "RCX at call site; caller-specific subobject as shown in context",
        })

    field_counts: dict[str, int] = {}
    for row in field_sites:
        for field in row["fields"]:
            field_counts[field] = field_counts.get(field, 0) + 1
    return {
        "status": "exact_captured_state_update_disassembly",
        "steam_build": 25480438,
        "entry": {
            "rva": hex(ENTRY_RVA),
            "end_exclusive": hex(END_RVA),
            "body_bytes": BODY_SIZE,
            "body_sha256": BODY_SHA256,
            "prologue": rows[:12],
            "epilogue": rows[-14:],
            "stack_frame": {"stack_subtract": "0x308", "saved_nonvolatile": ["RBX", "RBP", "RSI", "RDI", "R12", "R13", "R14", "R15"], "security_cookie": True},
        },
        "instructions": rows,
        "control_flow": {
            "instruction_count": len(rows),
            "branch_count": len(branches),
            "back_edge_count": sum(1 for x in branches if x["back_edge"]),
            "branches": branches,
            "direct_calls": direct_calls,
            "indirect_call_rvas": indirect_calls,
            "return_rvas": returns,
        },
        "owner_field_sites": field_sites,
        "owner_field_counts": field_counts,
        "four_immediate_sites": four_sites,
        "callers": callers,
        "abi": {
            "input": "RCX = owner/platform subobject; no stable public return value (callers ignore EAX)",
            "preserved": "RBX/RBP/RSI/RDI/R12-R15 and XMM6 are restored; stack cookie checked before return",
            "owner_subobject_examples": ["caller 0x108f078 passes root+0x1c00", "callers 0x134e44a and 0x13f788a pass root+0x1d470"],
            "control_fields": ["+0x1b78", "+0x1b7c", "+0x1b80", "+0x1b84", "+0x1b98", "+0x1b9c", "+0x1ba0", "+0x1ba4", "+0x1ba5", "+0x1ba6", "+0x1ba7", "+0x1ba8", "+0x1ba9", "+0x1bac"],
            "member_storage": {"inline_ids": "owner+0x1b58+8*i", "inline_count": "owner+0x1bb0", "original_capacity": 4},
        },
        "sidecar_patch_assessment": {
            "installable": False,
            "runtime_verified": False,
            "multiplayer_verified": False,
            "safe_leaf_replacement": False,
            "reason": "The 3640-byte routine has multiple state-machine branches, 18 owner control fields, indirect callbacks, three distinct caller subobjects, a stack cookie, and four-slot storage reads/writes. A sidecar requires a complete field-by-field shim plus owner-lifetime and callback ABI binding; changing constants or replacing this function with an unbound stub is unsafe.",
            "required_before_patch": ["resolve sidecar ownership keyed by the exact RCX subobject", "bind all indirect callbacks and 0x1091800/0x1093120/0x1093280 cleanup paths", "redirect every inline member-buffer read/write without altering adjacent control fields", "prove exception/unwind and reentrant callback behavior", "run live five-to-eight account acceptance"],
        },
        "source": {
            "capture_sha256": report["capture_sha256"],
            "capture_report_sha256": sha256((CAPTURE_DIR / "capture-report.json").read_bytes()),
            "captured_data_sha256": sha256((CAPTURE_DIR / "captured-data.bin").read_bytes()),
        },
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "refusing overwrite")
    result = recover()
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "instruction_count": result["control_flow"]["instruction_count"], "four_sites": len(result["four_immediate_sites"]), "installable": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
