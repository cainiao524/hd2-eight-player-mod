"""Offline peer/confirmed-peer lifecycle contract for build 25480438.

This module models the ownership and rollback boundary that a future native
peer-admission bridge must preserve.  It does not inspect a process, call a
native function, patch a binary, or send a network message.

The model keeps network index, member/peer identity, generation, resource
handles, callback leases, and host ownership separate.  Departure is
idempotent for the same generation, reconnect receives a new generation, and
host migration is a transaction that cannot commit while callbacks or
partially released records remain in flight.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Iterable

BUILD = 25480438
CAPACITY = 8
VALID_INDEXES = range(CAPACITY)
MAX_GENERATION = 0xFFFFFFFF


class PeerState(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    RELEASING = "releasing"


@dataclass(frozen=True)
class PeerToken:
    network_index: int
    generation: int


@dataclass(frozen=True)
class CallbackLease:
    lease_id: int
    token: PeerToken


@dataclass(frozen=True)
class MigrationToken:
    transaction_id: int
    owner_key: int
    owner_epoch: str


@dataclass
class PeerRecord:
    member_id: str
    peer_id: str
    network_index: int
    generation: int
    state: PeerState
    resource_handle: str | None = None


class PeerLifecycleSidecar:
    """Fail-closed eight-slot peer/confirmed-peer lifecycle model."""

    CONFIRM_STAGES = ("handle_registry", "component_registry", "confirmed_dispatch")
    RELEASE_STAGES = ("confirmed_dispatch", "component_registry", "handle_registry")

    def __init__(self, owner_key: int, owner_epoch: str, build: int = BUILD) -> None:
        if type(owner_key) is not int or owner_key <= 0:
            raise ValueError("owner_key must be non-zero")
        if type(owner_epoch) is not str or not owner_epoch:
            raise ValueError("owner_epoch must be non-empty")
        if type(build) is not int or build != BUILD:
            raise ValueError("unsupported build")
        self.owner_key = owner_key
        self.owner_epoch = owner_epoch
        self.build = build
        self._generation = [0] * CAPACITY
        self._records: list[PeerRecord | None] = [None] * CAPACITY
        self._member_to_index: dict[str, int] = {}
        self._peer_to_index: dict[str, int] = {}
        self._retired: set[tuple[str, int]] = set()
        self._retired_tokens: set[tuple[int, int]] = set()
        self._cancelled: set[tuple[str, int]] = set()
        self._cancelled_tokens: set[tuple[int, int]] = set()
        self._handles: set[str] = set()
        self._components: set[tuple[int, int]] = set()
        self._published: set[tuple[int, int]] = set()
        self._leases: dict[int, PeerToken] = {}
        self._next_lease = 1
        self._migration: dict[str, Any] | None = None
        self._next_migration = 1
        self._migration_history: dict[int, str] = {}
        self._diagnostics: list[dict[str, Any]] = []

    @staticmethod
    def _identity(value: Any) -> bool:
        return type(value) is str and bool(value)

    @staticmethod
    def _valid_index(value: Any) -> bool:
        return type(value) is int and value in VALID_INDEXES

    @staticmethod
    def _valid_generation(value: Any) -> bool:
        return type(value) is int and 0 < value <= MAX_GENERATION

    @staticmethod
    def _valid_owner(value: Any) -> bool:
        return type(value) is int and value > 0

    @classmethod
    def _valid_token_shape(cls, token: Any) -> bool:
        return (type(token) is PeerToken and cls._valid_index(token.network_index)
                and cls._valid_generation(token.generation))

    @staticmethod
    def _valid_migration_token(token: Any) -> bool:
        return (type(token) is MigrationToken and type(token.transaction_id) is int
                and token.transaction_id > 0 and type(token.owner_key) is int
                and token.owner_key > 0 and type(token.owner_epoch) is str
                and bool(token.owner_epoch))

    def _record(self, operation: str, accepted: bool, reason: str, **details: Any) -> dict[str, Any]:
        row = {"operation": operation, "accepted": accepted, "reason": reason, **details}
        self._diagnostics.append(deepcopy(row))
        return row

    def _token(self, token: PeerToken) -> PeerRecord:
        if type(token) is not PeerToken:
            raise ValueError("invalid peer token")
        if not self._valid_index(token.network_index) or not self._valid_generation(token.generation):
            raise ValueError("invalid peer token")
        record = self._records[token.network_index]
        if record is None or record.generation != token.generation:
            raise ValueError("stale or missing peer token")
        return record

    def _lookup(self, token: PeerToken) -> PeerRecord | None:
        if (type(token) is not PeerToken or not self._valid_index(token.network_index)
                or not self._valid_generation(token.generation)):
            return None
        record = self._records[token.network_index]
        if record is None or record.generation != token.generation:
            return None
        return record

    def reserve(self, member_id: str, peer_id: str, network_index: int) -> PeerToken:
        if not self._identity(member_id) or not self._identity(peer_id):
            raise ValueError("identity_missing")
        if not self._valid_index(network_index):
            raise ValueError("network_index_invalid")
        if self._migration is not None:
            raise ValueError("migration_in_progress")
        if self._records[network_index] is not None:
            raise ValueError("network_index_occupied")
        if member_id in self._member_to_index or peer_id in self._peer_to_index:
            raise ValueError("duplicate_identity")
        generation = self._generation[network_index]
        if generation >= MAX_GENERATION:
            raise ValueError("generation_exhausted")
        generation += 1
        self._generation[network_index] = generation
        record = PeerRecord(member_id, peer_id, network_index, generation, PeerState.PENDING)
        self._records[network_index] = record
        self._member_to_index[member_id] = network_index
        self._peer_to_index[peer_id] = network_index
        self.validate()
        self._record("reserve", True, "pending", network_index=network_index, generation=generation)
        return PeerToken(network_index, generation)

    def confirm(self, token: PeerToken, resource_handle: str,
                fail_stage: str | None = None) -> dict[str, Any]:
        """Confirm through staged sidecar callbacks, rolling back on failure.

        ``fail_stage`` is a deterministic offline fault injection used by the
        tests; it represents a native callback or dispatcher rejection.
        """
        record = self._lookup(token)
        if record is None:
            return self._record("confirm", False, "stale_or_missing")
        if record.state is not PeerState.PENDING:
            return self._record("confirm", False, "already_confirmed")
        if not self._identity(resource_handle):
            return self._record("confirm", False, "resource_handle_missing")
        if resource_handle in self._handles:
            return self._record("confirm", False, "resource_handle_duplicate")
        if fail_stage is not None and fail_stage not in self.CONFIRM_STAGES:
            return self._record("confirm", False, "callback_stage_invalid")
        acquired: list[str] = []
        component_key = (record.network_index, record.generation)
        published_key = component_key
        try:
            for stage in self.CONFIRM_STAGES:
                if stage == "handle_registry":
                    self._handles.add(resource_handle)
                    acquired.append("handle")
                elif stage == "component_registry":
                    self._components.add(component_key)
                    acquired.append("component")
                elif stage == "confirmed_dispatch":
                    self._published.add(published_key)
                    acquired.append("published")
                if fail_stage == stage:
                    raise RuntimeError(stage)
        except RuntimeError as error:
            self._rollback_confirm(resource_handle, component_key, published_key, acquired)
            self.validate()
            return self._record("confirm", False, "callback_failed", stage=str(error), rolled_back=True)
        record.resource_handle = resource_handle
        record.state = PeerState.CONFIRMED
        self.validate()
        return self._record("confirm", True, "confirmed", network_index=record.network_index,
                            generation=record.generation)

    def _rollback_confirm(self, handle: str, component_key: tuple[int, int],
                          published_key: tuple[int, int], acquired: list[str]) -> None:
        if "published" in acquired:
            self._published.discard(published_key)
        if "component" in acquired:
            self._components.discard(component_key)
        if "handle" in acquired:
            self._handles.discard(handle)

    def cancel_pending(self, token: PeerToken) -> dict[str, Any]:
        record = self._lookup(token)
        if record is None:
            if self._valid_token_shape(token) and (token.network_index, token.generation) in self._cancelled_tokens:
                return self._record("cancel_pending", True, "already_cancelled")
            return self._record("cancel_pending", False, "stale_or_missing")
        if record.state is not PeerState.PENDING:
            return self._record("cancel_pending", False, "not_pending")
        key = (record.peer_id, record.generation)
        del self._member_to_index[record.member_id]
        del self._peer_to_index[record.peer_id]
        self._records[record.network_index] = None
        self._cancelled.add(key)
        self._cancelled_tokens.add((record.network_index, record.generation))
        self.validate()
        return self._record("cancel_pending", True, "cancelled", network_index=record.network_index,
                            generation=record.generation)

    def acquire_callback(self, token: PeerToken) -> CallbackLease:
        record = self._lookup(token)
        if record is None:
            raise ValueError("stale_or_missing")
        if record.state is PeerState.RELEASING:
            raise ValueError("record_releasing")
        lease = CallbackLease(self._next_lease, token)
        self._next_lease += 1
        self._leases[lease.lease_id] = token
        self._record("callback_enter", True, "lease_acquired", lease_id=lease.lease_id,
                     network_index=token.network_index, generation=token.generation)
        return lease

    def release_callback(self, lease: CallbackLease) -> dict[str, Any]:
        if type(lease) is not CallbackLease:
            return self._record("callback_leave", False, "invalid_lease")
        if lease.lease_id not in self._leases:
            return self._record("callback_leave", True, "already_released", lease_id=lease.lease_id)
        token = self._leases[lease.lease_id]
        if token != lease.token:
            return self._record("callback_leave", False, "lease_token_mismatch")
        self._leases.pop(lease.lease_id)
        return self._record("callback_leave", True, "lease_released", lease_id=lease.lease_id)

    def begin_release(self, token: PeerToken) -> dict[str, Any]:
        record = self._lookup(token)
        if record is None:
            if self._valid_token_shape(token) and (token.network_index, token.generation) in self._retired_tokens:
                return self._record("begin_release", True, "already_removed")
            return self._record("begin_release", False, "stale_or_missing")
        if record.state is not PeerState.CONFIRMED:
            return self._record("begin_release", False, "not_confirmed")
        if any(active == token for active in self._leases.values()):
            return self._record("begin_release", False, "callback_in_flight")
        record.state = PeerState.RELEASING
        self.validate()
        return self._record("begin_release", True, "releasing", network_index=token.network_index,
                            generation=token.generation)

    def abort_release(self, token: PeerToken) -> dict[str, Any]:
        record = self._lookup(token)
        if record is None:
            return self._record("abort_release", False, "stale_or_missing")
        if record.state is not PeerState.RELEASING:
            return self._record("abort_release", False, "not_releasing")
        record.state = PeerState.CONFIRMED
        self.validate()
        return self._record("abort_release", True, "release_aborted", network_index=token.network_index,
                            generation=token.generation)

    def finish_release(self, token: PeerToken, fail_stage: str | None = None) -> dict[str, Any]:
        record = self._lookup(token)
        if record is None:
            if self._valid_token_shape(token) and (token.network_index, token.generation) in self._retired_tokens:
                return self._record("finish_release", True, "already_removed")
            return self._record("finish_release", False, "stale_or_missing")
        if record.state is not PeerState.RELEASING:
            return self._record("finish_release", False, "not_releasing")
        if any(active == token for active in self._leases.values()):
            return self._record("finish_release", False, "callback_in_flight")
        if fail_stage is not None and fail_stage not in self.RELEASE_STAGES:
            return self._record("finish_release", False, "callback_stage_invalid")
        # Release is staged but sidecar state is only destroyed after all
        # callbacks succeed.  A failure leaves the record recoverable.
        if fail_stage is not None:
            self.abort_release(token)
            return self._record("finish_release", False, "callback_failed",
                                stage=fail_stage, rolled_back=True)
        handle = record.resource_handle
        self._published.discard((record.network_index, record.generation))
        self._components.discard((record.network_index, record.generation))
        if handle is not None:
            self._handles.discard(handle)
        del self._member_to_index[record.member_id]
        del self._peer_to_index[record.peer_id]
        self._records[record.network_index] = None
        self._retired.add((record.peer_id, record.generation))
        self._retired_tokens.add((record.network_index, record.generation))
        self.validate()
        return self._record("finish_release", True, "removed", network_index=token.network_index,
                            generation=token.generation)

    def depart(self, token: PeerToken, fail_stage: str | None = None) -> dict[str, Any]:
        """Release a peer; duplicate delivery of the same event is harmless."""
        result = self.begin_release(token)
        if result["accepted"]:
            return self.finish_release(token, fail_stage=fail_stage)
        if type(token) is PeerToken and (self._retired_contains(token)):
            return self._record("depart", True, "already_removed", network_index=token.network_index,
                                generation=token.generation)
        return result

    def _retired_contains(self, token: PeerToken) -> bool:
        return self._valid_token_shape(token) and (token.network_index, token.generation) in self._retired_tokens

    def begin_migration(self, owner_key: int, owner_epoch: str,
                        records: Iterable[dict[str, Any]] | None = None) -> MigrationToken:
        if not self._valid_owner(owner_key):
            raise ValueError("owner_key_invalid")
        if type(owner_epoch) is not str or not owner_epoch:
            raise ValueError("owner_epoch_invalid")
        if self._migration is not None:
            raise ValueError("migration_in_progress")
        if self._leases:
            raise ValueError("callback_in_flight")
        if any(record is not None and record.state is not PeerState.CONFIRMED
               for record in self._records):
            raise ValueError("records_not_quiescent")
        staged = self._normalize_migration_records(records)
        transaction_id = self._next_migration
        self._next_migration += 1
        token = MigrationToken(transaction_id, owner_key, owner_epoch)
        self._migration = {
            "token": token,
            "owner_key": self.owner_key,
            "owner_epoch": self.owner_epoch,
            "records": staged,
        }
        self._record("migration_begin", True, "prepared", transaction_id=transaction_id,
                     owner_key=owner_key, owner_epoch=owner_epoch)
        return token

    def _normalize_migration_records(self, records: Iterable[dict[str, Any]] | None) -> list[PeerRecord | None]:
        if records is None:
            return [deepcopy(record) if record is not None else None for record in self._records]
        try:
            rows = list(records)
        except TypeError as error:
            raise ValueError("migration_records_invalid") from error
        staged: list[PeerRecord | None] = [None] * CAPACITY
        members: set[str] = set()
        peers: set[str] = set()
        for row in rows:
            if type(row) is not dict:
                raise ValueError("migration_record_invalid")
            member_id = row.get("member_id")
            peer_id = row.get("peer_id")
            index = row.get("network_index")
            if not self._identity(member_id) or not self._identity(peer_id) or not self._valid_index(index):
                raise ValueError("migration_record_invalid")
            if index in range(CAPACITY) and staged[index] is not None:
                raise ValueError("migration_duplicate_index")
            if member_id in members or peer_id in peers:
                raise ValueError("migration_duplicate_identity")
            current = self._records[index]
            if current is None:
                raise ValueError("migration_unknown_index")
            generation = (current.generation
                          if peer_id == current.peer_id and member_id == current.member_id
                          else current.generation + 1)
            if generation > MAX_GENERATION:
                raise ValueError("generation_exhausted")
            staged[index] = PeerRecord(member_id, peer_id, index, generation,
                                       PeerState.CONFIRMED, current.resource_handle)
            members.add(member_id)
            peers.add(peer_id)
        if sum(record is not None for record in staged) != sum(record is not None for record in self._records):
            raise ValueError("migration_record_count_mismatch")
        return staged

    def commit_migration(self, token: MigrationToken) -> dict[str, Any]:
        if not self._valid_migration_token(token):
            return self._record("migration_commit", False, "invalid_token")
        if self._migration is None:
            if self._migration_history.get(token.transaction_id) == "committed":
                return self._record("migration_commit", True, "already_committed",
                                    transaction_id=token.transaction_id)
            return self._record("migration_commit", False, "stale_or_missing")
        if self._migration["token"] != token:
            return self._record("migration_commit", False, "stale_or_missing")
        if self._leases:
            return self._record("migration_commit", False, "callback_in_flight")
        staged: list[PeerRecord | None] = self._migration["records"]
        # Rebuild identity indexes atomically from the staged records.
        member_map = {record.member_id: record.network_index for record in staged if record}
        peer_map = {record.peer_id: record.network_index for record in staged if record}
        if len(member_map) != len([record for record in staged if record]) or len(peer_map) != len(member_map):
            return self._record("migration_commit", False, "migration_identity_invalid")
        self._records = staged
        self._generation = [record.generation if record is not None else generation
                            for record, generation in zip(staged, self._generation)]
        self._member_to_index = member_map
        self._peer_to_index = peer_map
        self._components = {
            (record.network_index, record.generation)
            for record in staged if record is not None and record.resource_handle is not None
        }
        self._published = set(self._components)
        self.owner_key = token.owner_key
        self.owner_epoch = token.owner_epoch
        self._migration = None
        self._migration_history[token.transaction_id] = "committed"
        self.validate()
        return self._record("migration_commit", True, "committed",
                            transaction_id=token.transaction_id, owner_key=self.owner_key,
                            owner_epoch=self.owner_epoch)

    def abort_migration(self, token: MigrationToken) -> dict[str, Any]:
        if not self._valid_migration_token(token):
            return self._record("migration_abort", False, "invalid_token")
        if self._migration is None:
            if self._migration_history.get(token.transaction_id) == "aborted":
                return self._record("migration_abort", True, "already_aborted",
                                    transaction_id=token.transaction_id)
            return self._record("migration_abort", False, "stale_or_missing")
        if self._migration["token"] != token:
            return self._record("migration_abort", False, "stale_or_missing")
        self._migration = None
        self._migration_history[token.transaction_id] = "aborted"
        self.validate()
        return self._record("migration_abort", True, "rolled_back", transaction_id=token.transaction_id,
                            owner_key=self.owner_key, owner_epoch=self.owner_epoch)

    def validate(self) -> None:
        if len(self._records) != CAPACITY or len(self._generation) != CAPACITY:
            raise AssertionError("capacity invariant broken")
        seen_member: dict[str, int] = {}
        seen_peer: dict[str, int] = {}
        for index, record in enumerate(self._records):
            if record is None:
                continue
            if record.network_index != index or record.generation != self._generation[index]:
                raise AssertionError("record/index generation mismatch")
            if record.state not in set(PeerState):
                raise AssertionError("invalid state")
            if record.member_id in seen_member or record.peer_id in seen_peer:
                raise AssertionError("duplicate identity")
            if record.state is PeerState.PENDING and record.resource_handle is not None:
                raise AssertionError("pending resource leak")
            if record.state is PeerState.CONFIRMED and not record.resource_handle:
                raise AssertionError("confirmed resource missing")
            seen_member[record.member_id] = index
            seen_peer[record.peer_id] = index
        if seen_member != self._member_to_index or seen_peer != self._peer_to_index:
            raise AssertionError("identity map mismatch")
        expected_components = {
            (record.network_index, record.generation)
            for record in self._records if record is not None and record.resource_handle is not None
        }
        expected_handles = {
            record.resource_handle for record in self._records
            if record is not None and record.resource_handle is not None
        }
        if self._components != expected_components or self._handles != expected_handles:
            raise AssertionError("resource registry mismatch")
        if not self._published.issubset(expected_components):
            raise AssertionError("confirmed dispatch mismatch")

    def snapshot(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema": "hd2_peer_lifecycle_sidecar_contract_v1",
            "build": self.build,
            "capacity": CAPACITY,
            "owner_key": self.owner_key,
            "owner_epoch": self.owner_epoch,
            "records": [
                ({**asdict(record), "state": record.state.value} if record else None)
                for record in self._records
            ],
            "generation": list(self._generation),
            "member_to_index": dict(self._member_to_index),
            "peer_to_index": dict(self._peer_to_index),
            "callback_leases": len(self._leases),
            "migration_in_progress": self._migration is not None,
            "diagnostics": deepcopy(self._diagnostics),
        }


def synthetic_report() -> dict[str, Any]:
    sidecar = PeerLifecycleSidecar(0x1000, "epoch-1")
    cancel_probe = PeerLifecycleSidecar(0x1001, "epoch-cancel")
    cancel_token = cancel_probe.reserve("member-cancel", "peer-cancel", 0)
    cancel_first = cancel_probe.cancel_pending(cancel_token)
    cancel_second = cancel_probe.cancel_pending(cancel_token)
    token = sidecar.reserve("member-4", "peer-4", 4)
    failed = sidecar.confirm(token, "handle-4", fail_stage="confirmed_dispatch")
    retry = sidecar.confirm(token, "handle-4")
    lease = sidecar.acquire_callback(token)
    migration_blocked = False
    try:
        sidecar.begin_migration(0x2000, "epoch-2")
    except ValueError as error:
        migration_blocked = str(error) == "callback_in_flight"
    sidecar.release_callback(lease)
    migration = sidecar.begin_migration(0x2000, "epoch-2")
    committed = sidecar.commit_migration(migration)
    departed = sidecar.depart(token)
    duplicate_depart = sidecar.depart(token)
    reconnect = sidecar.reserve("member-4", "peer-4-reconnect", 4)
    sidecar.confirm(reconnect, "handle-4-reconnect")
    bool_index = sidecar.begin_release(PeerToken(True, reconnect.generation))
    bool_generation = sidecar.begin_release(PeerToken(reconnect.network_index, True))
    sidecar.validate()
    return {
        "schema": "hd2_peer_lifecycle_sidecar_contract_v1",
        "build": BUILD,
        "capacity": CAPACITY,
        "checks": {
            "partial_confirm_rollback": failed["reason"] == "callback_failed" and retry["accepted"],
            "callback_lease_quiescence": migration_blocked,
            "migration_commit": committed["accepted"] and sidecar.owner_epoch == "epoch-2",
            "departure_idempotence": departed["accepted"] and duplicate_depart["accepted"] and duplicate_depart["reason"] == "already_removed",
            "pending_cancel_idempotence": (cancel_first["accepted"]
                                            and cancel_second["accepted"]
                                            and cancel_second["reason"] == "already_cancelled"),
            "reconnect_generation_fence": reconnect.generation > token.generation,
            "resource_cleanup_no_leak": not sidecar._handles - {"handle-4-reconnect"},
            "stable_network_index": reconnect.network_index == 4,
            "token_identity_type_guard": (bool_index["reason"] == "stale_or_missing"
                                           and bool_generation["reason"] == "stale_or_missing"),
        },
        "snapshot": sidecar.snapshot(),
        "native_owner_quiescence_proven": False,
        "runtime_verified": False,
        "installable": False,
        "multiplayer_verified": False,
    }


__all__ = ["BUILD", "CAPACITY", "CallbackLease", "MigrationToken", "PeerLifecycleSidecar",
           "PeerState", "PeerToken", "synthetic_report"]
