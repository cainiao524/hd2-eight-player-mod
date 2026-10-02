"""Offline peer-admission adapter for the eight-player contract.

This is a data-only coordinator.  It accepts explicit observations, allocates
stable network indexes, and delegates roster/resource lifetime checks to
``AdmissionState``.  It never discovers a game process, calls PlayFab/Party,
uses FFI, installs a hook, or sends a packet.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from admission_observation import ObservationLog, validate_observation
from eight_player_capacity_contract import AdmissionState, CapacitySpec, Decision, identity, reject


VALID_MODES = {"host_only", "all_clients"}
VALID_ROLES = {"host", "client"}
REQUIRED_PREFLIGHT_LAYERS = {"playfab_lobby", "party_network", "host_peer"}


class PeerAdmissionAdapter:
    """Connect explicit session observations to the offline eight-slot model."""

    def __init__(self, mode: str = "host_only", role: str = "host",
                 spec: CapacitySpec = CapacitySpec()):
        if mode not in VALID_MODES:
            raise ValueError("mode_invalid")
        if role not in VALID_ROLES:
            raise ValueError("role_invalid")
        self.spec = spec
        self.mode = mode
        self.role = role
        self.state = AdmissionState(spec)
        self.observations = ObservationLog()
        self.latest: dict[str, dict[str, Any]] = {}
        self.observation_epoch: str | None = None
        self.members: dict[str, str] = {}
        self.peers: dict[str, str] = {}

    def _validate(self) -> Decision:
        valid = self.state.validate()
        if not valid.accepted:
            return valid
        if type(self.members) is not dict or type(self.peers) is not dict:
            return reject("identity_maps_invalid")
        if any(not identity(member) or not identity(peer) for member, peer in self.members.items()):
            return reject("identity_maps_invalid")
        if ({peer: member for member, peer in self.members.items()} != self.peers
                or len(self.members) != len(self.peers)
                or set(self.peers) != {entry.peer_id for entry in self.state.slots if entry is not None}):
            return reject("identity_maps_mismatch")
        if type(self.latest) is not dict:
            return reject("observations_invalid")
        for layer, fields in self.latest.items():
            ok, reason = validate_observation(layer, fields)
            if not ok:
                return reject(reason, layer=layer)
        return Decision("accepted", "adapter_state_valid")

    def observe(self, layer: str, fields: dict[str, Any], epoch: str) -> Decision:
        """Record one caller-supplied observation without side effects on rejection."""
        valid = self._validate()
        if not valid.accepted:
            return valid
        if not identity(epoch):
            self.latest.pop(layer, None)
            if not self.latest:
                self.observation_epoch = None
            return reject("observation_epoch_missing", layer=layer)
        if self.observation_epoch is not None and epoch != self.observation_epoch:
            self.latest.clear()
            self.observation_epoch = None
            return reject("observation_epoch_mismatch", layer=layer)
        ok, reason = validate_observation(layer, fields)
        if not ok:
            self.latest.pop(layer, None)
            if not self.latest:
                self.observation_epoch = None
            return reject(reason, layer=layer)
        accepted, recorded = self.observations.append(layer, fields)
        if not accepted:
            return reject(recorded, layer=layer)
        self.latest[layer] = deepcopy(fields)
        self.observation_epoch = epoch
        return Decision("accepted", "observation_recorded", {"layer": layer})

    def _preflight(self) -> Decision:
        valid = self._validate()
        if not valid.accepted:
            return valid
        missing = sorted(REQUIRED_PREFLIGHT_LAYERS.difference(self.latest))
        if missing:
            return reject("preflight_observation_missing", layers=missing)
        if self.observation_epoch is None:
            return reject("observation_epoch_missing")
        # validate again so a caller cannot mutate a previously returned dict
        # and bypass the layer bounds before admission.
        for layer in REQUIRED_PREFLIGHT_LAYERS:
            ok, reason = validate_observation(layer, self.latest[layer])
            if not ok:
                return reject(reason, layer=layer)
        lobby = self.latest["playfab_lobby"]
        party = self.latest["party_network"]
        if lobby["membership_lock"]:
            return reject("membership_locked")
        if lobby["join_status"] != "accepted" or party["join_status"] != "accepted":
            return reject("join_not_accepted")
        next_count = self.state.occupied_count + 1
        if next_count > min(lobby["member_count"], lobby["max_member_count"],
                            party["user_count"], party["max_user_count"]):
            return reject("observed_session_capacity_insufficient")
        return Decision("accepted", "preflight_valid")

    def _next_index(self, requested: int | None) -> Decision:
        if requested is not None:
            ok, reason = self.spec.validate_network_index(requested)
            if not ok:
                return reject(reason, network_index=requested)
            return Decision("accepted", "requested_index", {"network_index": requested})
        for index in range(self.spec.first_network_index, self.spec.last_network_index + 1):
            if index not in self.state.by_network_index:
                return Decision("accepted", "allocated_index", {"network_index": index})
        return reject("no_free_network_index")

    def admit_peer(self, member_id: str, peer_id: str,
                   network_index: int | None = None) -> Decision:
        """Reserve one peer as pending after explicit lobby/Party preflight."""
        preflight = self._preflight()
        if not preflight.accepted:
            return self.state.record("admit_peer", preflight)
        if not identity(member_id):
            return self.state.record("admit_peer", reject("member_id_missing"))
        if not identity(peer_id):
            return self.state.record("admit_peer", reject("peer_id_missing"))
        if member_id in self.members:
            return self.state.record("admit_peer", reject("duplicate_member_id"))
        if peer_id in self.peers:
            return self.state.record("admit_peer", reject("duplicate_peer_id"))
        selected = self._next_index(network_index)
        if not selected.accepted:
            return self.state.record("admit_peer", selected)
        index = selected.details["network_index"]
        if index in self.state.by_network_index:
            return self.state.record("admit_peer", reject("duplicate_network_index"))
        expected_peer = {"member_id": member_id, "peer_id": peer_id, "network_index": index}
        if expected_peer not in self.latest["host_peer"]["records"]:
            return self.state.record("admit_peer", reject("host_peer_not_observed"))
        result = self.state.insert(peer_id, index)
        if not result.accepted:
            return result
        self.members[member_id] = peer_id
        self.peers[peer_id] = member_id
        return self.state.record("admit_peer", Decision(
            "accepted", "peer_reserved", {
                "member_id": member_id,
                "peer_id": peer_id,
                "network_index": index,
                "ordinal": result.details["ordinal"],
                "generation": result.details["generation"],
                "mode": self.mode,
                "role": self.role,
            }))

    def _peer_entry(self, peer_id: str):
        valid = self._validate()
        if not valid.accepted:
            return valid, None
        if not identity(peer_id):
            return reject("peer_id_missing"), None
        if peer_id not in self.peers:
            return reject("peer_id_missing"), None
        member_id = self.peers[peer_id]
        result, entry = self.state.lookup(
            next(index for index, ordinal in self.state.by_network_index.items()
                 if self.state.slots[ordinal].peer_id == peer_id))
        if not result.accepted:
            return result, None
        return Decision("accepted", "peer_found", {"member_id": member_id}), entry

    def bind_resource(self, peer_id: str, resource_handle: str, expected_generation: int) -> Decision:
        result, entry = self._peer_entry(peer_id)
        if not result.accepted:
            return self.state.record("bind_resource", result)
        if type(expected_generation) is not int or expected_generation != entry.generation:
            return self.state.record("bind_resource", reject("stale_generation"))
        confirmation = self.latest.get("client_confirmed_peer")
        expected_peer = {"peer_id": peer_id, "member_id": self.peers[peer_id], "network_index": entry.network_index}
        if confirmation is None or expected_peer not in confirmation["records"]:
            return self.state.record("bind_resource", reject("client_confirmation_missing"))
        result = self.state.bind_resource(entry.network_index, resource_handle, expected_generation)
        return self.state.record("bind_resource", result)

    def depart_peer(self, peer_id: str, expected_generation: int) -> Decision:
        result, entry = self._peer_entry(peer_id)
        if not result.accepted:
            return self.state.record("depart_peer", result)
        result = self.state.remove(entry.network_index, expected_generation)
        if result.accepted:
            member_id = self.peers.pop(peer_id)
            del self.members[member_id]
            # Require a fresh caller-supplied session view before reuse.
            self.latest.clear()
            self.observation_epoch = None
        return self.state.record("depart_peer", result)

    def reconnect_peer(self, member_id: str, peer_id: str,
                       network_index: int | None = None) -> Decision:
        """Reserve a new generation for a departed member/peer identity."""
        valid = self._validate()
        if not valid.accepted:
            return valid
        if not identity(member_id) or not identity(peer_id):
            return reject("identity_missing")
        if member_id in self.members or peer_id in self.peers:
            return self.state.record("reconnect_peer", reject("identity_still_active"))
        return self.admit_peer(member_id, peer_id, network_index)

    def snapshot(self) -> dict[str, Any]:
        valid = self._validate()
        if not valid.accepted:
            raise ValueError(valid.reason)
        return {
            "mode": self.mode,
            "role": self.role,
            "observation_epoch": self.observation_epoch,
            "capacity": deepcopy(self.state.snapshot()),
            "members": deepcopy(self.members),
            "peers": deepcopy(self.peers),
            "observations": self.observations.snapshot(),
            "native_adapter_present": False,
            "game_integration": False,
            "live_ready": False,
            "multiplayer_verified": False,
        }
