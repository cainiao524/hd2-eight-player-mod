"""Capture bounded live dispatcher data without invoking or modifying HD2.

This utility is deliberately narrower than a debugger: it verifies the exact
build, reads the existing API object paths, and scans only the two pinned image
ranges for pointers to the recovered confirmed-peer/member functions and the
event hash.  It never follows an arbitrary pointer, calls a function, writes
memory, loads a DLL, or installs a hook.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import sys

import interface_probe as base


MAX_READ = 220 * 1024 * 1024
PAGE = 0x1000
TARGETS = {
    "confirmed_peer_receiver": 0x0BABA80,
    "confirmed_peer_insert": 0x0B90B20,
    "platform_member_consumer": 0x1093590,
    "platform_member_leaf_reader": 0x10936E0,
    "platform_member_state_update": 0x10937A0,
    "player_creation_gate": 0x1086460,
    "host_join_root": 0x108BC70,
    "host_confirmed_peer_sender": 0x108C760,
}
EVENT_HASH = 0x4804FCF4


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_qword(reader, address: int, label: str) -> dict:
    raw = reader.read(address, 8)
    return {"label": label, "address": hex(address), "bytes": raw.hex(),
            "value": hex(int.from_bytes(raw, "little"))}


def disk_rva_bytes(path: str, rva: int, size: int) -> bytes:
    """Resolve one RVA using the PE section table without loading it."""
    blob = Path(path).read_bytes()
    pe = struct.unpack_from("<I", blob, 0x3C)[0]
    section_count = struct.unpack_from("<H", blob, pe + 6)[0]
    optional_size = struct.unpack_from("<H", blob, pe + 20)[0]
    section_base = pe + 24 + optional_size
    for index in range(section_count):
        offset = section_base + index * 40
        virtual_size, virtual_address, raw_size, raw_pointer = struct.unpack_from("<IIII", blob, offset + 8)
        if virtual_address <= rva < virtual_address + max(virtual_size, raw_size):
            raw_offset = raw_pointer + (rva - virtual_address)
            return blob[raw_offset:raw_offset + size]
    raise ValueError("RVA is not covered by a PE section")


def scan_image(reader, module_name: str, module: dict, patterns: dict[str, bytes],
               hits: list[dict]) -> int:
    start, end = int(module["base"]), int(module["base"]) + int(module["size"])
    pages = 0
    cursor = start
    while cursor < end:
        amount = min(PAGE, end - cursor)
        try:
            raw = reader.read(cursor, amount, executable=False)
        except (ValueError, OSError):
            cursor += amount
            continue
        pages += 1
        for name, pattern in patterns.items():
            offset = 0
            while True:
                found = raw.find(pattern, offset)
                if found < 0:
                    break
                address = cursor + found
                hits.append({"pattern": name, "module": module_name,
                             "address": hex(address),
                             "rva": hex(address - int(module["base"])),
                             "page": hex(cursor), "page_sha256": digest(raw)})
                offset = found + 1
        cursor += amount
    return pages


def scan(pid: int, output: Path) -> dict:
    # Existing interface_probe captures use a 64 KiB budget.  This utility
    # explicitly caps itself at 220 MiB for the two pinned images only.
    base.READ_BUDGET = MAX_READ
    reader = base.WindowsReader(pid)
    try:
        executable = reader.executable()
        modules = reader.modules()
        selected = base.check_files(modules, executable)
        base.verify_loaded(reader, selected)
        game = selected["game.dll"]
        game_base = int(game["base"])
        exe_base = int(selected["helldivers2.exe"]["base"])

        # Pin the known generic send-side dispatcher body.  This is a code
        # identity check only; no branch or indirect target is followed.
        dispatcher_address = game_base + 0x0BDE430
        dispatcher_size = 0x2A1
        dispatcher_raw = reader.read(dispatcher_address, dispatcher_size, executable=True)
        dispatcher_again = reader.read(dispatcher_address, dispatcher_size, executable=True)
        dispatcher_code = {
            "rva": "0xBDE430", "address": hex(dispatcher_address),
            "size": dispatcher_size, "sha256": digest(dispatcher_raw),
            "reread_sha256": digest(dispatcher_again),
            "unchanged_on_reread": dispatcher_raw == dispatcher_again,
            "expected_saved_sha256": "ab22276e39bd854e07e369533ff043f1b8c5b9afd03d2da4a81c0b5d219861c5",
        }
        disk_dispatcher = disk_rva_bytes(game["path"], 0x0BDE430, dispatcher_size)
        dispatcher_code.update({
            "disk_raw_sha256": digest(disk_dispatcher),
            "disk_raw_size": len(disk_dispatcher),
            "disk_raw_matches_live": disk_dispatcher == dispatcher_raw,
            "disk_raw_note": "The image file's raw section bytes are compared for diagnostics; no file is changed.",
        })

        # Read the already known API root and its immediate tables.  We do not
        # follow any newly discovered pointer beyond these fixed paths.
        api_field = read_qword(reader, game_base + 0x3326308, "game_api_global")
        config_field = read_qword(reader, game_base + 0x3326340, "game_config_global")
        api_root = int(api_field["value"], 16)
        config_root = int(config_field["value"], 16)
        fixed_fields = [api_field]
        for offset, label in ((0x00, "api_root+0x00"), (0x30, "api_root+0x30"),
                              (0x38, "api_root+0x38"), (0xF8, "api_root+0xF8"),
                              (0x100, "api_root+0x100"), (0xC0, "api_root+0xC0")):
            fixed_fields.append(read_qword(reader, api_root + offset, label))
        table_fields = []
        for row in fixed_fields[2:]:
            value = int(row["value"], 16)
            # Only read fixed, documented subtable slots. A null/non-user value
            # is recorded and not chased.
            if value < 0x10000 or value >= 0x800000000000:
                continue
            if row["label"] == "api_root+0x30":
                table_fields.extend([read_qword(reader, value + 0x18, "api+0x30.table+0x18"),
                                     read_qword(reader, value + 0x38, "api+0x30.table+0x38"),
                                     read_qword(reader, value + 0x40, "api+0x30.table+0x40")])
            elif row["label"] == "api_root+0xF8":
                table_fields.extend([read_qword(reader, value + 0xA0, "api+0xF8.table+0xA0"),
                                     read_qword(reader, value + 0xA8, "api+0xF8.table+0xA8")])

        # Inspect exactly one 4 KiB page at the already-established API root.
        # This records candidate object pointers without treating any of them
        # as callable or as a dispatcher.  A one-level 64-byte reread is
        # allowed only for pointers outside loaded images and is fail-closed.
        root_page = api_root & ~(PAGE - 1)
        root_raw = reader.read(root_page, PAGE, executable=False)
        loaded_ranges = [(int(m["base"]), int(m["base"]) + int(m["size"]), name)
                         for name, m in ((Path(m["path"]).name.lower(), m) for m in modules)]

        def owner_name(value: int) -> str:
            for low, high, name in loaded_ranges:
                if low <= value < high:
                    return name
            return "outside_loaded_images"

        api_object_qwords = []
        followed = []
        for offset in range(0, PAGE, 8):
            value = int.from_bytes(root_raw[offset:offset + 8], "little")
            if not (0x10000 <= value < 0x800000000000):
                continue
            owner = owner_name(value)
            row = {"offset": hex(offset), "address": hex(root_page + offset),
                   "value": hex(value), "owner": owner}
            api_object_qwords.append(row)
            if owner == "outside_loaded_images" and len(followed) < 64:
                try:
                    probe = reader.read(value, 64, executable=False)
                except (ValueError, OSError):
                    continue
                followed.append({"value": hex(value), "sha256_64_bytes": digest(probe),
                                 "first_qword": hex(int.from_bytes(probe[:8], "little"))})

        # The existing probe also exposes a configuration-root pointer. Read
        # only its page and a bounded 64 KiB neighborhood; this is the one
        # private object path justified by saved evidence, and is where a
        # writable runtime registry would most plausibly be referenced.
        config_page = config_root & ~(PAGE - 1)
        config_neighborhood_hits = []
        config_pages_read = 0
        config_start = config_page
        config_end = config_page + 0x10000
        config_root_raw = reader.read(config_page, PAGE, executable=False)
        config_root_qwords = []
        for offset in range(0, PAGE, 8):
            value = int.from_bytes(config_root_raw[offset:offset + 8], "little")
            if 0x10000 <= value < 0x800000000000:
                config_root_qwords.append({"offset": hex(offset), "value": hex(value),
                                           "owner": owner_name(value)})
        config_patterns = {name: struct.pack("<Q", game_base + rva)
                           for name, rva in TARGETS.items()}
        config_patterns["confirmed_peer_event_hash"] = struct.pack("<I", EVENT_HASH)
        cursor = config_start
        while cursor < config_end:
            try:
                raw = reader.read(cursor, PAGE, executable=False)
            except (ValueError, OSError):
                cursor += PAGE
                continue
            config_pages_read += 1
            for name, pattern in config_patterns.items():
                offset = 0
                while True:
                    found = raw.find(pattern, offset)
                    if found < 0:
                        break
                    config_neighborhood_hits.append({"pattern": name,
                                                     "address": hex(cursor + found),
                                                     "page": hex(cursor)})
                    offset = found + 1
            cursor += PAGE

        patterns = {name: struct.pack("<Q", game_base + rva)
                    for name, rva in TARGETS.items()}
        patterns["confirmed_peer_event_hash"] = struct.pack("<I", EVENT_HASH)
        hits: list[dict] = []
        page_count = 0
        for module_name in ("helldivers2.exe", "game.dll"):
            page_count += scan_image(reader, module_name, selected[module_name], patterns, hits)

        # Re-read each unique hit page so the pointer/hash observation is
        # explicitly marked stable.  The output does not infer registration.
        pages = sorted({(h["module"], h["page"]) for h in hits})
        stable_pages = []
        for module_name, page_hex in pages:
            page = int(page_hex, 16)
            raw = reader.read(page, PAGE, executable=False)
            stable_pages.append({"module": module_name, "page": page_hex,
                                 "sha256_reread": digest(raw)})
        base.verify_loaded(reader, selected)
        result = {
            "schema": "hd2_live_dispatcher_data_capture_v1",
            "build": base.BUILD,
            "pid": pid,
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "scope": "authorized read-only fixed-path API/data scan; no calls, writes, hooks, install, or pointer-following outside listed paths",
            "pinned_images": selected,
            "fixed_api_path": {
                "global_rva": "0x3326308",
                "api_root": hex(api_root),
                "config_global_rva": "0x3326340",
                "config_root": hex(config_root),
                "fields": fixed_fields,
                "table_fields": table_fields,
                "root_page": hex(root_page),
                "root_page_sha256": digest(root_raw),
                "api_object_qwords": api_object_qwords,
                "outside_image_pointer_probes": followed,
                "config_neighborhood": {
                    "start": hex(config_start), "end": hex(config_end),
                    "pages_read": config_pages_read,
                    "root_page": hex(config_page),
                    "root_page_sha256": digest(config_root_raw),
                    "root_qwords": config_root_qwords,
                    "pattern_hits": config_neighborhood_hits,
                },
            },
            "generic_send_dispatcher_code": dispatcher_code,
            "target_functions": {name: {"module": "game.dll", "rva": hex(rva),
                                         "live_address": hex(game_base + rva)}
                                  for name, rva in TARGETS.items()},
            "patterns": {name: {"length": len(pattern), "sha256": digest(pattern)}
                          for name, pattern in patterns.items()},
            "hits": hits,
            "stable_hit_pages": stable_pages,
            "scan_stats": {"pages_read": page_count, "hit_pages": len(pages),
                            "memory_bytes_read": reader.used},
            "read_only": True,
            "calls_made": False,
            "writes_made": False,
            "hooks_installed": False,
            "resolver_closed": False,
            "eight_player_verified": False,
            "limitations": [
                "The fixed API fields are observed but not invoked; their ABI and service semantics are not proved.",
                "A pointer to 0xBABA80 in a static callback run does not prove hash-to-receiver registration.",
                "Only pinned executable image ranges were scanned; heap/private writable registries may be outside this capture.",
                "No player creation, Party/PlayFab result, network frame, or multiplayer mission was tested.",
            ],
        }
        output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return result
    finally:
        reader.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("refusing to overwrite output")
    result = scan(args.pid, args.output)
    counts = {}
    for row in result["hits"]:
        counts[row["pattern"]] = counts.get(row["pattern"], 0) + 1
    print(json.dumps({"output": str(args.output), "hits": counts,
                      "pages": result["scan_stats"]["pages_read"]}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as error:
        print("Stopped: " + str(error), file=sys.stderr)
        raise SystemExit(1)
