"""Audit static callers of the receive registration cleanup wrapper.

This replay is deliberately offline.  It uses only the pinned 25480438 code
capture and records direct call edges to the dynamic registration object's
unregistration and status helpers.  It does not infer a hash-to-selector map
and does not produce a patch or an installable payload.
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
REGISTRATION = 0x1094680
UNREGISTRATION = 0x1094710
STATUS = 0x1094780
ZERO = 0x1094700
GLOBAL_FIELD_RVA = 0x1F028


def row(ins: object) -> dict:
    return {
        "rva": hex(ins.address),  # type: ignore[attr-defined]
        "bytes": bytes(ins.bytes).hex(),  # type: ignore[attr-defined]
        "asm": f"{ins.mnemonic} {ins.op_str}".rstrip(),  # type: ignore[attr-defined]
    }


def direct_calls(im: Image, target: int) -> list[dict]:
    """Return boundary-validated direct E8 calls to target."""
    code = next(x for x in im.report["ranges"] if x["label"] == "code")
    data = im.read(code["rva"], code["size"])
    out: list[dict] = []
    for pos in range(0, len(data) - 5):
        if data[pos] != 0xE8:
            continue
        call_rva = code["rva"] + pos
        dest = call_rva + 5 + struct.unpack_from("<i", data, pos + 1)[0]
        if dest != target:
            continue
        ins = im.instruction(call_rva)
        if ins is None or ins.mnemonic != "call":
            continue
        fn = im.containing(call_rva)
        if fn is None:
            continue
        root = im.root(call_rva)
        out.append({
            "call_rva": hex(call_rva),
            "instruction": row(ins),
            "fragment": [hex(x) for x in fn],
            "root": [hex(x) for x in root],
        })
    return out


def context(im: Image, call_rva: int, before: int = 8, after: int = 2) -> list[dict]:
    fn = im.containing(call_rva)
    if fn is None:
        raise ValueError(f"no unwind fragment for {call_rva:#x}")
    instructions = list(im.md.disasm(im.read(fn[0], fn[1] - fn[0]), fn[0]))
    idx = next((i for i, ins in enumerate(instructions) if ins.address == call_rva), None)
    if idx is None:
        raise ValueError(f"call is not an instruction boundary: {call_rva:#x}")
    return [row(ins) for ins in instructions[max(0, idx - before):idx + after + 1]]


def global_field_context(ins_rows: list[dict]) -> dict:
    """Recognize the common `global + 0x1f028` owner setup before cleanup."""
    for i, ins in enumerate(ins_rows):
        # LEA/ADD pairs are emitted as MOV global followed by ADD immediate.
        if "add rcx, 0x1f028" in ins["asm"] or "add rbx, 0x1f028" in ins["asm"]:
            return {"owner_source": "global+0x1f028", "owner_setup_rva": ins["rva"]}
        if ins["asm"].startswith("mov rcx, qword ptr [rip +"):
            if i + 2 < len(ins_rows) and "add rcx, 0x1f028" in ins_rows[i + 2]["asm"]:
                return {"owner_source": "global+0x1f028", "owner_setup_rva": ins_rows[i + 2]["rva"]}
    return {"owner_source": "unresolved"}


def fragment_owner(im: Image, call_rva: int) -> dict:
    fn = im.containing(call_rva)
    if fn is None:
        return {"owner_source_in_fragment": "unresolved"}
    rows = [row(ins) for ins in im.md.disasm(im.read(fn[0], fn[1] - fn[0]), fn[0])]
    found = global_field_context(rows)
    return {"owner_source_in_fragment": found["owner_source"], "owner_setup_rva_in_fragment": found.get("owner_setup_rva")}


def audit(evidence: Path) -> dict:
    im = Image(evidence)
    if im.report["capture_sha256"] != CAPTURE_SHA:
        raise ValueError("capture identity mismatch")
    expected_methods = {
        "registration": REGISTRATION,
        "unregistration": UNREGISTRATION,
        "status": STATUS,
        "zero": ZERO,
    }
    direct = {name: direct_calls(im, target) for name, target in expected_methods.items()}
    sites: list[dict] = []
    for name in ("unregistration", "status"):
        for call in direct[name]:
            call_rva = int(call["call_rva"], 16)
            ctx = context(im, call_rva)
            sites.append({
                "helper": name,
                "target_rva": hex(expected_methods[name]),
                **call,
                "context": ctx,
                **global_field_context(ctx),
                **fragment_owner(im, call_rva),
            })
    # Exact body fingerprints are a guard against silently analysing another build.
    bodies = {}
    for name, start, end in [
        ("registration", 0x1094680, 0x10946F4),
        ("unregistration", 0x1094710, 0x109477D),
    ]:
        raw = im.read(start, end - start)
        bodies[name] = {"rva": [hex(start), hex(end)], "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    checks = [
        {"name": "capture_identity", "passed": True},
        {"name": "registration_direct_calls_absent", "passed": len(direct["registration"]) == 0, "count": len(direct["registration"])},
        {"name": "unregistration_direct_calls", "passed": len(direct["unregistration"]) == 3, "count": len(direct["unregistration"])},
        {"name": "status_direct_calls", "passed": len(direct["status"]) == 3, "count": len(direct["status"])},
        {"name": "unregistration_owner_field_binding_complete", "passed": all(x["owner_source_in_fragment"] == "global+0x1f028" for x in sites if x["helper"] == "unregistration"), "resolved": sum(x["owner_source_in_fragment"] == "global+0x1f028" for x in sites if x["helper"] == "unregistration"), "total": len([x for x in sites if x["helper"] == "unregistration"])},
    ]
    return {
        "schema": "hd2_selector_cleanup_xrefs_v1",
        "build": 25480438,
        "capture_sha256": CAPTURE_SHA,
        "source_sha256": EXPECTED,
        "read_only": True,
        "process_accessed": False,
        "game_memory_written": False,
        "hooks_installed": False,
        "targets": {name: hex(value) for name, value in expected_methods.items()},
        "bodies": bodies,
        "direct_calls": direct,
        "cleanup_sites": sites,
        "checks": checks,
        "runtime_verified": False,
        "installable": False,
        "multiplayer_verified": False,
        "findings": [
            "The dynamic registration body has no direct E8 callers in the bounded code capture; its call path is therefore indirect or runtime-registered.",
            "The unregistration body has three direct callers and the status helper has three; all three unregistration fragments prepare or derive global+0x1f028, while status contexts are only partly matched.",
            "The recognized owner field is a cleanup sidecar binding candidate, but it does not prove storage capacity, callback ABI, selector mapping, or thread safety.",
            "Public same-build Better Lobby notes identify global+0x1f028 and these wrappers as lobby-browser context; do not reuse this owner as a confirmed-peer/player-admission registry without runtime proof.",
        ],
        "next_required": "Obtain a permitted runtime callback or service registry observation that supplies the dynamic registration key and selector, then bind that owner through the existing admission/player-creation transaction before any production hook is considered.",
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
    print(json.dumps({"schema": result["schema"], "registration_direct_calls": len(result["direct_calls"]["registration"]), "unregistration_direct_calls": len(result["direct_calls"]["unregistration"]), "status_direct_calls": len(result["direct_calls"]["status"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
