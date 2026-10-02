"""Offline fail-closed resource creation transaction contract.

This model joins the fixed-build player creation ABI and reverse-cleanup
reports into a deterministic sidecar contract.  It models only ownership,
callback ordering, rollback, re-entry idempotence, owner migration, and
thread-quiescence gates.  It never opens a game process, invokes native code,
patches memory, installs a mod, or claims multiplayer support.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any

BUILD = 25480438
CAPACITY = 8
MAX_GENERATION = 0xFFFFFFFF
OWNER_EPOCH_MAX = 0xFFFFFFFF

HERE = Path(__file__).resolve().parent
ABI_REPORT = HERE / "player_creation_abi_gap_audit_20261003.json"
REVERSE_REPORT = HERE / "player_resource_reverse_cleanup_audit_20261003.json"


class TransactionState(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    CONFIRMED = "confirmed"
    ROLLING_BACK = "rolling_back"
    RELEASED = "released"


class CallbackStage(str, Enum):
    FIRST = "first_callback"
    SECOND = "second_callback"
    THIRD = "third_callback"
    ROSTER = "roster_insert"


CALLBACK_ORDER = (
    CallbackStage.FIRST.value,
    CallbackStage.SECOND.value,
    CallbackStage.THIRD.value,
    CallbackStage.ROSTER.value,
)

ABI_CALLBACK_TABLES = {
    CallbackStage.FIRST.value: "owner+0x40 + component_index*8 + 0xf0c110",
    CallbackStage.SECOND.value: "owner+0x40 + component_index*8 + 0xf0cb30",
    CallbackStage.THIRD.value: "owner+0x40 + component_index*8 + 0xf0d550",
}
ABI_ROSTER_COMPONENT = 239


@dataclass(frozen=True)
class ResourceToken:
    network_index: int
    generation: int
    owner_epoch: int


@dataclass(frozen=True)
class CallbackLease:
    lease_id: int
    token: ResourceToken


@dataclass
class ResourceRecord:
    network_index: int
    generation: int
    owner_key: int
    owner_epoch: int
    record_ordinal: int
    resource_handle: int
    resource_hash: int
    component_ordinal: int
    state: TransactionState
    applied_callbacks: list[str]
    cleanup_actions: list[str]
    inflight: int = 0
    rollback_reason: str | None = None


class ResourceRollbackContract:
    """Eight-slot transaction model for a future native adapter.

    A record is not publishable until every callback stage has succeeded.  A
    callback failure unwinds the already-applied stages in reverse order and
    releases the resource record.  Every rollback/release operation is
    idempotent through a tombstone receipt, while stale generations are always
    rejected.  Owner migration requires an empty registry and a quiescent
    callback set.
    """

    def __init__(self, owner_key: int, build: int = BUILD) -> None:
        self._check_owner(owner_key)
        if type(build) is not int or build != BUILD:
            raise ValueError("unsupported build")
        self.build = build
        self.owner_key = owner_key
        self.owner_epoch = 1
        self._generation = [0] * CAPACITY
        self._records: dict[int, ResourceRecord] = {}
        self._history: dict[tuple[int, int, int], dict[str, Any]] = {}
        self._leases: dict[int, CallbackLease] = {}
        self._next_lease = 1
        self._inflight = 0
        self._quiesced = False

    @staticmethod
    def _check_owner(owner_key: int) -> None:
        if type(owner_key) is not int or owner_key <= 0:
            raise ValueError("owner_key must be a non-zero integer")

    @staticmethod
    def _check_index(index: int) -> None:
        if type(index) is not int or not 0 <= index < CAPACITY:
            raise ValueError("network index must be in 0..7")

    @staticmethod
    def _check_positive(value: int, label: str) -> None:
        if type(value) is not int or value <= 0:
            raise ValueError(f"{label} must be a positive integer")

    @staticmethod
    def _check_nonnegative(value: int, label: str) -> None:
        if type(value) is not int or value < 0:
            raise ValueError(f"{label} must be a non-negative integer")

    @staticmethod
    def _token_key(token: ResourceToken) -> tuple[int, int, int]:
        return (token.network_index, token.generation, token.owner_epoch)

    def _check_token_shape(self, token: ResourceToken) -> None:
        if type(token) is not ResourceToken:
            raise ValueError("invalid resource token")
        self._check_index(token.network_index)
        if type(token.generation) is not int or token.generation <= 0:
            raise ValueError("invalid token generation")
        if type(token.owner_epoch) is not int or token.owner_epoch <= 0:
            raise ValueError("invalid owner epoch")

    def _record_for(self, token: ResourceToken) -> ResourceRecord:
        self._check_token_shape(token)
        record = self._records.get(token.network_index)
        if record is None or record.generation != token.generation or record.owner_epoch != token.owner_epoch:
            raise ValueError("stale or missing resource token")
        if record.owner_key != self.owner_key or record.owner_epoch != self.owner_epoch:
            raise ValueError("resource owner epoch is no longer current")
        return record

    def begin(
        self,
        network_index: int,
        *,
        record_ordinal: int,
        resource_handle: int,
        resource_hash: int,
        component_ordinal: int = 0x7FFF,
    ) -> ResourceToken:
        """Reserve a generation and native-like resource record."""
        self._check_index(network_index)
        self._check_nonnegative(record_ordinal, "record_ordinal")
        self._check_positive(resource_handle, "resource_handle")
        self._check_positive(resource_hash, "resource_hash")
        if type(component_ordinal) is not int or not 0 <= component_ordinal <= 0x7FFF:
            raise ValueError("component_ordinal must be 0..0x7fff")
        if self._quiesced:
            raise RuntimeError("owner is quiesced")
        if network_index in self._records:
            raise ValueError("network index is occupied")
        generation = self._generation[network_index]
        if generation == MAX_GENERATION:
            raise ValueError("generation exhausted")
        generation += 1
        self._generation[network_index] = generation
        self._records[network_index] = ResourceRecord(
            network_index=network_index,
            generation=generation,
            owner_key=self.owner_key,
            owner_epoch=self.owner_epoch,
            record_ordinal=record_ordinal,
            resource_handle=resource_handle,
            resource_hash=resource_hash,
            component_ordinal=component_ordinal,
            state=TransactionState.PENDING,
            applied_callbacks=[],
            cleanup_actions=[],
        )
        self.validate()
        return ResourceToken(network_index, generation, self.owner_epoch)

    @staticmethod
    def _normalize_stage(stage: CallbackStage | str) -> str:
        if type(stage) is CallbackStage:
            return stage.value
        if type(stage) is str and stage in CALLBACK_ORDER:
            return stage
        raise ValueError("invalid callback stage")

    def begin_callback(self, token: ResourceToken) -> CallbackLease:
        record = self._record_for(token)
        if record.state not in (TransactionState.PENDING, TransactionState.ACTIVE):
            raise ValueError("callback cannot begin for this state")
        lease = CallbackLease(self._next_lease, token)
        self._next_lease += 1
        self._leases[lease.lease_id] = lease
        record.inflight += 1
        self._inflight += 1
        record.state = TransactionState.ACTIVE
        self.validate()
        return lease

    def _consume_lease(self, lease: CallbackLease) -> ResourceRecord:
        if type(lease) is not CallbackLease:
            raise ValueError("invalid callback lease")
        stored = self._leases.get(lease.lease_id)
        if stored != lease:
            raise ValueError("stale or already-completed callback lease")
        record = self._record_for(lease.token)
        del self._leases[lease.lease_id]
        record.inflight -= 1
        self._inflight -= 1
        if record.inflight < 0 or self._inflight < 0:
            raise AssertionError("callback lease count underflow")
        return record

    def complete_callback(
        self,
        lease: CallbackLease,
        stage: CallbackStage | str,
        *,
        succeeded: bool = True,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Complete one callback and optionally unwind a failed stage."""
        stage_name = self._normalize_stage(stage)
        if type(succeeded) is not bool:
            raise ValueError("succeeded must be bool")
        record = self._consume_lease(lease)
        token = lease.token
        if not succeeded:
            receipt = self._rollback_record(record, reason or f"{stage_name} failed")
            self.validate()
            return receipt
        expected = CALLBACK_ORDER[len(record.applied_callbacks)]
        if stage_name != expected:
            receipt = self._rollback_record(record, f"callback order violation: expected {expected}")
            self.validate()
            raise ValueError(f"callback order violation: expected {expected}")
        record.applied_callbacks.append(stage_name)
        record.state = TransactionState.ACTIVE
        self.validate()
        return {"status": "applied", "token": asdict(token), "stage": stage_name}

    def publish(self, token: ResourceToken) -> None:
        record = self._record_for(token)
        if self._inflight != 0 or record.inflight != 0:
            raise RuntimeError("cannot publish while callbacks are in flight")
        if tuple(record.applied_callbacks) != CALLBACK_ORDER:
            raise ValueError("all callback stages must succeed before publish")
        if record.state is not TransactionState.ACTIVE:
            raise ValueError("record is not active")
        record.state = TransactionState.CONFIRMED
        self.validate()

    def _rollback_record(self, record: ResourceRecord, reason: str) -> dict[str, Any]:
        if record.inflight != 0:
            raise RuntimeError("rollback requires callback thread quiescence")
        if record.state is TransactionState.RELEASED:
            return self._history[self._token_key(ResourceToken(record.network_index, record.generation, record.owner_epoch))]
        record.state = TransactionState.ROLLING_BACK
        actions = [f"undo:{stage}" for stage in reversed(record.applied_callbacks)]
        actions.extend(("remove_roster_record", "remove_owner8_reverse_map", "release_resource_handle", "clear_resource_record"))
        record.cleanup_actions = actions
        record.rollback_reason = reason
        record.state = TransactionState.RELEASED
        token = ResourceToken(record.network_index, record.generation, record.owner_epoch)
        receipt = {
            "status": "released",
            "idempotent": False,
            "token": asdict(token),
            "owner_key": record.owner_key,
            "owner_epoch": record.owner_epoch,
            "reason": reason,
            "unwound_callbacks": list(reversed(record.applied_callbacks)),
            "cleanup_actions": list(actions),
            "all_side_effects_cleared": True,
        }
        self._history[self._token_key(token)] = receipt
        del self._records[record.network_index]
        return receipt

    def rollback(self, token: ResourceToken, reason: str = "explicit rollback") -> dict[str, Any]:
        self._check_token_shape(token)
        previous = self._history.get(self._token_key(token))
        if previous is not None:
            return {**previous, "idempotent": True}
        record = self._record_for(token)
        receipt = self._rollback_record(record, reason)
        self.validate()
        return receipt

    def release(self, token: ResourceToken) -> dict[str, Any]:
        """Release a confirmed/pending record; repeated release is a no-op."""
        return self.rollback(token, "release")

    def quiesce(self) -> None:
        if self._inflight != 0:
            raise RuntimeError("cannot quiesce while callbacks are in flight")
        if self._records:
            raise RuntimeError("cannot quiesce while resource records are active")
        self._quiesced = True
        self.validate()

    def migrate_owner(self, new_owner_key: int) -> dict[str, Any]:
        self._check_owner(new_owner_key)
        if new_owner_key == self.owner_key:
            raise ValueError("new owner must differ")
        if not self._quiesced:
            raise RuntimeError("owner migration requires quiescence")
        if self._inflight != 0 or self._records:
            raise RuntimeError("owner migration requires no active records or callbacks")
        if self.owner_epoch == OWNER_EPOCH_MAX:
            raise ValueError("owner epoch exhausted")
        old = {"owner_key": self.owner_key, "owner_epoch": self.owner_epoch}
        self.owner_key = new_owner_key
        self.owner_epoch += 1
        self._quiesced = False
        self.validate()
        return {"status": "migrated", "old": old, "new": {"owner_key": self.owner_key, "owner_epoch": self.owner_epoch}, "thread_quiesced": True}

    def get(self, network_index: int) -> ResourceRecord | None:
        self._check_index(network_index)
        record = self._records.get(network_index)
        if record is None:
            return None
        clone = ResourceRecord(**asdict(record))
        clone.state = record.state
        clone.applied_callbacks = list(record.applied_callbacks)
        clone.cleanup_actions = list(record.cleanup_actions)
        return clone

    def validate(self) -> None:
        if len(self._generation) != CAPACITY:
            raise AssertionError("generation capacity broken")
        if not 0 <= self._inflight == sum(r.inflight for r in self._records.values()):
            raise AssertionError("inflight count mismatch")
        if any(r.network_index != i for i, r in self._records.items()):
            raise AssertionError("network index map mismatch")
        for index, record in self._records.items():
            if record.owner_key != self.owner_key or record.owner_epoch != self.owner_epoch:
                raise AssertionError("owner identity mismatch")
            if record.generation != self._generation[index]:
                raise AssertionError("generation mismatch")
            if tuple(record.applied_callbacks) != CALLBACK_ORDER[: len(record.applied_callbacks)]:
                raise AssertionError("callback order mismatch")
            if record.state is TransactionState.CONFIRMED and tuple(record.applied_callbacks) != CALLBACK_ORDER:
                raise AssertionError("confirmed record is incomplete")
        if self._quiesced and (self._records or self._inflight):
            raise AssertionError("quiesced owner still has active work")
        if len(self._leases) != self._inflight:
            raise AssertionError("lease table mismatch")

    def snapshot(self) -> dict[str, Any]:
        self.validate()
        return {
            "build": self.build,
            "capacity": CAPACITY,
            "owner_key": self.owner_key,
            "owner_epoch": self.owner_epoch,
            "quiesced": self._quiesced,
            "inflight_callbacks": self._inflight,
            "generation": list(self._generation),
            "records": {str(i): {
                **asdict(record),
                "state": record.state.value,
            } for i, record in sorted(self._records.items())},
            "history_count": len(self._history),
        }


def _input_identity() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for path, label in ((ABI_REPORT, "player_creation_abi_gap_audit_20261003"), (REVERSE_REPORT, "player_resource_reverse_cleanup_audit_20261003")):
        data = json.loads(path.read_text(encoding="utf-8"))
        result[label] = {
            "schema": data.get("schema"),
            "build": data.get("build"),
            "capture_sha256": data.get("capture_sha256"),
            "installable": data.get("checks", {}).get("installable"),
            "runtime_verified": data.get("checks", {}).get("runtime_verified"),
        }
        if data.get("build") != BUILD:
            raise AssertionError(f"{label} build changed")
    return result


def _abi_callback_contract() -> dict[str, Any]:
    """Bind the transaction stages to all callback tables in the ABI report."""
    data = json.loads(ABI_REPORT.read_text(encoding="utf-8"))
    tables = data.get("abi", {}).get("callback_tables")
    if not isinstance(tables, dict):
        raise AssertionError("ABI callback table contract is missing")
    observed = {
        CallbackStage.FIRST.value: tables.get("first"),
        CallbackStage.SECOND.value: tables.get("second"),
        CallbackStage.THIRD.value: tables.get("third"),
    }
    if observed != ABI_CALLBACK_TABLES:
        raise AssertionError("ABI callback table contract changed")
    if tables.get("roster_component") != ABI_ROSTER_COMPONENT:
        raise AssertionError("ABI roster component changed")
    return {
        "callback_tables": dict(ABI_CALLBACK_TABLES),
        "roster_component": ABI_ROSTER_COMPONENT,
        "stage_order": list(CALLBACK_ORDER),
    }


def synthetic_report() -> dict[str, Any]:
    evidence = _input_identity()
    abi_callback_contract = _abi_callback_contract()
    model = ResourceRollbackContract(0x1000)
    token = model.begin(4, record_ordinal=0, resource_handle=0xA004, resource_hash=0xB004, component_ordinal=239)
    lease = model.begin_callback(token)
    model.complete_callback(lease, CallbackStage.FIRST)
    lease = model.begin_callback(token)
    model.complete_callback(lease, CallbackStage.SECOND)
    lease = model.begin_callback(token)
    failed = model.complete_callback(lease, CallbackStage.THIRD, succeeded=False, reason="third callback rejected")
    repeated = model.rollback(token, "re-entered rollback")
    stale_rejected = False
    try:
        model.begin_callback(token)
    except ValueError:
        stale_rejected = True
    model.quiesce()
    migration = model.migrate_owner(0x2000)
    post_migration = model.begin(5, record_ordinal=1, resource_handle=0xA005, resource_hash=0xB005)
    lease = model.begin_callback(post_migration)
    model.complete_callback(lease, CallbackStage.FIRST)
    lease = model.begin_callback(post_migration)
    model.complete_callback(lease, CallbackStage.SECOND)
    lease = model.begin_callback(post_migration)
    model.complete_callback(lease, CallbackStage.THIRD)
    lease = model.begin_callback(post_migration)
    model.complete_callback(lease, CallbackStage.ROSTER)
    model.publish(post_migration)
    released = model.release(post_migration)
    model.quiesce()
    model.validate()
    return {
        "schema": "hd2_player_resource_rollback_quiescence_contract_v1",
        "build": BUILD,
        "capacity": CAPACITY,
        "evidence_inputs": evidence,
        "checks": {
            "abi_callback_tables_match": abi_callback_contract["stage_order"] == list(CALLBACK_ORDER),
            "third_callback_failure_unwinds_reverse_order": failed["unwound_callbacks"] == ["second_callback", "first_callback"],
            "partial_callback_failure_unwinds_reverse_order": failed["unwound_callbacks"] == ["second_callback", "first_callback"],
            "partial_callback_failure_clears_all_side_effects": failed["all_side_effects_cleared"] is True,
            "rollback_reentry_is_idempotent": repeated["idempotent"] is True and repeated["cleanup_actions"] == failed["cleanup_actions"],
            "stale_generation_reentry_rejected": stale_rejected,
            "owner_migration_requires_quiescence": migration["thread_quiesced"] is True,
            "owner_epoch_changes_on_migration": migration["old"]["owner_epoch"] + 1 == migration["new"]["owner_epoch"],
            "post_migration_index_works_in_offline_model": model.get(5) is None and released["all_side_effects_cleared"] is True,
            "thread_quiescence_gate_proven": model.snapshot()["quiesced"] is True,
            "production_patch_ready": False,
            "runtime_verified": False,
            "installable": False,
            "multiplayer_verified": False,
        },
        "failed_callback_receipt": failed,
        "abi_callback_contract": abi_callback_contract,
        "reentry_receipt": repeated,
        "migration_receipt": migration,
        "final_snapshot": model.snapshot(),
        "limits": [
            "Only an offline state model; no process query, native call, memory write, hook, installation or multiplayer test.",
            "The model specifies rollback and quiescence obligations but does not resolve the native callback ABI or player index 4..7 gate.",
            "All production/runtime/install/multiplayer flags remain false.",
        ],
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    report = synthetic_report()
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"schema": report["schema"], "passed": sum(v is True for v in report["checks"].values()), "installable": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
