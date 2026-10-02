"""Emit a read-only, machine-verifiable confirmed-peer external-chain inventory.

This artifact links the fixed-site live captures for host capacity/index allocation,
confirmed-peer send/receive, client append, and player creation.  It is evidence
only: it performs no process access, calls, writes, hooks, or patch generation.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CAPTURE = ROOT / "five_player_feasibility_20260927" / "native_admission_sites_live_20261002_r2.json"
CONFIRMED_CAPTURE = ROOT / "five_player_feasibility_20260927" / "native_admission_confirmed_peer_live_20261002_r3.json"
BUILD = 25480438
EXPECTED_CAPTURE_SHA = ""


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def _read_rows(path: Path, key: str = "sites") -> dict[str, dict]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    rows = doc.get(key, [])
    return {str(row["rva"]).lower(): row for row in rows}


def recover() -> dict:
    main = json.loads(CAPTURE.read_text(encoding="utf-8"))
    confirmed = json.loads(CONFIRMED_CAPTURE.read_text(encoding="utf-8"))
    require(main["build"] == BUILD and confirmed["build"] == BUILD, "capture build mismatch")
    rows = _read_rows(CAPTURE, "rows")
    crows = _read_rows(CONFIRMED_CAPTURE, "rows")
    # The r3 capture supersedes the shorter site window for the sender and records
    # the same fixed-site bytes with a second read consistency check.
    required = {
        "0x108c18f": ("host_capacity_gate", "remaining capacity computes 4-occupied and forwards r8d=4"),
        "0x108c3d8": ("host_index_allocator", "host+0x100 flags scan compares ecx with 4; a second table has r14d<4"),
        "0x108c760": ("host_confirmed_peer_sender", "session+0x20/session+0x40 confirmed-peer tables are stride 0x38 with four-slot loops"),
        "0xb90b20": ("client_confirmed_peer_insert", "client+0xc8 count appends client+0xd0 records with 0x20 stride; fifth append reaches +0x150"),
        "0x1086460": ("player_creation_gate", "player index at owner-relative +0x163ac is rejected when >=4"),
    }
    sites = []
    for rva, (name, semantic) in required.items():
        row = crows.get(rva) if rva == "0x108c760" else rows.get(rva)
        require(row is not None, f"missing capture row {rva}")
        sites.append({
            "rva": rva,
            "name": name,
            "semantic": semantic,
            "source_capture": str((CONFIRMED_CAPTURE if rva == "0x108c760" else CAPTURE).relative_to(ROOT)),
            "source_row_sha256": row["sha256"],
            "size": row["size"],
            "unchanged_on_reread": row.get("unchanged_on_reread", main.get("read_only", False)),
            "read_only": True,
        })
    return {
        "schema": "confirmed_peer_external_chain_v1",
        "status": "static_external_abi_blocker",
        "steam_build": BUILD,
        "capture_integrity": {
            "main_capture": str(CAPTURE.relative_to(ROOT)),
            "main_capture_sha256": sha(CAPTURE),
            "confirmed_capture": str(CONFIRMED_CAPTURE.relative_to(ROOT)),
            "confirmed_capture_sha256": sha(CONFIRMED_CAPTURE),
            "pid": main["pid"],
            "read_only": True,
            "calls_made": False,
            "writes_made": False,
            "hooks_or_injection": False,
        },
        "sites": sites,
        "required_lifecycle_paths": [
            {"rva": "0x108d190", "name": "host_peer_cleanup", "required": "clear sidecar peer record and release owner reservation"},
            {"rva": "0x1089720", "name": "host_migration_rebuild", "required": "rebuild ordinal map preserving holes/generation"},
            {"rva": "0x1087540", "name": "client_confirmed_peer_remove", "required": "remove by owner key and compact only logical map"},
            {"rva": "0x10845b0", "name": "client_confirmed_peer_reset", "required": "reset all eight records without touching adjacent +0x150 fields"},
        ],
        "sidecar_contract": {
            "logical_max_players": 8,
            "valid_network_index": [0, 7],
            "owner_key": "host/session or client owner pointer, never peer ordinal",
            "record_storage": "8 confirmed-peer records and 8 client records, separately owned",
            "must_preserve": ["pending/confirmed transition", "duplicate rejection", "departure/reconnect", "host migration", "serializer/receiver schema", "resource/player creation handles", "unwind and rollback"],
            "reject_if": ["sender-only redirect", "inline client+0x150 overlap", "unknown dispatcher binding", "missing cleanup or migration path", "ordinal/index aliasing"],
            "installable": False,
            "runtime_verified": False,
            "multiplayer_verified": False,
        },
        "blockers": [
            "Host capacity and index allocation are independent four-slot paths.",
            "Client append has a four-record in-object footprint; record five overlaps adjacent live fields.",
            "Player creation rejects index 4 and higher before resource/roster creation.",
            "Cleanup, migration, dispatcher binding, and receiver lifetime are not closed by fixed-site bytes alone.",
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    require(not args.output.exists(), "refusing overwrite")
    result = recover()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "sites": len(result["sites"]), "installable": False}, ensure_ascii=False))

if __name__ == "__main__":
    main()

