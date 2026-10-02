"""Bounded read-only capture of six fixed game.dll native sites.

The PID is always explicit.  This tool does not enumerate processes, write
memory, call game code, install hooks, or follow pointers outside the six
fixed 4096-byte ranges.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import interface_probe as base


SITES = (
    (0x108C3D8, "host_index_allocator"),
    (0x1089720, "host_migration_rebuild"),
    (0x108D190, "host_peer_remove"),
    (0x1087540, "client_confirmed_peer_remove"),
    (0x10845B0, "client_confirmed_peer_reset"),
    (0x1086460, "player_creation_gate"),
)
RANGE_SIZE = 4096


def capture(pid: int) -> dict:
    reader = base.WindowsReader(pid)
    try:
        executable = reader.executable()
        modules = reader.modules()
        selected = base.check_files(modules, executable)
        base.verify_loaded(reader, selected)
        game = selected["game.dll"]
        rows = []
        for rva, name in SITES:
            address = game["base"] + rva
            first = reader.read(address, RANGE_SIZE, executable=True)
            second = reader.read(address, RANGE_SIZE, executable=True)
            base.require(first == second, f"site changed during reread: {hex(rva)}")
            rows.append({
                "module": "game",
                "rva": hex(rva),
                "name": name,
                "address": hex(address),
                "size": RANGE_SIZE,
                "sha256": base.digest(first),
                "reread_sha256": base.digest(second),
                "unchanged_on_reread": True,
                "bytes": first.hex(),
            })
        base.require(reader.executable() == executable and reader.modules() == modules,
                     "process image/module list changed")
        base.require(base.check_files(modules, executable) == selected,
                     "disk identity changed")
        return {
            "schema": "hd2_native_site_capture_v1",
            "pid": pid,
            "build": base.BUILD,
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "scope": "authorized read-only live process memory capture; six fixed game.dll sites; no writes, calls, hooks, or pointer following",
            "pinned_images": selected,
            "sites": rows,
            "memory_bytes_read": reader.used,
            "runtime_capture": True,
            "multiplayer_verified": False,
            "mod_installed": False,
        }
    finally:
        reader.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    base.require(0 < args.pid <= 0xFFFFFFFF, "invalid PID")
    base.require(not args.output.exists(), "refusing to overwrite output")
    result = capture(args.pid)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "memory_bytes_read": result["memory_bytes_read"],
        "sites": [{"rva": row["rva"], "sha256": row["sha256"]} for row in result["sites"]],
    }))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print("Stopped: " + str(error), file=sys.stderr)
        raise SystemExit(1)
