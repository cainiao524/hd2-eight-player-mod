"""Verify the external Party/PlayFab capacity audit without loading DLLs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


EXPECTED = {
    "PartyWin.dll": {
        "size": 4031520,
        "sha256": "de34667c2f7084013d9c03cd5d1cb5dc3321bc36bb616a845e35534e4e7995e0",
    },
    "PlayFabMultiplayerWin.dll": {
        "size": 1878048,
        "sha256": "95bc5f958e519f612b479de4227f3bdffaba9b2b8de987eb3f7991960b8ced17",
    },
}


def verify(path: Path) -> dict:
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("schema") != "hd2_external_party_playfab_capacity_audit_v1":
        raise ValueError("unexpected schema")
    if report.get("build") != "25480438":
        raise ValueError("unexpected build")
    for flag in ("read_only", "dlls_loaded", "process_accessed", "writes_made", "hooks_installed"):
        expected = False if flag != "read_only" else True
        if report.get(flag) is not expected:
            raise ValueError(f"unexpected {flag}: {report.get(flag)!r}")
    for name, expected in EXPECTED.items():
        actual = report.get("libraries", {}).get(name)
        if not actual or actual.get("size") != expected["size"] or actual.get("sha256") != expected["sha256"]:
            raise ValueError(f"fingerprint mismatch: {name}")
        if actual.get("target_event_hash_little_endian_offsets") or actual.get("target_event_hash_text_offsets"):
            raise ValueError(f"target event hash unexpectedly present: {name}")
    if report.get("target_event_hash_hits"):
        raise ValueError("target event hash unexpectedly present")
    for flag in (
        "party_api_exposes_network_configuration",
        "party_api_exposes_local_users_and_endpoints",
        "playfab_lobby_exposes_max_member_count",
        "documented_service_capacity_is_not_game_admission_proof",
        "external_service_is_not_proven_four_player_bottleneck",
        "game_native_clamp_still_unresolved",
    ):
        if report.get(flag) is not True:
            raise ValueError(f"expected true: {flag}")
    for flag in ("game_native_peer_admission_resolved", "game_native_player_creation_resolved", "installable", "multiplayer_verified"):
        if report.get(flag) is not False:
            raise ValueError(f"expected false: {flag}")
    return {
        "schema": "hd2_external_party_playfab_capacity_verification_v1",
        "report": str(path),
        "report_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "build": report["build"],
        "libraries": {name: {"size": value["size"], "sha256": value["sha256"]} for name, value in EXPECTED.items()},
        "target_event_hash_hits": 0,
        "read_only": True,
        "installable": False,
        "multiplayer_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite output: {args.output}")
    result = verify(args.report)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"output": str(args.output), "target_event_hash_hits": 0, "installable": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
