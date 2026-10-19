"""Recover HD2 wrapper-to-virtual dispatch from saved bytes, without game access.

These two captures share a PID and pinned images. They do NOT prove that a
later host-admission RCX has the same type or lifetime as the captured session.
Public SDK method names are deliberately excluded from the recovered ABI.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

from capstone import Cs, CS_ARCH_X86, CS_MODE_64

HERE = Path(__file__).resolve().parent
PINS = {
    "live_c_api_table_prefixes_20261003.json": "1676c701926f3ea168b5d90d50c2ea2880a60755552fa8c767b4552c8ae833c3",
    "live_engine_session_vtable_20261003.json": "ef35587ba76dfab0fc2d814c161d73f91495686e258c2fee186da070060254f0",
    "host_expansion_disasm_108d9f0.json": "5e065ebbac9e6274ab59f486155e06fed146d1ba5e42bc3bebf22e5f5803e888",
}
IMAGE_HASHES = {
    "helldivers2.exe": "f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06",
    "game.dll": "2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e",
}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def number(value):
    return int(value, 0) if isinstance(value, str) else value


def decode(code, rva):
    return [{"rva": hex(i.address), "bytes": i.bytes.hex(),
             "asm": (i.mnemonic + " " + i.op_str).strip()}
            for i in Cs(CS_ARCH_X86, CS_MODE_64).disasm(code, rva)]


def analyze(tables_capture, object_capture, host):
    require(tables_capture["pid"] == object_capture["pid"], "capture_pid_mismatch")
    require(object_capture["build"] == 25480438, "build_mismatch")
    require(object_capture["unchanged"] is True, "unstable_object_capture")
    require(object_capture["calls_made"] is False and object_capture["writes_made"] is False,
            "object_capture_not_passive")
    require(tables_capture["memory_writes"] is False and
            tables_capture["calls_made_by_capture"] is False, "table_capture_not_passive")
    for name, fingerprint in IMAGE_HASHES.items():
        a, b = tables_capture["pinned_images"][name], object_capture["pinned_images"][name]
        require(a == b and a["sha256"] == fingerprint, "capture_image_mismatch")
    exe_base = tables_capture["pinned_images"]["helldivers2.exe"]["base"]
    tables = {t["label_from_public_sdk"]: t for t in tables_capture["tables"]}
    require(len(tables) == len(tables_capture["tables"]) and set(tables) == {"Network", "GameSession"},
            "table_labels_invalid")
    by_label = {}
    for label, table in tables.items():
        require(table["reread_equal"] is True and table["module"] == "helldivers2.exe",
                "unstable_or_wrong_table_module")
        require(number(table["address"]) == exe_base + number(table["rva"]), "table_rva_mismatch")
        raw = bytes.fromhex(table["raw"])
        entries = {}
        for entry in table["entries"]:
            slot, rva = number(entry["slot_offset"]), number(entry["rva"])
            require(slot % 8 == 0 and slot + 8 <= len(raw) and slot not in entries, "invalid_slot")
            require(entry["module"] == "helldivers2.exe", "wrong_wrapper_module")
            require(struct.unpack_from("<Q", raw, slot)[0] == number(entry["pointer"]) == exe_base + rva,
                    "wrapper_pointer_mismatch")
            prefix = bytes.fromhex(entry["prefix"])
            require(hashlib.sha256(prefix).hexdigest() == entry["prefix_sha256"], "wrapper_prefix_hash_mismatch")
            entries[slot] = (entry, prefix)
        by_label[label] = entries
    getter, getter_bytes = by_label["Network"][8]
    require(number(getter["rva"]) == 0x34FDF0 and
            getter_bytes[:15] == bytes.fromhex("488b0581046c01488b80a8000000c3"), "getter_bytes_mismatch")
    require(0x34FDF0 + 7 + struct.unpack_from("<i", getter_bytes, 3)[0] ==
            number(object_capture["root_global_rva"]), "getter_root_mismatch")

    # Merge overlapping captured bytes; conflicting overlap is not silently won
    # by the last row. No missing suffix is inferred from neighboring methods.
    memory = {}
    vraw = bytes.fromhex(object_capture["vtable_raw"])
    for row in object_capture["rows"]:
        slot, rva = number(row["slot"]), number(row["rva"])
        require(row["module"] == "helldivers2.exe", "wrong_virtual_module")
        require(struct.unpack_from("<Q", vraw, slot)[0] == number(row["target"]) == exe_base + rva,
                "virtual_pointer_mismatch")
        for offset, byte in enumerate(bytes.fromhex(row["bytes"])):
            address = rva + offset
            require(address not in memory or memory[address] == byte, "conflicting_code_overlap")
            memory[address] = byte

    links = []
    # Expected pairs are checked against the raw machine instructions, not the
    # saved disassembly strings or the generic Autodesk structure declaration.
    for api_slot, virtual_slot, wrapper_rva in [(8, 0x80, 0x34B030),
            (0x40, 0x58, 0x34B0F0), (0x48, 0x30, 0x34B100),
            (0x50, 0x38, 0x34B110), (0x60, 0x70, 0x34B150)]:
        entry, code = by_label["GameSession"][api_slot]
        if api_slot == 8:
            expected = bytes.fromhex("4883ec28488b01ff90800000000fb6c04883c428c3")
        else:
            expected = bytes.fromhex("488b0148ff60") + bytes([virtual_slot])
        require(number(entry["rva"]) == wrapper_rva and code.startswith(expected), "wrapper_dispatch_mismatch")
        target_rva = struct.unpack_from("<Q", vraw, virtual_slot)[0] - exe_base
        captured = bytearray()
        while target_rva + len(captured) in memory:
            captured.append(memory[target_rva + len(captured)])
        instructions = decode(captured, target_rva)
        # The direct method ends at its first ret if one was actually captured.
        end = next((i + 1 for i, row in enumerate(instructions) if row["asm"] == "ret"), len(instructions))
        instructions = instructions[:end]
        links.append({"c_api_slot": hex(api_slot), "wrapper_rva": hex(wrapper_rva),
            "wrapper_instructions": decode(expected, wrapper_rva), "virtual_slot": hex(virtual_slot),
            "captured_session_target_rva": hex(target_rva), "target_instructions": instructions,
            "return_instruction_captured": bool(instructions and instructions[-1]["asm"] == "ret"),
            "host_object_type_and_lifetime_proven": False, "call_allowed": False})
    queue = next(row for row in links if row["c_api_slot"] == "0x50")
    require(queue["captured_session_target_rva"] == "0x291110", "queue_target_mismatch")
    require(any(i["bytes"] == "488bf9" for i in queue["target_instructions"]) and
            any(i["bytes"] == "89875c480000" for i in queue["target_instructions"]), "missing_session_write")
    count = next(row for row in links if row["c_api_slot"] == "0x60")
    require(count["captured_session_target_rva"] == "0x292be0" and
            [i["bytes"] for i in count["target_instructions"]] == ["8b8138010000", "c3"], "count_bytes_mismatch")

    host_rows = {}
    def visit(item):
        if isinstance(item, dict):
            if "rva" in item and "bytes" in item:
                host_rows[number(item["rva"])] = item
            for value in item.values(): visit(value)
        elif isinstance(item, list):
            for value in item: visit(value)
    visit(host)
    for rva, raw in [(0x108DDC7, "41ff5008"), (0x108DE09, "41ff5050")]:
        require(host_rows[rva]["bytes"] == raw, "host_callsite_mismatch")
    return {"schema": "hd2_saved_session_dispatch_v2", "build": 25480438,
        "capture_pid": tables_capture["pid"], "result": "wrapper_virtual_dispatch_recovered",
        "getter_module": "helldivers2.exe", "getter_rva": "0x34fdf0",
        "getter_root_global_rva": "0x1a10278", "dispatch": links,
        "findings": {
            "c_api_0x50_is_not_a_read_only_count_getter_on_captured_session": True,
            "c_api_0x50_writes_session_offset": "0x485c",
            "c_api_0x60_reads_opaque_record_count_offset": "0x138",
            "opaque_record_count_equals_player_count": False,
            "host_calls_0x08_and_0x50": ["game.dll+0x108ddc7", "game.dll+0x108de09"],
            "host_rcx_matches_captured_engine_session": False},
        "missing_evidence": ["Host call-site API root and RCX/vtable identity in the same snapshot",
            "Full 0x291110 body, completion/failure and inverse cleanup paths",
            "Complete 0x292c60 suffix and its caller return use",
            "Owner lifetime, thread quiescence, confirmed-peer and Player Clone ABI",
            "Client replication and eight-account full mission receipt"],
        "function_calls": False, "memory_writes": False, "installable": False,
        "runtime_verified": False, "multiplayer_verified": False}


def recover():
    docs = []
    for filename, expected in PINS.items():
        raw = (HERE / filename).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == expected, "source_hash_mismatch:" + filename)
        docs.append(json.loads(raw))
    result = analyze(*docs)
    result["source_sha256"] = PINS
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = recover()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result": result["result"], "links": len(result["dispatch"]),
                      "multiplayer_verified": False}))
