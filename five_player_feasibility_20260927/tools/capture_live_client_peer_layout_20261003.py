"""Bounded read-only capture of the fixed-build client peer layout.

The capture follows only the already pinned owner -> client offset and reads
the documented four 0x20-byte records plus the adjacent four 0x10-byte table.
It never calls a game function, follows an unknown pointer, writes memory, or
installs a hook.  This is runtime layout evidence, not an eight-player claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from datetime import datetime, timezone
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from interface_probe import BUILD, WindowsReader, check_files, pointer, verify_loaded  # noqa: E402

CONTEXT_PTR_RVA = 0x347CEF0
SESSION_OFFSET = 0xB390
CLIENT_OFFSET = 0x162C8
PEER_COUNT_OFFSET = 0xC8
PEER_RECORD_OFFSET = 0xD0
PEER_STRIDE = 0x20
PEER_INDEX_OFFSET = 0x14
ADJACENT_OFFSET = 0x150
ADJACENT_STRIDE = 0x10
ADJACENT_COUNT = 4
RECORD_COUNT = 4


def u64(raw: bytes) -> int:
    return struct.unpack("<Q", raw)[0]


def u32(raw: bytes) -> int:
    return struct.unpack("<I", raw)[0]


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read(reader: WindowsReader, address: int, size: int, label: str) -> bytes:
    if size <= 0 or size > 4096:
        raise ValueError(f"invalid_read_size:{label}")
    return reader.read(pointer(address), size)


def capture(pid: int) -> dict:
    reader = WindowsReader(pid)
    try:
        executable = reader.executable()
        modules = reader.modules()
        selected = check_files(modules, executable)
        verify_loaded(reader, selected)
        game_base = selected["game.dll"]["base"]
        context = u64(read(reader, game_base + CONTEXT_PTR_RVA, 8, "context_global"))
        if not context:
            raise ValueError("context_null")
        owner = u64(read(reader, context + SESSION_OFFSET, 8, "session_owner"))
        if not owner:
            raise ValueError("session_owner_null")
        client = owner + CLIENT_OFFSET
        count = u32(read(reader, client + PEER_COUNT_OFFSET, 4, "client_peer_count"))
        if count > 4:
            raise ValueError(f"client_peer_count_over_documented_layout:{count}")
        records_raw = read(reader, client + PEER_RECORD_OFFSET, RECORD_COUNT * PEER_STRIDE, "client_peer_records")
        adjacent_raw = read(reader, client + ADJACENT_OFFSET, ADJACENT_COUNT * ADJACENT_STRIDE, "adjacent_table")
        records = []
        for index in range(RECORD_COUNT):
            row = records_raw[index * PEER_STRIDE:(index + 1) * PEER_STRIDE]
            records.append({
                "ordinal": index,
                "network_index": u32(row[PEER_INDEX_OFFSET:PEER_INDEX_OFFSET + 4]),
                "raw_sha256": sha(row),
                "raw_hex": row.hex(),
            })
        adjacent = [
            {"ordinal": index, "raw_sha256": sha(adjacent_raw[index * ADJACENT_STRIDE:(index + 1) * ADJACENT_STRIDE]),
             "raw_hex": adjacent_raw[index * ADJACENT_STRIDE:(index + 1) * ADJACENT_STRIDE].hex()}
            for index in range(ADJACENT_COUNT)
        ]
        result = {
            "schema": "hd2_live_client_peer_layout_v1",
            "build": BUILD,
            "pid": pid,
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "scope": "authorized bounded read-only owner/client layout fields; no calls, writes, hooks, injection, or unknown pointer traversal",
            "pinned_images": selected,
            "game_base": hex(game_base),
            "roots": {"context": hex(context), "session_owner": hex(owner), "client": hex(client)},
            "offsets": {"client": hex(CLIENT_OFFSET), "count": hex(PEER_COUNT_OFFSET), "records": hex(PEER_RECORD_OFFSET), "record_stride": hex(PEER_STRIDE), "index": hex(PEER_INDEX_OFFSET), "adjacent": hex(ADJACENT_OFFSET), "adjacent_stride": hex(ADJACENT_STRIDE)},
            "peer_count": count,
            "records": records,
            "adjacent_table": adjacent,
            "raw_windows": {"records_sha256": sha(records_raw), "adjacent_sha256": sha(adjacent_raw)},
            "read_only": True,
            "calls_made": False,
            "writes_made": False,
            "hooks_installed": False,
            "runtime_verified": False,
            "installable": False,
            "multiplayer_verified": False,
        }
        result["snapshot_sha256"] = sha(json.dumps(result, sort_keys=True, ensure_ascii=False).encode())
        return result
    finally:
        reader.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("refusing_to_overwrite_output")
    try:
        result = capture(args.pid)
    except Exception as exc:
        result = {"schema": "hd2_live_client_peer_layout_v1", "build": BUILD, "pid": args.pid,
                  "status": "blocked", "error": f"{type(exc).__name__}:{exc}", "read_only": True,
                  "calls_made": False, "writes_made": False, "multiplayer_verified": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "status": result.get("status", "observed"), "peer_count": result.get("peer_count")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
