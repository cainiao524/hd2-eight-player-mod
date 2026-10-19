"""Fail-closed verifier for a real two-client HD2 lifecycle capture.

The input is a sequence of bounded, read-only ``hd2_live_session_snapshot_v1``
files.  This tool never starts the game, reads a process, calls a game API, or
changes memory.  A passing receipt proves only the requested two-client
lifecycle; it does not prove capacity above two players.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


BUILD = 25480438
EXE_SHA256 = "f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06"
GAME_SHA256 = "2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e"
SCHEMA = "hd2_live_session_snapshot_v1"
PHASES = ("host_before", "joined", "after_leave", "migration_before", "migration_after", "cleanup")


class LifecycleError(ValueError):
    """An input capture cannot prove the requested lifecycle step."""


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LifecycleError(f"cannot_read:{path}") from exc
    if not isinstance(value, dict):
        raise LifecycleError(f"root_not_object:{path}")
    return value


def _image_sha(snapshot: dict[str, Any], module: str) -> str:
    images = snapshot.get("pinned_images")
    if not isinstance(images, dict) or not isinstance(images.get(module), dict):
        raise LifecycleError(f"missing_pinned_image:{module}")
    digest = images[module].get("sha256")
    if not isinstance(digest, str):
        raise LifecycleError(f"missing_image_sha256:{module}")
    return digest


def _peer_id(record: dict[str, Any]) -> str:
    lo = record.get("lo")
    hi = record.get("hi")
    if type(lo) is not int or type(hi) is not int or lo < 0 or hi < 0:
        raise LifecycleError("invalid_peer_record")
    return f"{hi:08x}{lo:08x}"


def _snapshot(path: Path) -> dict[str, Any]:
    data = _load(path)
    if data.get("schema") != SCHEMA:
        raise LifecycleError(f"snapshot_schema_mismatch:{path}")
    if data.get("build") != BUILD:
        raise LifecycleError(f"build_mismatch:{path}")
    if data.get("status") != "observed_context":
        raise LifecycleError(f"snapshot_not_observed_context:{path}")
    if data.get("read_only") is not True or data.get("calls_made") is not False:
        raise LifecycleError(f"snapshot_not_read_only:{path}")
    if data.get("writes_made") is not False or data.get("hooks_installed") is not False:
        raise LifecycleError(f"snapshot_side_effect_flags_invalid:{path}")
    if _image_sha(data, "helldivers2.exe") != EXE_SHA256:
        raise LifecycleError(f"exe_identity_mismatch:{path}")
    if _image_sha(data, "game.dll") != GAME_SHA256:
        raise LifecycleError(f"game_identity_mismatch:{path}")

    session = data.get("session")
    if not isinstance(session, dict):
        raise LifecycleError(f"missing_session:{path}")
    roots = data.get("roots")
    if not isinstance(roots, dict):
        raise LifecycleError(f"missing_roots:{path}")
    root_values = {name: roots.get(name) for name in ("context", "roster", "game_state")}
    if any(not isinstance(value, str) or not value for value in root_values.values()):
        raise LifecycleError(f"invalid_roots:{path}")
    count = session.get("peer_count_raw")
    peers = session.get("peers")
    owner = session.get("session_owner")
    local = session.get("local_peer_hex")
    host = session.get("host_peer_hex")
    if type(count) is not int or count < 0 or not isinstance(peers, list):
        raise LifecycleError(f"invalid_session_count:{path}")
    if count != len(peers):
        raise LifecycleError(f"peer_count_list_mismatch:{path}")
    if not isinstance(owner, str) or not owner or not isinstance(local, str) or not local:
        raise LifecycleError(f"missing_session_identity:{path}")
    if not isinstance(host, str) or not host:
        raise LifecycleError(f"missing_host_identity:{path}")

    peer_ids: set[str] = set()
    indexes: set[int] = set()
    for peer in peers:
        if not isinstance(peer, dict):
            raise LifecycleError(f"invalid_peer_list:{path}")
        peer_id = _peer_id(peer)
        index = peer.get("network_index")
        if peer_id in peer_ids:
            raise LifecycleError(f"duplicate_peer_id:{path}")
        if type(index) is not int or index < 0 or index > 1:
            raise LifecycleError(f"two_client_index_invalid:{path}")
        if index in indexes:
            raise LifecycleError(f"duplicate_network_index:{path}")
        peer_ids.add(peer_id)
        indexes.add(index)

    roster = data.get("roster")
    if not isinstance(roster, dict) or not isinstance(roster.get("records"), list):
        raise LifecycleError(f"missing_roster:{path}")
    roster_ids: set[str] = set()
    for record in roster["records"]:
        if not isinstance(record, dict):
            raise LifecycleError(f"invalid_roster_record:{path}")
        ordinal = record.get("ordinal")
        peer_hex = record.get("peer_id_hex")
        if type(ordinal) is not int or ordinal < 0 or ordinal > 3:
            raise LifecycleError(f"roster_ordinal_invalid:{path}")
        if not isinstance(peer_hex, str) or len(peer_hex) != 16:
            raise LifecycleError(f"roster_peer_id_invalid:{path}")
        if peer_hex != "0000000000000000":
            if peer_hex in roster_ids:
                raise LifecycleError(f"duplicate_roster_peer:{path}")
            roster_ids.add(peer_hex)

    return {
        "path": str(path),
        "pid": data.get("pid"),
        "roots": root_values,
        "session_owner": owner,
        "local_peer": local,
        "host_peer": host,
        "count": count,
        "peer_ids": peer_ids,
        "indexes": indexes,
        "roster_ids": roster_ids,
    }


def _same_process(left: dict[str, Any], right: dict[str, Any], label: str) -> None:
    if left.get("pid") != right.get("pid"):
        raise LifecycleError(f"{label}_pid_changed")
    if left.get("roots") != right.get("roots"):
        raise LifecycleError(f"{label}_game_roots_changed")


def _require_join(phases: dict[str, dict[str, Any]]) -> None:
    before = phases["host_before"]
    joined = phases["joined"]
    _same_process(before, joined, "join")
    if before["count"] != 1 or before["indexes"] != {0}:
        raise LifecycleError("host_before_is_not_one_player")
    if joined["count"] != 2 or joined["indexes"] != {0, 1}:
        raise LifecycleError("joined_is_not_two_players")
    if before["local_peer"] != joined["local_peer"] or before["host_peer"] != joined["host_peer"]:
        raise LifecycleError("host_identity_changed_on_join")
    if not before["peer_ids"].issubset(joined["peer_ids"]):
        raise LifecycleError("host_peer_not_preserved_on_join")
    if not joined["roster_ids"].issuperset(before["roster_ids"]):
        raise LifecycleError("host_roster_not_preserved_on_join")


def _require_leave(phases: dict[str, dict[str, Any]]) -> None:
    joined = phases["joined"]
    after = phases["after_leave"]
    _same_process(joined, after, "leave")
    if joined["count"] != 2 or after["count"] != 1:
        raise LifecycleError("leave_count_transition_missing")
    if not after["peer_ids"].issubset(joined["peer_ids"]):
        raise LifecycleError("leave_survivor_not_from_joined_session")
    if len(joined["peer_ids"] - after["peer_ids"]) != 1:
        raise LifecycleError("leave_did_not_release_one_peer")
    if not after["indexes"].issubset(joined["indexes"]):
        raise LifecycleError("leave_network_index_not_released_from_session")
    if after["local_peer"] != joined["local_peer"] or after["host_peer"] != joined["host_peer"]:
        raise LifecycleError("host_identity_changed_on_leave")


def _require_migration(phases: dict[str, dict[str, Any]]) -> None:
    before = phases["migration_before"]
    after = phases["migration_after"]
    _same_process(before, after, "migration")
    if before["count"] != 2 or after["count"] != 1:
        raise LifecycleError("migration_count_transition_missing")
    if after["local_peer"] != after["host_peer"]:
        raise LifecycleError("migration_local_peer_is_not_host")
    if before["host_peer"] in after["peer_ids"]:
        raise LifecycleError("old_host_still_present_after_migration")
    if after["local_peer"] not in after["peer_ids"]:
        raise LifecycleError("migrated_local_peer_missing")


def _require_cleanup(phase: dict[str, Any]) -> None:
    if phase["count"] != 0:
        raise LifecycleError("cleanup_peer_count_not_zero")
    if phase["peer_ids"] or phase["roster_ids"]:
        raise LifecycleError("cleanup_retained_peer_or_roster")


def verify(inputs: dict[str, Path], scope: str = "full") -> dict[str, Any]:
    if scope not in {"join", "full"}:
        raise LifecycleError("unsupported_scope")
    unknown = set(inputs) - set(PHASES)
    if unknown:
        raise LifecycleError("unknown_phase:" + ",".join(sorted(unknown)))
    phases = {name: _snapshot(path) for name, path in inputs.items()}
    required = {"host_before", "joined"}
    if scope == "full":
        required |= {"after_leave", "migration_before", "migration_after", "cleanup"}
    missing = required - set(phases)
    if missing:
        raise LifecycleError("missing_phase:" + ",".join(sorted(missing)))
    _require_join(phases)
    if scope == "full":
        _require_leave(phases)
        _require_migration(phases)
        _require_cleanup(phases["cleanup"])

    paths = [inputs[name] for name in sorted(inputs)]
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.read_bytes())
    return {
        "schema": "hd2_two_client_lifecycle_acceptance_v1",
        "status": "passed_two_client_lifecycle" if scope == "full" else "passed_two_client_join",
        "scope": scope,
        "build": BUILD,
        "client_count": 2,
        "phases": sorted(inputs),
        "read_only": True,
        "calls_made": False,
        "writes_made": False,
        "hooks_installed": False,
        "synthetic": False,
        "capacity_above_two_verified": False,
        "input_sha256": digest.hexdigest(),
        "limitations": [
            "This receipt proves only a two-client lifecycle.",
            "It does not prove five-to-eight player admission, replication, or a public release.",
        ],
    }


def _parse_inputs(items: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for item in items:
        phase, separator, raw_path = item.partition("=")
        if not separator or phase not in PHASES or not raw_path:
            raise LifecycleError("each_snapshot_must_be_PHASE=PATH")
        if phase in result:
            raise LifecycleError("duplicate_phase:" + phase)
        result[phase] = Path(raw_path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=("join", "full"), default="full")
    parser.add_argument("--snapshot", action="append", required=True,
                        help="phase=path; phases: " + ", ".join(PHASES))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify(_parse_inputs(args.snapshot), args.scope)
    except (LifecycleError, OSError) as exc:
        result = {"schema": "hd2_two_client_lifecycle_acceptance_v1",
                  "status": "blocked", "error": str(exc), "capacity_above_two_verified": False}
        print(json.dumps(result, ensure_ascii=False))
        return 2
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
