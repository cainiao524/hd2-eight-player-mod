"""Capture a bounded read-only session/roster snapshot for build 25480438.

Only known global/context fields are read.  The tool never calls a game
function, follows an unknown pointer, writes memory, installs a hook, or
changes the game.  A missing or unreadable context is recorded as a blocked
snapshot rather than guessed as an empty lobby.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from interface_probe import BUILD, HASHES, WindowsReader, check_files, pointer, verify_loaded  # noqa: E402

CONTEXT_PTR_RVA = 0x347CEF0
ROSTER_PTR_RVA = 0x347CED8
GAME_STATE_PTR_RVA = 0x3326340
MODE_OFFSET = 0xAC21C
LOCAL_OFFSET = 0xB398
HOST_OFFSET = 0xB3A8
PEER_COUNT_OFFSET = 0x16390
PEERS_OFFSET = 0x16398
PEER_STRIDE = 0x20
PEER_INDEX_OFFSET = 0x14
ROSTER_STRIDE = 0xC0
ROSTER_ID_OFFSET = 0
ROSTER_NAME_OFFSET = 8
ROSTER_NAME_LIMIT = 0x78
MAX_SLOTS = 8
DOCUMENTED_ROSTER_SLOTS = 4
READ_LIMIT = 32 * 1024


def u32(raw: bytes) -> int:
    return struct.unpack("<I", raw)[0]


def u64(raw: bytes) -> int:
    return struct.unpack("<Q", raw)[0]


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_exact(reader: WindowsReader, address: int, size: int, label: str) -> bytes:
    if size <= 0 or size > 4096:
        raise ValueError(f"invalid_read_size:{label}")
    return reader.read(pointer(address), size)


def read_u64(reader: WindowsReader, address: int, label: str) -> int:
    return u64(read_exact(reader, address, 8, label))


def read_u32(reader: WindowsReader, address: int, label: str) -> int:
    return u32(read_exact(reader, address, 4, label))


def read_peer_table(reader: WindowsReader, context: int, count: int) -> tuple[list[dict], list[str]]:
    if count > MAX_SLOTS:
        return [], [f"peer_count_over_capacity:{count}"]
    peers: list[dict] = []
    errors: list[str] = []
    for ordinal in range(count):
        entry = context + PEERS_OFFSET + ordinal * PEER_STRIDE
        try:
            lo = read_u32(reader, entry, f"peer_{ordinal}_lo")
            hi = read_u32(reader, entry + 4, f"peer_{ordinal}_hi")
            index = read_u32(reader, entry + PEER_INDEX_OFFSET, f"peer_{ordinal}_index")
        except Exception as exc:  # bounded read failure is evidence, not zero
            errors.append(f"peer_read_failed:{ordinal}:{type(exc).__name__}")
            break
        peers.append({"ordinal": ordinal, "lo": lo, "hi": hi, "network_index": index})
    return peers, errors


def read_roster_table(reader: WindowsReader, roster: int) -> tuple[list[dict], list[str]]:
    records: list[dict] = []
    errors: list[str] = []
    # The public fixed-build layout documents four inline roster records.  Do
    # not read slots 4..7 as if they belonged to that object; an adjacent
    # allocation can be readable while still being unrelated state.
    for ordinal in range(DOCUMENTED_ROSTER_SLOTS):
        record = roster + ordinal * ROSTER_STRIDE
        try:
            raw_id = read_exact(reader, record + ROSTER_ID_OFFSET, 8, f"roster_{ordinal}_id")
            name_raw = read_exact(reader, record + ROSTER_NAME_OFFSET, ROSTER_NAME_LIMIT, f"roster_{ordinal}_name")
        except Exception as exc:
            errors.append(f"roster_read_failed:{ordinal}:{type(exc).__name__}")
            break
        name = name_raw.split(b"\0", 1)[0].decode("utf-8", errors="replace")
        records.append({"ordinal": ordinal, "peer_id_hex": raw_id.hex(), "name": name})
    return records, errors


def capture(pid: int) -> dict:
    reader = WindowsReader(pid)
    try:
        executable = reader.executable()
        modules = reader.modules()
        selected = check_files(modules, executable)
        verify_loaded(reader, selected)
        game_base = selected["game.dll"]["base"]
        result: dict = {
            "schema": "hd2_live_session_snapshot_v1",
            "build": BUILD,
            "pid": pid,
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "scope": "authorized bounded read-only session/context/roster fields; no calls, writes, hooks, injection, or unknown pointer traversal",
            "pinned_images": selected,
            "game_base": hex(game_base),
            "read_limit": READ_LIMIT,
            "read_bytes": reader.used,
            "read_only": True,
            "calls_made": False,
            "writes_made": False,
            "hooks_installed": False,
            "status": "blocked_no_context",
            "errors": [],
        }
        try:
            context = read_u64(reader, game_base + CONTEXT_PTR_RVA, "context_global")
            roster = read_u64(reader, game_base + ROSTER_PTR_RVA, "roster_global")
            state = read_u64(reader, game_base + GAME_STATE_PTR_RVA, "game_state_global")
            result["roots"] = {"context": hex(context), "roster": hex(roster), "game_state": hex(state)}
            mode = read_u32(reader, state + MODE_OFFSET, "game_mode") if state else 0
            result["mode"] = mode
            if not context:
                result["errors"].append("context_null")
            else:
                local = read_exact(reader, context + LOCAL_OFFSET, 8, "local_peer")
                host = read_exact(reader, context + HOST_OFFSET, 8, "host_peer")
                raw_count = read_u32(reader, context + PEER_COUNT_OFFSET, "peer_count")
                peers, errors = read_peer_table(reader, context, raw_count)
                result["session"] = {
                    "local_peer_hex": local.hex(),
                    "host_peer_hex": host.hex(),
                    "peer_count_raw": raw_count,
                    "peers": peers,
                }
                result["errors"].extend(errors)
                result["status"] = "observed_context" if not errors else "blocked_partial_context"
            if roster:
                records, errors = read_roster_table(reader, roster)
                result["roster"] = {
                    "documented_slot_count": DOCUMENTED_ROSTER_SLOTS,
                    "records": records,
                    "out_of_contract_slots": list(range(DOCUMENTED_ROSTER_SLOTS, MAX_SLOTS)),
                }
                result["errors"].extend(errors)
            else:
                result["errors"].append("roster_null")
        except Exception as exc:
            result["errors"].append(f"snapshot_read_failed:{type(exc).__name__}:{exc}")
            result["status"] = "blocked_snapshot_read"
        result["read_bytes"] = reader.used
        result["snapshot_sha256"] = digest(json.dumps(result, sort_keys=True, ensure_ascii=False).encode("utf-8"))
        return result
    finally:
        reader.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("refusing_to_overwrite_output")
    try:
        result = capture(args.pid)
    except Exception as exc:
        result = {
            "schema": "hd2_live_session_snapshot_v1",
            "build": BUILD,
            "pid": args.pid,
            "status": "blocked_preflight",
            "error": f"{type(exc).__name__}:{exc}",
            "read_only": True,
            "calls_made": False,
            "writes_made": False,
            "multiplayer_verified": False,
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"output": str(args.output), "status": result.get("status"), "errors": result.get("errors", [])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
