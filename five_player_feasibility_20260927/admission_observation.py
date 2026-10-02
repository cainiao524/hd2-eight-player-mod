"""Fail-closed schema for externally supplied admission observations.

The module accepts already captured dictionaries only.  It performs no lobby,
Party, process, filesystem, or network access.  An adapter must provide the
observations explicitly and must not mark a player active until a roster
resource handle is confirmed by the capacity contract.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

LAYERS = {
    "playfab_lobby": {"member_count", "max_member_count", "membership_lock", "join_status"},
    "party_network": {
        "user_count", "max_user_count", "device_count", "max_device_count",
        "endpoint_count", "max_endpoint_count", "join_status",
    },
    "host_peer": {"peer_count", "records"},
    "client_confirmed_peer": {"peer_count", "records"},
    "player_creation": {"network_index", "resource_call", "handle_status"},
    "roster": {"occupied_count", "active_count", "generation", "entries"},
}
MAX_RECORDS = 8


def _int(value: Any, maximum: int = 2**31 - 1) -> bool:
    return type(value) is int and 0 <= value <= maximum


def validate_observation(layer: Any, fields: Any) -> tuple[bool, str]:
    if type(layer) is not str or layer not in LAYERS:
        return False, "unknown_layer"
    if type(fields) is not dict or set(fields) != LAYERS[layer]:
        return False, "field_set_mismatch"
    for key in ("member_count", "max_member_count", "user_count", "max_user_count",
                "device_count", "max_device_count", "endpoint_count", "max_endpoint_count", "peer_count",
                "occupied_count", "active_count", "generation", "network_index"):
        if key in fields and not _int(fields[key], 2**53 - 1):
            return False, "invalid_integer:" + key
    for key in ("records", "entries"):
        if key in fields and (type(fields[key]) is not list or len(fields[key]) > MAX_RECORDS):
            return False, "invalid_records:" + key
    if "membership_lock" in fields and type(fields["membership_lock"]) is not bool:
        return False, "invalid_membership_lock"
    if "join_status" in fields and fields["join_status"] not in ("accepted", "pending", "rejected"):
        return False, "invalid_join_status"
    if layer in ("host_peer", "client_confirmed_peer"):
        if fields["peer_count"] != len(fields["records"]):
            return False, "peer_count_mismatch"
        seen_peers, seen_members, seen_indices = set(), set(), set()
        for record in fields["records"]:
            if type(record) is not dict or set(record) != {"peer_id", "member_id", "network_index"}:
                return False, "peer_record_shape_invalid"
            if any(type(record[key]) is not str or not 0 < len(record[key]) <= 256
                   for key in ("peer_id", "member_id")):
                return False, "peer_identity_invalid"
            if not _int(record["network_index"], 7):
                return False, "peer_network_index_invalid"
            if (record["peer_id"] in seen_peers or record["member_id"] in seen_members
                    or record["network_index"] in seen_indices):
                return False, "duplicate_peer_identity"
            seen_peers.add(record["peer_id"])
            seen_members.add(record["member_id"])
            seen_indices.add(record["network_index"])
    if layer == "playfab_lobby" and fields["member_count"] > fields["max_member_count"]:
        return False, "member_count_exceeds_max"
    if layer == "party_network":
        if fields["user_count"] > fields["max_user_count"]:
            return False, "user_count_exceeds_max"
        if fields["device_count"] > fields["max_device_count"]:
            return False, "device_count_exceeds_max"
        if fields["endpoint_count"] > fields["max_endpoint_count"]:
            return False, "endpoint_count_exceeds_max"
    if layer == "roster" and fields["active_count"] > fields["occupied_count"]:
        return False, "active_exceeds_occupied"
    return True, "observation_valid"


@dataclass(frozen=True)
class Observation:
    sequence: int
    layer: str
    fields: dict[str, Any]


@dataclass
class ObservationLog:
    observations: list[Observation] = field(default_factory=list)

    def append(self, layer: str, fields: dict[str, Any]) -> tuple[bool, str]:
        ok, reason = validate_observation(layer, fields)
        if not ok:
            return False, reason
        self.observations.append(Observation(len(self.observations), layer, deepcopy(fields)))
        return True, "recorded"

    def snapshot(self) -> list[dict[str, Any]]:
        return [
            {"sequence": item.sequence, "layer": item.layer, "fields": deepcopy(item.fields)}
            for item in self.observations
        ]
