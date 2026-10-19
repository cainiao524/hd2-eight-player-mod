"""Fail-closed verifier for real configurable-capacity acceptance logs.

The verifier consumes caller-supplied JSON logs only.  It never starts the
game, contacts Steam/Party/PlayFab, or treats synthetic fixtures as success.
Each log must describe one independent account/client and include the same
mission id, build fingerprint, peer/index/entity/roster fields, and the full
mission lifecycle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


BUILD = 25480438
EXE_VERSION = "1.8.46015.0"
SUPPORTED_CAPACITIES = (4, 5, 8, 12, 16)
REQUIRED_EVENTS = (
    "ship_join",
    "mission_join",
    "combat",
    "death",
    "reinforcement",
    "departure",
    "reconnect",
    "extraction",
    "settlement",
)
GLOBAL_EVENTS = ("host_migration",)


class AcceptanceError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AcceptanceError(f"cannot_read:{path}") from exc
    if not isinstance(value, dict):
        raise AcceptanceError(f"root_not_object:{path}")
    return value


def _digest(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for path in paths:
        h.update(path.read_bytes())
    return h.hexdigest()


def verify(paths: list[Path], capacity: int = 8) -> dict[str, Any]:
    if capacity not in SUPPORTED_CAPACITIES:
        raise AcceptanceError("unsupported_capacity")
    if len(paths) != capacity:
        raise AcceptanceError(f"exactly_{capacity}_logs_required")
    logs = [_load(path) for path in paths]
    account_ids = [str(log.get("account_id", "")) for log in logs]
    client_ids = [str(log.get("client_id", "")) for log in logs]
    if any(not value for value in account_ids) or len(set(account_ids)) != capacity:
        raise AcceptanceError(f"account_ids_must_be_{capacity}_unique_nonempty")
    if any(not value for value in client_ids) or len(set(client_ids)) != capacity:
        raise AcceptanceError(f"client_ids_must_be_{capacity}_unique_nonempty")
    for log in logs:
        if log.get("steam_build") != BUILD or log.get("exe_version") != EXE_VERSION:
            raise AcceptanceError("build_mismatch")
        if log.get("capacity") != capacity:
            raise AcceptanceError("capacity_declaration_mismatch")
        if log.get("multiplayer_verified") is not True:
            raise AcceptanceError("input_log_not_marked_live_multiplayer")
    mission_ids = {str(log.get("mission_id", "")) for log in logs}
    if len(mission_ids) != 1 or "" in mission_ids:
        raise AcceptanceError("mission_id_mismatch")
    session_ids = {str(log.get("session_id", "")) for log in logs}
    if len(session_ids) != 1 or "" in session_ids:
        raise AcceptanceError("session_id_mismatch")

    indexes: list[int] = []
    peer_ids: set[str] = set()
    resource_handles: set[str] = set()
    entity_ids: set[str] = set()
    roster_ordinals: set[int] = set()
    rows: list[dict[str, Any]] = []
    for log in logs:
        peer = str(log.get("peer_id", ""))
        resource = str(log.get("resource_handle", ""))
        entity = str(log.get("entity_id", ""))
        roster = log.get("roster_ordinal")
        index = log.get("network_index")
        if not peer or not resource or not entity or not isinstance(roster, int):
            raise AcceptanceError("missing_peer_resource_entity_roster")
        if not isinstance(index, int) or index < 0 or index >= capacity:
            raise AcceptanceError("network_index_out_of_range")
        if roster < 0 or roster >= capacity:
            raise AcceptanceError("roster_ordinal_out_of_range")
        if peer in peer_ids:
            raise AcceptanceError("duplicate_peer_id")
        if resource in resource_handles:
            raise AcceptanceError("duplicate_resource_handle")
        if entity in entity_ids:
            raise AcceptanceError("duplicate_entity_id")
        if roster in roster_ordinals:
            raise AcceptanceError("duplicate_roster_ordinal")
        peer_ids.add(peer)
        resource_handles.add(resource)
        entity_ids.add(entity)
        roster_ordinals.add(roster)
        indexes.append(index)
        events = log.get("events")
        if not isinstance(events, list):
            raise AcceptanceError("events_not_array")
        event_names = [item.get("name") for item in events if isinstance(item, dict)]
        missing = [name for name in REQUIRED_EVENTS if name not in event_names]
        if missing:
            raise AcceptanceError("lifecycle_missing:" + ",".join(missing))
        positions = [event_names.index(name) for name in REQUIRED_EVENTS]
        if positions != sorted(positions):
            raise AcceptanceError("lifecycle_order_invalid")
        rows.append({
            "account_id": log["account_id"],
            "client_id": log["client_id"],
            "network_index": index,
            "peer_id": peer,
            "resource_handle": resource,
            "entity_id": entity,
            "roster_ordinal": roster,
            "event_count": len(events),
        })
    if sorted(indexes) != list(range(capacity)):
        raise AcceptanceError(f"network_indexes_must_be_exactly_0_to_{capacity - 1}")
    global_events = {
        event.get("name")
        for log in logs
        for event in log.get("events", [])
        if isinstance(event, dict)
    }
    missing_global = [name for name in GLOBAL_EVENTS if name not in global_events]
    if missing_global:
        raise AcceptanceError("global_lifecycle_missing:" + ",".join(missing_global))
    return {
        "schema": "hd2_configurable_capacity_multiplayer_acceptance_v2",
        "status": "passed_live_multiplayer_acceptance",
        "steam_build": BUILD,
        "exe_version": EXE_VERSION,
        "capacity": capacity,
        "mission_id": next(iter(mission_ids)),
        "session_id": next(iter(session_ids)),
        "account_count": capacity,
        "client_count": capacity,
        "network_indexes": sorted(indexes),
        "rows": sorted(rows, key=lambda row: row["network_index"]),
        "input_sha256": _digest(paths),
        "multiplayer_verified": True,
        "synthetic": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capacity", type=int, choices=SUPPORTED_CAPACITIES, default=8)
    parser.add_argument("--log", type=Path, action="append", required=True,
                        help="one live client JSON log; pass exactly --capacity times")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify(args.log, args.capacity)
    except (AcceptanceError, OSError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False))
        return 2
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
