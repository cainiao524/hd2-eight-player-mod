"""Offline analysis of the authorized EXE RVA 0x1AE380 capture.

This tool reads only a saved JSON capture and fixed evidence files.  It does
not open a process, read memory, call game code, or modify an image.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import capstone


BUILD = 25480438
TARGET_RVA = 0x1AE380
ARRIVAL_RVA = 0x6054F0
MASK_RVA = 0x1277920
ARRIVAL_SHA = "6ad21683150fa35285c490fb75b00d8f0af68ab36dad70cbced0bccfc745288a"
MASK_SHA = "aecf466c012f2e9ba64787a5108b1807753f55166b484d7a0c21c71a21e5d1ca"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def require(value: bool, message: str) -> None:
    if not value:
        raise ValueError(message)


def direct_targets(raw: bytes, start: int):
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    instructions = []
    calls = []
    jumps = []
    references = []
    for ins in md.disasm(raw, start):
        row = {
            "rva": hex(ins.address),
            "bytes": ins.bytes.hex(),
            "asm": f"{ins.mnemonic} {ins.op_str}".rstrip(),
        }
        instructions.append(row)
        for operand in ins.operands:
            if operand.type == capstone.x86_const.X86_OP_IMM:
                value = int(operand.imm)
                if value in (ARRIVAL_RVA, MASK_RVA):
                    references.append({"rva": hex(ins.address), "asm": row["asm"], "target_rva": hex(value)})
                if ins.mnemonic == "call":
                    calls.append({"rva": hex(ins.address), "target_rva": hex(value), "asm": row["asm"]})
                elif ins.mnemonic.startswith("j"):
                    jumps.append({"rva": hex(ins.address), "target_rva": hex(value), "asm": row["asm"]})
    return instructions, calls, jumps, references


def load_evidence(path: Path, key: str, address: int, expected_sha: str):
    value = json.loads(path.read_text(encoding="utf-8"))
    if key == "bodies":
        body = value[key][hex(address)]
    else:
        body = value["body"]
    actual = body.get("sha256")
    require(actual == expected_sha, f"{path}: unexpected body SHA")
    require(int(body["entry"], 16) == address, f"{path}: unexpected body entry")
    return {
        "path": str(path),
        "file_sha256": sha(path.read_bytes()),
        "entry_rva": hex(address),
        "end_exclusive": body.get("end_exclusive"),
        "size_bytes": body.get("size_bytes"),
        "body_sha256": actual,
        "capture_identity_sha256": value.get("capture_identity_sha256"),
        "replay_sha256": value.get("replay_sha256"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--arrival-evidence", type=Path, required=True)
    parser.add_argument("--mask-evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    capture_raw = args.capture.read_bytes()
    capture = json.loads(capture_raw)
    require(capture.get("runtime_capture") is True, "capture is not marked runtime_capture")
    require(capture.get("build") == BUILD, "unsupported build")
    function = capture["function"]
    require(int(function["module_rva"], 16) == TARGET_RVA, "unexpected captured entry")
    code = bytes.fromhex(function["bytes"])
    reread = function["reread_sha256"]
    require(len(code) == function["size"] == 4096, "unexpected capture size")
    require(sha(code) == function["sha256"] == reread, "capture bytes or reread SHA mismatch")

    instructions, calls, jumps, references = direct_targets(code, TARGET_RVA)
    arrival = load_evidence(args.arrival_evidence, "bodies", ARRIVAL_RVA, ARRIVAL_SHA)
    mask = load_evidence(args.mask_evidence, "body", MASK_RVA, MASK_SHA)

    result = {
        "schema_version": 1,
        "purpose": "Offline relation check for the authorized EXE 0x1AE380 capture",
        "build": BUILD,
        "capture": {
            "path": str(args.capture),
            "file_sha256": sha(capture_raw),
            "bytes": len(capture_raw),
            "pid": capture.get("pid"),
            "utc": capture.get("utc"),
            "memory_bytes_read": capture.get("memory_bytes_read"),
            "runtime_capture": capture.get("runtime_capture"),
            "atomic_snapshot": capture.get("atomic_snapshot"),
            "eight_player_verified": capture.get("eight_player_verified"),
            "function": {
                "module": function.get("module"),
                "address": function.get("address"),
                "module_rva": function.get("module_rva"),
                "size": function.get("size"),
                "sha256": function.get("sha256"),
                "reread_sha256": function.get("reread_sha256"),
                "unchanged_on_reread": function.get("unchanged_on_reread"),
            },
        },
        "decoded": {
            "instruction_count": len(instructions),
            "direct_call_count": len(calls),
            "direct_jump_count": len(jumps),
            "direct_calls": calls,
            "direct_jumps": jumps,
            "references_to_roster_entries": references,
        },
        "related_saved_evidence": {
            "6054f0": arrival,
            "1277920": mask,
        },
        "conclusion": {
            "target_is_loaded_exe_code": True,
            "target_reread_equal": function.get("unchanged_on_reread") is True,
            "direct_reference_to_6054f0": any(int(row["target_rva"], 16) == ARRIVAL_RVA for row in references),
            "direct_reference_to_1277920": any(int(row["target_rva"], 16) == MASK_RVA for row in references),
            "entry_relation_established": False,
            "reason": "The bounded EXE prefix contains no direct call/jump/immediate reference to either game.dll RVA; the two roster entries remain separately captured evidence.",
        },
        "limits": [
            "The 4096-byte EXE range is a bounded prefix, not a proven function extent.",
            "Indirect calls, exception paths, runtime pointer targets, and cross-module callbacks are not followed.",
            "The capture proves code identity and stable rereads only; it does not prove invocation, entity creation, or multiplayer behavior.",
        ],
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "capture_sha256": result["capture"]["file_sha256"],
        "target_sha256": function["sha256"],
        "instruction_count": len(instructions),
        "references_to_roster_entries": len(references),
    }))


if __name__ == "__main__":
    main()
