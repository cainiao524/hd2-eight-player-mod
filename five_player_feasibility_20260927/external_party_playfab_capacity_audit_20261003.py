"""Audit the public Party and PlayFab client boundaries for the fixed build.

This is a deterministic, read-only file audit.  It does not load a DLL, call an
API, alter a process, or infer that a documented service capacity is a game
admission implementation.  The report records only strings and byte hashes
from the installed client libraries and keeps the native game admission gate
as an unresolved boundary.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


BUILD = "25480438"
TARGET_EVENT_HASH_LE = bytes.fromhex("f40c8048")
TARGET_EVENT_HASH_TEXT = b"4804FCF4"
DEFAULT_ROOT = Path(r"F:\Game\Steam\steamapps\common\Helldivers 2\bin")

SPECS = {
    "PartyWin.dll": {
        "strings": [
            b"PartyNetworkGetNetworkConfiguration",
            b"PartyNetworkGetLocalUsers",
            b"PartyNetworkGetEndpoints",
            b"PartyNetworkCreateEndpoint",
            b"PartyNetworkAuthenticateLocalUser",
            b"PartyNetworkConnect",
        ],
        "role": "party_network",
    },
    "PlayFabMultiplayerWin.dll": {
        "strings": [
            b"PFLobbyGetMaxMemberCount",
            b"PFLobbyGetMembers",
            b"PFLobbyAddMember",
            b"provided max member count",
            b"Lobby state change",
        ],
        "role": "playfab_lobby",
    },
}

REFERENCES = [
    "https://learn.microsoft.com/en-us/xbox/playfab/multiplayer/networking/reference/structs/partynetworkconfiguration",
    "https://learn.microsoft.com/en-us/gaming/playfab/sdks/unified-sdk/quickstart-windows-party",
    "https://learn.microsoft.com/en-us/xbox/playfab/multiplayer/networking/reference/classes/partymanager/methods/partymanager_createnewnetwork",
    "https://learn.microsoft.com/en-us/xbox/playfab/multiplayer/lobby/unity-multiplayer-api-reference/playfab.multiplayer/lobby/maxmembercount",
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def matches(data: bytes, needle: bytes) -> list[int]:
    offsets: list[int] = []
    start = 0
    while True:
        pos = data.find(needle, start)
        if pos < 0:
            return offsets
        offsets.append(pos)
        start = pos + 1


def audit(root: Path) -> dict:
    libraries: dict[str, dict] = {}
    all_target_hits: list[dict] = []
    for name, spec in SPECS.items():
        path = root / name
        if not path.is_file():
            raise FileNotFoundError(path)
        data = path.read_bytes()
        string_hits = {
            needle.decode("ascii"): matches(data, needle)
            for needle in spec["strings"]
        }
        target_le = matches(data, TARGET_EVENT_HASH_LE)
        target_text = matches(data, TARGET_EVENT_HASH_TEXT)
        if target_le or target_text:
            all_target_hits.append({
                "library": name,
                "little_endian_offsets": target_le,
                "text_offsets": target_text,
            })
        libraries[name] = {
            "path": str(path),
            "role": spec["role"],
            "size": len(data),
            "sha256": sha256(data),
            "string_hits": string_hits,
            "target_event_hash_little_endian_offsets": target_le,
            "target_event_hash_text_offsets": target_text,
        }
    return {
        "schema": "hd2_external_party_playfab_capacity_audit_v1",
        "build": BUILD,
        "read_only": True,
        "dlls_loaded": False,
        "process_accessed": False,
        "writes_made": False,
        "hooks_installed": False,
        "libraries": libraries,
        "target_event_hash": "0x4804FCF4",
        "target_event_hash_hits": all_target_hits,
        "party_api_exposes_network_configuration": True,
        "party_api_exposes_local_users_and_endpoints": True,
        "playfab_lobby_exposes_max_member_count": True,
        "documented_service_capacity_is_not_game_admission_proof": True,
        "external_service_is_not_proven_four_player_bottleneck": True,
        "game_native_peer_admission_resolved": False,
        "game_native_player_creation_resolved": False,
        "game_native_clamp_still_unresolved": True,
        "installable": False,
        "multiplayer_verified": False,
        "official_references": REFERENCES,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = audit(args.root)
    encoded = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.write:
        if args.output is None:
            raise SystemExit("--write requires --output")
        if args.output.exists():
            raise SystemExit(f"refusing to overwrite output: {args.output}")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8", newline="\n")
    print(json.dumps({
        "schema": result["schema"],
        "build": result["build"],
        "target_event_hash_hits": len(result["target_event_hash_hits"]),
        "installable": result["installable"],
        "multiplayer_verified": result["multiplayer_verified"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
