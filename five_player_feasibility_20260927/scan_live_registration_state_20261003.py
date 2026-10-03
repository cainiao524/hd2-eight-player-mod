"""Bounded read-only scan for fixed-build registration anchors.

The scan is evidence collection only. It never calls game code, follows
unknown pointers, changes memory, installs hooks, or loads a module.
"""
from __future__ import annotations

import argparse
import ctypes as C
from ctypes import wintypes as W
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "tools"))
import interface_probe as base

PAGE = 0x1000
READABLE = {2, 4, 8, 0x20, 0x40, 0x80}
MEM_COMMIT, MEM_PRIVATE = 0x1000, 0x20000
STATIC_HASHES = (0xBDE53653, 0x3E3F525A, 0x5DCD723A, 0x19339CD6,
                 0x36334D22, 0x520227A4, 0x068601A2)


class MEMORY_BASIC_INFORMATION(C.Structure):
    _fields_ = [
        ("base", C.c_void_p), ("allocation", C.c_void_p),
        ("allocation_protect", W.DWORD), ("partition", W.WORD),
        ("size", C.c_size_t), ("state", W.DWORD),
        ("protect", W.DWORD), ("kind", W.DWORD),
    ]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def scan_regions(reader, kernel, patterns: dict[str, bytes], limit: int,
                  max_read: int) -> tuple[dict, list[dict], list[dict]]:
    """Scan readable private pages and report exact coverage termination."""
    if callable(kernel):
        query_region = kernel
    else:
        kernel.VirtualQueryEx.argtypes = [W.HANDLE, C.c_void_p, C.c_void_p, C.c_size_t]
        kernel.VirtualQueryEx.restype = C.c_size_t

        def query_region(address):
            info = MEMORY_BASIC_INFORMATION()
            size = kernel.VirtualQueryEx(reader.handle, C.c_void_p(address),
                                         C.byref(info), C.sizeof(info))
            if size != C.sizeof(info):
                return None
            return {"base": int(info.base or 0), "size": int(info.size or 0),
                    "state": int(info.state), "protect": int(info.protect),
                    "kind": int(info.kind)}

    address, consumed, pages, regions = 0x10000, 0, 0, 0
    hits: list[dict] = []
    errors: list[dict] = []
    reason = "address_space_end"
    carry = b""
    previous_end = None
    overlap = max(len(value) for value in patterns.values()) - 1
    while address < 0x800000000000 and consumed < limit:
        info = query_region(address)
        if info is None or not info["size"]:
            errors.append({"phase": "query", "address": hex(address),
                           "error": "VirtualQueryEx_failed"})
            reason = "query_error"
            break
        base_address = info["base"]
        end = base_address + info["size"]
        if not base_address <= address < end:
            errors.append({"phase": "query", "address": hex(address),
                           "error": "invalid_region_extent"})
            reason = "query_error"
            break
        readable = (info["state"] == MEM_COMMIT and info["kind"] == MEM_PRIVATE
                    and (info["protect"] & 0xFF) in READABLE
                    and not (info["protect"] & 0x100))
        if not readable:
            carry, previous_end = b"", None
            address = end
            continue
        regions += 1
        cursor = address
        while cursor < end and consumed < limit:
            amount = min(PAGE, end - cursor, limit - consumed)
            if reader.used + amount + 16384 > max_read:
                errors.append({"phase": "read", "address": hex(cursor),
                               "error": "read_budget_exhausted"})
                reason = "read_budget_exhausted"
                break
            try:
                raw = reader.read(cursor, amount, executable=False)
                if len(raw) != amount:
                    raise ValueError("short_process_read")
            except (ValueError, OSError) as exc:
                errors.append({"phase": "read", "address": hex(cursor),
                               "error": f"{type(exc).__name__}:{exc}"})
                reason = "read_error"
                break
            consumed += len(raw)
            pages += 1
            joined = raw if previous_end != cursor else carry + raw
            carry_len = 0 if previous_end != cursor else len(carry)
            for name, pattern in patterns.items():
                start = 0
                while True:
                    found = joined.find(pattern, start)
                    if found < 0:
                        break
                    if found + len(pattern) > carry_len:
                        hits.append({"pattern": name,
                                     "address": hex(cursor - carry_len + found)})
                    start = found + 1
            carry = joined[-overlap:] if overlap else b""
            previous_end = cursor + amount
            cursor += amount
        if errors:
            break
        address = end
    if not errors and consumed == limit:
        reason = "scan_limit_reached"
    stats = {"private_regions": regions, "pages_read": pages,
             "memory_bytes_read": consumed, "limit_bytes": limit,
             "reader_bytes_used": reader.used, "termination_reason": reason,
             "coverage_complete": reason == "scan_limit_reached" and consumed == limit,
             "truncated": reason != "scan_limit_reached" or consumed != limit}
    return stats, hits, errors


def scan(pid: int, output: Path, limit: int, max_read: int) -> dict:
    if limit <= 0 or max_read < limit + 16384:
        raise ValueError("max_read must leave verification headroom beyond limit")
    old_budget = base.READ_BUDGET
    base.READ_BUDGET = max_read
    reader = base.WindowsReader(pid)
    try:
        executable = reader.executable()
        modules = reader.modules()
        selected = base.check_files(modules, executable)
        base.verify_loaded(reader, selected)
        game_base = int(selected["game.dll"]["base"])
        patterns = {
            "confirmed_peer_receiver_ptr": struct.pack("<Q", game_base + 0xBABA80),
            "confirmed_peer_insert_ptr": struct.pack("<Q", game_base + 0xB90B20),
            "platform_member_consumer_ptr": struct.pack("<Q", game_base + 0x1093590),
            "platform_member_state_update_ptr": struct.pack("<Q", game_base + 0x10937A0),
            "confirmed_peer_event_hash": struct.pack("<I", 0x4804FCF4),
        }
        patterns.update({f"static_registration_hash_{i}": struct.pack("<I", value)
                         for i, value in enumerate(STATIC_HASHES)})
        stats, hits, errors = scan_regions(reader, reader.k, patterns, limit, max_read)
        coverage_complete = stats["coverage_complete"]
        postflight = False
        postflight_details = {}
        try:
            base.verify_loaded(reader, selected)
            current_executable = reader.executable()
            current_modules = reader.modules()
            disk_identity = base.check_files(current_modules, current_executable) == selected
            postflight_details = {
                "executable_unchanged": current_executable == executable,
                "module_list_unchanged": current_modules == modules,
                "disk_identity_unchanged": disk_identity,
            }
            postflight = all(postflight_details.values())
        except (ValueError, OSError) as exc:
            errors.append({"phase": "postflight", "error": f"{type(exc).__name__}:{exc}"})
            postflight_details["exception"] = f"{type(exc).__name__}:{exc}"
        result = {
            "schema": "hd2_live_registration_state_scan_v2",
            "build": base.BUILD, "pid": pid,
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "scope": "authorized read-only bounded MEM_PRIVATE scan; no calls, writes, hooks, injection or installation",
            "pinned_images": selected,
            "patterns": {name: {"length": len(pattern), "sha256": sha256(pattern)}
                         for name, pattern in patterns.items()},
            "hits": hits, "errors": errors,
            "scan_stats": {
                **stats,
            },
            "coverage_complete": coverage_complete,
            "postflight": postflight_details,
            "postflight_verified": postflight,
            "status": "bounded_scan_complete" if coverage_complete else "incomplete",
            "negative_observation_valid": coverage_complete and postflight and not hits,
            "read_only": True, "calls_made": False, "writes_made": False,
            "hooks_installed": False, "hash_to_selector_proven": False,
            "resolver_closed": False, "installable": False,
            "multiplayer_verified": False,
            "meaning": "The result covers only the reported readable private-memory prefix. "
                       "A pattern hit is not ownership proof and a negative scan does not "
                       "prove that no registry exists.",
        }
        output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8", newline="\n")
        return result
    finally:
        reader.close()
        base.READ_BUDGET = old_budget


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit-mib", type=int, default=128)
    parser.add_argument("--max-read-mib", type=int, default=160)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("refusing_to_overwrite_output")
    result = scan(args.pid, args.output, args.limit_mib * 1024 * 1024,
                  args.max_read_mib * 1024 * 1024)
    print(json.dumps({"output": str(args.output), "status": result["status"],
                      "hits": len(result["hits"]), "scan_stats": result["scan_stats"]}))
    return 0 if result["status"] == "bounded_scan_complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
