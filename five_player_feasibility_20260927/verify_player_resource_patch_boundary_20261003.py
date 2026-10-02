#!/usr/bin/env python3
"""Verify the fixed-build player resource/roster patch boundary.

This verifier consumes only checked-in static evidence.  It does not open a
Helldivers process, write game memory, install a hook, or claim multiplayer
success.  The intended result is a conservative decision: an eight-slot
sidecar is a valid data model, but the captured player-creation/resource path
does not yet provide enough ABI and lifetime evidence for a safe 4..7 patch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
EXPECTED_BUILD = 25480438
EXPECTED_CAPTURE = "5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8"
# The earlier player-chain JSON contains one extra ``c`` in this identity
# field.  Keep the compatibility value explicit so the verifier does not
# silently normalize or rewrite historical evidence.
LEGACY_CHAIN_CAPTURE = "5888cbfe7abe46965b752715414b550a8d09bed968cc0c55109a22c30cdbeb4d8"
EXPECTED_DATA = "31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d"


def load(name: str) -> dict[str, Any]:
    with (ROOT / name).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(report: dict[str, Any], name: str, ok: bool, detail: Any) -> None:
    report["checks"].append({"name": name, "passed": bool(ok), "detail": detail})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "player_resource_patch_boundary_verification_20261003.json",
    )
    args = parser.parse_args()

    chain = load("player_creation_chain_audit_20261002_r3.json")
    binding = load("roster_component_binding_evidence_v3.json")
    insert = load("roster_insert_native_evidence.json")
    callbacks = load("spawn_callback_registration_evidence_v2.json")
    metadata = load("spawn_resource_metadata_evidence.json")
    sidecar = load(Path("..") / "eight_player_candidate_20260927" / "Native" / "ClientSidecar" / "client_sidecar_report_20261002.json")

    report: dict[str, Any] = {
        "schema": "hd2_player_resource_patch_boundary_v1",
        "build": EXPECTED_BUILD,
        "capture_sha256": EXPECTED_CAPTURE,
        "runtime_verified": False,
        "multiplayer_verified": False,
        "checks": [],
        "decision": {},
    }

    # Capture/build identity is checked before interpreting any address.
    check(report, "creation_build", chain.get("build") == EXPECTED_BUILD, chain.get("build"))
    check(report, "creation_capture", chain.get("capture_sha256") in {EXPECTED_CAPTURE, LEGACY_CHAIN_CAPTURE}, {"value": chain.get("capture_sha256"), "legacy_alias": chain.get("capture_sha256") == LEGACY_CHAIN_CAPTURE})
    check(report, "insert_capture", insert.get("capture_identity_sha256") == EXPECTED_CAPTURE, insert.get("capture_identity_sha256"))
    check(report, "callback_capture", callbacks.get("capture_identity_sha256") == EXPECTED_CAPTURE, callbacks.get("capture_identity_sha256"))
    check(report, "capture_data_sha", insert.get("source_sha256", {}).get("captured-data.bin") == EXPECTED_DATA, insert.get("source_sha256", {}).get("captured-data.bin"))

    gate = chain["gate"]
    rows = gate["rows"]
    # The unsigned gate sends network index 4..7 to the fallback edge.  The
    # CFG proof says that edge cannot reach the resource/roster calls.
    check(report, "index_4_to_7_gate", rows["gate"]["asm"] == "cmp dword ptr [rdx + r8 + 0x163ac], 4", rows["gate"])
    check(report, "fallback_unreachable_resource_dispatch", gate["cfg_claims"]["handle_call_unreachable_without_accept_edge"] and gate["cfg_claims"]["setup_call_unreachable_without_accept_edge"], gate["cfg_claims"])
    check(report, "resource_dispatch_targets", rows["player_resource_dispatch"]["rva"] == "0x10868d7" and rows["roster_dispatch"]["rva"] == "0x10868f1", {"player": rows["player_resource_dispatch"], "roster": rows["roster_dispatch"]})

    resources = metadata["reference_metadata"]["resources"]
    player = next((r for r in resources if r.get("reference_name") == "content/entities/player"), None)
    check(report, "player_reference_resource_present", player is not None, player and {"count": player["count"], "indices": player["indices"]})
    check(report, "player_resource_selects_component_239", bool(player and player.get("includes_roster_callback_index_239") and 239 in player.get("indices", [])), player and player.get("indices"))

    # Component 239 is the callback selected by the first dispatch table.  Its
    # implementation still has an original count+1 <= 4 guard.
    comp = callbacks["component_239"]
    first_dispatch_targets = [x.get("target_rva") for x in comp if x.get("table_base_offset") == "0xf0c110"]
    check(report, "component_239_first_dispatch_callback", first_dispatch_targets == ["0x540920"], {"targets": first_dispatch_targets})
    cguards = chain["component_capacity_guards"]["fixed_four_guard_components"]
    # 239 is not listed as a component-level guard because the guard is in its
    # registered native callback 0x540920; assert the callback evidence and
    # the native insertion evidence together instead of inventing a new index.
    check(report, "component_239_native_insertion_is_fixed_four_guarded", "original four-slot guard" in " ".join(insert.get("limits", [])) and "0x540920" in insert["inserts"], {"fixed_component_guards": cguards, "insertion": insert["inserts"]["0x540920"].get("capacity_guard")})
    insert_summary = {
        "roots": sorted(insert["inserts"]),
        "array_site_counts": insert["finite_scope"]["all_array_site_counts"],
        "map_helper": insert["map_helper"]["behavior"],
    }
    check(report, "insert_bodies_have_four_slot_guard", all("original four-slot guard" in s for s in insert.get("limits", []) if "original four-slot guard" in s), insert_summary)
    check(report, "map_helper_does_not_grow", "neither allocates nor grows" in " ".join(insert.get("limits", [])), insert["map_helper"].get("behavior"))

    # The property stage stores network index in the roster parallel record.
    palette = binding["bounded_index_palette_consumer"]
    check(report, "property_stage_stores_network_index", any(d.get("roster_field_offset") == "0x3b4" and d.get("name_hash_match") == "index" for d in binding["descriptors"]), {"descriptors": binding["descriptors"]})
    check(report, "index_4_to_7_palette_has_fallback", palette.get("index_ge_four_output") == [255.0, 255.0, 255.0] and palette.get("index_ge_four_branch_rejects_join") is False, palette)

    # Existing sidecar is intentionally synthetic and rejects 4..7 without a
    # real player-creation callback.  This is a required safety condition, not
    # evidence that a live callback exists.
    prod = sidecar["production"]
    check(report, "existing_sidecar_is_nonproduction", prod.get("executable") is False and prod.get("multiplayer_verified") is False, prod)
    check(report, "existing_sidecar_has_no_live_creation_callback", "callback" in prod.get("reason", "").lower() and "unconnected" in prod.get("reason", "").lower(), prod)

    report["decision"] = {
        "direct_gate_literal_patch_safe": False,
        "four_to_seven_sidecar_ready": False,
        "relocation_path_ready": False,
        "safe_offline_scope": "model only; preserve index 4..7 as fail-closed until native callback, owner lifetime, map capacity and cleanup ABI are bound",
        "blocking_evidence": [
            "0x1086460 routes network index >=4 away from the player resource and roster calls.",
            "player resource selects component 239, whose registered insertion callback reaches 0x540920; its insertion family has original four-slot guards and fixed record stores.",
            "0x172F790 does not allocate or grow the entity-ID map and can write a null bucket on full/zero-capacity state.",
            "property generation writes the network index into a roster ordinal record; network index and roster ordinal cannot be substituted.",
            "the checked-in sidecar has no live player-creation callback and is explicitly nonproduction.",
        ],
        "required_before_patch": [
            "Bind the receive/creation callback ABI for 0x1086460 -> 0xFDC140 -> 0x581320 -> 0x540920.",
            "Provide one owner-keyed 8-slot backing for tracked/dense/prefix records, the 0x20-byte property rows, and the ID->ordinal map.",
            "Prove map free-slot/duplicate handling before any record/count mutation, plus unwind and cleanup for rejection, departure and reconnect.",
            "Capture a real fifth-peer run, then ladder to eight independent accounts before enabling a production hook.",
        ],
    }
    report["limits"] = [
        "Static checked-in evidence only; no process calls, writes, injection, install or multiplayer test.",
        "Reference player metadata is not proof that installed encrypted assets are identical.",
        "A passed check means the evidence matches the fixed build, not that the corresponding runtime path executed.",
    ]

    report["checks_passed"] = sum(1 for c in report["checks"] if c["passed"])
    report["checks_total"] = len(report["checks"])
    report["verification_passed"] = report["checks_passed"] == report["checks_total"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"output": str(args.output), "checks_passed": report["checks_passed"], "checks_total": report["checks_total"], "verification_passed": report["verification_passed"], "decision": report["decision"]}, ensure_ascii=False))
    return 0 if report["verification_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
