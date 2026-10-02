"""Bounded read-only capture of the live session-member native sites.

This utility reads only fixed game.dll RVAs from an explicitly supplied PID.
It verifies the executable and game.dll fingerprints before and after the
reads, and never calls code, follows pointers, writes memory, loads a DLL, or
installs a hook.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import interface_probe as base


SITES = (
    (0x108BC70, 0x1000, "host_join_runtime"),
    (0x1092E60, 0x1000, "platform_member_enumerator"),
    (0x1093590, 0x1000, "platform_member_consumer"),
    (0x10936E0, 0x1000, "platform_member_leaf_reader"),
    (0x10937A0, 0x1000, "platform_member_state_update_prefix"),
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def capture(pid: int) -> dict:
    reader = base.WindowsReader(pid)
    try:
        executable = reader.executable()
        modules = reader.modules()
        selected = base.check_files(modules, executable)
        base.verify_loaded(reader, selected)
        game = selected["game.dll"]
        rows = []
        for rva, size, name in SITES:
            address = game["base"] + rva
            first = reader.read(address, size, executable=True)
            second = reader.read(address, size, executable=True)
            base.require(first == second, f"site changed during reread: {hex(rva)}")
            rows.append({
                "module": "game",
                "rva": hex(rva),
                "name": name,
                "address": hex(address),
                "size": size,
                "sha256": digest(first),
                "reread_sha256": digest(second),
                "unchanged_on_reread": True,
                "bytes": first.hex(),
            })
        base.require(reader.executable() == executable and reader.modules() == modules,
                     "process image/module list changed")
        base.require(base.check_files(modules, executable) == selected,
                     "disk identity changed")
        return {
            "schema": "hd2_session_member_site_capture_v1",
            "pid": pid,
            "build": base.BUILD,
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "scope": "authorized read-only live process memory capture; five fixed game.dll sites; no writes, calls, hooks, injection, or pointer following",
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
