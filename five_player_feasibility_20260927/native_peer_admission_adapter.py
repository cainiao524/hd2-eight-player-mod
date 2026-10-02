"""Exact-build native peer-admission plan and sidecar state.

This module is the boundary between the data-only admission contract and a
future in-process bridge.  It intentionally does not write a game binary,
install a hook, or call PlayFab/Party.  The current build stores host peers,
flags, pending records, and client confirmed peers inline in four-entry
regions.  Extending those regions in place would overwrite adjacent live
state, so the candidate keeps entries in sidecars and requires explicit
trampolines at the recorded native roots.

The module has two useful jobs today:

* validate the exact live/disk build and the saved native signatures;
* exercise the sidecar lifecycle that a native bridge must preserve.

``plan_from_capture`` consumes an explicitly supplied capture document.  It
does not discover processes or infer addresses from a mutable installation.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

MAX_PLAYERS = 8
VALID_INDEXES = range(MAX_PLAYERS)
STEAM_BUILD = 25480438
EXE_SHA256 = "f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06"
GAME_SHA256 = "2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e"
PARTY_SHA256 = "de34667c2f7084013d9c03cd5d1cb5dc3321bc36bb616a845e35534e4e7995e0"
PLAYFAB_SHA256 = "95bc5f958e519f612b479de4227f3bdffaba9b2b8de987eb3f7991960b8ced17"


class NativePlanError(ValueError):
    """Raised when an exact-build plan cannot be proven safe."""


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_build_files(files: dict[str, str | Path]) -> dict[str, Any]:
    """Hash explicitly supplied files and fail closed on a mismatch.

    The caller provides paths for ``exe``, ``game``, ``party`` and ``playfab``.
    There is no Steam discovery and no fallback to a different build.
    """
    expected = {"exe": EXE_SHA256, "game": GAME_SHA256,
                "party": PARTY_SHA256, "playfab": PLAYFAB_SHA256}
    if set(files) != set(expected):
        raise NativePlanError("all four native files are required")
    rows = {}
    for role, raw in files.items():
        path = Path(raw)
        if not path.is_file():
            raise NativePlanError(f"missing file: {role}")
        observed = _digest(path)
        rows[role] = {"path": str(path), "expected_sha256": expected[role],
                      "observed_sha256": observed, "matched": observed == expected[role]}
        if observed != expected[role]:
            raise NativePlanError(f"fingerprint mismatch: {role}")
    return {"steam_build": STEAM_BUILD, "files": rows, "verified": True}


# These are interception boundaries, not byte edits.  Their four-entry
# consumers must be redirected to sidecars as a unit; changing a single cmp
# immediate to 8 would write into adjacent fields.
NATIVE_SITES: tuple[dict[str, Any], ...] = (
    {"module": "game", "rva": 0x108BC70, "name": "host_join_root",
     "four_slot_effect": "host peer, pending, flags and large record roots",
     "action": "trampoline_to_host_sidecar"},
    {"module": "game", "rva": 0x108C18F, "name": "host_capacity_gate",
     "four_slot_effect": "remaining-capacity calculation",
     "action": "replace_with_sidecar_count"},
    {"module": "game", "rva": 0x108C3D8, "name": "host_index_allocator",
     "four_slot_effect": "host+0x100 byte flags and index 0..3 scan",
     "action": "sidecar_index_allocator"},
    {"module": "game", "rva": 0x108C760, "name": "confirmed_peer_sender",
     "four_slot_effect": "four inline host slots",
     "action": "sidecar_confirmed_peer_emit"},
    {"module": "game", "rva": 0x1089720, "name": "host_migration_rebuild",
     "four_slot_effect": "migration peer/flag scans",
     "action": "sidecar_migration_rebuild"},
    {"module": "game", "rva": 0x108D190, "name": "host_peer_remove",
     "four_slot_effect": "peer, flag and four large-record cleanup",
     "action": "sidecar_remove_and_release"},
    {"module": "game", "rva": 0xB90B20, "name": "client_confirmed_peer_insert",
     "four_slot_effect": "client+0xD0 record array overlaps +0x150 on entry 5",
     "action": "sidecar_client_confirmed_insert"},
    {"module": "game", "rva": 0x1087540, "name": "client_confirmed_peer_remove",
     "four_slot_effect": "count/stride removal over inline records",
     "action": "sidecar_client_confirmed_remove"},
    {"module": "game", "rva": 0x10845B0, "name": "client_confirmed_peer_reset",
     "four_slot_effect": "128-byte inline reset",
     "action": "sidecar_client_confirmed_reset"},
    {"module": "game", "rva": 0x1086460, "name": "player_creation_gate",
     "four_slot_effect": "network index < 4 branch skips player resource call",
     "action": "sidecar_player_creation_dispatch"},
)

# Four-kilobyte loaded-image signatures from the authorized 2026-10-02
# capture.  A future runtime must match these before any bridge is considered.
# They are identity checks, not permission to patch the process.
CAPTURE_SITE_SHA256 = {
    0x108BC70: "091be1b9510cc8b76bf19e3efde819cc07f83dfb5951b050892ac727875520fa",
    0x108C18F: "48ff750deb7494432efede9988923444c6694a8068dd6f3b9429328b56a5a4ca",
    0x108C3D8: "ec844da4927996be016d4af7173c2ab5afb6659ac6a25f7308a175fe3dc6d6dc",
    0x108C760: "1400f933c08efc61110e184134cb5ccde5583a0e1f308abc56715bb314dc66e8",
    0x1089720: "2b56e46bc251fd1dcc117bdb9816ddb5aeb7ad38031f6243249f7953fe7656bb",
    0x108D190: "47e8be4bee09f6ed59d20dda75ebdbebc60db9a3c0fc3ac4a545ae401ae0a0f3",
    0xB90B20: "24fa11534f0fd92c803dd165b94214db95762b07ea00a69d7091c8c6cb3ddb10",
    0x1087540: "0ece0bae1fc26a84c12e93de1df0a720946a3b895270df81a4e2fbb41f963611",
    0x10845B0: "871cdeb8785316636f005d35b079dd1f0c9c0e65a95bf9ccffb7b7afed6c26cf",
    0x1086460: "7da855eb1e6b4340ed6ac2cce2c25f8994da70f61407ccdefd36c1bf925b61d4",
}


@dataclass
class SidecarPeer:
    member_id: str
    peer_id: str
    network_index: int
    generation: int
    pending: bool = True
    resource_handle: str | None = None


@dataclass
class NativeSidecar:
    """Stable host/client sidecar storage used by the future trampoline layer."""

    peers: list[SidecarPeer | None] = field(default_factory=lambda: [None] * MAX_PLAYERS)
    generations: list[int] = field(default_factory=lambda: [0] * MAX_PLAYERS)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def _record(self, operation: str, accepted: bool, reason: str, **details: Any) -> dict[str, Any]:
        row = {"operation": operation, "accepted": accepted, "reason": reason, **details}
        self.diagnostics.append(deepcopy(row))
        return row

    def _valid_index(self, index: Any) -> bool:
        return type(index) is int and index in VALID_INDEXES

    def reserve(self, member_id: str, peer_id: str, network_index: int) -> dict[str, Any]:
        if not isinstance(member_id, str) or not member_id or not isinstance(peer_id, str) or not peer_id:
            return self._record("reserve", False, "identity_missing")
        if not self._valid_index(network_index):
            return self._record("reserve", False, "network_index_invalid", network_index=network_index)
        if self.peers[network_index] is not None:
            return self._record("reserve", False, "network_index_occupied", network_index=network_index)
        if any(entry and (entry.peer_id == peer_id or entry.member_id == member_id) for entry in self.peers):
            return self._record("reserve", False, "duplicate_identity")
        self.generations[network_index] += 1
        if self.generations[network_index] <= 0:
            return self._record("reserve", False, "generation_exhausted")
        entry = SidecarPeer(member_id, peer_id, network_index, self.generations[network_index])
        self.peers[network_index] = entry
        return self._record("reserve", True, "pending", network_index=network_index,
                            generation=entry.generation)

    def confirm(self, peer_id: str, generation: int, resource_handle: str) -> dict[str, Any]:
        found = next((item for item in self.peers if item and item.peer_id == peer_id), None)
        if found is None:
            return self._record("confirm", False, "peer_missing")
        if type(generation) is not int or generation != found.generation:
            return self._record("confirm", False, "stale_generation")
        if not isinstance(resource_handle, str) or not resource_handle:
            return self._record("confirm", False, "resource_handle_missing")
        if not found.pending:
            return self._record("confirm", False, "already_confirmed")
        if any(item and item.resource_handle == resource_handle for item in self.peers):
            return self._record("confirm", False, "resource_handle_duplicate")
        found.pending = False
        found.resource_handle = resource_handle
        return self._record("confirm", True, "confirmed", network_index=found.network_index,
                            generation=found.generation)

    def remove(self, peer_id: str, generation: int) -> dict[str, Any]:
        found = next(((i, item) for i, item in enumerate(self.peers)
                      if item and item.peer_id == peer_id), None)
        if found is None:
            return self._record("remove", False, "peer_missing")
        ordinal, entry = found
        if type(generation) is not int or generation != entry.generation:
            return self._record("remove", False, "stale_generation")
        self.peers[ordinal] = None  # preserve a hole; never compact an active native table
        self.generations[ordinal] += 1
        return self._record("remove", True, "removed", network_index=ordinal,
                            generation=generation)

    def validate(self) -> dict[str, Any]:
        seen_peer: set[str] = set()
        seen_member: set[str] = set()
        seen_handle: set[str] = set()
        for index, entry in enumerate(self.peers):
            if entry is None:
                continue
            if entry.network_index != index or entry.peer_id in seen_peer or entry.member_id in seen_member:
                return {"accepted": False, "reason": "sidecar_mapping_invalid"}
            if not entry.pending and (not entry.resource_handle or entry.resource_handle in seen_handle):
                return {"accepted": False, "reason": "sidecar_resource_invalid"}
            seen_peer.add(entry.peer_id)
            seen_member.add(entry.member_id)
            if entry.resource_handle:
                seen_handle.add(entry.resource_handle)
        return {"accepted": True, "reason": "sidecar_valid"}

    def snapshot(self) -> dict[str, Any]:
        valid = self.validate()
        if not valid["accepted"]:
            raise NativePlanError(valid["reason"])
        return {"peers": [deepcopy(entry.__dict__) if entry else None for entry in self.peers],
                "generations": list(self.generations),
                "diagnostics": deepcopy(self.diagnostics),
                "occupied_count": sum(entry is not None for entry in self.peers),
                "active_count": sum(entry is not None and not entry.pending for entry in self.peers)}


def plan_from_capture(capture: dict[str, Any]) -> dict[str, Any]:
    """Build a read-only native plan from an explicit live capture document."""
    if not isinstance(capture, dict) or capture.get("schema") != "hd2_live_module_capture_v1":
        raise NativePlanError("capture_schema_invalid")
    if capture.get("build") != STEAM_BUILD:
        raise NativePlanError("steam_build_mismatch")
    if "rows" not in capture or not isinstance(capture["rows"], list):
        raise NativePlanError("capture_rows_missing")
    rows = {(row.get("module"), row.get("rva")): row for row in capture["rows"]
            if isinstance(row, dict) and "rva" in row}
    required = [("game", hex(site["rva"])) for site in NATIVE_SITES if site["module"] == "game"]
    missing = [key for key in required if key not in rows]
    if missing:
        raise NativePlanError("capture_site_missing:" + ",".join(map(str, missing)))
    for site in NATIVE_SITES:
        if site["module"] != "game":
            continue
        row = rows[("game", hex(site["rva"]))]
        if row.get("size") != 4096 or row.get("sha256") != CAPTURE_SITE_SHA256[site["rva"]]:
            raise NativePlanError("capture_site_signature_mismatch:" + hex(site["rva"]))
    return {
        "steam_build": STEAM_BUILD,
        "capture_pid": capture.get("pid"),
        "scope": capture.get("scope"),
        "sites": deepcopy(list(NATIVE_SITES)),
        "sidecar": {"host_peer_slots": MAX_PLAYERS, "client_confirmed_slots": MAX_PLAYERS,
                     "stable_network_indexes": list(VALID_INDEXES),
                     "hole_preserving": True},
        "executable": False,
        "requires": ["trampoline_unwind_registration", "host_sidecar_lifetime",
                     "client_sidecar_lifetime", "confirmed_peer_dispatch", "player_creation_gate"],
        "multiplayer_verified": False,
    }


def save_plan(capture_path: Path, output_path: Path) -> dict[str, Any]:
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    plan = plan_from_capture(capture)
    output_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return plan


__all__ = ["NativePlanError", "NativeSidecar", "NATIVE_SITES", "plan_from_capture",
           "save_plan", "validate_build_files"]
