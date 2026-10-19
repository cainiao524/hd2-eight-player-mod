"""Decode indirect calls from the probe's runtime-captured code windows.

The input is the read-only HD2PartyApiProbe log.  The decoder never reads or
executes the game and never treats an indirect slot as a Party method merely
because its register shape looks similar.  It reports only the exact runtime
slot address, its captured target when available, and named IAT matches.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import capstone
from capstone.x86 import X86_REG_RIP


def latest_section(raw: str) -> str:
    starts = list(re.finditer(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d START ", raw, re.M))
    if not starts:
        raise ValueError("no probe section")
    section = raw[starts[-1].start():]
    if "DONE read_only=true no_calls=true no_writes=true hooks_installed=false direct_slot_capture=true" not in section:
        raise ValueError("latest section is incomplete")
    return section


def hx(value: str) -> int:
    return int(value, 16)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw_bytes = args.log.read_bytes()
    section = latest_section(raw_bytes.decode("utf-8"))
    modules = re.search(
        r"MODULES game_base=(0x[0-9A-F]+) party_base=(0x[0-9A-F]+) "
        r"(?:playfab_base=(0x[0-9A-F]+) )?exe_base=(0x[0-9A-F]+)", section)
    if not modules:
        raise ValueError("missing module bases")
    game_base, party_base, playfab_base, exe_base = [hx(x) if x else None for x in modules.groups()]
    iat_by_address = {}
    for match in re.finditer(
        r"EXE_IAT rva=(0x[0-9A-F]+) label=([^ ]+) address=(0x[0-9A-F]+) "
        r"target=(0x[0-9A-F]+) in_party=(true|false) "
        r"(?:in_playfab=(true|false) )?in_exe=(true|false)", section):
        rva, label, address, target, in_party, in_playfab, in_exe = match.groups()
        iat_by_address[hx(address)] = {
            "rva": rva, "label": label, "target": target,
            "in_party": in_party == "true",
            "in_playfab": in_playfab == "true" if in_playfab else False,
            "in_exe": in_exe == "true",
        }
    slot_by_address = {}
    for match in re.finditer(
        r"EXE_SLOT rva=(0x[0-9A-F]+) label=([^ ]+) address=(0x[0-9A-F]+) "
        r"target=(0x[0-9A-F]+) in_party=(true|false) in_exe=(true|false)", section):
        rva, label, address, target, in_party, in_exe = match.groups()
        slot_by_address[hx(address)] = {
            "rva": rva, "label": label, "target": target,
            "in_party": in_party == "true", "in_exe": in_exe == "true",
        }
    windows = []
    for match in re.finditer(
        r"EXE_CALLSITE_WINDOW rva=(0x[0-9A-F]+) label=([^ ]+) address=(0x[0-9A-F]+) "
        r"size=(0x[0-9A-F]+) code4096=([0-9A-F]+)", section):
        rva, label, address, size, code_hex = match.groups()
        code = bytes.fromhex(code_hex)
        if len(code) != hx(size):
            raise ValueError(f"window size mismatch: {label}")
        windows.append((rva, label, hx(address), code))
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    calls = []
    for rva, label, address, code in windows:
        for ins in md.disasm(code, address):
            if ins.mnemonic != "call" or not ins.operands:
                continue
            op = ins.operands[0]
            if op.type != capstone.x86.X86_OP_MEM or op.mem.base != X86_REG_RIP:
                continue
            slot = ins.address + ins.size + op.mem.disp
            row = {
                "window": label,
                "instruction": hex(ins.address),
                "instruction_rva": hex(ins.address - exe_base),
                "slot": hex(slot),
                "slot_rva": hex(slot - exe_base) if slot >= exe_base else None,
                "bytes": ins.bytes.hex(),
            }
            if slot in iat_by_address:
                row["iat"] = iat_by_address[slot]
            if slot in slot_by_address:
                row["exe_slot"] = slot_by_address[slot]
            calls.append(row)
    direct_party_calls = [x for x in calls if x.get("iat", {}).get("in_party") or x.get("exe_slot", {}).get("in_party")]
    result = {
        "schema": "hd2_runtime_callsite_slot_audit_v1",
        "build": 25480438,
        "log_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "probe_section": re.search(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d START .*)$", section, re.M).group(1),
        "modules": {"game_base": hex(game_base), "party_base": hex(party_base),
                    "playfab_base": hex(playfab_base) if playfab_base else None,
                    "exe_base": hex(exe_base)},
        "read_only": True,
        "calls_made": False,
        "writes_made": False,
        "hooks_installed": False,
        "runtime_captured_windows": [
            {"rva": rva, "label": label, "address": hex(address),
             "size": len(code), "sha256": hashlib.sha256(code).hexdigest()}
            for rva, label, address, code in windows
        ],
        "indirect_call_count": len(calls),
        "indirect_calls": calls,
        "findings": {
            "indirect_calls_to_partywin_targets_observed": bool(direct_party_calls),
            "named_party_iat_calls_observed": any("iat" in x and x["iat"]["in_party"] for x in calls),
            "candidate_exe_slot_calls_observed": any("exe_slot" in x for x in calls),
            "call_semantics_proven": False,
            "session_party_abi_proven": False,
        },
        "limits": [
            "This disassembles only runtime-captured windows; it does not follow or invoke targets.",
            "A register/stack shape remains an ABI candidate until direct target and return/state behavior are verified.",
        ],
    }
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "indirect_call_count": len(calls),
                      "partywin_target_calls": len(direct_party_calls)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
