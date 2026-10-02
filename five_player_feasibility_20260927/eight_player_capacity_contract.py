"""Offline eight-player admission contract.

The model is intentionally separate from the native dense/pending roster. It
does not read a game process, load a DLL, call FFI, or install a mod.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field, replace
from typing import Any

TARGET_PROFILE = {
    "build": 25480438,
    "exe_sha256": "f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06",
    "game_dll_sha256": "2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e",
}
MAX_GENERATION = 9007199254740991
MAX_DIAGNOSTICS = 256


def integer(value: Any, lo: int, hi: int) -> bool:
    return type(value) is int and lo <= value <= hi


def identity(value: Any) -> bool:
    return type(value) is str and 0 < len(value) <= 256


@dataclass(frozen=True)
class CapacitySpec:
    logical_max_players: int = 8
    storage_slots: int = 8
    first_network_index: int = 0
    last_network_index: int = 7

    def __post_init__(self):
        if (self.logical_max_players, self.storage_slots,
                self.first_network_index, self.last_network_index) != (8, 8, 0, 7):
            raise ValueError("unsupported_capacity")

    def profile(self) -> dict[str, Any]:
        return {**TARGET_PROFILE, **asdict(self)}

    def validate_profile(self, profile: Any) -> tuple[bool, str]:
        if type(profile) is not dict:
            return False, "profile_not_table"
        for key, expected in self.profile().items():
            if type(profile.get(key)) is not type(expected) or profile.get(key) != expected:
                return False, "profile_mismatch:" + key
        return True, "profile_match"

    def validate_network_index(self, value: Any) -> tuple[bool, str]:
        if type(value) is not int:
            return False, "network_index_not_integer"
        if not self.first_network_index <= value <= self.last_network_index:
            return False, "network_index_out_of_range"
        return True, "network_index_valid"

    def validate_count(self, value: Any) -> tuple[bool, str]:
        if type(value) is not int:
            return False, "count_not_integer"
        if not 0 <= value <= self.logical_max_players:
            return False, "count_out_of_range"
        return True, "count_valid"


@dataclass(frozen=True)
class PlayerRecord:
    peer_id: str
    network_index: int
    ordinal: int
    resource_handle: str | None = None
    generation: int = 0
    phase: str = "pending"


@dataclass(frozen=True)
class Decision:
    status: str
    reason: str
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def accepted(self) -> bool:
        return self.status == "accepted"


def reject(reason: str, **details: Any) -> Decision:
    return Decision("rejected", reason, details)


def validate_snapshot(snapshot: Any, spec: CapacitySpec = CapacitySpec()) -> Decision:
    if type(snapshot) is not dict:
        return reject("snapshot_not_table")
    ok, reason = spec.validate_profile(snapshot.get("profile"))
    if not ok:
        return reject(reason)
    generation = snapshot.get("generation")
    if not integer(generation, 0, MAX_GENERATION):
        return reject("generation_invalid")
    entries = snapshot.get("entries")
    if type(entries) is not list or len(entries) > spec.storage_slots:
        return reject("entries_out_of_range")
    seen_indices, seen_ordinals, seen_peers, seen_handles, seen_tokens = set(), set(), set(), set(), set()
    active_count = 0
    for entry in entries:
        if type(entry) is not dict or not identity(entry.get("peer_id")):
            return reject("peer_id_missing")
        ok, reason = spec.validate_network_index(entry.get("network_index"))
        if not ok:
            return reject(reason)
        index, ordinal = entry["network_index"], entry.get("ordinal")
        token, handle, phase = entry.get("generation"), entry.get("resource_handle"), entry.get("phase")
        if not integer(ordinal, 0, spec.storage_slots - 1):
            return reject("ordinal_out_of_range")
        if not integer(token, 1, generation):
            return reject("token_invalid")
        if index in seen_indices:
            return reject("duplicate_network_index")
        if ordinal in seen_ordinals:
            return reject("duplicate_ordinal")
        if entry["peer_id"] in seen_peers:
            return reject("duplicate_peer_id")
        if token in seen_tokens:
            return reject("duplicate_generation")
        if phase == "pending":
            if handle is not None:
                return reject("pending_has_resource")
        elif phase == "active":
            if not identity(handle):
                return reject("resource_handle_missing")
            if handle in seen_handles:
                return reject("duplicate_resource_handle")
            seen_handles.add(handle)
            active_count += 1
        else:
            return reject("phase_invalid")
        seen_indices.add(index)
        seen_ordinals.add(ordinal)
        seen_peers.add(entry["peer_id"])
        seen_tokens.add(token)
    if type(snapshot.get("occupied_count")) is not int or snapshot.get("occupied_count") != len(entries):
        return reject("occupied_count_mismatch")
    if type(snapshot.get("active_count")) is not int or snapshot.get("active_count") != active_count:
        return reject("active_count_mismatch")
    return Decision("accepted", "snapshot_valid",
                    {"occupied_count": len(entries), "active_count": active_count})


class AdmissionState:
    """Stable coordinator slots; remove leaves a hole and does not compact."""

    def __init__(self, spec: CapacitySpec = CapacitySpec(), profile: dict[str, Any] | None = None):
        self.spec = spec
        supplied = spec.profile() if profile is None else profile
        ok, reason = spec.validate_profile(supplied)
        if not ok:
            raise ValueError(reason)
        self.profile = deepcopy(supplied)
        self.generation = 0
        self.slots: list[PlayerRecord | None] = [None] * spec.storage_slots
        self.by_network_index: dict[int, int] = {}
        self.diagnostics: list[dict[str, Any]] = []

    @property
    def occupied_count(self) -> int:
        return sum(entry is not None for entry in self.slots)

    @property
    def active_count(self) -> int:
        return sum(entry is not None and entry.phase == "active" for entry in self.slots)

    def _serialized(self) -> dict[str, Any]:
        return {
            "profile": deepcopy(self.profile),
            "generation": self.generation,
            "occupied_count": self.occupied_count,
            "active_count": self.active_count,
            "entries": [asdict(entry) for entry in self.slots if entry is not None],
        }

    def record(self, event: str, result: Decision) -> Decision:
        if type(self.diagnostics) is not list or len(self.diagnostics) > MAX_DIAGNOSTICS:
            return result
        self.diagnostics.append({
            "layer": "admission_model",
            "event": event,
            "result": result.status,
            "reason": result.reason,
            **deepcopy(result.details),
        })
        del self.diagnostics[:-MAX_DIAGNOSTICS]
        return result

    def validate(self) -> Decision:
        if type(self.slots) is not list or len(self.slots) != self.spec.storage_slots:
            return reject("state_slots_invalid")
        if any(entry is not None and type(entry) is not PlayerRecord for entry in self.slots):
            return reject("state_entry_invalid")
        if type(self.diagnostics) is not list or len(self.diagnostics) > MAX_DIAGNOSTICS:
            return reject("diagnostics_invalid")
        if any(type(item) is not dict for item in self.diagnostics):
            return reject("diagnostics_invalid")
        ok, reason = self.spec.validate_profile(self.profile)
        if not ok:
            return reject(reason)
        result = validate_snapshot(self._serialized(), self.spec)
        if not result.accepted:
            return result
        expected: dict[int, int] = {}
        for ordinal, entry in enumerate(self.slots):
            if entry is not None:
                if entry.ordinal != ordinal:
                    return reject("ordinal_mismatch", ordinal=ordinal)
                expected[entry.network_index] = ordinal
        if expected != self.by_network_index:
            return reject("index_ordinal_mismatch")
        return Decision("accepted", "state_valid",
                        {"occupied_count": self.occupied_count, "active_count": self.active_count,
                         "generation": self.generation})

    def _guard(self) -> Decision:
        valid = self.validate()
        if not valid.accepted:
            return valid
        if self.generation >= MAX_GENERATION:
            return reject("generation_exhausted")
        return valid

    def insert(self, peer_id: str, network_index: int) -> Decision:
        guard = self._guard()
        if not guard.accepted:
            return self.record("reserve", guard)
        if not identity(peer_id):
            return self.record("reserve", reject("peer_id_missing"))
        ok, reason = self.spec.validate_network_index(network_index)
        if not ok:
            return self.record("reserve", reject(reason, network_index=network_index))
        if network_index in self.by_network_index:
            return self.record("reserve", reject("duplicate_network_index"))
        if any(entry is not None and entry.peer_id == peer_id for entry in self.slots):
            return self.record("reserve", reject("duplicate_peer_id"))
        if self.occupied_count >= self.spec.storage_slots:
            return self.record("reserve", reject("no_free_storage_slot"))
        ordinal = self.slots.index(None)
        token = self.generation + 1
        self.slots[ordinal] = PlayerRecord(peer_id, network_index, ordinal, generation=token)
        self.by_network_index[network_index] = ordinal
        self.generation = token
        return self.record("reserve", Decision("accepted", "reserved",
                                               {"ordinal": ordinal, "generation": token}))

    def lookup(self, network_index: int) -> tuple[Decision, PlayerRecord | None]:
        valid = self.validate()
        if not valid.accepted:
            return valid, None
        ok, reason = self.spec.validate_network_index(network_index)
        if not ok:
            return reject(reason), None
        ordinal = self.by_network_index.get(network_index)
        if ordinal is None:
            return reject("network_index_missing"), None
        entry = self.slots[ordinal]
        if entry is None or entry.network_index != network_index:
            return reject("index_ordinal_mismatch"), None
        return Decision("accepted", "found", {"ordinal": ordinal}), entry

    def _token_entry(self, network_index: int, expected_generation: int) -> tuple[Decision, PlayerRecord | None]:
        result, entry = self.lookup(network_index)
        if not result.accepted:
            return result, None
        if type(expected_generation) is not int or expected_generation != entry.generation:
            return reject("stale_generation"), None
        return result, entry

    def remove(self, network_index: int, expected_generation: int) -> Decision:
        guard = self._guard()
        if not guard.accepted:
            return self.record("remove", guard)
        result, entry = self._token_entry(network_index, expected_generation)
        if not result.accepted:
            return self.record("remove", result)
        self.slots[entry.ordinal] = None
        del self.by_network_index[network_index]
        self.generation += 1
        return self.record("remove", Decision("accepted", "removed",
                                               {"ordinal": entry.ordinal, "generation": self.generation}))

    def bind_resource(self, network_index: int, resource_handle: str, expected_generation: int) -> Decision:
        guard = self._guard()
        if not guard.accepted:
            return self.record("confirm", guard)
        result, entry = self._token_entry(network_index, expected_generation)
        if not result.accepted:
            return self.record("confirm", result)
        if entry.phase != "pending":
            return self.record("confirm", reject("already_confirmed"))
        if not identity(resource_handle):
            return self.record("confirm", reject("resource_handle_missing"))
        if any(existing is not None and existing.resource_handle == resource_handle for existing in self.slots):
            return self.record("confirm", reject("duplicate_resource_handle"))
        self.slots[entry.ordinal] = replace(entry, resource_handle=resource_handle, phase="active")
        self.generation += 1
        return self.record("confirm", Decision("accepted", "confirmed",
                                               {"ordinal": entry.ordinal, "generation": self.generation}))

    def snapshot(self) -> dict[str, Any]:
        result = self.validate()
        if not result.accepted:
            raise ValueError(result.reason)
        return {**deepcopy(self._serialized()), "diagnostics": deepcopy(self.diagnostics),
                "game_integration": False, "multiplayer_verified": False}
