"""Verify that the saved fixed-build ABI evidence is internally consistent.

This receipt is deliberately an offline gate.  It hashes and cross-checks the
existing reports; it never opens a process, follows pointers, calls native
code, writes memory, installs a payload, or marks the mod as playable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

BUILD = 25480438
HERE = Path(__file__).resolve().parent

REPORTS = {
    "player_resource_callback_abi": HERE / "player_resource_callback_abi_binding_20261003.json",
    "player_creation_abi": HERE / "player_creation_abi_gap_audit_20261003.json",
    "player_resource_rollback": HERE / "resource_rollback_quiescence_contract_20261003.json",
    "peer_lifecycle": HERE / "peer_lifecycle_sidecar_contract_20261003.json",
    "loadout_lifecycle": HERE / "loadout_lifecycle_abi_audit_20261003.json",
    "native_admission_plan": HERE / "native_peer_admission_plan_20261002.json",
    "native_admission_capture": HERE / "native_admission_confirmed_peer_live_20261002_r3.json",
    "confirmed_peer_external_chain": HERE.parent / "eight_player_candidate_20260927" / "Native" / "SessionMembers" / "confirmed_peer_external_chain_20261002.json",
    "confirmed_peer_live_abi": HERE.parent / "eight_player_candidate_20260927" / "Native" / "SessionMembers" / "confirmed_peer_admission_live_abi_20261002.json",
    "public_runtime_entry_audit": HERE / "public_runtime_entry_audit_20261003.json",
    "join_handler_fixed_four_inventory": HERE / "join_handler_fixed_four_inventory_20261003.json",
    "external_party_playfab_capacity": HERE / "external_party_playfab_capacity_audit_20261003.json",
}

PRODUCTION_FALSE = ("production_patch_ready", "runtime_verified", "installable", "multiplayer_verified")


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _build(report: dict[str, Any]) -> Any:
    build = report.get("build", report.get("steam_build"))
    value = build.get("steam_build") if isinstance(build, dict) else build
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return value


def _all_named_checks_true(report: dict[str, Any], names: list[str]) -> bool:
    checks = report.get("checks")
    return isinstance(checks, dict) and all(checks.get(name) is True for name in names)


def verify() -> dict[str, Any]:
    reports = {name: _read(path) for name, path in REPORTS.items()}

    checks: dict[str, bool] = {
        "all_sources_present": all(path.is_file() for path in REPORTS.values()),
        "all_sources_fixed_build": all(_build(report) == BUILD for report in reports.values()),
        "player_resource_abi_static_checks": _all_named_checks_true(
            reports["player_resource_callback_abi"],
            [
                "fixed_build_matches", "callback_tables_match", "callback_stage_order_complete",
                "model_tables_match", "roster_in_first_table", "registration_capture_matches",
                "roster_component_matches", "roster_leaf_guard_and_writes_present",
                "resource_dispatch_abi_present", "resource_record_rollback_requirement_present",
                "reverse_cleanup_anchors_complete", "reverse_cleanup_edges_complete",
            ],
        ),
        "player_creation_static_checks": _all_named_checks_true(
            reports["player_creation_abi"],
            [
                "gate_rejects_index_4_to_7", "resource_record_has_dynamic_search_counter",
                "resource_record_has_handle_hash_metadata_and_flag", "three_callback_tables_have_explicit_owner_base",
                "first_stage_roster_has_fixed_four_guard", "roster_inline_record_write_is_not_sidecar",
                "component238_cleanup_is_owner_scoped", "player_resource_reverse_cleanup_proven",
            ],
        ),
        "rollback_static_checks": _all_named_checks_true(
            reports["player_resource_rollback"],
            [
                "abi_callback_tables_match", "callback_failure_matrix_complete",
                "third_callback_failure_unwinds_reverse_order", "partial_callback_failure_unwinds_reverse_order",
                "partial_callback_failure_clears_all_side_effects", "rollback_reentry_is_idempotent",
                "stale_generation_reentry_rejected", "owner_migration_requires_quiescence",
                "owner_epoch_changes_on_migration", "post_migration_index_works_in_offline_model",
                "thread_quiescence_gate_proven",
            ],
        ),
        "peer_lifecycle_static_checks": _all_named_checks_true(
            reports["peer_lifecycle"],
            [
                "partial_confirm_rollback", "callback_lease_quiescence", "migration_commit",
                "departure_idempotence", "pending_cancel_idempotence", "reconnect_generation_fence",
                "resource_cleanup_no_leak", "stable_network_index", "token_identity_type_guard",
            ],
        ),
        "loadout_lifecycle_static_checks": reports["loadout_lifecycle"].get("verification_passed") is True
        and reports["loadout_lifecycle"].get("checks_total") == reports["loadout_lifecycle"].get("checks_passed")
        and reports["loadout_lifecycle"].get("checks_total", 0) > 0,
        "native_plan_has_eight_slots_and_ten_sites": (
            reports["native_admission_plan"].get("executable") is False
            and reports["native_admission_plan"].get("multiplayer_verified") is False
            and len(reports["native_admission_plan"].get("sites", [])) == 10
            and reports["native_admission_plan"].get("sidecar", {}).get("host_peer_slots") == 8
            and reports["native_admission_plan"].get("sidecar", {}).get("client_confirmed_slots") == 8
        ),
        "live_capture_is_read_only": (
            reports["native_admission_capture"].get("read_only") is True
            and reports["native_admission_capture"].get("calls_made") is False
            and reports["native_admission_capture"].get("writes_made") is False
            and reports["native_admission_capture"].get("multiplayer_verified") is False
        ),
        "external_chain_remains_blocked": (
            reports["confirmed_peer_external_chain"].get("status") == "static_external_abi_blocker"
            and len(reports["confirmed_peer_external_chain"].get("sites", [])) == 5
            and reports["confirmed_peer_external_chain"].get("sidecar_contract", {}).get("installable") is False
        ),
        "confirmed_peer_abi_remains_blocked": (
            reports["confirmed_peer_live_abi"].get("status") == "static_live_abi_blocker"
            and len(reports["confirmed_peer_live_abi"].get("semantic_sites", [])) >= 8
            and reports["confirmed_peer_live_abi"].get("sidecar_plan", {}).get("installable") is False
        ),
        "public_runtime_bridge_remains_unavailable": (
            reports["public_runtime_entry_audit"].get("build", {}).get("steam_build") == BUILD
            and reports["public_runtime_entry_audit"].get("build", {}).get("game_dll_sha256")
            == "2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e"
            and reports["public_runtime_entry_audit"].get("conclusion", {}).get("public_peer_admission_abi_found") is False
            and reports["public_runtime_entry_audit"].get("conclusion", {}).get("public_player_creation_writer_found") is False
            and reports["public_runtime_entry_audit"].get("conclusion", {}).get("public_network_spawn_writer_found") is False
            and reports["public_runtime_entry_audit"].get("conclusion", {}).get("eight_player_status") == "unverified"
        ),
        "join_handler_four_literals_classified": (
            reports["join_handler_fixed_four_inventory"].get("build") == BUILD
            and reports["join_handler_fixed_four_inventory"].get("module") == "game.dll"
            and reports["join_handler_fixed_four_inventory"].get("verification_passed") is True
            and reports["join_handler_fixed_four_inventory"].get("checks_total") == 7
            and len(reports["join_handler_fixed_four_inventory"].get("fixed_four_sites", [])) == 5
            and len(reports["join_handler_fixed_four_inventory"].get("protected_four_literals", [])) == 3
            and reports["join_handler_fixed_four_inventory"].get("decision", {}).get("production_patch_ready") is False
        ),
        "external_party_playfab_boundary_is_not_game_bridge": (
            reports["external_party_playfab_capacity"].get("read_only") is True
            and reports["external_party_playfab_capacity"].get("dlls_loaded") is False
            and reports["external_party_playfab_capacity"].get("process_accessed") is False
            and reports["external_party_playfab_capacity"].get("writes_made") is False
            and reports["external_party_playfab_capacity"].get("hooks_installed") is False
            and reports["external_party_playfab_capacity"].get("party_api_exposes_network_configuration") is True
            and reports["external_party_playfab_capacity"].get("playfab_lobby_exposes_max_member_count") is True
            and reports["external_party_playfab_capacity"].get("target_event_hash_hits") == []
            and reports["external_party_playfab_capacity"].get("game_native_peer_admission_resolved") is False
            and reports["external_party_playfab_capacity"].get("game_native_player_creation_resolved") is False
            and reports["external_party_playfab_capacity"].get("installable") is False
            and reports["external_party_playfab_capacity"].get("multiplayer_verified") is False
        ),
    }

    production_flags: dict[str, dict[str, Any]] = {}
    for name, report in reports.items():
        flags: dict[str, Any] = {}
        source_checks = report.get("checks") if isinstance(report.get("checks"), dict) else {}
        for field in PRODUCTION_FALSE:
            if field in source_checks:
                flags[field] = source_checks[field]
            elif field in report:
                flags[field] = report[field]
        production_flags[name] = flags
        for field, value in flags.items():
            checks[f"{name}_{field}_false"] = value is False

    return {
        "schema": "hd2_static_abi_closure_receipt_v1",
        "build": BUILD,
        "scope": "offline fixed-build evidence closure; no process access or executable patch",
        "checks": checks,
        "source_reports": {
            name: {
                "path": str(path),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "schema": reports[name].get("schema"),
                "build": _build(reports[name]),
            }
            for name, path in REPORTS.items()
        },
        "production_flags": production_flags,
        "limits": [
            "This receipt proves only static evidence consistency and fail-closed state.",
            "It does not provide a native resolver, executable payload, installation, fifth-to-eighth peer admission, or task synchronization.",
            "The game is not modified and no process memory is queried or written by this verifier.",
        ],
        "installable": False,
        "runtime_verified": False,
        "multiplayer_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    report = verify()
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    passed = sum(value is True for value in report["checks"].values())
    total = len(report["checks"])
    print(json.dumps({"schema": report["schema"], "passed": passed, "total": total, "installable": False}, ensure_ascii=False))
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
