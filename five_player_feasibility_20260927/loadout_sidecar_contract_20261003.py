"""Fail-closed eight-slot MenuScreenLoadout sidecar contract.

This module models the storage and lifecycle boundary identified by the fixed
build audit.  It intentionally has no process, pointer, package or native
callback access.  Network index, UI slot, widget token and generation are kept
as separate keys so a future native adapter cannot accidentally compact one
while changing another.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


BUILD = 25480438
CAPACITY = 8
MAX_GENERATION = 0xFFFFFFFF


class SlotState(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    RELEASING = "releasing"


@dataclass(frozen=True)
class LoadoutToken:
    network_index: int
    generation: int


@dataclass
class LoadoutRecord:
    network_index: int
    ui_slot: int
    widget_token: int
    generation: int
    state: SlotState


class LoadoutSidecar:
    """Stable eight-slot record and lifecycle model for native integration."""

    def __init__(self, owner_key: int, build: int = BUILD) -> None:
        if owner_key <= 0:
            raise ValueError("owner_key must be non-zero")
        if build != BUILD:
            raise ValueError("unsupported build")
        self.owner_key = owner_key
        self.build = build
        self._generation = [0] * CAPACITY
        self._records: list[LoadoutRecord | None] = [None] * CAPACITY
        self._ui_to_network: dict[int, int] = {}
        self._widget_to_network: dict[int, int] = {}

    @staticmethod
    def _check_index(index: int) -> None:
        if not isinstance(index, int) or not 0 <= index < CAPACITY:
            raise ValueError("network index must be in 0..7")

    @staticmethod
    def _check_ui_slot(ui_slot: int) -> None:
        if not isinstance(ui_slot, int) or not 0 <= ui_slot < CAPACITY:
            raise ValueError("UI slot must be in 0..7")

    @staticmethod
    def _check_widget(widget_token: int) -> None:
        if not isinstance(widget_token, int) or widget_token <= 0:
            raise ValueError("widget token must be non-zero")

    def _record_for(self, token: LoadoutToken) -> LoadoutRecord:
        self._check_index(token.network_index)
        if not isinstance(token.generation, int) or token.generation <= 0:
            raise ValueError("invalid generation")
        record = self._records[token.network_index]
        if record is None or record.generation != token.generation:
            raise ValueError("stale or missing loadout token")
        return record

    def reserve(self, network_index: int, ui_slot: int, widget_token: int) -> LoadoutToken:
        self._check_index(network_index)
        self._check_ui_slot(ui_slot)
        self._check_widget(widget_token)
        if self._records[network_index] is not None:
            raise ValueError("network index is occupied")
        if ui_slot in self._ui_to_network:
            raise ValueError("UI slot is occupied")
        if widget_token in self._widget_to_network:
            raise ValueError("widget token is occupied")
        generation = self._generation[network_index]
        if generation == MAX_GENERATION:
            raise ValueError("generation exhausted")
        generation += 1
        self._generation[network_index] = generation
        self._records[network_index] = LoadoutRecord(
            network_index, ui_slot, widget_token, generation, SlotState.PENDING
        )
        self._ui_to_network[ui_slot] = network_index
        self._widget_to_network[widget_token] = network_index
        self.validate()
        return LoadoutToken(network_index, generation)

    def confirm(self, token: LoadoutToken) -> None:
        record = self._record_for(token)
        if record.state is not SlotState.PENDING:
            raise ValueError("only pending records can be confirmed")
        record.state = SlotState.CONFIRMED
        self.validate()

    def move_ui(self, token: LoadoutToken, ui_slot: int) -> None:
        self._check_ui_slot(ui_slot)
        record = self._record_for(token)
        if record.state is SlotState.RELEASING:
            raise ValueError("releasing records cannot move UI slots")
        owner = self._ui_to_network.get(ui_slot)
        if owner is not None and owner != record.network_index:
            raise ValueError("UI slot is occupied")
        del self._ui_to_network[record.ui_slot]
        record.ui_slot = ui_slot
        self._ui_to_network[ui_slot] = record.network_index
        self.validate()

    def begin_release(self, token: LoadoutToken) -> None:
        record = self._record_for(token)
        if record.state is not SlotState.CONFIRMED:
            raise ValueError("only confirmed records can begin release")
        record.state = SlotState.RELEASING
        self.validate()

    def abort_release(self, token: LoadoutToken) -> None:
        record = self._record_for(token)
        if record.state is not SlotState.RELEASING:
            raise ValueError("only releasing records can abort")
        record.state = SlotState.CONFIRMED
        self.validate()

    def finish_release(self, token: LoadoutToken) -> None:
        record = self._record_for(token)
        if record.state is not SlotState.RELEASING:
            raise ValueError("release must be started before finish")
        del self._ui_to_network[record.ui_slot]
        del self._widget_to_network[record.widget_token]
        self._records[record.network_index] = None  # Preserve the network hole.
        self.validate()

    def get(self, network_index: int) -> LoadoutRecord | None:
        self._check_index(network_index)
        record = self._records[network_index]
        if record is None:
            return None
        return LoadoutRecord(**asdict(record))

    def by_widget(self, widget_token: int) -> LoadoutRecord | None:
        self._check_widget(widget_token)
        index = self._widget_to_network.get(widget_token)
        return self.get(index) if index is not None else None

    def snapshot(self) -> dict[str, Any]:
        self.validate()
        return {
            "build": self.build,
            "owner_key": self.owner_key,
            "capacity": CAPACITY,
            "records": [
                ({**asdict(record), "state": record.state.value} if record is not None else None)
                for record in self._records
            ],
            "generation": list(self._generation),
            "ui_to_network": dict(self._ui_to_network),
            "widget_to_network": dict(self._widget_to_network),
        }

    def validate(self) -> None:
        if len(self._records) != CAPACITY or len(self._generation) != CAPACITY:
            raise AssertionError("capacity invariant broken")
        seen_ui: dict[int, int] = {}
        seen_widget: dict[int, int] = {}
        for index, record in enumerate(self._records):
            if record is None:
                continue
            if record.network_index != index or record.generation != self._generation[index]:
                raise AssertionError("record/index generation mismatch")
            if record.state not in set(SlotState):
                raise AssertionError("invalid record state")
            if record.ui_slot in seen_ui or record.widget_token in seen_widget:
                raise AssertionError("duplicate UI slot or widget token")
            seen_ui[record.ui_slot] = index
            seen_widget[record.widget_token] = index
        if seen_ui != self._ui_to_network or seen_widget != self._widget_to_network:
            raise AssertionError("forward/inverse map mismatch")


def synthetic_report() -> dict[str, Any]:
    sidecar = LoadoutSidecar(owner_key=0x1000)
    tokens = [sidecar.reserve(i, i, 0x9000 + i) for i in range(CAPACITY)]
    for token in tokens:
        sidecar.confirm(token)
    sidecar.begin_release(tokens[7])
    sidecar.finish_release(tokens[7])
    sidecar.move_ui(tokens[0], 7)
    sidecar.begin_release(tokens[3])
    sidecar.abort_release(tokens[3])
    sidecar.begin_release(tokens[3])
    sidecar.finish_release(tokens[3])
    reconnect = sidecar.reserve(3, 0, 0xA003)
    sidecar.confirm(reconnect)
    reconnect_ui = sidecar.reserve(7, 3, 0xA007)
    sidecar.confirm(reconnect_ui)
    sidecar.validate()
    return {
        "schema": "hd2_loadout_sidecar_contract_v1",
        "build": BUILD,
        "capacity": CAPACITY,
        "active_records": sum(record is not None for record in sidecar._records),
        "hole_preserved_after_release": sidecar.get(3) is not None,
        "reconnect_generation": reconnect.generation,
        "network_index_ui_slot_separate": sidecar.get(3).ui_slot == 0 and sidecar.get(3).network_index == 3,
        "snapshot": sidecar.snapshot(),
        "production_patch_ready": False,
        "runtime_verified": False,
        "installable": False,
        "multiplayer_verified": False,
    }
