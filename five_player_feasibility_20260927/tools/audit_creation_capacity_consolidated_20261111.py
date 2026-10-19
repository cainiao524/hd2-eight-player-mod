from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "output" / "native_dispatch_20261010" / "static_creation_capacity_consolidated_20261111.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def flatten_pins(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if {"rva", "bytes", "asm"}.issubset(value):
            found.append(value)
        for child in value.values():
            found.extend(flatten_pins(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(flatten_pins(child))
    return found


def pin(doc: Any, rva: str) -> dict[str, Any]:
    matches = [item for item in flatten_pins(doc) if item.get("rva") == rva]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one pin at {rva}, found {len(matches)}")
    return matches[0]


def compact_pin(item: dict[str, Any]) -> dict[str, Any]:
    return {key: item[key] for key in ("rva", "bytes", "asm", "root") if key in item}


creation_path_path = ROOT / "five_player_feasibility_20260927" / "creation_path_evidence_v3.json"
roster_path = ROOT / "five_player_feasibility_20260927" / "player_roster_evidence.json"
creation_findings_path = ROOT / "five_player_feasibility_20260927" / "creation_path_findings.zh-TW.md"
client_notes_path = ROOT / "five_player_feasibility_20260927" / "client_expansion_notes.md"
report_path = ROOT / "five_player_feasibility_20260927" / "REPORT.zh-TW.md"
prior_audit_path = ROOT / "output" / "native_dispatch_20261010" / "completion_audit_20261111_r7.json"

creation_path = load(creation_path_path)
roster = load(roster_path)

sources = []
for path in (creation_path_path, roster_path, creation_findings_path, client_notes_path, report_path, prior_audit_path):
    sources.append({"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)})

creation_request_pins = [
    compact_pin(pin(creation_path, "0x1091a9c")),
    compact_pin(pin(creation_path, "0x1091aa2")),
    compact_pin(pin(creation_path, "0x1091aa5")),
    compact_pin(pin(creation_path, "0x1093a90")),
    compact_pin(pin(creation_path, "0x1093a96")),
    compact_pin(pin(creation_path, "0x1093a99")),
]

platform_enumeration_pins = [
    compact_pin(pin(creation_path, "0x1092e78")),
    compact_pin(pin(creation_path, "0x1092ecb")),
    compact_pin(pin(creation_path, "0x1092ed0")),
    compact_pin(pin(creation_path, "0x1092f31")),
    compact_pin(pin(creation_path, "0x1093c91")),
    compact_pin(pin(creation_path, "0x1093c96")),
]

roster_guard_pins = [
    compact_pin(pin(roster, "0x60ca9c")),
    compact_pin(pin(roster, "0x60cbbb")),
]

report = {
    "schema": "hd2_creation_capacity_consolidated_audit_v1",
    "build_id": 25480438,
    "scope": "offline static evidence consolidation; no current game process access",
    "sources": sources,
    "creation_request_shape": {
        "observed": True,
        "status": "shape_only",
        "description": (
            "The host/recreate path derives a value from owner+0x1B90 and adds 4 before an unresolved "
            "platform-interface call. In the documented zero-config branch the derived first integer is 8."
        ),
        "pins": creation_request_pins,
        "api_name_resolved": False,
        "service_acceptance_verified": False,
        "player_capacity_meaning_verified": False,
    },
    "platform_lobby_enumeration": {
        "four_limit_observed": True,
        "status": "explicit_four_limit",
        "description": (
            "The helper and recreate/update path clamp returned member counts to 4 and pass 4 as "
            "enumeration capacity."
        ),
        "pins": platform_enumeration_pins,
    },
    "native_host_roster": {
        "four_limit_observed": True,
        "status": "explicit_four_entry_layout",
        "description": (
            "Both insertion paths reject tracked_count+1 above 4; the owner has four pointer positions "
            "at +0xE8, +0xF0, +0xF8 and +0x100 before another record region."
        ),
        "pins": roster_guard_pins,
        "derived_layout": roster.get("derived_layout", {}),
        "limits": roster.get("limits", []),
    },
    "client_layout": {
        "four_entry_layout_observed": True,
        "status": "adjacent_field_collision_at_fifth_entry",
        "description": (
            "The confirmed-peer list starts at client+0xD0 with 0x20-byte records and ends at +0x150, "
            "which is already used. Existing reset logic clears only 0x80 bytes, covering four records."
        ),
        "source": "client_expansion_notes.md",
        "requires_relayout": True,
    },
    "decision": {
        "eight_player_runtime_verified": False,
        "service_acceptance_verified": False,
        "safe_single_constant_patch": False,
        "safe_public_package": False,
        "max_verified_players": 4,
        "public_release_allowed": False,
    },
    "remaining_gaps": [
        "Resolve the platform-interface targets and calling semantics from an explicitly authorized live room capture.",
        "Verify service-side admission above four instead of inferring it from a static argument value.",
        "Relayout and verify host roster, client records, cleanup, migration, entity/resource creation and consumers together.",
        "Complete host/client join, leave, host migration and cleanup tests.",
        "Complete an 5-8 independent-client same-mission run before any public package.",
    ],
}

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"output": OUTPUT.relative_to(ROOT).as_posix(), "sha256": sha256(OUTPUT), "status": "written"}, ensure_ascii=False))
