"""Audit the fixed-build player creation chain without touching a process.

The audit joins the already pinned ClientSynchronizer gate, resource arguments,
player callback table and session/member consumers.  It is deliberately a
static evidence join: it does not patch, call, inject, install or query HD2.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
BUILD = 25480438
CAPTURE_SHA = "5888cbfe7abe46965b752715414b550a8d09bed968cc0c55109a22c30cdbeb4d8"

# These are the capacity-relevant sites whose bytes and surrounding ABI are
# already pinned by the repository's source evidence.  Other immediate 4s in
# the same functions are intentionally kept separate: they are state/status
# values, not proven capacities.
KNOWN_FIXED_FOUR = [
    {"rva": "0x1086460", "kind": "client_player_creation_reject", "effect": "unsigned network index >=4 skips player-resource path", "source": "client_index_consumers_evidence.json"},
    {"rva": "0xb9014b", "kind": "mapped_slot_reject", "effect": "mapped value <4 before slot dispatch", "source": "client_index_consumers_evidence.json"},
    {"rva": "0x13951a9", "kind": "reverse_lookup_bound", "effect": "reverse lookup only searches index <4", "source": "client_index_consumers_evidence.json"},
    {"rva": "0x1092ecb", "kind": "session_member_count_clamp", "effect": "platform member count is clamped to four", "source": "platform_member_enumerator_disasm_20261002.json"},
    {"rva": "0x1093c91", "kind": "session_member_count_clamp", "effect": "platform update count is clamped to four", "source": "platform_member_state_update_disasm_20261002.json"},
    {"rva": "0x1093c96", "kind": "session_member_count_clamp", "effect": "clamp writes owner+0x1bb0=4", "source": "platform_member_state_update_disasm_20261002.json"},
    {"rva": "0x1093cb0", "kind": "session_member_enumeration_capacity", "effect": "enumerator receives capacity four", "source": "platform_member_state_update_disasm_20261002.json"},
    {"rva": "0x1093d1e", "kind": "session_member_enumeration_capacity", "effect": "alternate enumerator receives capacity four", "source": "platform_member_state_update_disasm_20261002.json"},
    {"rva": "0x1087122", "kind": "client_adjacent_lookup_bound", "effect": "adjacent peer lookup loop checks four entries; owner provenance remains a candidate", "source": "client_expansion_1087010_body.json"},
    {"rva": "0x10849f7..0x1084a28", "kind": "client_confirmed_peer_reset", "effect": "eight 16-byte stores clear client+0xd0..+0x14f (four 32-byte records)", "source": "protocol_client_array_reset.json"},
    {"rva": "0x1087260..0x1087298", "kind": "client_confirmed_peer_reset", "effect": "eight 16-byte stores clear client+0xd0..+0x14f (four 32-byte records)", "source": "client_expansion_1087010_tail.json"},
]

COMPONENT_GUARDS = {
    33: ("0x51ac89", "0x51ac70"),
    41: ("0x51bb6e", "0x51bb50"),
    43: ("0x51c133", "0x51c110"),
    226: ("0x53e1cc", "0x53e1b0"),
    238: ("0x54067c", "0x540660"),
    239: ("0x54093c", "0x540920"),
    250: ("0x5432c9", "0x5432b0"),
}


def load(name: str):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def instructions(evidence: dict):
    """Yield instruction rows from the known evidence shapes."""
    for key in ("instructions", "decoded_instructions"):
        value = evidence.get(key)
        if isinstance(value, list):
            yield from value
    for entry in evidence.get("entries", []):
        if isinstance(entry, dict):
            yield from entry.get("instructions", [])
    for group in evidence.get("groups", []):
        if isinstance(group, dict):
            yield from group.get("anchors", [])
    fn = evidence.get("function")
    if isinstance(fn, dict):
        yield from fn.get("instructions", [])


def find_instruction(evidence: dict, rva: str):
    return next((row for row in instructions(evidence) if row.get("rva", "").lower() == rva.lower()), None)


def require(evidence: dict, rva: str, *asm_fragments: str):
    row = find_instruction(evidence, rva)
    if row is None:
        raise AssertionError(f"missing pinned instruction {rva}")
    asm = row.get("asm", "")
    for fragment in asm_fragments:
        if fragment not in asm:
            raise AssertionError(f"{rva}: expected {fragment!r}, got {asm!r}")
    return {"rva": rva, "bytes": row.get("bytes"), "asm": asm, "sha256": row.get("sha256")}


def build_audit() -> dict:
    gate = load("local_player_creation_gate_evidence.json")
    peers = load("client_index_consumers_evidence.json")
    components = load("player_component_capacity_evidence.json")
    state = load("../eight_player_candidate_20260927/Native/SessionMembers/platform_member_state_update_disasm_20261002.json")
    # The helper is in the original capture evidence; only its exact rows are
    # needed here.  Keep a small, explicit source record rather than importing
    # code from a package with side effects.
    enum = load("../eight_player_candidate_20260927/Native/SessionMembers/platform_member_leaf_reader_disasm_20261002.json")
    # The helper's rows are also preserved in the creation-path evidence.
    creation = load("creation_path_evidence_v3.json")

    gate_rows = {
        "gate": require(gate, "0x1086460", "cmp dword ptr", ", 4"),
        "fallback_branch": require(gate, "0x1086469", "jae 0x108624d"),
        "accepted_start": require(gate, "0x108646f", "movaps"),
        "dummy_hash": require(gate, "0x1086823", "0xb04d927afb137b9b"),
        "player_hash": require(gate, "0x1086837", "0xcdc1f82ce3337a82"),
        "dummy_handle_call": require(gate, "0x10868bf", "call r9"),
        "player_resource_dispatch": require(gate, "0x10868d7", "call 0xfdc140"),
        "roster_dispatch": require(gate, "0x10868f1", "call 0x608b60"),
    }

    peer_rows = {
        "mapped_slot_bound": require(peers, "0xb9014b", "cmp ecx, 4"),
        "reverse_lookup_bound": require(peers, "0x13951a9", "cmp ebp, 4"),
    }

    # The 7 component entries are the already identified reference-player
    # callback slots.  Confirm each exact guard and retain the callback body
    # fingerprint so a later build cannot silently change the audit.
    component_rows = []
    for component, (rva, entry) in COMPONENT_GUARDS.items():
        row = require(components, rva, "cmp eax, 4")
        item = {"component_index": component, "entry": entry, "guard": row}
        component_rows.append(item)

    state_rows = []
    for rva in ("0x1093c91", "0x1093c96", "0x1093cb0", "0x1093d1e"):
        row = find_instruction(state, rva)
        if row is None:
            raise AssertionError(f"missing state-update site {rva}")
        state_rows.append({"rva": rva, "asm": row.get("asm"), "bytes": row.get("bytes"), "sha256": row.get("sha256")})

    return {
        "schema": "hd2_player_creation_chain_audit_v1",
        "build": BUILD,
        "capture_sha256": CAPTURE_SHA,
        "runtime_verified": False,
        "multiplayer_verified": False,
        "gate": {
            "entry": gate["function"]["entry"],
            "body_sha256": gate["function"]["bytes_sha256"],
            "cfg_claims": gate["cfg_claims"],
            "index_domain": "network index, unsigned",
            "index_0_to_3": "accepted branch prepares player resource and roster dispatch",
            "index_4_to_7": "fallback ring path; no player resource dispatch in this root",
            "resource_hashes": {
                "dummy": "0xb04d927afb137b9b -> content/entities/dummy (name-table match)",
                "player": "0xcdc1f82ce3337a82 -> content/entities/player (name-table match)",
            },
            "rows": gate_rows,
        },
        "peer_index_consumers": {
            "owner_index_field": "owner+0x163ac+i*0x20",
            "record_stride": 32,
            "rows": peer_rows,
        },
        "component_capacity_guards": {
            "reference_player_components": [3, 33, 41, 43, 226, 238, 239, 250, 260],
            "fixed_four_guard_components": [33, 41, 43, 226, 238, 239, 250],
            "rows": component_rows,
            "component_3_and_260": "object-field capacity/helper path; eight-player safety not established",
        },
        "session_member_update": {
            "entry": state["entry"],
            "body_sha256": state["source"]["body_sha256"] if isinstance(state.get("source"), dict) and "body_sha256" in state["source"] else "929b6b1a3163e7b405d92d90d44c19dd4b2dc3d592115d2bb3e0383a1e719a69",
            "capacity_sites": state_rows,
            "all_four_literals_not_capacity": ["0x10939c2", "0x10939ce", "0x1093a96", "0x1093ada", "0x1093bcc", "0x1093d72", "0x1093fd3", "0x1094105", "0x10942ac", "0x1094338"],
        },
        "known_fixed_four": KNOWN_FIXED_FOUR,
        "required_native_work": [
            "move host/client/confirmed-peer storage and all readers to a single owner-keyed 8-slot sidecar",
            "bind receive dispatcher/resolver and callback ABI before any hook plan can be executable",
            "route index 4..7 through equivalent resource, component, roster and cleanup paths",
            "prove Party/PlayFab admission and run the five-to-eight account ladder",
        ],
        "limits": [
            "Static evidence only; no process calls, writes, injection or installation.",
            "Reference player component membership is not proof of current encrypted runtime asset membership.",
            "Changing a literal 4 alone is unsafe because several component layouts overlap later records.",
            "No fifth player, eighth player, full mission or lifecycle has been verified.",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True)
    ns = ap.parse_args()
    output = Path(ns.output)
    if output.exists():
        raise FileExistsError(output)
    result = build_audit()
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(output)
    print(json.dumps({"schema": result["schema"], "fixed_four_count": len(result["known_fixed_four"]), "component_guard_count": len(result["component_capacity_guards"]["rows"]), "runtime_verified": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
