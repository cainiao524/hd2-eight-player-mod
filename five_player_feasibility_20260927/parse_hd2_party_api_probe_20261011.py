"""Parse the read-only PartyWin pointer/jump-chain probe log.

The parser accepts only the latest complete direct-slot capture.  It records
runtime addresses and bounded code hashes, but never assigns API semantics to
protected jump-table or heuristic E8 byte matches.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


BUILD = 25480438
PARTY_MANAGER_HOLDER_RVA = 0x27CED10
PARTY_EXPORT_NAMES = {
    "PartyCreateNewNetwork",
    "PartyConnectToNetwork",
    "PartyNetworkAuthenticateLocalUser",
    "PartyNetworkCreateEndpoint",
    "PartyNetworkLeaveNetwork",
    "PartyNetworkKickUser",
    "PartyNetworkRemoveLocalUser",
    "PartyCleanup",
    "PartyNetworkGetNetworkConfiguration",
    "PartyNetworkGetNetworkDescriptor",
    "PartyNetworkSetCustomContext",
    "PartyStartProcessingStateChanges",
    "PartyFinishProcessingStateChanges",
    "PartyDoWork",
}
PARTY_EXPORT_RVAS = {
    "PartyCreateNewNetwork": 0x15720,
    "PartyConnectToNetwork": 0x14FE0,
    "PartyNetworkAuthenticateLocalUser": 0x1BC80,
    "PartyNetworkCreateEndpoint": 0x1C050,
    "PartyNetworkLeaveNetwork": 0x1E640,
    "PartyNetworkKickUser": 0x1E500,
    "PartyNetworkRemoveLocalUser": 0x1E7F0,
    "PartyCleanup": 0x14DC0,
    "PartyNetworkGetNetworkConfiguration": 0x1DB30,
    "PartyNetworkGetNetworkDescriptor": 0x1DCD0,
    "PartyNetworkSetCustomContext": 0x1EBF0,
    "PartyStartProcessingStateChanges": 0x1FEE0,
    "PartyFinishProcessingStateChanges": 0x193C0,
    "PartyDoWork": 0x17350,
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def latest_complete_section(raw: str) -> str:
    starts = list(re.finditer(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d START ", raw, re.M))
    if not starts:
        raise ValueError("no START section")
    section = raw[starts[-1].start() :]
    if "DONE read_only=true no_calls=true no_writes=true hooks_installed=false direct_slot_capture=true" not in section:
        raise ValueError("latest section is incomplete")
    return section


def parse_hex(value: str) -> int:
    return int(value, 16)


def parse_log(log_path: Path) -> dict:
    raw_bytes = log_path.read_bytes()
    raw = raw_bytes.decode("utf-8")
    section = latest_complete_section(raw)
    modules_match = re.search(
        r"MODULES game_base=(0x[0-9A-F]+) party_base=(0x[0-9A-F]+) "
        r"(?:playfab_base=(0x[0-9A-F]+) )?exe_base=(0x[0-9A-F]+)",
        section,
    )
    if not modules_match:
        raise ValueError("missing module bases")
    game_base = parse_hex(modules_match.group(1))
    party_base = parse_hex(modules_match.group(2))
    playfab_base = parse_hex(modules_match.group(3)) if modules_match.group(3) else None
    exe_base = parse_hex(modules_match.group(4))

    iat_rows = []
    for match in re.finditer(
        r"EXE_IAT rva=(0x[0-9A-F]+) label=([^ ]+) address=(0x[0-9A-F]+) "
        r"target=(0x[0-9A-F]+) in_party=(true|false) "
        r"(?:in_playfab=(true|false) )?in_exe=(true|false) raw=([0-9A-F]+) code64=([0-9A-F]+|nil)",
        section,
    ):
        rva, label, address, target, in_party, in_playfab, in_exe, raw_hex, code_hex = match.groups()
        row = {
            "rva": rva,
            "label": label,
            "address": address,
            "target": target,
            "in_party": in_party == "true",
            "in_playfab": in_playfab == "true" if in_playfab else False,
            "in_exe": in_exe == "true",
            "raw_sha256": sha256(bytes.fromhex(raw_hex)),
        }
        if code_hex != "nil":
            row["code64_sha256"] = sha256(bytes.fromhex(code_hex))
        iat_rows.append(row)

    slots = []
    for match in re.finditer(
        r"EXE_SLOT rva=(0x[0-9A-F]+) label=([^ ]+) address=(0x[0-9A-F]+) "
        r"target=(0x[0-9A-F]+) in_party=(true|false) in_exe=(true|false) raw=([0-9A-F]+) code512=([0-9A-F]+)",
        section,
    ):
        rva, label, address, target, in_party, in_exe, raw_hex, code_hex = match.groups()
        code = bytes.fromhex(code_hex)
        target_value = parse_hex(target)
        jump_target = None
        if code[:1] == b"\xE9" and len(code) >= 5:
            displacement = int.from_bytes(code[1:5], "little", signed=True)
            jump_target = target_value + 5 + displacement
        slots.append(
            {
                "rva": rva,
                "label": label,
                "slot_address": address,
                "target": target,
                "target_rva": hex(target_value - exe_base),
                "in_party": in_party == "true",
                "in_exe": in_exe == "true",
                "raw_sha256": sha256(bytes.fromhex(raw_hex)),
                "code512_sha256": sha256(code),
                "first_jump_target": hex(jump_target) if jump_target is not None else None,
            }
        )
    if len(slots) != 6:
        raise ValueError(f"expected six EXE slots, got {len(slots)}")

    table_window = None
    table_match = re.search(
        r"EXE_SLOT_TABLE_WINDOW address=(0x[0-9A-F]+) size=(0x[0-9A-F]+) bytes=([0-9A-F]+)",
        section,
    )
    if table_match:
        address, size, data_hex = table_match.groups()
        data = bytes.fromhex(data_hex)
        if len(data) != parse_hex(size):
            raise ValueError("slot table window size mismatch")
        export_by_address = {party_base + rva: name for name, rva in PARTY_EXPORT_RVAS.items()}
        party_rows = []
        for offset in range(0, len(data) - 7, 8):
            value = int.from_bytes(data[offset:offset + 8], "little")
            if party_base <= value < party_base + 0x400000:
                party_rows.append(
                    {
                        "offset": hex(offset),
                        "address": hex(parse_hex(address) + offset),
                        "value": hex(value),
                        "known_export": export_by_address.get(value),
                    }
                )
        table_window = {
            "address": address,
            "size": size,
            "sha256": sha256(data),
            "partywin_pointer_rows": party_rows,
        }

    global_pointers = []
    for match in re.finditer(
        r"EXE_GLOBAL_POINTER rva=(0x[0-9A-F]+) label=([^ ]+) address=(0x[0-9A-F]+) "
        r"target=(0x[0-9A-F]+|nil) in_party=(true|false) in_playfab=(true|false) "
        r"in_exe=(true|false) raw=([0-9A-F]+|nil) target_code64=([0-9A-F]+|nil)",
        section,
    ):
        rva, label, address, target, in_party, in_playfab, in_exe, raw_hex, code_hex = match.groups()
        row = {
            "rva": rva,
            "label": label,
            "address": address,
            "target": target,
            "in_party": in_party == "true",
            "in_playfab": in_playfab == "true",
            "in_exe": in_exe == "true",
        }
        if raw_hex != "nil":
            row["raw_sha256"] = sha256(bytes.fromhex(raw_hex))
        if code_hex != "nil":
            row["target_code64_sha256"] = sha256(bytes.fromhex(code_hex))
        if label == "party_manager_holder_candidate":
            # Historical probes named this a pointer and reported module-range
            # flags. The singleton actually holds an opaque Party C handle;
            # neither those flags nor target code establish an object binding.
            if (parse_hex(rva) != PARTY_MANAGER_HOLDER_RVA or
                    parse_hex(address) != exe_base + PARTY_MANAGER_HOLDER_RVA):
                raise ValueError("Party manager holder address mismatch")
            if (raw_hex == "nil") != (target == "nil"):
                raise ValueError("Party manager holder read is inconsistent")
            value = None
            if raw_hex != "nil":
                data = bytes.fromhex(raw_hex)
                if len(data) != 8 or int.from_bytes(data, "little") != parse_hex(target):
                    raise ValueError("Party manager holder value mismatch")
                value = int.from_bytes(data, "little")
            row.update({
                "value_kind": "opaque_handle_not_object_pointer",
                "holder_bytes_verified": value is not None,
                "handle_value": hex(value) if value is not None else None,
                "handle_nonzero": value is not None and value != 0,
                "manager_object_binding_proven": False,
            })
        global_pointers.append(row)

    callsite_windows = []
    for match in re.finditer(
        r"EXE_CALLSITE_WINDOW rva=(0x[0-9A-F]+) label=([^ ]+) address=(0x[0-9A-F]+) "
        r"size=(0x[0-9A-F]+) code4096=([0-9A-F]+)",
        section,
    ):
        rva, label, address, size, code_hex = match.groups()
        code = bytes.fromhex(code_hex)
        if len(code) != parse_hex(size):
            raise ValueError("callsite window size mismatch")
        callsite_windows.append(
            {
                "rva": rva,
                "label": label,
                "address": address,
                "size": size,
                "sha256": sha256(code),
                "first_bytes": code_hex[:64],
            }
        )

    hops = []
    for match in re.finditer(
        r"HOP label=([^ ]+) depth=(\d+) address=(0x[0-9A-F]+) code256=([0-9A-F]+)", section
    ):
        label, depth, address, code_hex = match.groups()
        hops.append(
            {
                "label": label,
                "depth": int(depth),
                "address": address,
                "rva": hex(parse_hex(address) - exe_base),
                "code256_sha256": sha256(bytes.fromhex(code_hex)),
                "first_bytes": code_hex[:32],
            }
        )

    hop_windows = []
    for match in re.finditer(
        r"HOP_WINDOW label=([^ ]+) depth=(\d+) address=(0x[0-9A-F]+) "
        r"size=(0x[0-9A-F]+) code4096=([0-9A-F]+)", section
    ):
        label, depth, address, size, code_hex = match.groups()
        code = bytes.fromhex(code_hex)
        if len(code) != parse_hex(size):
            raise ValueError("hop window size mismatch")
        hop_windows.append(
            {
                "label": label,
                "depth": int(depth),
                "address": address,
                "rva": hex(parse_hex(address) - exe_base),
                "size": size,
                "sha256": sha256(code),
                "first_bytes": code_hex[:32],
            }
        )

    rip_indirects = []
    for match in re.finditer(
        r"RIP_INDIRECT label=([^ ]+) kind=(call|jmp) at=(0x[0-9A-F]+) "
        r"slot=(0x[0-9A-F]+) target=(0x[0-9A-F]+|nil) in_party=(true|false) "
        r"in_playfab=(true|false) in_exe=(true|false) raw=([0-9A-F]+|nil)", section
    ):
        label, kind, instruction, slot, target, in_party, in_playfab, in_exe, raw_hex = match.groups()
        row = {
            "label": label,
            "kind": kind,
            "instruction": instruction,
            "slot": slot,
            "target": target,
            "in_party": in_party == "true",
            "in_playfab": in_playfab == "true",
            "in_exe": in_exe == "true",
        }
        if target != "nil":
            row["target_rva"] = hex(parse_hex(target) - exe_base)
        if raw_hex != "nil":
            row["raw_sha256"] = sha256(bytes.fromhex(raw_hex))
        rip_indirects.append(row)

    call_targets = []
    for match in re.finditer(
        r"CALL_TARGET label=([^ ]+) at=(0x[0-9A-F]+) target=(0x[0-9A-F]+) code128=([0-9A-F]+|nil)",
        section,
    ):
        label, at, target, code_hex = match.groups()
        entry = {
            "label": label,
            "instruction": at,
            "target": target,
            "target_rva": hex(parse_hex(target) - exe_base),
            "heuristic_code_scan": True,
        }
        if code_hex != "nil":
            entry["code128_sha256"] = sha256(bytes.fromhex(code_hex))
            entry["first_bytes"] = code_hex[:32]
        call_targets.append(entry)

    exports = []
    for match in re.finditer(
        r"EXPORT name=([^ ]+) rva=(0x[0-9A-F]+) address=(0x[0-9A-F]+) code64=([0-9A-F]+)",
        section,
    ):
        name, rva, address, code_hex = match.groups()
        if name not in PARTY_EXPORT_NAMES:
            raise ValueError(f"unexpected export {name}")
        exports.append(
            {
                "name": name,
                "rva": rva,
                "address": address,
                "code64_sha256": sha256(bytes.fromhex(code_hex)),
                "first_bytes": code_hex[:32],
            }
        )
    if {x["name"] for x in exports} != PARTY_EXPORT_NAMES:
        raise ValueError("PartyWin export set is incomplete")

    pointer_refs = []
    for match in re.finditer(
        r"EXPORT name=([^ ]+) rva=(0x[0-9A-F]+) address=(0x[0-9A-F]+) pointer_refs=(\d+) code64=([0-9A-F]+)",
        raw,
    ):
        name, rva, address, count, code_hex = match.groups()
        pointer_refs.append(
            {
                "name": name,
                "rva": rva,
                "address": address,
                "pointer_refs": int(count),
                "code64_sha256": sha256(bytes.fromhex(code_hex)),
            }
        )
    latest_pointer_refs = {}
    for row in pointer_refs:
        latest_pointer_refs[row["name"]] = row

    return {
        "schema": "hd2_live_party_api_pointer_probe_v1",
        "build": BUILD,
        "probe": {
            "log_sha256": sha256(raw_bytes),
            "latest_start": re.search(
                r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d START .*)$", section, re.M
            ).group(1).rstrip(),
            "game_base": hex(game_base),
            "party_base": hex(party_base),
            "playfab_base": hex(playfab_base) if playfab_base is not None else None,
            "exe_base": hex(exe_base),
            "read_only": True,
            "calls_made": False,
            "writes_made": False,
            "hooks_installed": False,
        },
        "runtime_iat": iat_rows,
        "exe_indirect_slots": slots,
        "exe_slot_table_window": table_window,
        "exe_global_pointers": global_pointers,
        "exe_callsite_windows": callsite_windows,
        "jump_chain_windows": hops,
        "jump_chain_4096_windows": hop_windows,
        "rip_indirect_targets": rip_indirects,
        "heuristic_direct_call_targets": call_targets,
        "partywin_exports": exports,
        "prior_full_scan_pointer_refs": list(latest_pointer_refs.values()),
        "findings": {
            "all_six_slots_point_into_exe": all(x["in_exe"] and not x["in_party"] for x in slots),
            "all_six_slots_have_first_jump": all(x["first_jump_target"] is not None for x in slots),
            "party_create_connect_auth_endpoint_export_addresses_observed": all(
                any(x["name"] == name for x in exports)
                for name in (
                    "PartyCreateNewNetwork",
                    "PartyConnectToNetwork",
                    "PartyNetworkAuthenticateLocalUser",
                    "PartyNetworkCreateEndpoint",
                )
            ),
            "named_party_iat_binding_observed": any(
                row["label"] == "PartyNetworkSetCustomContext"
                and row["in_party"]
                and parse_hex(row["target"]) == party_base + PARTY_EXPORT_RVAS["PartyNetworkSetCustomContext"]
                for row in iat_rows
            ),
            "named_playfab_iat_binding_observed": any(
                row["label"] == "PFLobbySendInvite" and row["in_playfab"] for row in iat_rows
            ),
            "party_manager_holder_candidate_runtime_observed": any(
                row.get("holder_bytes_verified", False)
                for row in global_pointers
            ),
            "party_manager_handle_nonzero_observed": any(
                row.get("handle_nonzero", False) for row in global_pointers
            ),
            "party_manager_object_binding_proven": False,
            "partywin_target_observed_in_candidate_windows": any(
                row["in_party"] for row in rip_indirects
            ),
            "playfab_target_observed_in_candidate_windows": any(
                row["in_playfab"] for row in rip_indirects
            ),
            "direct_party_export_pointer_binding_proven": False,
            "call_target_semantics_proven": False,
            "session_party_abi_proven": False,
        },
        "production": {
            "installable": False,
            "runtime_verified": False,
            "multiplayer_verified": False,
        },
        "limits": [
            "EXE slot targets and bounded jump/call windows were read without invoking them.",
            "The E8 byte scan is heuristic and can match protected data; it does not prove a call edge or callee semantics.",
            "PartyWin exports are loaded and addressable, but no create/connect/auth/endpoint slot points directly to them in the pointer scan.",
            "Named IAT binding proves only PartyNetworkSetCustomContext and PFLobbySendInvite; it does not bind the unresolved create/connect/auth/endpoint slots.",
            "The manager holder stores an opaque handle. Historical module-range flags and target-code hashes do not establish handle validity or a manager object binding.",
            "No Session/Party method was called and no host/client or mission behavior was exercised.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = parse_log(args.log)
    args.output.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "sha256": sha256(args.output.read_bytes())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
