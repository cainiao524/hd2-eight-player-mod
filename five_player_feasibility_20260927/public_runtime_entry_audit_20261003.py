#!/usr/bin/env python3
"""Deterministic, offline audit of public HD2 runtime entry points.

This script only reads checked-in public snapshots and the existing capture
fixture.  It never opens a process, installs a mod, writes memory, or calls a
game/runtime API.  The generated JSON is a capability/boundary report, not a
multiplayer result.

Run from the repository root with::

    python five_player_feasibility_20260927/public_runtime_entry_audit_20261003.py --write

The optional ``--write`` flag writes the deterministic report next to this
script.  Without it the report is printed to stdout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = Path(__file__).with_name("public_runtime_entry_audit_20261003.json")

GAME_SHA = "2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e"
EXE_SHA = "f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06"
CAPTURE_SHA = "31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d"


def path(rel: str) -> Path:
    p = ROOT / rel
    if not p.is_file():
        raise AssertionError(f"missing source fixture: {rel}")
    return p


def text(rel: str) -> str:
    return path(rel).read_text(encoding="utf-8")


def load_json(rel: str) -> Any:
    return json.loads(text(rel))


def sha256_file(rel: str) -> str:
    h = hashlib.sha256()
    with path(rel).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def source_record(rel: str) -> dict[str, Any]:
    p = path(rel)
    return {"path": rel, "bytes": p.stat().st_size, "sha256": sha256_file(rel)}


def contains(rel: str, *needles: str) -> None:
    body = text(rel)
    for needle in needles:
        if needle not in body:
            raise AssertionError(f"{rel}: missing exact source marker {needle!r}")


def capture_bytes(report: dict[str, Any], data: bytes, rva: int, size: int) -> bytes:
    """Read a contiguous RVA range from the P11CAP02 chunked payload."""
    remaining = size
    cursor = rva
    result = bytearray()
    chunks = sorted(report["chunks"], key=lambda c: c["rva"])
    while remaining:
        hit = next(
            (
                c
                for c in chunks
                if c["rva"] <= cursor < c["rva"] + c["size"]
            ),
            None,
        )
        if hit is None:
            raise AssertionError(f"capture has no chunk at RVA 0x{cursor:X}")
        take = min(remaining, hit["rva"] + hit["size"] - cursor)
        start = hit["file_offset"] + (cursor - hit["rva"])
        result.extend(data[start : start + take])
        if len(result) != size - remaining + take:
            raise AssertionError("capture chunk bounds are inconsistent")
        cursor += take
        remaining -= take
    return bytes(result)


def package_proof() -> dict[str, Any]:
    spec_rel = "public_research_20261002/_clones/HD2Runtime/research/package-residency-F5FEE03DCFDB.json"
    capture_rel = "evidence/existing-code-evidence-25480438/capture-report.json"
    data_rel = "evidence/existing-code-evidence-25480438/captured-data.bin"
    spec = load_json(spec_rel)
    cap = load_json(capture_rel)
    payload = path(data_rel).read_bytes()
    if hashlib.sha256(payload).hexdigest() != CAPTURE_SHA:
        raise AssertionError("captured-data.bin SHA-256 changed")
    if cap["build_id"] != 25480438 or cap["game_sha256"].lower() != GAME_SHA:
        raise AssertionError("capture build fingerprint changed")
    if cap["capture_complete"] is not True or cap["readable_complete"] is not True:
        raise AssertionError("capture is not complete/readable")

    loader = spec["loader"]["gameDll"]
    expected = {
        "requestRva": 0x12FE350,
        "releaseRva": 0x12FE4E0,
        "instanceGlobalRva": 0x347CEB0,
        "engineLoadSlot": 0x2F0,
        "engineUnloadSlot": 0x300,
    }
    for key, value in expected.items():
        if loader[key] != value:
            raise AssertionError(f"package ABI {key} changed: {loader[key]!r}")

    out: dict[str, Any] = {
        "build": spec["build"],
        "source_spec": source_record(spec_rel),
        "capture_report": source_record(capture_rel),
        "capture_payload": {
            **source_record(data_rel),
            "sha256_pinned": CAPTURE_SHA,
            "bytes": len(payload),
        },
        "request": {
            "rva": loader["requestRva"],
            "rva_hex": f"0x{loader['requestRva']:X}",
            "proof_bytes": len(loader["requestProof"]) // 2,
            "proof_sha256": hashlib.sha256(bytes.fromhex(loader["requestProof"])).hexdigest(),
            "capture_matches": False,
        },
        "release": {
            "rva": loader["releaseRva"],
            "rva_hex": f"0x{loader['releaseRva']:X}",
            "proof_bytes": len(loader["releaseProof"]) // 2,
            "proof_sha256": hashlib.sha256(bytes.fromhex(loader["releaseProof"])).hexdigest(),
            "capture_matches": False,
        },
        "abi": {
            "request": "void(instance, const uint64_t*, uint32_t count)",
            "release": "void(instance, const uint64_t*, uint32_t count)",
            "instance_global_rva_hex": f"0x{loader['instanceGlobalRva']:X}",
            "engine_load_vtable_slot_hex": f"0x{loader['engineLoadSlot']:X}",
            "engine_unload_vtable_slot_hex": f"0x{loader['engineUnloadSlot']:X}",
            "refcount_map": loader["refcountMap"],
            "scope": "local package residency/loadout assets only",
        },
    }
    for key, rva, proof in (
        ("request", loader["requestRva"], loader["requestProof"]),
        ("release", loader["releaseRva"], loader["releaseProof"]),
    ):
        observed = capture_bytes(cap, payload, rva, len(proof) // 2)
        if observed.hex().lower() != proof.lower():
            raise AssertionError(f"package {key} proof does not match capture")
        out[key]["capture_matches"] = True
        out[key]["captured_sha256"] = hashlib.sha256(observed).hexdigest()
    return out


def build_report() -> dict[str, Any]:
    runtime_natives = "public_research_20261002/_clones/HD2Runtime/domains/event_natives.lua"
    runtime_world = "public_research_20261002/_clones/HD2Runtime/runtime/event_world.lua"
    runtime_events = "public_research_20261002/_clones/HD2Runtime/docs/events.md"
    runtime_api = "public_research_20261002/_clones/HD2Runtime/api/hd2.lua"
    runtime_write = "public_research_20261002/_clones/HD2Runtime/runtime/windows_write.lua"
    runtime_assets = "public_research_20261002/_clones/HD2Runtime/core/assets.lua"
    lobby_game = "public_research_20261002/_clones/BetterLobbyManagement/src/game.lua"
    lobby_tech = "public_research_20261002/_clones/BetterLobbyManagement/docs/TECHNICAL.md"
    loader = "public_research_20261002/BingusSharedLoader/src/shared_loader.lua"
    loader_tech = "public_research_20261002/BingusSharedLoader/docs/TECHNICAL.md"
    chusky_readme = "public_research_20261002/CChusky_hd2_tools/README.md"
    chusky_watcher = "public_research_20261002/CChusky_hd2_tools/hook/watcher.c"
    chusky_injector = "public_research_20261002/CChusky_hd2_tools/hook/dll_injector.c"
    avatar = "public_research_20261002/Darctor_Helldivers2_RawData/Data/entities/AvatarComponentData.json"
    raw_map = "public_research_20261002/Darctor_Helldivers2_RawData/Data/settings/EntityComponentMap.json"
    old_map = "public_research_20261002/shalzuth_HelldiversData/data/entities/EntityComponentMap.json"
    net_data = "public_research_20261002/shalzuth_HelldiversData/data/components/EntityNetworkData.json"
    net_array = "public_research_20261002/shalzuth_HelldiversData/data/components/EntityNetworkDataArray.json"
    net_override = "public_research_20261002/shalzuth_HelldiversData/data/components/NetworkOverrideComponent.json"
    teleporter = "public_research_20261002/shalzuth_HelldiversData/data/components/ShipTeleporterComponent.json"

    contains(runtime_natives, '["maxPlayers"]=4', '["peerStride"]=56', '["gameDllSha256"]')
    contains(runtime_world, "function M.players(world,with_avatars)", "count>P.maxPlayers", "function M.network_entity")
    contains(runtime_events, "HD2PlayerHandle", "valid while the peer is in the player list")
    contains(runtime_api, "READ_ONLY_MILESTONE", "No gameplay writer is included")
    contains(runtime_write, "void (*)(void *, const uint64_t *, uint32_t)", "runtime.package_request")
    contains(runtime_assets, "loader.requestRva", "RefcountedPackageSystem request", "runtime.package_request")
    contains(lobby_game, "G.ROSTER_PTR = 0x347ced8", "G.PEER_COUNT, G.PEERS, G.PEER_STRIDE, G.PEER_INDEX = 0x16390, 0x16398, 32, 20", "G.MAX_PEERS = 4")
    contains(lobby_tech, "fewer than 4 players", "the game's own player-menu KICK")
    contains(loader, "application.can_get('lua', name)", "pcall(require, name)")
    contains(loader_tech, "does not own", "performs no process-memory writes", "cannot establish")
    contains(chusky_readme, "pure data capture", "shared memory `Local\\HD2RaycastShm`")
    contains(chusky_watcher, "auto-inject", "WriteProcessMemory", "CreateRemoteThread")
    contains(chusky_injector, "OpenProcess", "WriteProcessMemory", "CreateRemoteThread")

    raw = load_json(raw_map)[0]["EntityComponentMap"]
    avatar_data = load_json(avatar)
    logical_hash = "14826404319954434690"
    avatar_hash = "5556372446766824087"
    logical = next(e for e in raw["entities"] if e["hash"] == logical_hash)
    avatar_entity = next(e for e in raw["entities"] if e["hash"] == avatar_hash)
    if len(logical["components"]) != 9 or len(avatar_entity["components"]) != 49:
        raise AssertionError("RawData Player/Avatar component counts changed")
    av_entry = avatar_data["entities"][0]["0x4D1C334D294DFA97"]
    if av_entry["hash"] != avatar_hash or av_entry["name"] != "Player Clone (Avatar)":
        raise AssertionError("RawData avatar identity changed")
    old = load_json(old_map)
    if 222 not in old[logical_hash] or 18 not in old[avatar_hash]:
        raise AssertionError("historical Player/Avatar component IDs changed")
    network = load_json(net_data)["EntityNetworkData"]
    network_array = load_json(net_array)["EntityNetworkDataArray"]["entities"]
    override = load_json(net_override)["NetworkOverrideComponent"]
    if set(network) != {"game_object_id", "settings_hashmap_index"}:
        raise AssertionError("EntityNetworkData schema changed")
    if network_array != {"type": "array", "subtype": "EntityNetworkData"}:
        raise AssertionError("EntityNetworkDataArray is no longer a dynamic array schema")
    if "dummy" not in override:
        raise AssertionError("NetworkOverrideComponent schema changed")
    tele = load_json(teleporter)["ShipTeleporterComponent"]
    if not {"charge_time", "spawn_time", "cooldown_time"}.issubset(tele):
        raise AssertionError("ShipTeleporterComponent timing schema changed")

    source_paths = [
        runtime_natives, runtime_world, runtime_events, runtime_api, runtime_write, runtime_assets,
        lobby_game, lobby_tech, loader, loader_tech, chusky_readme, chusky_watcher,
        chusky_injector, avatar, raw_map, old_map, net_data, net_array, net_override, teleporter,
    ]
    source_paths = sorted(set(source_paths))

    claims = [
        {
            "id": "runtime_player_reader",
            "status": "supported_observation_only",
            "claim": "HD2Runtime exposes a build-pinned reader for the current player list and resolves avatar network IDs; its generated profile rejects count > 4.",
            "evidence": [runtime_natives, runtime_world, runtime_events],
            "does_not_prove": ["peer admission", "player-slot insertion", "confirmed-peer creation", "network entity spawn"],
        },
        {
            "id": "public_package_native_abi",
            "status": "supported_local_asset_only",
            "claim": "The exact request/release byte pins and typed FFI call are reproducible against the existing capture, but the ABI requests/releases local RefcountedPackageSystem loadout packages.",
            "evidence": [runtime_write, runtime_assets, "public_research_20261002/_clones/HD2Runtime/research/package-residency-F5FEE03DCFDB.json", "evidence/existing-code-evidence-25480438/captured-data.bin"],
            "does_not_prove": ["Party/PlayFab admission", "peer index 4..7", "remote player entity replication"],
        },
        {
            "id": "better_lobby_boundary",
            "status": "supported_four_slot_reader",
            "claim": "Better Lobby Management documents a four-entry roster and MAX_PEERS=4; its public native wrappers kick or initiate normal joins, not append confirmed peers.",
            "evidence": [lobby_game, lobby_tech],
            "does_not_prove": ["capacity expansion", "safe fifth-player insertion", "host migration with extra peers"],
        },
        {
            "id": "loader_boundary",
            "status": "supported_loader_only",
            "claim": "Bingus Shared Loader discovers Lua resources and requires modules; its own technical notes state it performs no process-memory writes and cannot establish multiplayer compatibility.",
            "evidence": [loader, loader_tech],
            "does_not_prove": ["session admission", "peer allocation", "roster mutation"],
        },
        {
            "id": "observer_hook_boundary",
            "status": "observer_with_injection_hazard",
            "claim": "CChusky hd2-tools exposes entity/raycast capture over shared memory, while its watcher/injector source uses process injection; no public peer/roster admission API is present in the checked snapshot.",
            "evidence": [chusky_readme, chusky_watcher, chusky_injector],
            "does_not_prove": ["admission ABI", "safe production hook", "eight-player success"],
        },
        {
            "id": "rawdata_player_avatar_distinction",
            "status": "schema_only",
            "claim": "Current RawData separates the logical content/entities/player resource (9 components) from Player Clone (Avatar) (49 components); historical maps also list different component IDs. They must not be treated as one admission structure.",
            "evidence": [raw_map, avatar, old_map, net_data, net_array, net_override],
            "measurements": {
                "logical_player_hash": logical_hash,
                "logical_player_component_count": len(logical["components"]),
                "avatar_hash": avatar_hash,
                "avatar_component_count": len(avatar_entity["components"]),
                "historical_logical_component_ids": old[logical_hash],
                "historical_avatar_component_ids": old[avatar_hash],
            },
            "does_not_prove": ["dynamic peer admission", "network entity replication capacity"],
        },
    ]

    report = {
        "schema": "public-runtime-entry-audit/1",
        "generated_by": Path(__file__).name,
        "scope": "offline public-source and existing-capture audit",
        "build": {
            "steam_build": 25480438,
            "exe_version": "1.8.46015.0",
            "game_dll_sha256": GAME_SHA,
            "exe_sha256": EXE_SHA,
            "runtime_process_accessed": False,
            "mod_installed": False,
            "multiplayer_verified": False,
        },
        "sources": [source_record(rel) for rel in source_paths],
        "package_abi_proof": package_proof(),
        "claims": claims,
        "conclusion": {
            "public_peer_admission_abi_found": False,
            "public_player_creation_writer_found": False,
            "public_network_spawn_writer_found": False,
            "recommended_entry": "Use the package ABI only as a local resource-residency helper. The next real implementation gate is an authorized, version-pinned Session/Party/peer-admission and player-creation path; no checked public snapshot supplies it.",
            "eight_player_status": "unverified",
        },
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="write the deterministic JSON report")
    args = parser.parse_args()
    try:
        report = build_report()
    except Exception as exc:  # keep verifier failures machine-readable on CI
        print(f"PUBLIC_RUNTIME_ENTRY_AUDIT_FAIL: {exc}", file=sys.stderr)
        return 1
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.write:
        REPORT_PATH.write_text(rendered, encoding="utf-8", newline="\n")
        print(f"PUBLIC_RUNTIME_ENTRY_AUDIT_OK: {REPORT_PATH.relative_to(ROOT)}")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
