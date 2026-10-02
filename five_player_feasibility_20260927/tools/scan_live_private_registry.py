"""Bounded read-only scan of committed private memory for dispatcher anchors.

This is a negative/positive evidence tool, not an injector.  It opens an
explicit fixed-build PID with query/read rights and scans at most 128 MiB of
readable MEM_PRIVATE pages for qword pointers to the recovered receiver and
member functions plus the confirmed-peer event hash.  It never invokes code,
writes memory, follows pointers, or loads a module.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import sys
import ctypes as C
from ctypes import wintypes as W

import interface_probe as base


SCAN_LIMIT = 128 * 1024 * 1024
# Leave headroom for build verification and stable-page rereads in the
# underlying reader's hard budget.
MAX_READ = 160 * 1024 * 1024
PAGE = 0x1000
READABLE = {0x02, 0x04, 0x08, 0x20, 0x40, 0x80}
MEM_COMMIT, MEM_PRIVATE = 0x1000, 0x20000


class MEMORY_BASIC_INFORMATION(C.Structure):
    _fields_ = [
        ("base", C.c_void_p), ("allocation", C.c_void_p),
        ("allocation_protect", W.DWORD), ("partition", W.WORD),
        ("size", C.c_size_t), ("state", W.DWORD),
        ("protect", W.DWORD), ("kind", W.DWORD),
    ]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def scan(pid: int, output: Path) -> dict:
    base.READ_BUDGET = MAX_READ
    reader = base.WindowsReader(pid)
    try:
        executable = reader.executable()
        modules = reader.modules()
        selected = base.check_files(modules, executable)
        base.verify_loaded(reader, selected)
        game = selected["game.dll"]
        game_base = int(game["base"])
        patterns = {
            "confirmed_peer_receiver": struct.pack("<Q", game_base + 0x0BABA80),
            "confirmed_peer_insert": struct.pack("<Q", game_base + 0x0B90B20),
            "platform_member_consumer": struct.pack("<Q", game_base + 0x1093590),
            "platform_member_state_update": struct.pack("<Q", game_base + 0x10937A0),
            "confirmed_peer_event_hash": struct.pack("<I", 0x4804FCF4),
        }
        kernel = reader.k
        kernel.VirtualQueryEx.argtypes = [W.HANDLE, C.c_void_p, C.c_void_p, C.c_size_t]
        kernel.VirtualQueryEx.restype = C.c_size_t
        address = 0x10000
        consumed = 0
        regions = 0
        pages = 0
        hits: list[dict] = []
        while address < 0x800000000000 and consumed < SCAN_LIMIT:
            info = MEMORY_BASIC_INFORMATION()
            size = kernel.VirtualQueryEx(reader.handle, C.c_void_p(address), C.byref(info), C.sizeof(info))
            if size != C.sizeof(info) or not info.size:
                break
            base_addr = int(info.base)
            end = base_addr + int(info.size)
            if info.state == MEM_COMMIT and info.kind == MEM_PRIVATE and (info.protect & 0xFF) in READABLE and not (info.protect & 0x100):
                regions += 1
                cursor = base_addr
                while cursor < end and consumed < SCAN_LIMIT:
                    amount = min(PAGE, end - cursor, SCAN_LIMIT - consumed)
                    try:
                        raw = reader.read(cursor, amount, executable=False)
                    except (ValueError, OSError):
                        cursor += amount
                        continue
                    consumed += len(raw)
                    pages += 1
                    for name, pattern in patterns.items():
                        offset = 0
                        while True:
                            found = raw.find(pattern, offset)
                            if found < 0:
                                break
                            hits.append({"pattern": name, "address": hex(cursor + found),
                                         "region": hex(base_addr),
                                         "region_size": hex(int(info.size)),
                                         "protection": hex(int(info.protect)),
                                         "offset": hex(found)})
                            offset = found + 1
                    cursor += amount
            address = end

        # Re-read pages containing hits and record a digest; no hit is treated
        # as a registration proof without an independent owner/ABI trace.
        stable = []
        for page in sorted({int(h["address"], 16) & ~(PAGE - 1) for h in hits}):
            try:
                raw = reader.read(page, PAGE, executable=False)
            except (ValueError, OSError):
                continue
            stable.append({"page": hex(page), "sha256_reread": digest(raw)})
        base.verify_loaded(reader, selected)
        result = {
            "schema": "hd2_live_private_registry_scan_v1",
            "build": base.BUILD,
            "pid": pid,
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "scope": "authorized read-only bounded MEM_PRIVATE scan; no calls, writes, hooks, install, or pointer following",
            "pinned_images": selected,
            "patterns": {name: {"length": len(pattern), "sha256": digest(pattern)}
                          for name, pattern in patterns.items()},
            "hits": hits,
            "stable_hit_pages": stable,
            "scan_stats": {"private_regions": regions, "pages_read": pages,
                            "memory_bytes_read": consumed, "limit_bytes": SCAN_LIMIT,
                            "truncated": consumed >= SCAN_LIMIT},
            "read_only": True,
            "calls_made": False,
            "writes_made": False,
            "hooks_installed": False,
            "resolver_closed": False,
            "eight_player_verified": False,
            "limitations": [
                "The bounded scan covers only the first 128 MiB of readable private regions in VirtualQueryEx address order.",
                "A pointer/hash hit is not a registration proof without table ownership and dispatch ABI evidence.",
                "No function was invoked and no network/player lifecycle was exercised.",
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
                      "stats": result["scan_stats"]}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as error:
        print("Stopped: " + str(error), file=sys.stderr)
        raise SystemExit(1)
